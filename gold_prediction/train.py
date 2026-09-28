import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss


def read_series(filename, value, date_name):
    data = pd.read_csv(
        f"./data/{filename}",
        parse_dates=["observation_date"]
    )
    data[value] = pd.to_numeric(data[value], errors="coerce")
    data = data.dropna(subset=[value])
    data = data.sort_values("observation_date").copy()
    return data.rename(columns={"observation_date": date_name})


def attach(gold, external, date_name, columns):
    return pd.merge_asof(
        gold.sort_values("date"),
        external[[date_name] + columns].sort_values(date_name),
        left_on="date",
        right_on=date_name,
        direction="backward",
        tolerance=pd.Timedelta(days=7),
        allow_exact_matches=False,
    )


def fit_score(train, test, features):
    model = make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000)
    )
    model.fit(train[features], train["next_day_up"])

    probability = model.predict_proba(test[features])[:, 1]
    accuracy = accuracy_score(
        test["next_day_up"], probability >= 0.5
    )
    brier = brier_score_loss(test["next_day_up"], probability)
    return accuracy, brier


# 1. 파일 읽기
gold = pd.read_csv(
    "./data/02_gold_next_trading_day_labels.csv",
    parse_dates=["date", "next_trading_date"]
)
gold = gold.sort_values("date")
gold = gold[gold["date"] >= "2016-01-01"].copy()

dollar = read_series("DTWEXBGS달라.csv", "DTWEXBGS", "dollar_date")
rate = read_series("DFII10실질금리.csv", "DFII10", "rate_date")
stock = read_series("SP500.csv", "SP500", "stock_date")
oil = read_series("DCOILWTICO원유.csv", "DCOILWTICO", "oil_date")
cpi = read_series("CPIAUCSL물가.csv", "CPIAUCSL", "cpi_month")

# 2. 다른 시장 자료의 1·5·10일 변화 만들기
for data, value, prefix in [
    (dollar, "DTWEXBGS", "dollar"),
    (stock, "SP500", "stock"),
    (oil, "DCOILWTICO", "oil"),
]:
    for days in [1, 5, 10]:
        data[f"{prefix}_{days}d"] = data[value].pct_change(
            days, fill_method=None
        )

for days in [1, 5, 10]:
    rate[f"rate_{days}d"] = rate["DFII10"].diff(days)

cpi["cpi_1m"] = cpi["CPIAUCSL"].pct_change(fill_method=None)

# CPI는 대상 월의 날짜가 곧 발표일은 아니다.
# 여기서는 대상 월 시작일에서 두 달 후부터 사용한다고 가정한다.
cpi["available_date"] = (
    cpi["cpi_month"] + pd.DateOffset(months=2)
)

# 3. 금 날짜보다 이전에 관측된 자료 연결
gold = attach(
    gold, dollar, "dollar_date",
    [f"dollar_{days}d" for days in [1, 5, 10]]
)
gold = attach(
    gold, rate, "rate_date",
    [f"rate_{days}d" for days in [1, 5, 10]]
)
gold = attach(
    gold, stock, "stock_date",
    [f"stock_{days}d" for days in [1, 5, 10]]
)
gold = attach(
    gold, oil, "oil_date",
    [f"oil_{days}d" for days in [1, 5, 10]]
)

gold = pd.merge_asof(
    gold.sort_values("date"),
    cpi[["available_date", "cpi_1m"]].sort_values(
        "available_date"
    ),
    left_on="date",
    right_on="available_date",
    direction="backward",
    allow_exact_matches=False,
)

# 4. 금값에서 여러 기간의 흐름과 변동 폭 만들기
price = gold["close_usd_per_troy_oz"]

for days in [1, 3, 5, 10, 20]:
    gold[f"gold_{days}d"] = price.pct_change(
        days, fill_method=None
    )

for days in [5, 10, 20]:
    gold[f"vol_{days}d"] = (
        gold["gold_1d"].rolling(days).std()
    )

# 5. 비교할 입력 조합
feature_sets = {
    "기존": [
        "gold_1d", "gold_3d", "gold_5d",
        "dollar_1d", "rate_1d",
    ],
    "금 장기 흐름": [
        "gold_1d", "gold_3d", "gold_5d",
        "gold_10d", "gold_20d",
        "vol_5d", "vol_20d",
    ],
    "금+달러+금리 흐름": [
        "gold_1d", "gold_3d", "gold_5d",
        "gold_10d", "gold_20d", "vol_5d",
        "dollar_1d", "dollar_5d", "dollar_10d",
        "rate_1d", "rate_5d", "rate_10d",
    ],
    "전체 흐름": [
        "gold_1d", "gold_3d", "gold_5d",
        "gold_10d", "gold_20d",
        "vol_5d", "vol_20d",
        "dollar_1d", "dollar_5d", "dollar_10d",
        "rate_1d", "rate_5d", "rate_10d",
        "stock_1d", "stock_5d", "stock_10d",
        "oil_1d", "oil_5d", "oil_10d",
        "cpi_1m",
    ],
}

# 모든 조합을 같은 날짜에서 비교
all_features = sorted(
    set().union(*feature_sets.values())
)
gold = gold.dropna(
    subset=all_features + [
        "next_day_up", "next_close_usd_per_troy_oz"
    ]
)
gold = gold[
    gold["close_usd_per_troy_oz"]
    != gold["next_close_usd_per_troy_oz"]
].copy()

# 6. 2022년 전까지 학습, 2022~2023년에서 조합 선택
train = gold[gold["next_trading_date"] < "2022-01-01"]
validation = gold[
    (gold["date"] >= "2022-01-01")
    & (gold["next_trading_date"] < "2024-01-01")
]

# 선택 후 2024년 전까지 다시 학습하여 이후 기간 평가
final_train = gold[
    gold["next_trading_date"] < "2024-01-01"
]
test = gold[gold["date"] >= "2024-01-01"]

if min(len(train), len(validation), len(test)) == 0:
    raise ValueError(
        "학습·검증·시험 기간 중 데이터가 비었습니다."
    )

print(
    "학습:", len(train),
    "검증:", len(validation),
    "최종 시험:", len(test)
)
print("입력 조합별 2022~2023년 결과:")

results = {}

for name, features in feature_sets.items():
    accuracy, brier = fit_score(
        train, validation, features
    )
    results[name] = (accuracy, brier)
    print(
        f"{name}: 정답률 {accuracy:.2%}, "
        f"Brier 점수 {brier:.4f}"
    )

selected = max(
    results,
    key=lambda name: (
        results[name][0],
        -results[name][1]
    )
)
print("선택한 입력 조합:", selected)

# 7. 최종 시험
baseline_rate = final_train["next_day_up"].mean()
baseline_prediction = int(baseline_rate >= 0.5)
baseline_accuracy = accuracy_score(
    test["next_day_up"],
    [baseline_prediction] * len(test)
)
print(
    f"2024년 이후 단순 기준 정답률: "
    f"{baseline_accuracy:.2%}"
)

accuracy, brier = fit_score(
    final_train,
    test,
    feature_sets[selected]
)
print(
    f"2024년 이후 선택 모델: "
    f"정답률 {accuracy:.2%}, "
    f"Brier 점수 {brier:.4f}"
)