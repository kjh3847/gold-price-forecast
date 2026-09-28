import pandas as pd
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression


def load():
    df = pd.read_csv(
        "./data/02_gold_next_trading_day_labels.csv",
        parse_dates=["date"]
    )
    df = df.sort_values("date")
    df = df[df["date"] >= "2016-01-01"].copy()
    df = df.reset_index(drop=True)

    price = df["close_usd_per_troy_oz"]
    for n in [1, 3, 5, 10, 20]:
        df[f"gold_{n}d"] = price.pct_change(n, fill_method=None)
    df["vol_5d"] = df["gold_1d"].rolling(5).std()

    sources = [
        ("DTWEXBGS달라.csv", "DTWEXBGS", "dollar", "pct"),
        ("DFII10실질금리.csv", "DFII10", "rate", "diff"),
        ("SP500.csv", "SP500", "stock", "pct"),
        ("DCOILWTICO원유.csv", "DCOILWTICO", "oil", "pct"),
    ]

    for filename, value, prefix, kind in sources:
        external = pd.read_csv(
            "./data/" + filename,
            parse_dates=["observation_date"]
        )
        external[value] = pd.to_numeric(
            external[value], errors="coerce"
        )
        external = external.dropna(subset=[value])
        external = external.sort_values("observation_date").copy()

        if kind == "pct":
            external[prefix] = external[value].pct_change(
                fill_method=None
            )
        else:
            external[prefix] = external[value].diff()

        date_column = prefix + "_date"
        external = external.rename(
            columns={"observation_date": date_column}
        )

        df = pd.merge_asof(
            df.sort_values("date"),
            external[[date_column, prefix]],
            left_on="date",
            right_on=date_column,
            direction="backward",
            tolerance=pd.Timedelta(days=7),
            allow_exact_matches=False,
        )

    features = [
        "gold_1d", "gold_3d", "gold_5d",
        "gold_10d", "gold_20d", "vol_5d",
        "dollar", "rate", "stock", "oil",
    ]

    return df.dropna(subset=features).reset_index(drop=True), features


def make_model():
    return make_pipeline(
        StandardScaler(),
        LogisticRegression(max_iter=1000)
    )


def split_data(df):
    train = df[df["target_date"] < "2022-01-01"]
    validation = df[
        (df["date"] >= "2022-01-01")
        & (df["target_date"] < "2024-01-01")
    ]
    final_train = df[df["target_date"] < "2024-01-01"]
    test = df[df["date"] >= "2024-01-01"]

    if min(
        len(train), len(validation), len(final_train), len(test)
    ) == 0:
        raise ValueError("학습·검증·시험 자료 중 빈 구간이 있습니다.")

    return train, validation, final_train, test