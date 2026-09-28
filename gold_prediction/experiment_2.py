import numpy as np
from sklearn.metrics import accuracy_score
from experiment_common import load, make_model, split_data


df, features = load()
horizon = 5
threshold = 0.01

df["target_date"] = df["date"].shift(-horizon)
df["future_close"] = (
    df["close_usd_per_troy_oz"].shift(-horizon)
)
df = df.dropna(
    subset=["target_date", "future_close"]
).copy()

change = (
    df["future_close"] / df["close_usd_per_troy_oz"] - 1
)

df["direction"] = np.select(
    [
        change <= -threshold,
        change >= threshold,
    ],
    [-1, 1],
    default=0,
)

_, _, final_train, test = split_data(df)

model = make_model()
model.fit(final_train[features], final_train["direction"])
prediction = model.predict(test[features])

majority = final_train["direction"].mode().iloc[0]

print("-1: 1% 이상 하락 / 0: ±1% 안쪽 / 1: 1% 이상 상승")
print(
    f"전체 {len(test)}건 / "
    f"모델 {accuracy_score(test['direction'], prediction):.2%} / "
    f"단순 기준 "
    f"{accuracy_score(test['direction'], [majority] * len(test)):.2%}"
)
print(
    "시험 기간 실제 정답 개수:",
    test["direction"].value_counts().sort_index().to_dict()
)