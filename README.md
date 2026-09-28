Gold Price Forecast

금 가격 데이터를 수집하고 머신러닝/딥러닝 모델을 활용해 금값의 미래 가격을 예측하는 프로젝트입니다.

현재는 Kaggle을 기반으로 금 가격 데이터를 수집·정제하고 있으며, 이후 모델 학습 및 예측 API와 웹 프론트엔드를 구축할 예정입니다.

🚧 현재 개발 초기 단계입니다.
모델, 세부 아키텍처 및 예측 방식은 데이터 분석 및 실험 결과에 따라 결정할 예정입니다.

Project Overview

금 가격의 과거 데이터를 기반으로 미래 가격을 예측하는 것을 목표로 합니다.

전체적인 개발 흐름은 다음과 같습니다.

Kaggle Dataset
      ↓
Data Collection
      ↓
Data Cleaning / Preprocessing
      ↓
Exploratory Data Analysis
      ↓
Model Training
      ↓
Model Evaluation
      ↓
Prediction API
      ↓
React Frontend

Current Progress

 프로젝트 초기 설정

 Kaggle 데이터 수집

 데이터 정제 및 전처리

 데이터 분석 및 시각화

 Feature Engineering

 Baseline 모델 구현

 모델 비교 및 평가

 최종 모델 선정

 예측 API 구현

 SQLite 데이터베이스 구성

 React 프론트엔드 구현

 프론트엔드 ↔ API 연동

 배포

Tech Stack

현재 고려하고 있는 기술 스택입니다.

Data / Machine Learning

Python

Pandas

NumPy

Scikit-learn

Kaggle Dataset

TBD: Machine Learning / Deep Learning Model

모델은 데이터 분석 결과를 바탕으로 결정할 예정입니다.

예를 들어 다음과 같은 모델들을 비교할 수 있습니다.

Linear Regression

Random Forest

XGBoost / LightGBM

LSTM

기타 시계열 예측 모델

Backend

TBD

Python 기반 API framework 예정

SQLite

백엔드 및 API 구조는 모델 선정 이후 구체화할 예정입니다.

Frontend

React

JavaScript / TypeScript

TBD: Chart Library

프론트엔드에서는 금 가격 데이터와 예측 결과를 차트 형태로 시각화하는 것을 목표로 합니다.

Database

현재는 SQLite를 사용할 예정입니다.

주요 저장 데이터 예시:

과거 금 가격 데이터

전처리된 데이터

모델 예측 결과

모델 관련 메타데이터

프로젝트 규모와 배포 환경에 따라 추후 다른 데이터베이스로 변경될 수 있습니다.

Dataset

현재 Kaggle
에서 금 가격 관련 데이터를 수집하고 있습니다.

데이터셋에 따라 다음과 같은 정보를 활용할 수 있습니다.

Date

Open

High

Low

Close

Volume

기타 시장 관련 지표

실제 사용 데이터와 Feature는 데이터 탐색 및 전처리 과정에서 결정할 예정입니다.

Dataset License

사용하는 Kaggle 데이터셋의 라이선스 및 이용 조건을 확인한 후 기록할 예정입니다.

Prediction

최종적으로 다음과 같은 형태의 서비스를 만드는 것을 목표로 합니다.

과거 금 가격 데이터
        ↓
     ML Model
        ↓
   미래 금 가격 예측
        ↓
   API를 통한 제공
        ↓
   React Dashboard


웹 화면에서는 예를 들어 다음과 같은 정보를 제공할 예정입니다.

금 가격 차트

과거 가격 추이

예측 가격

실제 가격과 예측 가격 비교

모델 성능 지표

예측 결과 업데이트

Project Structure

초기에는 다음과 같은 구조를 고려하고 있습니다.

gold-price-forecast/
├── data/
│   ├── raw/
│   └── processed/
│
├── notebooks/
│   └── exploration.ipynb
│
├── src/
│   ├── data/
│   ├── features/
│   ├── models/
│   └── evaluation/
│
├── backend/
│   └── ...
│
├── frontend/
│   └── ...
│
├── database/
│   └── ...
│
├── tests/
│
├── requirements.txt
├── README.md
└── .gitignore


실제 구조는 프로젝트 진행 과정에서 변경될 수 있습니다.

Model Evaluation

단순히 예측값을 만드는 것뿐만 아니라 실제 가격과 비교하여 모델의 성능을 평가할 예정입니다.

고려 중인 평가 지표:

MAE

RMSE

MAPE

R²

최종적으로 데이터 특성과 예측 목적에 적합한 평가 방법을 선정할 예정입니다.

Development Plan
Phase 1 — Data Collection

Kaggle 데이터 수집

데이터 구조 확인

결측치 및 이상치 확인

데이터 정제

데이터베이스 저장 방식 결정

Phase 2 — Model Training

데이터 분석

Feature Engineering

Baseline 모델 구현

여러 모델 실험

모델 성능 비교

최종 모델 선정

Phase 3 — Backend

예측 모델 저장

Prediction API 구현

SQLite 연동

예측 결과 저장 및 조회

Phase 4 — Frontend

React를 사용하여 금 가격 및 예측 결과를 확인할 수 있는 Dashboard를 구현합니다.

예정 기능:

금 가격 그래프

미래 가격 예측

실제 가격 / 예측 가격 비교

모델 성능 확인

데이터 조회

Phase 5 — Integration
React
  ↕
Prediction API
  ↕
ML Model
  ↕
SQLite


프론트엔드와 백엔드를 연결하고 전체 서비스를 통합합니다.

Disclaimer

본 프로젝트의 예측 결과는 머신러닝 모델에 기반한 실험적 예측값이며 실제 금 가격의 미래 움직임을 보장하지 않습니다.

본 프로젝트는 머신러닝 및 시계열 데이터 분석을 학습하고 실험하기 위한 목적으로 제작되었습니다.

License

TBD
