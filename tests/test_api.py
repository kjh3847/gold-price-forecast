import json
from datetime import date
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from api.health import app
from gold_service import db
from gold_service import collection


@pytest.fixture
def client(tmp_path, monkeypatch):
    url = f"sqlite:///{tmp_path / 'api.db'}"
    monkeypatch.setenv("DATABASE_URL", url)
    for key in ("AWS_REGION", "COLLECTION_S3_BUCKET", "COLLECTION_LOG_GROUP", "COLLECTION_LOG_STREAM"):
        monkeypatch.delenv(key, raising=False)
    engine = db.make_engine(url)
    db.init_db(engine)
    with Session(engine) as session:
        session.add(db.Price(date=date(2026, 9, 24), close=4000, source="test"))
        session.add(db.ForecastRow(date=date(2026, 9, 24), sigma=0.01, grade="LOW", percentile=20,
                                   is_fallback=False, band_low=3800, band_high=4200, z=1.645, z_is_default=True))
        session.commit()
    yield TestClient(app), engine
    engine.dispose()


def create(client):
    return client.post("/api/submissions", json={"forecast_date": "2026-09-24", "weekly_amount": 300000, "product": "금 현물"})


def test_end_to_end(client):
    api, engine = client
    assert api.get("/api/health").status_code == 200
    assert api.get("/api/forecast/latest").json()["date"] == "2026-09-24"
    assert api.get("/api/forecast/full").json()["price"] == 4000
    result = create(api)
    assert result.status_code == 201, result.text
    record = result.json()
    assert record["delivery"] == {"s3": "disabled", "cloudwatch": "disabled"}
    receipt = record["id"]
    assert record["forecast"]["target_date"] == "2026-10-01"
    assert api.get(f"/api/submissions/{receipt}").json()["actual"] is None
    for value, hit in ((4000, True), (4300, False), (3800, True), (1, False)):
        result = api.put(f"/api/submissions/{receipt}/actual", json={"kind": "price", "value": value, "observed_on": "2026-10-01"})
        assert result.status_code == 200, result.text
        assert result.json()["actual"]["within_band"] is hit
        assert result.json()["actual"]["value"] == value
    result = api.put(f"/api/submissions/{receipt}/actual", json={"kind": "boolean", "value": False, "observed_on": "2026-10-01"})
    assert result.json()["actual"]["within_band"] is False
    with Session(engine) as session:
        assert session.get(db.Submission, receipt).actual_at
        events = list(session.scalars(select(db.CollectionEvent)))
        assert len(events) == 6
        assert events[0].payload["actual"] is None  # immutable input event
        assert events[-1].payload["forecast"] == record["forecast"]


def test_validation(client):
    api, _ = client
    for amount in (0, -1, 1.5, True, 1000000001):
        assert api.post("/api/submissions", json={"forecast_date": "2026-09-24", "weekly_amount": amount, "product": "금 현물"}).status_code == 422
    assert api.post("/api/submissions", json={"forecast_date": "2026-09-23", "weekly_amount": 1, "product": "금 현물"}).status_code == 409
    receipt = create(api).json()["id"]
    for kind, value in (("boolean", "true"), ("price", True), ("price", -1), ("price", "NaN")):
        assert api.put(f"/api/submissions/{receipt}/actual", json={"kind": kind, "value": value, "observed_on": "2026-10-01"}).status_code == 422
    assert api.put(f"/api/submissions/{receipt}/actual", json={"kind": "price", "value": 4000, "observed_on": "2026-09-25"}).status_code == 422
    assert api.get("/api/submissions/00000000-0000-0000-0000-000000000000").status_code == 404
    assert api.get("/api/submissions/bad").status_code == 422


def test_empty_forecast(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'empty.db'}")
    api = TestClient(app)
    assert api.get("/api/forecast/latest").status_code == 404
    assert api.get("/api/forecast/full").status_code == 404
    assert create(api).status_code == 404


def test_aws_delivery_and_retry(client, monkeypatch):
    api, engine = client
    for key, value in {"AWS_REGION": "ap-northeast-2", "COLLECTION_S3_BUCKET": "test-bucket", "COLLECTION_LOG_GROUP": "gold", "COLLECTION_LOG_STREAM": "inputs"}.items():
        monkeypatch.setenv(key, value)
    s3, logs = Mock(), Mock()
    logs.put_log_events.return_value = {}
    s3.put_object.side_effect = RuntimeError("offline")
    monkeypatch.setattr(collection.boto3, "client", lambda service, **kwargs: s3 if service == "s3" else logs)
    result = create(api)
    assert result.status_code == 201
    assert result.json()["delivery"] == {"s3": "failed", "cloudwatch": "sent"}
    with Session(engine) as session:
        event = session.scalar(select(db.CollectionEvent))
        assert json.loads(logs.put_log_events.call_args.kwargs["logEvents"][0]["message"])["id"] == result.json()["id"]
        s3.put_object.side_effect = None
        assert collection.deliver(event) == {"s3": "sent", "cloudwatch": "sent"}
        assert logs.put_log_events.call_count == 1
        assert json.loads(s3.put_object.call_args.kwargs["Body"])["user_input"]["weekly_amount"] == 300000
    receipt = result.json()["id"]
    assert api.put(f"/api/submissions/{receipt}/actual", json={"kind": "boolean", "value": True, "observed_on": "2026-10-01"}).status_code == 200
    assert json.loads(s3.put_object.call_args.kwargs["Body"])["actual"]["within_band"] is True
