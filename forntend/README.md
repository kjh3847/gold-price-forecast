# React UI 실행 및 연동 안내

루트 README의 5개 주요 기능을 구현한 시연용 UI입니다. 기존 로컬 디렉터리명 `forntend`를 유지했습니다. 루트 README에 표기된 `frontend` 대신 이 폴더에서 실행합니다. 백엔드와 머신러닝 디렉터리는 변경하지 않았습니다.

## 실행

Node.js 22.12 이상이 필요합니다.

```powershell
cd forntend
npm install
npm run dev
```

http://127.0.0.1:5173 에 접속합니다. `npm start`도 동일하게 동작합니다.

이번 작업 환경에 Node.js가 없어 루트 `.tools/node-v22.23.3-win-x64`에 공식 휴대용 런타임을 다운로드하고 SHA-256을 검증했습니다. 이 환경에서는 다음처럼 실행할 수 있습니다. 시스템 PATH를 변경하거나 Node.js를 전역 설치하지 않았습니다.

```powershell
# 프로젝트 루트에서 실행
$env:PATH = (Join-Path (Get-Location) '.tools\node-v22.23.3-win-x64') + ';' + $env:PATH
cd forntend
npm.cmd run dev
```

## 구성

- `src/components/`: 레이아웃, 요약 카드, 차트, 예측, 평가 지표, 가격 테이블, 저장 내역
- `src/data/mockGold.js`: 재현 가능한 365일 mock 시세, 고정 기준일, 모델 상태
- `src/services/goldService.js`: 조회/예측/평가/저장 비동기 인터페이스
- `src/utils/format.js`: 가격과 날짜 포맷
- `src/App.jsx`: 화면 구성과 상태 연결, hash 기반 메뉴 이동
- `src/styles.css`: PC/태블릿/모바일 스타일

## README 기능 대응

1. 금 시세 데이터 조회: 시작일·종료일 필터, 페이지 이동, 결과 없음/입력 오류 상태
2. 금 시세 시각화: Recharts 기반 1개월/3개월/6개월/1년 일별 가격 차트
3. 금 시세 예측: 1일/7일/30일 후 mock 예측, 변동액·변동률·기준일 표시
4. 실제값/예측값 비교: 차트 비교 토글, 별도 모델 성능 화면, MAE/RMSE/MAPE/R² 학습 대기 상태
5. 예측 결과 저장: localStorage 임시 저장, 중복 방지, 새로고침 유지, 저장 오류 안내

모든 시세와 예측값은 가상 데이터이며 단위는 KRW/g입니다. 기준일은 2026-09-28로 고정되어 있습니다. 일별 mock 시리즈는 휴장일을 고려하지 않습니다. 평가 지표는 실제 모델 학습 전이므로 표시하지 않습니다. localStorage는 현재 브라우저·origin에만 저장되며 SQLite 저장을 대신하지 않습니다.

## API 및 SQLite/ML 연결

React 컴포넌트는 데이터베이스에 직접 접근하지 않습니다. `goldService.js`의 메서드 구현을 API 호출로 교체합니다. 다음 경로는 제안하는 계약이며 현재 구현된 백엔드 경로가 아닙니다.

| 서비스 메서드 | 향후 API 예시 | 책임 |
|---|---|---|
| getDashboard | GET /api/gold/summary | 현재/이전 종가, 기준일, 모델 메타데이터 |
| getPrices | GET /api/gold/prices?period=3M&start=...&end=... | 날짜 필터, OHLC 및 예측값 |
| getPrediction | GET /api/predictions?date=... | ML 추론, 기준 가격, 변화량, 모델 버전 |
| getModelEvaluation | GET /api/models/evaluation | 별도 테스트 구간 비교 데이터와 평가 지표 |
| getSavedPredictions | GET /api/predictions/saved | SQLite 저장 내역 |
| savePrediction | POST /api/predictions | 서버 검증 후 SQLite 저장, 중복 방지 |

백엔드는 날짜, 가격 단위, 예측 가능 날짜, 모델 버전을 검증해야 합니다. 현재 `periods`는 mock 설정입니다. `getPredictionOptions()`는 예측 가능 날짜 목록을 비동기로 반환하므로 향후 API 응답으로 교체합니다. 서버 저장 시 가격과 모델 정보를 클라이언트 입력에 의존하지 않고 서버에서 조회합니다. 저장 키는 기준일+예측일+모델 버전이며 실제 서비스에서는 서버 고유 ID를 사용합니다.

### 모델 미학습 단계 및 예측 교체 계약

현재 **데이터 수집 단계이며 모델 학습은 전혀 수행하지 않았습니다.** `src/data/mockPredictions.js`의 가격은 UI 시연을 위한 임의 계산입니다. 예측 정확도나 통계적 의미는 없습니다. 학습 코드나 모델 파일은 추가하지 않았습니다.

`PredictionCard`는 임의 가격 생성이나 날짜 목록을 직접 참조하지 않습니다. 서비스가 반환한 예측과 날짜 목록을 props로 받습니다. 가격·모델명·버전·예측 날짜는 응답에서 가져오며, mock 날짜 밖의 미래 예측도 같은 계약으로 처리할 수 있습니다.

모델 연동 시 `goldService.js`의 `getPrediction(date)`에서 백엔드 응답을 받아 `normalizePrediction(response)`에 전달합니다. `src/services/predictionContract.js`가 날짜, 숫자, 단위, 출처 및 모델 버전을 검증하고 변동액·변동률을 공통 계산합니다. API 오류 시 임의 예측으로 몰래 대체하지 말고 오류를 표시해야 합니다.

```json
{
  "id": "backend-prediction-id",
  "asOf": "2027-01-01",
  "date": "2027-01-08",
  "currentPrice": 160000,
  "predictedPrice": 161000,
  "model": "실제 학습 모델명",
  "modelVersion": "v1",
  "source": "model",
  "unit": "KRW/g"
}
```

`getPredictionOptions()`의 응답은 `[{ "date": "2027-01-08", "days": 7 }]` 형식입니다. 기본 예측일은 반드시 이 목록에 포함되어야 합니다. 현재는 mock만 사용하며 실제 API가 구현되어 있지는 않습니다. 예측 외의 시세·평가·저장 메서드도 각 백엔드 API에 연결하고, 전체 서비스를 실제 데이터로 전환할 때 화면의 전역 데모 안내 및 학습 대기 안내를 실제 서비스 상태에 맞게 바꿔야 합니다. 기존 mock 저장 내역을 실제 모델 결과로 이관하지 마세요.

흐름: **React → API → Backend → SQLite / ML Model**

## 검증

```powershell
npm run build
npm test
npm run test:ui
```

UI 테스트는 Windows의 설치된 Microsoft Edge를 headless로 사용합니다. Edge가 없으면 Playwright 브라우저를 설치하고 `playwright.config.js`의 channel을 조정하세요. UI 테스트는 dev 서버를 자동 실행하고 차트, 메뉴, 필터, 저장, 오류, 모바일/태블릿 가로 넘침과 브라우저 콘솔을 검사합니다. 스크린샷은 `test-results/`에 생성됩니다.
