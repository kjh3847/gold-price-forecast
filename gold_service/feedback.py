"""서비스 로그 → 재학습·강화학습용 데이터셋 전처리.

    python -m gold_service.feedback --source cloudwatch --log-group /gold-forecast/collection
    python -m gold_service.feedback --source s3 --bucket <bucket>
    python -m gold_service.feedback --source file --path logs.json
    python -m gold_service.feedback --source db            # 서버의 SQLite submissions 테이블

입력 이벤트(gold_service.collection 이 보내는 JSON):
  input_saved   : 사용자 입력(주간 금액·상품) + 그 시점 예측 스냅샷(σ, 등급, 범위, 대상일)
  actual_saved  : 위 내용 + 실제 정답(가격 또는 T/F)과 범위 적중 여부
  trade_saved   : 위 내용 + 플랜 회차별 실제 매수(체결일·단가·금액)

출력 (기본 data/feedback/):
  feedback.csv        접수번호당 한 행. 실제 가격이 있으면 ret5, 표준화 오차 e = |ret5| / (σ√5)
  executions.csv      회차별 매수 기록 (분할 규칙 학습 입력: python -m gold_service.policy train --feedback)
  rl_transitions.csv  (상태, 행동, 보상) 형식. 보상은 대리 지표 — 아래 reward() 참고
  rejected.csv        버린 이벤트와 이유
  summary.json        건수, 적중률, 표준화 오차 분위수 등
"""
from __future__ import annotations

import argparse
import csv
import json
import logging
import math
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator

from gold_service.planner import SPLIT_RULES
from gold_service.grading import Grade

log = logging.getLogger("gold_service")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = PROJECT_ROOT / "data" / "feedback"
EVENT_TYPES = ("input_saved", "actual_saved", "trade_saved")
REQUIRED_KEYS = ("event_type", "event_at", "id", "user_input", "forecast")
WIDTH_PENALTY = 2.0  # 보상의 범위 폭 벌점 계수 (반폭 ±5% → 0.1 감점)
LABEL_TO_GRADE = {g.label: g for g in Grade}

FEEDBACK_COLUMNS = [
    "submission_id", "status", "created_at", "actual_at", "as_of", "target_date", "price", "sigma_daily",
    "grade", "percentile", "is_fallback", "z", "band_low", "band_high", "band_half_width",
    "weekly_amount", "product", "n_splits", "actual_kind", "actual_value", "within_band",
    "ret5", "sd5", "std_error", "policy_version", "trades_done", "exec_amount", "exec_avg_cost",
    "exec_first_date", "n_events",
]
EXECUTION_COLUMNS = [
    "submission_id", "policy_version", "grade", "n_splits", "seq", "planned_weekday", "trade_date",
    "trade_weekday", "price", "amount",
]
RL_COLUMNS = [
    "submission_id", "as_of", "state_sigma_daily", "state_percentile", "state_grade",
    "action_n_splits", "reward", "within_band", "band_half_width", "done",
]


# ---------------------------------------------------------------- 불러오기
def _iter_json_values(text: str) -> Iterator[object]:
    """JSON 배열, 객체 하나, JSON Lines 를 모두 받는다."""
    text = text.strip()
    if not text:
        return
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        for line in text.splitlines():
            if line.strip():
                yield json.loads(line)
        return
    yield from value if isinstance(value, list) else [value]


def unwrap(value: object) -> Iterator[object]:
    """CloudWatch 내보내기 형식({"events":[{"message": "..."}]}, {"message": "..."})을 풀어 이벤트만 낸다."""
    if isinstance(value, dict) and isinstance(value.get("events"), list):
        for item in value["events"]:
            yield from unwrap(item)
    elif isinstance(value, dict) and isinstance(value.get("message"), str) and "event_type" not in value:
        try:
            yield json.loads(value["message"])
        except json.JSONDecodeError:
            yield {"_raw": value["message"]}
    else:
        yield value


def load_file(path: Path) -> list[object]:
    """파일 하나 또는 폴더(S3에서 받은 *.json 등)를 읽는다."""
    files = sorted(p for p in path.rglob("*") if p.suffix in (".json", ".jsonl", ".log", ".txt")) if path.is_dir() else [path]
    events = []
    for f in files:
        for value in _iter_json_values(f.read_text(encoding="utf-8-sig")):
            events.extend(unwrap(value))
    return events


def fetch_cloudwatch(log_group: str, region: str, stream: str | None = None, start_ms: int | None = None) -> list[object]:
    import boto3

    client = boto3.client("logs", region_name=region)
    kwargs = {"logGroupName": log_group}
    if stream:
        kwargs["logStreamNames"] = [stream]
    if start_ms is not None:
        kwargs["startTime"] = start_ms
    events = []
    for page in client.get_paginator("filter_log_events").paginate(**kwargs):
        for item in page.get("events", []):
            events.extend(unwrap({"message": item["message"]}))
    return events


def fetch_s3(bucket: str, region: str, prefix: str = "collection/") -> list[object]:
    import boto3

    client = boto3.client("s3", region_name=region)
    events = []
    for page in client.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            body = client.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read().decode("utf-8")
            for value in _iter_json_values(body):
                events.extend(unwrap(value))
    return events


def load_db(database_url: str) -> list[object]:
    """서버 SQLite 의 submissions 테이블을 이벤트 형식으로 바꾼다 (로그 전송이 안 됐을 때 대안)."""
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from gold_service import db

    engine = db.make_engine(database_url)
    try:
        with Session(engine) as session:
            rows = session.scalars(select(db.Submission)).all()
            events = []
            for r in rows:
                trades = [{"seq": t.seq, "trade_date": t.trade_date.isoformat(), "price": t.price,
                           "amount": t.amount, "recorded_at": t.recorded_at} for t in r.executions]
                stamps = [r.created_at, r.actual_at or "", *(t["recorded_at"] for t in trades)]
                events.append({
                    "event_type": "trade_saved" if trades else ("actual_saved" if r.actual else "input_saved"),
                    "event_at": max(stamps),
                    "id": r.id, "created_at": r.created_at, "user_input": r.user_input,
                    "forecast": r.forecast, "actual": r.actual, "actual_at": r.actual_at, "trades": trades,
                })
            return events
    finally:
        engine.dispose()


# ---------------------------------------------------------------- 정리
@dataclass
class Prepared:
    rows: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)
    duplicates: int = 0
    executions: list[dict] = field(default_factory=list)


def _parse_time(value) -> datetime | None:
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def validate(event: object) -> str | None:
    """문제가 있으면 이유를, 정상이면 None."""
    if not isinstance(event, dict):
        return "JSON 객체가 아님"
    if "_raw" in event:
        return "메시지가 JSON이 아님"
    missing = [k for k in REQUIRED_KEYS if k not in event]
    if missing:
        return f"필수 키 없음: {missing}"
    if event["event_type"] not in EVENT_TYPES:
        return f"알 수 없는 event_type: {event['event_type']}"
    if _parse_time(event["event_at"]) is None:
        return "event_at 형식 오류"
    fc = event["forecast"]
    if not isinstance(fc, dict) or not isinstance(fc.get("band"), dict):
        return "forecast 스냅샷 형식 오류"
    for key in ("price", "sigma_daily"):
        v = fc.get(key)
        if not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
            return f"forecast.{key} 값 오류"
    if event["event_type"] == "actual_saved" and not isinstance(event.get("actual"), dict):
        return "actual_saved 인데 actual 없음"
    return None


def _trades(event: dict) -> list[dict]:
    trades = event.get("trades")
    return [t for t in trades if isinstance(t, dict)] if isinstance(trades, list) else []


def n_splits(grade_label: str | None) -> int | None:
    grade = LABEL_TO_GRADE.get(grade_label) or (Grade(grade_label) if grade_label in Grade.__members__ else None)
    return len(SPLIT_RULES[grade]) if grade else None


def reward(within_band: bool | None, band_half_width: float | None) -> float | None:
    """강화학습용 대리 보상 = 범위 적중(1/0) − WIDTH_PENALTY × 범위 반폭.

    로그에는 회차별 체결가가 없어 '분할매수가 실제로 유리했는지'를 알 수 없다.
    그래서 '좁으면서 맞는 범위'를 좋은 결과로 보는 대리 지표를 쓴다.
    """
    if within_band is None or band_half_width is None:
        return None
    return round((1.0 if within_band else 0.0) - WIDTH_PENALTY * band_half_width, 6)


def build_row(submission_id: str, events: list[dict]) -> dict:
    """같은 접수번호의 이벤트들을 하나로 합친다. 정답은 가장 최근 actual_saved 기준."""
    events = sorted(events, key=lambda e: _parse_time(e["event_at"]))
    latest = events[-1]
    actual_events = [e for e in events if e["event_type"] == "actual_saved"]
    actual = actual_events[-1]["actual"] if actual_events else None
    fc = latest["forecast"]
    band = fc["band"]
    price, sigma = float(fc["price"]), float(fc["sigma_daily"])
    horizon = int(band.get("horizon_days", 5))
    low, high = band.get("low"), band.get("high")
    half_width = (high - low) / (2 * price) if isinstance(low, (int, float)) and isinstance(high, (int, float)) else None
    user = latest.get("user_input") or {}

    row = {k: None for k in FEEDBACK_COLUMNS}
    row.update(
        submission_id=submission_id,
        created_at=events[0].get("created_at") or events[0]["event_at"],
        actual_at=actual_events[-1].get("actual_at") if actual_events else None,
        as_of=fc.get("as_of"), target_date=fc.get("target_date"), price=price, sigma_daily=sigma,
        grade=fc.get("grade"), percentile=fc.get("percentile"), is_fallback=fc.get("is_fallback"),
        z=band.get("z"), band_low=low, band_high=high,
        band_half_width=None if half_width is None else round(half_width, 6),
        weekly_amount=user.get("weekly_amount"), product=user.get("product"),
        n_splits=(fc.get("plan") or {}).get("n_splits") or n_splits(fc.get("grade")), n_events=len(events),
        policy_version=(fc.get("plan") or {}).get("policy_version"),
    )
    trades = [t for t in _trades(latest) if isinstance(t.get("price"), (int, float)) and t["price"] > 0
              and isinstance(t.get("amount"), (int, float)) and t["amount"] > 0]
    row["trades_done"] = len(trades)
    if trades:
        total = sum(t["amount"] for t in trades)
        row.update(exec_amount=total, exec_avg_cost=round(total / sum(t["amount"] / t["price"] for t in trades), 6),
                   exec_first_date=min(t["trade_date"] for t in trades))
    if actual is None:
        row["status"] = "no_actual"
        return row

    row.update(actual_kind=actual.get("kind"), actual_value=actual.get("value"), within_band=actual.get("within_band"))
    if actual.get("kind") == "price" and isinstance(actual.get("value"), (int, float)) and actual["value"] > 0:
        ret5 = math.log(actual["value"] / price)
        sd5 = sigma * math.sqrt(horizon)
        row.update(ret5=round(ret5, 8), sd5=round(sd5, 8), std_error=round(abs(ret5) / sd5, 6), status="price")
    else:
        row["status"] = "bool"
    return row


def prepare(events: Iterable[object]) -> Prepared:
    out = Prepared()
    seen: set[str] = set()
    grouped: dict[str, list[dict]] = {}
    for event in events:
        reason = validate(event)
        if reason:
            out.rejected.append({"reason": reason, "event": json.dumps(event, ensure_ascii=False, default=str)[:500]})
            continue
        key = json.dumps(event, sort_keys=True, ensure_ascii=False, default=str)
        if key in seen:  # 재전송 등으로 똑같은 이벤트가 두 번 들어온 경우
            out.duplicates += 1
            continue
        seen.add(key)
        grouped.setdefault(str(event["id"]), []).append(event)
    out.rows = [build_row(sid, evs) for sid, evs in sorted(grouped.items())]
    out.executions = executions([e for evs in grouped.values() for e in evs], out.rows)
    return out


def executions(events: list[dict], rows: list[dict]) -> list[dict]:
    """접수번호별 최신 이벤트의 매수 기록을 회차 단위 행으로 편다."""
    latest: dict[str, dict] = {}
    for e in events:
        if validate(e) is None:
            cur = latest.get(str(e["id"]))
            if cur is None or _parse_time(e["event_at"]) >= _parse_time(cur["event_at"]):
                latest[str(e["id"])] = e
    by_id = {r["submission_id"]: r for r in rows}
    result = []
    for sid, e in sorted(latest.items()):
        plan = {it.get("seq"): it for it in (e["forecast"].get("plan") or {}).get("items", [])}
        for t in sorted(_trades(e), key=lambda t: t.get("seq", 0)):
            trade_date = t.get("trade_date")
            try:
                weekday = datetime.fromisoformat(str(trade_date)).weekday()
            except ValueError:
                weekday = None
            result.append({
                "submission_id": sid, "policy_version": by_id.get(sid, {}).get("policy_version"),
                "grade": by_id.get(sid, {}).get("grade"), "n_splits": by_id.get(sid, {}).get("n_splits"),
                "seq": t.get("seq"), "planned_weekday": (plan.get(t.get("seq")) or {}).get("weekday"),
                "trade_date": trade_date, "trade_weekday": weekday, "price": t.get("price"), "amount": t.get("amount"),
            })
    return result


def rl_transitions(rows: list[dict]) -> list[dict]:
    """정답이 있는 행만 (상태, 행동, 보상) 한 스텝짜리 전이로 만든다."""
    result = []
    for r in rows:
        if r["within_band"] is None:
            continue
        result.append({
            "submission_id": r["submission_id"], "as_of": r["as_of"],
            "state_sigma_daily": r["sigma_daily"], "state_percentile": r["percentile"], "state_grade": r["grade"],
            "action_n_splits": r["n_splits"], "reward": reward(bool(r["within_band"]), r["band_half_width"]),
            "within_band": bool(r["within_band"]), "band_half_width": r["band_half_width"], "done": True,
        })
    return result


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    pos = (len(s) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def summarize(prepared: Prepared, source: str) -> dict:
    rows = prepared.rows
    counts = {s: sum(r["status"] == s for r in rows) for s in ("price", "bool", "no_actual")}
    judged = [r for r in rows if r["within_band"] is not None]
    errors = [r["std_error"] for r in rows if r["std_error"] is not None]
    zs = [r["z"] for r in rows if r["std_error"] is not None and isinstance(r["z"], (int, float))]
    reasons: dict[str, int] = {}
    for item in prepared.rejected:
        reasons[item["reason"]] = reasons.get(item["reason"], 0) + 1
    return {
        "source": source,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "submissions": len(rows),
        "status_counts": counts,
        "rejected": len(prepared.rejected),
        "rejected_reasons": reasons,
        "duplicates_dropped": prepared.duplicates,
        "executions": len(prepared.executions),
        "submissions_all_trades_done": sum(
            1 for r in rows if r["n_splits"] and r["trades_done"] and r["trades_done"] >= r["n_splits"]),
        "hit_rate": None if not judged else round(sum(bool(r["within_band"]) for r in judged) / len(judged), 4),
        "n_judged": len(judged),
        "std_error_mean": None if not errors else round(sum(errors) / len(errors), 4),
        "std_error_q90": None if not errors else round(_quantile(errors, 0.9), 4),
        "z_used_mean": None if not zs else round(sum(zs) / len(zs), 4),
        "note": "표준화 오차 90% 분위수(std_error_q90)가 사용한 z보다 크면 범위가 좁았다는 뜻. 표본이 적으면 참고만 할 것.",
    }


def write_csv(path: Path, rows: list[dict], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_outputs(prepared: Prepared, out_dir: Path, source: str) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(out_dir / "feedback.csv", prepared.rows, FEEDBACK_COLUMNS)
    write_csv(out_dir / "executions.csv", prepared.executions, EXECUTION_COLUMNS)
    write_csv(out_dir / "rl_transitions.csv", rl_transitions(prepared.rows), RL_COLUMNS)
    write_csv(out_dir / "rejected.csv", prepared.rejected, ["reason", "event"])
    summary = summarize(prepared, source)
    (out_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return summary


# ---------------------------------------------------------------- CLI
def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level="INFO", format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="서비스 로그 → 재학습·강화학습용 데이터셋")
    parser.add_argument("--source", required=True, choices=["cloudwatch", "s3", "file", "db"])
    parser.add_argument("--log-group", help="cloudwatch: 로그 그룹 이름")
    parser.add_argument("--log-stream", help="cloudwatch: 특정 스트림만")
    parser.add_argument("--since", help="cloudwatch: 이 시각(ISO) 이후 로그만")
    parser.add_argument("--bucket", help="s3: 버킷 이름 (collection/ 아래 이벤트)")
    parser.add_argument("--path", type=Path, help="file: JSON/JSONL 파일 또는 폴더")
    parser.add_argument("--database-url", help="db: 기본값은 DATABASE_URL 설정")
    parser.add_argument("--region", default=None, help="기본값 AWS_REGION 또는 ap-northeast-2")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args(argv)

    import os

    region = args.region or os.getenv("AWS_REGION") or "ap-northeast-2"
    try:
        if args.source == "cloudwatch":
            if not args.log_group:
                parser.error("--log-group 이 필요합니다")
            start = _parse_time(args.since) if args.since else None
            if args.since and start is None:
                parser.error("--since 형식 오류 (예: 2026-11-09T00:00:00+09:00)")
            events = fetch_cloudwatch(args.log_group, region, args.log_stream,
                                      int(start.timestamp() * 1000) if start else None)
            source = f"cloudwatch:{args.log_group}"
        elif args.source == "s3":
            if not args.bucket:
                parser.error("--bucket 이 필요합니다")
            events, source = fetch_s3(args.bucket, region), f"s3:{args.bucket}"
        elif args.source == "file":
            if not args.path or not args.path.exists():
                parser.error("--path 에 있는 파일·폴더가 필요합니다")
            events, source = load_file(args.path), f"file:{args.path}"
        else:
            from gold_service.config import Settings

            url = args.database_url or Settings.from_env().database_url
            events, source = load_db(url), "db"
        prepared = prepare(events)
        summary = write_outputs(prepared, args.out, source)
    except Exception:
        log.exception("전처리 실패")
        return 1

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"저장: {args.out}/ (feedback.csv, executions.csv, rl_transitions.csv, rejected.csv, summary.json)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
