# 🪙 금 분할매수 도우미

금을 **매주 정해진 금액으로 사 모으는 사람**에게 이번 주에 **몇 번에 나눠, 어느 요일에** 살지 알려주는 서비스입니다. (강의 프로젝트)

- 금값이 오를지 내릴지는 **예측하지 않습니다**.
- "다음 5거래일 동안 금값이 얼마나 출렁일지(변동성)"만 예측하고, 이를 정해진 규칙으로 분할 횟수와 매수 요일로 바꿉니다.
- 백엔드 서버 없이 **Python 배치가 JSON 파일을 만들고 → React 정적 사이트가 그 파일을 읽어 보여주는** 구조입니다.

> 이 서비스는 예상 변동성에 따라 매수 시점을 나누는 일정 안내입니다. 금값 방향 예측이나 투자 권유가 아니며 수익을 보장하지 않습니다. 분할매수가 평균 단가를 높일 수도 있습니다.

---

## 전체 흐름

```
             Python (gold_service)                                   React (web/)
┌─────────────────────────────────────────────────────┐      ┌──────────────────────────┐
│ run_daily ─► prices ─► σ_t(HAR+GARCH) ─► 등급 ─► 5일 범위 │      │                          │
│              (DB)      (forecasts)                    │      │  fetch /data/forecast.json│
│ evaluate  ─► walk-forward 지표 (evaluations)           │ ───► │  (실패 시 sample.json)    │
│ export_json ─► web/public/data/forecast.json          │      │  → 정적 사이트(Vercel 등) │
└─────────────────────────────────────────────────────┘      └──────────────────────────┘
```

```bash
# 0) 설치 (한 번)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
(cd web && npm install)

# 1) 그날의 배치: 수집 → 예측(필요 시 재학습) → 등급 → 5일 가격 범위 → 저장
python -m gold_service.run_daily --date 2026-09-24

# 2) 모델 성적표용 walk-forward 평가 (모델·데이터가 바뀔 때만 다시 실행)
python -m gold_service.evaluate --start 2024-01-01

# 3) 웹이 읽을 JSON 내보내기
python -m gold_service.export_json --out web/public/data/forecast.json

# 4) 웹 실행 → http://localhost:5173
cd web && npm run dev
```

Python 없이 웹만 띄워도 됩니다. 커밋된 `web/public/data/forecast.json`(없으면 `forecast.sample.json`)을 읽습니다. 샘플로 대체되면 화면 위에 "샘플 데이터"가 표시됩니다.

> 현재 데이터(`data/gold_only_ready.csv`)는 **2026-09-24까지**만 있습니다. 그 이후 거래일을 `--date`로 주면 "가격 데이터 없음"(종료 코드 3)으로 끝납니다.

---

## 1부. 백엔드 (Python `gold_service`)

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

### 2. 변동성 등급과 주간 플랜

σ_t를 그날까지의 최근 252개 예측값 안에서 백분위로 바꿉니다(최소 60개, 미래 값 미사용).

| 등급 | 백분위 | 분할 | 요일 |
|---|---|---|---|
| 낮음 | ≤ 33% | 1회 | 월 |
| 보통 | 33~67% | 2회 | 월, 목 |
| 높음 | 67~90% | 3회 | 월, 수, 금 |
| 매우 높음 | > 90% | 5회 | 월~금 |

- 플랜은 매주 첫 거래일에 **직전 거래일 종가 기준** σ와 등급으로 만듭니다(MVP: 시장가만).
- 회차 금액 = 주간 금액 ÷ 분할 횟수 (원 단위, 나머지는 마지막 회차).
- 계획한 요일이 휴장이면 그 주의 다음 거래일로, 없으면 그 주 마지막 거래일로 미룹니다.

### 3. 다음 5거래일 90% 가격 범위 (적응형 배수)

```
ret5_t = log(close_{t+5} / close_t)
sd5_t  = σ_t × √5
z_t    = (|ret5| / sd5).shift(5).rolling(252, min_periods=120).quantile(0.9)   # i ≤ t−5 만 사용
범위   = close_t × exp(∓ z_t × sd5_t)
```

- 결과가 이미 확정된 과거 오차만으로 배수를 정하므로 미래 정보를 쓰지 않습니다.
- 표본이 120개 미만이면 `z = 1.645`를 쓰고 `forecasts.z_is_default = true`로 남깁니다.
- `forecasts`에 `z`, `band_low`, `band_high`, `z_is_default` 컬럼이 있습니다. 예전 DB는 `init_db`가 빠진 컬럼을 자동으로 추가합니다.
- 범위 폭(±%)은 `(상한 − 하한) / (2 × 기준가)`로 표시합니다.

### 4. 모니터링 (매주 첫 거래일)

- 지난 13주 **예측 범위 적중률**: 실제 5일 실현 변동성이 예측의 ±30% 안에 든 비율
- **단순 기준 대비 개선율**: `1 − QLIKE(모델) / QLIKE(rv22)`, `QLIKE = mean(y/h − log(y/h) − 1)`
- 개선율이 **4주 연속 0% 미만**이면 `monitoring.alert = true`와 경보 로그를 남깁니다.

### 5. 평가 명령 `evaluate`

```bash
python -m gold_service.evaluate --start 2024-01-01 [--end YYYY-MM-DD]
```

평가 시작 300거래일 전부터 일간 배치와 같은 규칙으로 walk-forward 예측을 돌립니다. 그래야 적응형 z가 평가 첫날부터 252개 오차로 채워집니다. 결과는 `evaluations` 테이블에 저장되고 `export_json`이 읽어 갑니다.

| 지표 | 정의 |
|---|---|
| 범위 적중률 | `|ret5| ≤ z × sd5`인 날의 비율 |
| 평균 범위 폭 | 범위 반폭(±%)의 평균 |
| 겹치지 않는 표본 적중률 | 첫 평가일부터 5거래일 간격으로 뽑은 날만 센 적중률 |
| 비교 기준 | "최근 1년 변동성": 252일 수익률 표준편차를 σ 대신 넣고 같은 방식(적응형 z)으로 만든 범위 |
| QLIKE 개선율 | `1 − QLIKE(모델) / QLIKE(rv22)` |

**실제 결과** (달러 금값, 2024-01-02 ~ 2026-09-17, 686거래일):

| 지표 | 이 서비스 (HAR+GARCH 평균) | 기대값 | 최근 1년 변동성 | 기대값 |
|---|---|---|---|---|
| 90% 범위 적중률 | **89.5%** | 약 89.5% | **88.5%** | 약 88.5% |
| 평균 범위 폭 | **±4.66%** | 약 ±4.6% | **±4.48%** | 약 ±4.5% |
| 겹치지 않는 표본 적중률 (138개) | 89.9% | - | 89.9% | - |
| QLIKE 개선율 (rv22 대비) | +7.93% | - | - | - |

### 6. JSON 내보내기 `export_json`

```bash
python -m gold_service.export_json --out web/public/data/forecast.json [--date YYYY-MM-DD]
```

DB(forecasts, prices, evaluations)만 읽어 아래 스키마로 씁니다. `--date`가 없으면 DB의 마지막 예측일 기준입니다.

| 키 | 타입 | 설명 |
|---|---|---|
| `generated_at` | string | 생성 시각 (ISO 8601, UTC) |
| `as_of` | string | 기준일(마지막 거래일), `YYYY-MM-DD` |
| `currency`, `unit` | string | `"USD"`, `"oz"` |
| `price` | number | 기준일 종가 |
| `sigma_daily` | number | σ (소수, `0.0131` = 하루 ±1.31%) |
| `grade` | string | `"낮음" \| "보통" \| "높음" \| "매우 높음"` |
| `percentile` | number \| null | 최근 252개 예측 중 백분위, 0~1 |
| `is_fallback` | bool | 모델 대신 rv22를 썼는지 |
| `band` | object | `horizon_days`(5), `coverage`(0.9), `z`, `z_is_default`, `low`, `high` |
| `history[]` | array | 최근 260거래일 `{date, price, sigma_daily, grade, band_low, band_high}`. `band_*`는 **그 날짜 종가 기준으로 낸** 다음 5거래일 범위입니다. 차트는 5행 뒤 날짜에 그립니다 |
| `evaluation` | object \| null | `model_name, period_start, period_end, n_days, coverage_target, hit_rate, avg_width, hit_rate_nonoverlap, n_nonoverlap, z_default_days, qlike_improvement, fallback_days, baseline{name, hit_rate, avg_width, hit_rate_nonoverlap, n_nonoverlap, z_default_days}`. 비율은 모두 0~1, `avg_width`는 반폭 비율(0.0466 = ±4.66%). `evaluate`를 안 돌렸으면 `null` |
| `split_rule` | object | `{"낮음":[0], "보통":[0,3], "높음":[0,2,4], "매우 높음":[0,1,2,3,4]}` (0=월) |

`web/public/data/forecast.sample.json`은 같은 스키마의 샘플(2026-09-24 기준)로, Python 없이도 웹이 뜨게 하려고 커밋해 둔 파일입니다.

### 7. 플랜 규칙 공유 테스트

```bash
python -m gold_service.export_planner_fixtures   # → web/src/planner.fixtures.json
```

Python planner로 **등급 4 × 주간 금액 3(300,000 / 100,000 / 99,999) × 주 3(휴장 없음 / 월·목 휴장 / 금 휴장) = 36개** 케이스를 내보냅니다. 두 쪽 테스트가 이 파일을 함께 씁니다.

- `tests/test_export.py`: 커밋된 픽스처가 현재 Python 규칙과 같은지 확인합니다.
- `web/src/planner.test.ts`: React `planner.ts`가 같은 결과를 내는지 확인합니다.

규칙을 바꾸면 픽스처를 다시 내보내야 두 테스트가 통과합니다.

### 실행 명령 요약

| 명령 | 하는 일 |
|---|---|
| `python -m gold_service.run_daily --date YYYY-MM-DD` | 그날 배치. 주 첫 거래일이면 플랜·모니터링까지. 멱등 |
| `python -m gold_service.evaluate --start 2024-01-01` | walk-forward 평가 → `evaluations` |
| `python -m gold_service.export_json --out web/public/data/forecast.json` | 웹용 JSON |
| `python -m gold_service.export_planner_fixtures` | 플랜 공유 테스트 픽스처 |
| `python -m gold_service.manage add-user --name 홍길동 --weekly-amount 300000` | (임시) 플랜 받을 사용자 추가 |
| `python -m gold_service.manage show-plans` | 사용자별 최신 플랜 출력 |

`run_daily` 종료 코드: 0 성공·휴장일 건너뜀, 1 실패, 2 인자 오류, 3 거래일인데 가격 데이터 없음.

처음 실행하면 최근 `BACKFILL_DAYS`(기본 520) 거래일을 같은 규칙으로 예측해 채웁니다. 이 정도면 웹 차트용 260일 모두에 적응형 z(오차 표본 120개 이상)가 들어갑니다.

### 환경변수

모두 선택값입니다. `.env.example`을 참고해 셸에서 `export` 하세요.

| 변수 | 기본값 | 설명 |
|---|---|---|
| `DATABASE_URL` | `sqlite:///<프로젝트>/gold_service.db` | SQLAlchemy URL. 예: `postgresql+psycopg2://user:pw@host:5432/gold` |
| `PRICE_SOURCE` | `csv` | 가격 소스 종류 |
| `PRICE_CSV_PATH` | `data/gold_only_ready.csv` | CSV 경로 |
| `PRICE_CSV_DATE_COL` / `PRICE_CSV_CLOSE_COL` | `date` / `gold` | 날짜·종가 컬럼 |
| `HOLIDAYS_FILE` | (없음) | 휴장일 CSV (첫 컬럼 `YYYY-MM-DD`). 없으면 주말만 휴장 |
| `BACKFILL_DAYS` | `520` | 예측이 비어 있을 때 거슬러 채울 거래일 수 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 |

### 데이터 소스 교체 (예: KRX 금현물 원화 가격)

1. `gold_service/sources/`에 `PriceSource`를 구현합니다. `fetch(start, end)`가 `date, open, high, low, close`를 돌려주면 되고, 마지막에 `self.normalize(df)`를 호출합니다.
2. `sources/__init__.py`의 `build_source`에 분기를 추가하고 `PRICE_SOURCE`로 고릅니다.
3. 원화로 바꾸면 수익률 분포가 달라지므로 새 DB에서 시작하고, 회귀·평가 기준을 다시 확인합니다. `export_json.py`의 `CURRENCY, UNIT`도 `"KRW", "g"`로 바꿔야 합니다. 웹은 `currency`가 `KRW`이면 "원"으로 표시합니다.

CSV만 바꾸는 경우엔 `PRICE_CSV_PATH`, `PRICE_CSV_CLOSE_COL`만 바꾸면 됩니다.

---

## 2부. 웹 (React `web/`)

Vite + React + TypeScript, 차트는 Recharts, 테스트는 Vitest입니다. 상태 관리·UI 라이브러리 없이 일반 CSS를 쓰고, 360px부터 데스크톱까지 반응형이며 다크 모드를 지원합니다.

| 섹션 | 내용 |
|---|---|
| 헤더 | 서비스 이름, 기준일, 마지막 업데이트(KST), 샘플 데이터 표시 |
| 변동성 날씨 | 등급 아이콘 + 글자(☀️ 낮음 / ⛅ 보통 / 🌧️ 높음 / ⛈️ 매우 높음), 하루 예상 움직임, 백분위, 한 줄 해설, 대체값 안내 |
| 5거래일 90% 범위 | "4,050 ~ 4,510 달러 (±5.4%)", 최근 260일 가격 선 + 5거래일 전에 낸 범위 띠 + 범위 밖 날 점, 툴팁, 표로 보기 |
| 분할 플랜 계산기 | 주간 금액·상품(표시용) 입력 → 분할 횟수, 회차별 요일·금액. 휴장 이월 안내 |
| 모델 성적표 | 테스트 기간, 적중률·평균 폭·겹치지 않는 표본 적중률을 비교 기준과 나란히 |
| 푸터 | 면책 문구 |

```bash
cd web
npm install
npm run dev       # 개발 서버
npm test          # Vitest (플랜 픽스처, 차트 데이터, 포맷, 화면·샘플 대체)
npm run build     # 타입 검사 + dist/ 빌드
npm run preview   # 빌드 결과 미리보기
```

주요 파일: `src/planner.ts`(플랜 순수 함수), `src/chart.ts`(5행 시프트·범위 밖 판정), `src/data.ts`(fetch + 샘플 대체), `src/format.ts`(표시·해설), `src/components/*`.

### 정적 배포

forecast.json을 새로 내보낸 뒤 커밋·푸시하면 배포 사이트에 반영됩니다.

**Vercel**
1. vercel.com → Add New Project → 이 저장소 선택
2. **Root Directory = `web`** (Framework: Vite가 자동 인식, `web/vercel.json`에 설정 있음)
3. Deploy. 이후 브랜치에 push할 때마다 자동 배포됩니다.

CLI로 하려면 `cd web && npx vercel --prod`.

**Netlify**
1. app.netlify.com → Add new site → Import from Git → 이 저장소
2. 저장소 루트의 `netlify.toml`이 `base = "web"`, `publish = "dist"`를 지정하므로 그대로 Deploy

CLI로 하려면 `cd web && npm run build && npx netlify deploy --prod --dir dist`.

---

## 테스트

```bash
pytest -q             # Python 61개
cd web && npm test    # 웹 50개
```

| 테스트 | 확인 내용 |
|---|---|
| `test_leakage.py` | t+1 이후 데이터를 바꿔도 t의 예측·피처·등급이 그대로인지 |
| `test_retrain.py` | HAR 학습 행 `i ≤ s−5`, GARCH가 s 이후 미사용, 63거래일마다 재학습 |
| `test_planner.py` | 등급별 분할·요일, 휴장 이월, 금액 합계, 등급 경계 |
| `test_fallback.py` | 실패·이력 부족·비정상 값일 때 rv22 대체와 플래그 |
| `test_regression.py` | 2024-01-01 이후 walk-forward에서 앙상블 QLIKE < rv22 기준 |
| `test_bands.py` | 범위 공식, z가 i ≤ t−5 오차만 쓰는지, 표본 부족 시 1.645와 플래그 |
| `test_evaluate.py` | 평가 지표가 노트북 기대값 근처인지 |
| `test_export.py` | forecast.json 스키마, 커밋된 샘플·픽스처가 최신인지 |
| `test_monitoring.py` / `test_run_daily.py` | 모니터링 지표·경보, SQLite 통합(멱등성, 플랜, 대체값, 범위 저장, 컬럼 추가, 종료 코드) |
| `web/src/planner.test.ts` | React planner가 Python 픽스처 36개와 똑같은 결과를 내는지 |
| `web/src/App.test.tsx` | 샘플 대체 표시, 모든 섹션 렌더링, 계산기, 방향·권유 표현 없음 |

GitHub Actions: `tests.yml`(push/PR마다 Python·웹 테스트와 빌드), `daily.yml`(월~금 16:30 KST 일간 배치 예시).

---

## 폴더 구조

```
gold_service/
  sources/                  # PriceSource 인터페이스, CSV 구현
  features.py               # 수익률·rv 피처, 학습 타깃
  models.py                 # HAR, GARCH, 앙상블, 대체값, 재학습 스케줄, walk-forward
  grading.py                # 백분위·등급
  bands.py                  # 5일 90% 가격 범위 (적응형 z)
  planner.py                # 주간 플랜 (요일 → 날짜 → 금액 단계별 함수)
  monitoring.py             # 적중률·QLIKE 개선율·경보
  evaluate.py               # walk-forward 평가 명령
  export_json.py            # 웹용 forecast.json
  export_planner_fixtures.py# 플랜 공유 테스트 픽스처
  trading_calendar.py       # 거래일 달력 (휴장일)
  notify.py                 # 알림 인터페이스 (현재 로그만)
  db.py / config.py / manage.py / run_daily.py
tests/
web/
  public/data/forecast.json, forecast.sample.json
  src/ (App.tsx, planner.ts, chart.ts, data.ts, format.ts, components/, *.test.ts)
data/gold_only_ready.csv
netlify.toml, .github/workflows/
```

DB 테이블: `prices`, `model_params`, `forecasts`(σ·등급·백분위·대체값·z·범위), `users`, `buy_plans`, `plan_items`, `trades`(스키마만), `monitoring`, `evaluations`.

---

## 구현 가정

**배치(1차)**
1. HAR 학습 창은 누적(expanding)이고, 학습 행이 252개 미만이면 실패로 보고 대체값을 씁니다.
2. GARCH `last_obs=s`는 arch 동작 그대로 s 당일을 제외합니다.
3. 재학습 기준점은 "직전 학습 기준일로부터 63거래일 이상"이고, 처음 실행하면 백필 시작일에 학습합니다.
4. 백분위는 그날 포함 최근 252개 중 그날 값 이하 비율이고, 경계는 33% → 낮음, 33% 초과 → 보통 식입니다.
5. 플랜은 `run_daily`가 주 첫 거래일 날짜로 실행될 때 직전 거래일 예측으로 만듭니다. 휴장 이월로 회차가 같은 날에 겹쳐도 합치지 않습니다.
6. 모니터링 실제값이 0이면 분산 하한 `1e-12`를 쓰고, 대체값 예측도 지표에 포함합니다. 경보는 `monitoring.alert` 컬럼과 로그로 남깁니다.

**범위·평가·웹(2차)**

7. **평가 워밍업**: `evaluate --start`는 300거래일 전부터 예측해 z를 채웁니다. 워밍업이 없으면 평가 첫 124일은 z=1.645가 되어 적중률 89.65%, 폭 ±4.68%로 조금 달라집니다. 기대값(노트북)은 워밍업이 있는 쪽과 일치합니다.
8. **비교 기준 범위**도 같은 적응형 z 방식(오차 분위수)을 씁니다. 252일 표준편차는 `pandas.rolling(252).std()`(ddof=1)입니다.
9. **평가의 QLIKE 개선율(+7.93%)이 회귀 테스트(+7.44%)와 다른 이유**는 walk-forward 시작점이 달라 63거래일 재학습 시점이 달라지기 때문입니다. 모델 자체는 같습니다.
10. **평균 범위 폭**은 `(상한−하한)/(2×기준가)`의 평균입니다. 로그 반폭 `z×sd5`와는 소수 둘째 자리 정도 차이가 납니다.
11. `BACKFILL_DAYS` 기본값을 400 → 520으로 올렸습니다. 모델·등급 규칙과 무관한 설정으로, 웹 차트 260일 전체에 적응형 z가 들어가게 하려는 것입니다.
12. `forecast.json`도 커밋합니다. 정적 배포에서 실제 데이터가 보이게 하려는 것이고, 현재는 샘플과 내용이 같습니다.
13. 웹 계산기는 휴장일 정보 없이 월~금 요일 기준으로만 표시합니다. `planner.ts`는 거래 요일 목록을 인자로 받을 수 있어 픽스처의 휴장 케이스까지 Python과 같게 계산합니다.
14. `forecast.json`이 없거나 필수 키가 빠지면 샘플로 대체합니다(형식 검사 포함).
15. JSON의 `band`에 명세에 없는 `z_is_default`를 하나 더 넣었습니다(웹에서 "기본 배수 사용" 안내용).

## 열린 질문

1. **플랜 시점**: 플랜은 "주 첫 거래일 아침"이 필요한데 배치는 장 마감 후에 돕니다. 월요일 저녁에 만들면 1회차(월)가 이미 지나 있습니다. 직전 주 마지막 거래일 배치에서 다음 주 플랜을 미리 만들지 정해야 합니다.
2. **웹 계산기 등급의 시점**: 웹은 `as_of`(마지막 거래일) 등급으로 "이번 주" 플랜을 계산합니다. 배치 규칙(주 첫 거래일에 직전 거래일 기준)과 같으려면 금요일 데이터로 다음 주를 보여주는 것이 맞습니다. 화면 문구를 "다음 주"로 할지, 주 중간에 보면 어떻게 할지 정해야 합니다.
3. **forecast.json 갱신 방법**: 시연용 정적 사이트라 수동으로 export → 커밋합니다. 매일 자동 갱신하려면 `daily.yml`에서 export 후 커밋·푸시하는 단계를 추가해야 하는데, 정적 CSV라 지금은 의미가 없습니다.
4. **원화(KRW) 전환** 후 z 분포·적중률을 다시 검증해야 하고, `currency`/`unit`을 설정으로 뺄지 정해야 합니다.
5. **최소 매수 단위**: KRX 금현물은 1g 단위라 회차 금액이 1g 가격보다 작으면 살 수 없습니다. 웹 계산기에 최소 금액 안내나 분할 축소 규칙이 필요한지 정해야 합니다.
6. **범위 해석 문구**: "약 90% 확률로 이 안에 있었다"는 과거 적중률 기준 표현입니다. 발표 때 더 보수적인 표현(예: "과거 같은 방식의 범위가 약 90% 맞았어요")을 쓸지 정해야 합니다.
7. 휴장일 데이터 출처(KRX), 장 마감 직후 데이터 지연 시 재시도 여부, 경보 이후 조치(자동 대체 여부) — 1차 때 질문 그대로 남아 있습니다.
