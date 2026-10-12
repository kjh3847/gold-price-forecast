"""walk-forward 평가.

    python -m gold_service.evaluate --start 2024-01-01 [--end YYYY-MM-DD]

평가 기간 시작 전 WARMUP_DAYS 거래일부터 일간 배치와 같은 규칙으로 예측해
적응형 z(최근 252개 오차)가 평가 첫날부터 채워지도록 한다.
결과는 evaluations 테이블에 저장되고 export_json이 읽어 간다.
"""
from __future__ import annotations

import argparse
import logging
import sys
from datetime import date

import numpy as np
import pandas as pd
from sqlalchemy.orm import Session

from gold_service import db
from gold_service.bands import COVERAGE, compute_bands, half_width
from gold_service.config import Settings
from gold_service.features import log_returns
from gold_service.models import walk_forward
from gold_service.monitoring import qlike
from gold_service.sources import build_source

log = logging.getLogger("gold_service")

WARMUP_DAYS = 300  # z 창(252) + 결과 확정 지연(5) 이상
BASELINE_WINDOW = 252
MODEL_NAME = "HAR+GARCH 평균"
BASELINE_NAME = "최근 1년 변동성"


def band_metrics(table: pd.DataFrame, close: pd.Series) -> dict:
    """table: compute_bands 결과 (평가 기간·결과 확정분만)."""
    hit = table["ret5"].abs() <= table["z"] * table["sd5"]
    width = half_width(table["band_low"], table["band_high"], close.reindex(table.index))
    nonoverlap = hit.iloc[::5]  # 첫 평가일부터 5거래일 간격
    return {
        "hit_rate": float(hit.mean()),
        "avg_width": float(width.mean()),
        "hit_rate_nonoverlap": float(nonoverlap.mean()),
        "n_nonoverlap": int(len(nonoverlap)),
        "z_default_days": int(table["z_is_default"].sum()),
    }


def evaluate(close: pd.Series, start: date | str, end: date | str | None = None) -> dict:
    """close: DatetimeIndex 종가. 결과가 확정된(t+5 종가가 있는) 날만 평가한다."""
    r = log_returns(close)
    start_ts = pd.Timestamp(start)
    start_pos = int(r.index.searchsorted(start_ts))
    if start_pos >= len(r):
        raise ValueError(f"평가 시작일 {start} 이후 데이터가 없습니다")
    warm_start = r.index[max(0, start_pos - WARMUP_DAYS)]

    wf = walk_forward(close, warm_start, end)
    model = compute_bands(close, wf["sigma"])
    base_sigma = r.rolling(BASELINE_WINDOW).std().reindex(wf.index)
    base = compute_bands(close, base_sigma)

    mask = (wf.index >= start_ts) & model["ret5"].notna() & base["ret5"].notna() & base_sigma.notna()
    if not mask.any():
        raise ValueError("평가할 수 있는 (결과가 확정된) 날이 없습니다")
    period = wf.index[mask]
    ev = wf[mask]

    metrics = {
        "model_name": MODEL_NAME,
        "period_start": period[0].date().isoformat(),
        "period_end": period[-1].date().isoformat(),
        "n_days": int(mask.sum()),
        "coverage_target": COVERAGE,
        **band_metrics(model[mask], close),
        "qlike_improvement": float(1 - qlike(ev["y_var"], ev["sigma"] ** 2) / qlike(ev["y_var"], ev["rv22"] ** 2)),
        "fallback_days": int(ev["is_fallback"].sum()),
        "baseline": {"name": BASELINE_NAME, **band_metrics(base[mask], close)},
    }
    return metrics


def format_report(m: dict) -> str:
    b = m["baseline"]
    rows = [
        ("90% 범위 적중률", f"{m['hit_rate']:.1%}", f"{b['hit_rate']:.1%}"),
        ("평균 범위 폭", f"±{m['avg_width']:.2%}", f"±{b['avg_width']:.2%}"),
        (f"겹치지 않는 표본 적중률 (n={m['n_nonoverlap']})", f"{m['hit_rate_nonoverlap']:.1%}", f"{b['hit_rate_nonoverlap']:.1%}"),
    ]
    lines = [
        f"평가 기간: {m['period_start']} ~ {m['period_end']} ({m['n_days']}거래일)",
        f"{'지표':<28}{MODEL_NAME:>14}{BASELINE_NAME:>14}",
        *[f"{a:<28}{x:>14}{y:>14}" for a, x, y in rows],
        f"QLIKE 개선율 (rv22 기준 대비): {m['qlike_improvement']:+.2%}",
        f"대체값 사용일: {m['fallback_days']}, z 기본값(1.645) 사용일: {m['z_default_days']}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    settings = Settings.from_env()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="walk-forward 평가")
    parser.add_argument("--start", required=True, type=date.fromisoformat)
    parser.add_argument("--end", type=date.fromisoformat, default=None)
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return 2 if exc.code else 0

    try:
        prices = build_source(settings).fetch(None, args.end or date.max)
        close = pd.Series(prices["close"].values, index=pd.DatetimeIndex(pd.to_datetime(prices["date"])), name="close")
        metrics = evaluate(close, args.start, args.end)
        engine = db.make_engine(settings.database_url)
        db.init_db(engine)
        with Session(engine) as session, session.begin():
            db.save_evaluation(session, date.fromisoformat(metrics["period_start"]),
                               date.fromisoformat(metrics["period_end"]), metrics)
    except Exception:
        log.exception("평가 실패")
        return 1
    print(format_report(metrics))
    return 0


if __name__ == "__main__":
    sys.exit(main())
