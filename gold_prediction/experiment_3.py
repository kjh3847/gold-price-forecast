from sklearn.metrics import accuracy_score
from experiment_common import load, make_model, split_data


df, features = load()
horizon = 1

df["target_date"] = df["date"].shift(-horizon)
df["future_close"] = (
    df["close_usd_per_troy_oz"].shift(-horizon)
)
df = df.dropna(
    subset=["target_date", "future_close"]
).copy()
df = df[
    df["close_usd_per_troy_oz"] != df["future_close"]
].copy()
df["up"] = (
    df["future_close"] > df["close_usd_per_troy_oz"]
).astype(int)

train, validation, final_train, test = split_data(df)

model = make_model()
model.fit(train[features], train["up"])
validation_probability = model.predict_proba(
    validation[features]
)[:, 1]

options = []

for threshold in [0.55, 0.60, 0.65, 0.70]:
    chosen = (
        (validation_probability >= threshold)
        | (validation_probability <= 1 - threshold)
    )

    # 검증 날짜 중 적어도 10%는 예측해야 후보로 인정
    if chosen.sum() >= max(1, int(0.10 * len(validation))):
        accuracy = accuracy_score(
            validation["up"][chosen],
            (validation_probability[chosen] >= 0.5).astype(int),
        )
        options.append(
            (accuracy, chosen.mean(), threshold)
        )

if not options:
    print("검증 기간에 10% 이상 예측할 수 있는 기준이 없습니다.")
else:
    validation_accuracy, coverage, threshold = max(
        options,
        key=lambda item: (item[0], item[1])
    )

    print(
        f"검증에서 선택한 기준: {threshold:.0%} / "
        f"정답률 {validation_accuracy:.2%} / "
        f"예측한 날짜 {coverage:.2%}"
    )

    model = make_model()
    model.fit(final_train[features], final_train["up"])
    probability = model.predict_proba(test[features])[:, 1]

    chosen = (
        (probability >= threshold)
        | (probability <= 1 - threshold)
    )

    if chosen.sum() == 0:
        print(f"시험 {len(test)}일 중 예측한 날이 없습니다.")
    else:
        accuracy = accuracy_score(
            test["up"][chosen],
            (probability[chosen] >= 0.5).astype(int),
        )
        print(
            f"시험 {len(test)}일 중 {chosen.sum()}일 예측 "
            f"({chosen.mean():.2%}) / "
            f"예측한 날의 정답률 {accuracy:.2%}"
        )