# 🪙 금 분할매수 도우미

금을 **매주 정해진 금액으로 사 모으는 사람**에게 이번 주에 **몇 번에 나눠, 어느 요일에** 살지 알려주는 서비스입니다.

- 금값이 오를지 내릴지는 **예측하지 않습니다**.
- "다음 5거래일 동안 금값이 얼마나 출렁일지(변동성)"만 예측하고, 이를 정해진 규칙으로 분할 횟수와 매수 요일로 바꿉니다.
- 이 저장소는 **일간 배치 파이프라인**(수집 → 학습/예측 → 등급 → 플랜 생성 → 저장 → 모니터링)입니다. 웹 화면과 알림 발송은 아직 범위 밖이며, 붙일 수 있도록 인터페이스만 분리해 두었습니다.

> 이 서비스는 예상 변동성에 따라 매수 시점을 나누는 일정 안내입니다. 금값 방향 예측이나 투자 권유가 아니며 수익을 보장하지 않습니다.

---

## 동작 개요

```
PriceSource ──► prices ──► 로그수익률 r_t ──► HAR + GARCH(1,1) ──► σ_t ──► 백분위·등급 ──► 주간 플랜
  (CSV)         (DB)                         (63거래일마다 재학습)   (forecasts)          (buy_plans, plan_items)
                                                                     │
                                                                     └──► 주간 모니터링 (monitoring)
```

### 1. 변동성 예측 σ_t (검증 완료된 모델, 임의 변경 금지)

날짜 t 종가까지 보고 "다음 5거래일의 하루 변동성"을 예측합니다.
학습 타깃은 `y_t = sqrt(mean(r_{t+1}² … r_{t+5}²))` 입니다.

| 모델 | 내용 |
|---|---|
| HAR | 피처 `log(rv1+1e-4), log(rv5+1e-4), log(rv22+1e-4)` → 타깃 `0.5·log(분산+1e-8)`, `LinearRegression`. 분산 예측 = `exp(2·예측값 + 2·잔차분산)` (로그정규 편향 보정) |
| GARCH(1,1) | `arch_model(r*100, mean='Constant', vol='GARCH', p=1, q=1, dist='t')`, 5일 분산 예측 평균 / 100² |
| 최종 | `σ_t = sqrt((HAR 분산 + GARCH 분산) / 2)` |

- **재학습**: 63거래일마다. 재학습 시점 s의 HAR 학습 행은 타깃이 확정된 `i ≤ s−5`까지만 씁니다. GARCH는 `last_obs=s`로 추정하고, 이후 날짜는 고정 파라미터에 그날까지의 수익률을 반영해 예측합니다.
- 학습된 파라미터와 학습 기준일은 `model_params`에 저장되고, 재학습일이 아니면 저장된 파라미터로 예측만 합니다.
- **장애 대체값**: 학습·예측이 실패하면 `σ = rv22`(최근 22일 실현 변동성)를 쓰고 `forecasts.is_fallback = true`로 남깁니다.

### 2. 변동성 등급

σ_t를 그날까지의 최근 252개 예측값 안에서 백분위로 바꿉니다(최소 60개, 미래 값 미사용).

| 등급 | 백분위 | 분할 | 요일 |
|---|---|---|---|
| 낮음 | ≤ 33% | 1회 | 월 |
| 보통 | 33~67% | 2회 | 월, 목 |
| 높음 | 67~90% | 3회 | 월, 수, 금 |
| 매우 높음 | > 90% | 5회 | 월~금 |

### 3. 주간 플랜 (MVP: 시장가만)

- 매주 첫 거래일에 **직전 거래일 종가 기준** σ와 등급으로 만듭니다.
- 회차 금액 = 주간 금액 ÷ 분할 횟수 (원 단위, 나머지는 마지막 회차에 더함).
- 계획한 요일이 휴장이면 그 주의 다음 거래일로 미루고, 없으면 그 주 마지막 거래일로 잡습니다.
- 플랜에는 등급, σ(하루 ±%), 5일 예상 범위(σ×√5), 회차별 날짜·금액이 들어갑니다.

### 4. 모니터링 (매주 첫 거래일)

지난 13주 동안 실제값이 확정된 예측으로 계산합니다.

- **예측 범위 적중률**: 실제 5일 실현 변동성이 예측의 ±30% 안에 든 비율
- **단순 기준 대비 개선율**: `1 − QLIKE(모델) / QLIKE(rv22)`, `QLIKE = mean(y/h − log(y/h) − 1)`
- 개선율이 **4주 연속 0% 미만**이면 `monitoring.alert = true`로 기록하고 경보 로그를 남깁니다.

---

## 설치

Python 3.10 이상이 필요합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"            # SQLite로 로컬 개발
pip install -e ".[dev,postgres]"   # PostgreSQL을 쓸 때
```

## 로컬 실행

```bash
# 1) (선택) 플랜을 받을 사용자 추가 — 사용자 기능 본 구현 전 임시 명령
python -m gold_service.manage add-user --name 홍길동 --weekly-amount 300000

# 2) 그날의 배치 실행: 수집 → 예측(필요 시 재학습) → 등급 → 저장
#    주 첫 거래일이면 플랜 생성과 모니터링까지 실행
python -m gold_service.run_daily --date 2026-09-21

# 3) 생성된 플랜 확인
python -m gold_service.manage show-plans
```

실행 결과 예시:

```
INFO gold_service: 백필: 400개 거래일 예측 (2025-02-21 ~ 2026-09-21)
INFO gold_service: 2026-09-21 예측: σ=0.0134 (하루 ±1.34%), 등급=NORMAL, 대체값=False
INFO gold_service.notify: 플랜 생성 (user=1 홍길동, week=2026-09-21)
이번 주 변동성 등급: 보통
예상 변동폭: 하루 ±1.36%, 5거래일 ±3.04%
분할 계획 (2회):
  1회차 2026-09-21(월) 150,000원
  2회차 2026-09-24(목) 150,000원
INFO gold_service: 모니터링(최근 13주, n=60): 적중률 66.7%, 개선율 +4.83%
```

- 처음 실행하면 DB가 비어 있으므로 최근 `BACKFILL_DAYS`(기본 400) 거래일을 같은 규칙으로 예측해 채웁니다. 등급 계산에 필요한 백분위 이력(최소 60개)을 확보하기 위해서입니다. 이후에는 빠진 날만 채우고 그날을 예측합니다.
- **멱등성**: 같은 날짜로 다시 실행해도 모든 테이블이 자연키(날짜, (사용자, 주) 등)로 upsert되어 행이 중복되지 않고 결과도 같습니다.

### 종료 코드

| 코드 | 의미 |
|---|---|
| 0 | 성공, 또는 휴장일이라 건너뜀 |
| 1 | 실패 (로그에 스택 트레이스) |
| 2 | 인자 오류 |
| 3 | 거래일인데 그날 가격 데이터가 없음 |

### 테스트

```bash
pytest -q
```

| 테스트 | 확인 내용 |
|---|---|
| `test_leakage.py` | t+1 이후 데이터를 바꿔도 t의 예측·피처·등급이 그대로인지 |
| `test_retrain.py` | HAR 학습 행이 `i ≤ s−5`로 제한되는지, GARCH가 s 이후를 안 쓰는지, 63거래일마다 재학습하는지 |
| `test_planner.py` | 등급별 분할 횟수·요일, 휴장일 이월, 금액 합계 = 주간 금액, 등급 경계값 |
| `test_fallback.py` | 학습·예측 실패, 이력 부족, 비정상 값일 때 rv22 대체와 플래그 |
| `test_regression.py` | `gold_only_ready.csv` 2024-01-01 이후 walk-forward에서 앙상블 QLIKE < rv22 기준 |
| `test_monitoring.py` | QLIKE, 13주 창, 4주 연속 경보 |
| `test_run_daily.py` | SQLite 통합 실행: 재실행 멱등성, 플랜 생성, 대체값 저장, 종료 코드 |

현재 데이터 기준 회귀 테스트 결과(rv22 대비 QLIKE 개선율): HAR +4.65%, GARCH +8.43%, **평균 +7.44%**.

---

## 환경변수

모두 선택값입니다. `.env.example`을 참고해 셸에서 `export` 하세요(자동으로 `.env`를 읽지는 않습니다).

| 변수 | 기본값 | 설명 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///<프로젝트>/gold_service.db` | SQLAlchemy URL. 예: `postgresql+psycopg2://user:pw@host:5432/gold` |
| `PRICE_SOURCE` | `csv` | 가격 소스 종류 |
| `PRICE_CSV_PATH` | `data/gold_only_ready.csv` | CSV 경로 |
| `PRICE_CSV_DATE_COL` | `date` | 날짜 컬럼 |
| `PRICE_CSV_CLOSE_COL` | `gold` | 종가 컬럼 |
| `HOLIDAYS_FILE` | (없음) | 휴장일 CSV. 첫 컬럼에 `YYYY-MM-DD`. 없으면 주말만 휴장으로 봅니다 |
| `BACKFILL_DAYS` | `400` | 예측이 비어 있을 때 거슬러 채울 거래일 수 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |

휴장일 파일 예:

```csv
date
2026-10-05
2026-10-09
```

---

## 데이터 소스 교체 방법 (예: KRX 금현물 원화 가격)

데이터 소스는 `gold_service/sources/base.py`의 `PriceSource` 인터페이스로 분리돼 있습니다.

1. `gold_service/sources/krx_source.py`에 구현체를 만듭니다.

   ```python
   from gold_service.sources.base import PriceSource

   class KRXGoldSource(PriceSource):
       name = "krx"

       def fetch(self, start, end):
           raw = ...  # KRX에서 [start, end] 일간 시세 조회 → date, open, high, low, close
           return self.normalize(raw)  # 컬럼 보정·정렬·중복 제거·검증
   ```

2. `gold_service/sources/__init__.py`의 `build_source`에 `PRICE_SOURCE == "krx"` 분기를 추가합니다.
3. `PRICE_SOURCE=krx`로 실행합니다. 시가·고가·저가는 `prices` 테이블에 저장되지만 현재 모델은 종가만 씁니다.
4. **주의**: 달러 → 원화로 바꾸면 수익률 분포가 달라지므로 기존 `prices`, `forecasts`, `model_params`를 비운 새 DB에서 시작하고, 회귀 테스트 기준도 원화 데이터로 다시 확인해야 합니다. 휴장일도 KRX 기준 `HOLIDAYS_FILE`로 맞추세요.

CSV만 바꾸는 경우엔 코드 수정 없이 `PRICE_CSV_PATH`, `PRICE_CSV_CLOSE_COL`만 바꾸면 됩니다.

---

## 예약 실행 (GitHub Actions)

- `.github/workflows/daily.yml`: 월~금 16:30 KST(07:30 UTC)에 `run_daily --date <오늘(KST)>`를 실행합니다. 저장소 Secrets에 `DATABASE_URL`(PostgreSQL)을 등록하세요. 수동 실행(`workflow_dispatch`)으로 날짜를 지정할 수도 있습니다.
- `.github/workflows/tests.yml`: push/PR마다 `pytest`를 실행합니다.

> 현재 소스는 정적 CSV라서 CSV가 갱신되지 않으면 예약 실행이 종료 코드 3으로 실패합니다. 실서비스 전 실시간 소스(KRX 등)로 교체해야 합니다.

---

## 폴더 구조

```
gold_service/
  sources/           # PriceSource 인터페이스, CSV 구현
  features.py        # 수익률·rv 피처, 학습 타깃
  models.py          # HAR, GARCH, 앙상블, 대체값, 재학습 스케줄, walk-forward
  grading.py         # 백분위·등급
  planner.py         # 주간 플랜 생성 (요일 → 날짜 → 금액 단계별 함수)
  monitoring.py      # 적중률·QLIKE 개선율·경보
  trading_calendar.py# 거래일 달력 (휴장일)
  notify.py          # 알림 인터페이스 (현재 로그만)
  db.py              # SQLAlchemy 스키마·저장 함수
  config.py          # 환경변수 설정
  manage.py          # 로컬 관리 명령 (사용자 추가, 플랜 보기)
  run_daily.py       # 일간 배치 진입점
tests/
data/gold_only_ready.csv
.github/workflows/
```

### DB 테이블

| 테이블 | 내용 |
|---|---|
| `prices` | 일간 시가·고가·저가·종가, 소스 |
| `model_params` | 학습 기준일, HAR 계수·절편·잔차분산, GARCH 파라미터, 학습 행 수·마지막 학습 행 |
| `forecasts` | date, sigma, grade, percentile, is_fallback (+ har_var, garch_var, rv22, 사용 파라미터, 오류) |
| `users` | 이름, 주간 금액 (스키마 위주) |
| `buy_plans` / `plan_items` | 사용자·주별 플랜과 회차별 날짜·금액·주문유형(MARKET) |
| `trades` | 실제 체결 기록 (스키마만) |
| `monitoring` | 주별 적중률, QLIKE, 개선율, 경보 |

### 확장 지점

- **알림**: `notify.Notifier`를 구현해 `run_daily.run(..., notifier=...)`로 넘기면 됩니다.
- **지정가**: `planner`가 `split_weekdays → resolve_trade_dates → allocate_amounts → build_plan`으로 나뉘어 있고 `plan_items.order_type`이 있어, 회차별 가격 조건 단계를 끼워 넣을 수 있습니다(현재는 시장가만).
- **웹**: `forecasts`, `buy_plans`, `plan_items`, `monitoring`을 읽기만 하면 됩니다.

---

## 구현 가정

1. **HAR 학습 창은 누적(expanding)**입니다. 재학습마다 데이터 시작부터 `s−5`까지 전부 씁니다. 최소 252행 미만이면 학습 실패로 보고 대체값을 씁니다.
2. **GARCH `last_obs=s`는 arch 패키지 동작 그대로** s 당일 수익률을 제외하고 추정합니다. 예측은 매일 그날까지의 수익률로 `fix()`한 모델에서 냅니다.
3. **재학습 주기 기준점**은 "직전 학습 기준일로부터 63거래일 이상 지났는가"입니다. 처음 실행하면 백필 시작일에 처음 학습합니다. 같은 날 다시 실행해도 기존 파라미터를 써서 결과가 같습니다.
4. **백분위**는 그날 값을 포함한 최근 252개 중 그날 값 이하의 비율(%)입니다. 등급 경계는 이상·초과로 해석합니다(33% → 낮음, 33% 초과 → 보통).
5. **플랜 생성 시점**: 명세대로 `run_daily`가 주 첫 거래일 날짜로 실행될 때 직전 거래일 예측으로 그 주 플랜을 만듭니다. 주 첫 거래일 여부는 DB에 쌓인 가격 데이터로 판단합니다.
6. **이번 주 남은 거래일**은 달력(주말 + `HOLIDAYS_FILE`)으로 판단합니다. 휴장일 이월 결과 두 회차가 같은 날이 되면 합치지 않고 회차를 그대로 둡니다.
7. 등급이 없으면(백분위 이력 60개 미만) 플랜을 만들지 않고 경고만 남깁니다.
8. **모니터링 실제값**: `y = mean(r_{t+1}²…r_{t+5}²)`이고, 실행일까지 확정된 예측만 씁니다(최근 5거래일 예측은 제외). 실제 분산이 0이면 `1e-12`를 하한으로 둡니다. 대체값 예측도 사용자에게 나간 값이라 지표에 포함합니다.
9. **경보**는 별도 이벤트 테이블 없이 `monitoring.alert` 컬럼과 WARNING 로그로 남깁니다.
10. 사용자 기능은 범위 밖이지만, 플랜을 저장할 대상이 필요해 `manage add-user` 임시 명령을 넣었습니다.

## 열린 질문

1. **플랜 시점과 배치 시각이 어긋납니다.** "주 첫 거래일 아침"에 플랜이 필요한데 배치는 장 마감 후에 돕니다. 지금처럼 월요일 장 마감 후에 만들면 1회차(월)가 이미 지나 있습니다. 직전 주 마지막 거래일 배치에서 다음 주 플랜을 미리 만들지, 아침 배치를 따로 둘지 정해야 합니다.
2. **휴장일 데이터**: KRX 휴장일 목록을 어디서 받아 갱신할지(수동 CSV / KRX API).
3. **데이터 지연·누락**: 장 마감 후 그날 가격이 아직 없으면 지금은 종료 코드 3으로 실패합니다. 재시도할지, 직전 값으로 예측할지 정해야 합니다.
4. **원화 전환 후 재검증**: KRX 원화 가격은 환율 변동이 섞입니다. HAR/GARCH 개선율과 등급 분포를 다시 확인하고, 시가·고가·저가로 rv를 개선할지는 별도 검증 과제입니다(현재는 종가만 사용).
5. **이월로 같은 날에 몰린 회차**를 합칠지 나눠 둘지.
6. **경보 이후 조치**: 경보가 뜨면 대체값(rv22)으로 자동 전환할지, 운영자 확인만 할지.
7. **최소 매수 단위**: KRX 금현물은 1g 단위라 회차 금액이 1g 가격보다 작으면 체결할 수 없습니다. 최소 금액 제한이나 분할 횟수 축소 규칙이 필요한지.
8. **주 중간에 가입한 사용자**의 첫 플랜 처리.
