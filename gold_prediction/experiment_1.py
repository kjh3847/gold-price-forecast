from experiment_common import load, make_model, split_data
from sklearn.metrics import accuracy_score


df, features = load()

for horizon in [1, 5, 20]:
    data = df.copy()

    data["target_date"] = data["date"].shift(-horizon)
    data["future_close"] = (
        data["close_usd_per_troy_oz"].shift(-horizon)
    )
    data = data.dropna(
        subset=["target_date", "future_close"]
    ).copy()

    data = data[
        data["close_usd_per_troy_oz"] != data["future_close"]
    ].copy()
    data["up"] = (
        data["future_close"] > data["close_usd_per_troy_oz"]
    ).astype(int)

    _, _, final_train, test = split_data(data)

    model = make_model()
    model.fit(final_train[features], final_train["up"])
    prediction = model.predict(test[features])

    model_accuracy = accuracy_score(test["up"], prediction)

    baseline = int(final_train["up"].mean() >= 0.5)
    baseline_accuracy = accuracy_score(
        test["up"], [baseline] * len(test)
    )

    print(
        f"{horizon}거래일 뒤 / 시험 {len(test)}건 / "
        f"모델 {model_accuracy:.2%} / "
        f"단순 기준 {baseline_accuracy:.2%}"
    )