"""서비스 로그 전처리: 실제 API가 남긴 이벤트 형식으로 검증한다."""
import csv
import json
import math
from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.health import app
from gold_service import db, feedback


@pytest.fixture
def service(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'svc.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    for key in ("AWS_REGION", "COLLECTION_S3_BUCKET", "COLLECTION_LOG_GROUP", "COLLECTION_LOG_STREAM"):
        monkeypatch.delenv(key, raising=False)
    engine = db.make_engine(url)
    db.init_db(engine)
    with Session(engine) as session:
        session.add(db.Price(date=date(2026, 9, 24), close=4000, source="test"))
        session.add(db.ForecastRow(date=date(2026, 9, 24), sigma=0.01, grade="LOW", percentile=20, is_fallback=False,
                                   band_low=3800, band_high=4200, z=1.645, z_is_default=True))
        session.commit()
    client = TestClient(app)

    def submit(amount, actual=None):
        receipt = client.post("/api/submissions", json={"forecast_date": "2026-09-24", "weekly_amount": amount,
                                                        "product": "금 현물"}).json()["id"]
        if actual is not None:
            kind = "boolean" if isinstance(actual, bool) else "price"
            res = client.put(f"/api/submissions/{receipt}/actual",
                             json={"kind": kind, "value": actual, "observed_on": "2026-10-01"})
            assert res.status_code == 200, res.text
        return receipt

    yield submit, url, engine
    engine.dispose()


def logged_events(engine):
    """collection 이 CloudWatch/S3 로 보내는 것과 같은 payload."""
    with Session(engine) as session:
        return [e.payload for e in session.scalars(select(db.CollectionEvent))]


def test_merges_input_and_actual_per_receipt(service):
    submit, _, engine = service
    hit = submit(300_000, actual=4100.0)
    miss = submit(100_000, actual=4300.0)
    pending = submit(50_000)
    told = submit(70_000, actual=False)

    events = logged_events(engine)
    assert len(events) == 7  # 입력 4 + 정답 3
    rows = {r["submission_id"]: r for r in feedback.prepare(events).rows}

    assert rows[hit]["status"] == "price" and rows[hit]["within_band"] is True
    assert rows[hit]["n_events"] == 2 and rows[hit]["weekly_amount"] == 300_000
    assert rows[hit]["ret5"] == pytest.approx(math.log(4100 / 4000))
    assert rows[hit]["std_error"] == pytest.approx(abs(math.log(4100 / 4000)) / (0.01 * math.sqrt(5)), rel=1e-5)
    assert rows[hit]["band_half_width"] == pytest.approx(0.05)
    assert rows[hit]["n_splits"] == 1  # 낮음 → 1회
    assert rows[miss]["within_band"] is False
    assert rows[pending]["status"] == "no_actual" and rows[pending]["within_band"] is None
    assert rows[told]["status"] == "bool" and rows[told]["std_error"] is None


def test_db_source_matches_log_source(service):
    submit, url, engine = service
    submit(300_000, actual=4100.0)
    submit(50_000)
    from_logs = feedback.prepare(logged_events(engine)).rows
    from_db = feedback.prepare(feedback.load_db(url)).rows
    keys = ("submission_id", "status", "within_band", "std_error", "weekly_amount")
    assert [{k: r[k] for k in keys} for r in from_logs] == [{k: r[k] for k in keys} for r in from_db]


def test_rejects_bad_events_and_drops_duplicates(service):
    submit, _, engine = service
    submit(300_000, actual=4100.0)
    good = logged_events(engine)
    broken = dict(good[0], forecast={"price": -1, "sigma_daily": 0.01, "band": {}})
    events = good + [good[0], {"hello": 1}, "not json object", dict(good[0], event_type="clicked"), broken]
    prepared = feedback.prepare(events)
    assert len(prepared.rows) == 1
    assert prepared.duplicates == 1
    reasons = [r["reason"] for r in prepared.rejected]
    assert len(reasons) == 4
    assert any("필수 키" in r for r in reasons) and any("event_type" in r for r in reasons)
    assert any("forecast.price" in r for r in reasons)


def test_reads_cloudwatch_export_and_jsonl(service, tmp_path):
    submit, _, engine = service
    submit(300_000, actual=4100.0)
    events = logged_events(engine)
    # aws logs filter-log-events 출력 형식
    cw = tmp_path / "cw.json"
    cw.write_text(json.dumps({"events": [{"timestamp": 1, "message": json.dumps(e, ensure_ascii=False)} for e in events]}),
                  encoding="utf-8")
    jsonl = tmp_path / "s3" / "collection"
    jsonl.mkdir(parents=True)
    for i, e in enumerate(events):
        (jsonl / f"{i}.json").write_text(json.dumps(e, ensure_ascii=False), encoding="utf-8")
    assert len(feedback.load_file(cw)) == len(events)
    assert len(feedback.load_file(tmp_path / "s3")) == len(events)
    assert feedback.prepare(feedback.load_file(cw)).rows == feedback.prepare(events).rows


def test_rl_transitions_and_reward():
    assert feedback.reward(True, 0.05) == pytest.approx(0.9)
    assert feedback.reward(False, 0.05) == pytest.approx(-0.1)
    assert feedback.reward(None, 0.05) is None
    rows = [
        {"submission_id": "a", "as_of": "2026-09-24", "sigma_daily": 0.01, "percentile": 0.2, "grade": "낮음",
         "n_splits": 1, "within_band": True, "band_half_width": 0.05},
        {"submission_id": "b", "as_of": "2026-09-24", "sigma_daily": 0.01, "percentile": 0.2, "grade": "낮음",
         "n_splits": 1, "within_band": None, "band_half_width": 0.05},
    ]
    transitions = feedback.rl_transitions(rows)
    assert [t["submission_id"] for t in transitions] == ["a"]
    assert transitions[0]["action_n_splits"] == 1 and transitions[0]["done"] is True


def test_cli_writes_outputs(service, tmp_path):
    submit, _, engine = service
    submit(300_000, actual=4100.0)
    submit(100_000, actual=4300.0)
    submit(50_000)
    path = tmp_path / "events.jsonl"
    path.write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in logged_events(engine)), encoding="utf-8")
    out = tmp_path / "out"
    assert feedback.main(["--source", "file", "--path", str(path), "--out", str(out)]) == 0

    summary = json.loads((out / "summary.json").read_text(encoding="utf-8"))
    assert summary["submissions"] == 3
    assert summary["status_counts"] == {"price": 2, "bool": 0, "no_actual": 1}
    assert summary["hit_rate"] == 0.5 and summary["n_judged"] == 2
    with (out / "feedback.csv").open(encoding="utf-8-sig") as f:
        assert len(list(csv.DictReader(f))) == 3
    with (out / "rl_transitions.csv").open(encoding="utf-8-sig") as f:
        assert len(list(csv.DictReader(f))) == 2


def test_trade_recording_flows_into_executions(service, tmp_path):
    submit, url, engine = service
    from gold_service import policy

    # 학습된 규칙이 활성화돼 있으면 입력 시점 플랜에 그 규칙과 버전이 고정된다
    trained = {g: list(policy.ACTIONS[2]) for g in policy.GRADE_ORDER}
    with Session(engine) as session, session.begin():
        db.save_policy(session, "policy-test", "trained", policy.rule_to_json(trained), 0.001, {}, activate=True)

    client = TestClient(app)
    receipt = client.post("/api/submissions", json={"forecast_date": "2026-09-24", "weekly_amount": 100_001,
                                                    "product": "금 현물"}).json()
    plan = receipt["forecast"]["plan"]
    assert plan["policy_version"] == "policy-test" and plan["n_splits"] == 2
    assert [it["amount"] for it in plan["items"]] == [50_000, 50_001]

    rid = receipt["id"]
    bad = client.put(f"/api/submissions/{rid}/trades/1", json={"trade_date": "2026-09-24", "price": 4000})
    assert bad.status_code == 422  # 기준일 당일은 불가
    assert client.put(f"/api/submissions/{rid}/trades/3", json={"trade_date": "2026-09-28", "price": 4000}).status_code == 404
    assert client.put(f"/api/submissions/{rid}/trades/1", json={"trade_date": "2026-09-28", "price": -1}).status_code == 422

    first = client.put(f"/api/submissions/{rid}/trades/1", json={"trade_date": "2026-09-28", "price": 3900}).json()
    assert first["trade_summary"]["done"] == 1
    client.put(f"/api/submissions/{rid}/trades/1", json={"trade_date": "2026-09-28", "price": 4000})  # 수정
    done = client.put(f"/api/submissions/{rid}/trades/2", json={"trade_date": "2026-10-01", "price": 4100}).json()
    summary = done["trade_summary"]
    assert summary == {"n_splits": 2, "done": 2, "total_amount": 100_001,
                       "avg_cost": pytest.approx(100_001 / (50_000 / 4000 + 50_001 / 4100), abs=1e-3)}
    assert client.get(f"/api/submissions/{rid}").json()["trades"][0]["price"] == 4000

    events = logged_events(engine)
    assert [e["event_type"] for e in events].count("trade_saved") == 3
    for prepared in (feedback.prepare(events), feedback.prepare(feedback.load_db(url))):
        row = next(r for r in prepared.rows if r["submission_id"] == rid)
        assert row["policy_version"] == "policy-test" and row["n_splits"] == 2 and row["trades_done"] == 2
        assert row["exec_avg_cost"] == pytest.approx(summary["avg_cost"], abs=1e-3)
        assert row["exec_first_date"] == "2026-09-28"
        trades = [t for t in prepared.executions if t["submission_id"] == rid]
        assert [(t["seq"], t["price"], t["trade_weekday"]) for t in trades] == [(1, 4000, 0), (2, 4100, 3)]

    out = tmp_path / "fb"
    feedback.write_outputs(feedback.prepare(events), out, "test")
    with (out / "executions.csv").open(encoding="utf-8-sig") as f:
        assert len(list(csv.DictReader(f))) == 2
    assert json.loads((out / "summary.json").read_text(encoding="utf-8"))["submissions_all_trades_done"] == 1


def test_policy_log_samples_from_feedback_csv(tmp_path):
    import pandas as pd
    from gold_service import policy

    close = pd.Series([100, 102, 98, 101, 99], index=pd.bdate_range("2026-09-28", periods=5))
    path = tmp_path / "feedback.csv"
    feedback.write_csv(path, [
        {"submission_id": "a", "grade": "낮음", "n_splits": 2, "trades_done": 2, "exec_avg_cost": 100.5,
         "exec_first_date": "2026-09-28"},
        {"submission_id": "b", "grade": "낮음", "n_splits": 2, "trades_done": 1, "exec_avg_cost": 100,
         "exec_first_date": "2026-09-28"},
        {"submission_id": "c", "grade": "보통", "n_splits": 3, "trades_done": 3, "exec_avg_cost": 100,
         "exec_first_date": "2026-11-02"},
    ], feedback.FEEDBACK_COLUMNS)
    samples, stats = policy.log_samples(path, close)
    assert stats == {"rows": 3, "used": 1, "incomplete": 1, "no_week_prices": 1}
    assert samples.iloc[0]["grade"] == "LOW" and samples.iloc[0]["source"] == "log"
    assert samples.iloc[0]["timing_error"] == pytest.approx(abs(100.5 / 100 - 1))
