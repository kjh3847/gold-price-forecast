"""AWS delivery of durable SQLite events. Retry: python -m gold_service.collection."""
import json
import logging
import os
from datetime import datetime

import boto3
from botocore.config import Config
from sqlalchemy import select
from sqlalchemy.orm import Session
from gold_service import db
from gold_service.config import Settings


def deliver(event):
    status = dict(event.delivery)
    region = os.getenv("AWS_REGION")
    bucket = os.getenv("COLLECTION_S3_BUCKET")
    group = os.getenv("COLLECTION_LOG_GROUP")
    stream = os.getenv("COLLECTION_LOG_STREAM")
    body = json.dumps(event.payload, ensure_ascii=False, allow_nan=False)
    config = Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 1})
    for destination, configured in (("s3", bucket and region), ("cloudwatch", group and stream and region)):
        if status.get(destination) == "sent":
            continue
        if not configured:
            status[destination] = "disabled"
            continue
        try:
            if destination == "s3":
                boto3.client("s3", region_name=region, config=config).put_object(
                    Bucket=bucket, Key=f"collection/{event.id}.json",
                    Body=body.encode("utf-8"), ContentType="application/json")
            else:
                result = boto3.client("logs", region_name=region, config=config).put_log_events(
                    logGroupName=group, logStreamName=stream,
                    logEvents=[{"timestamp": int(datetime.fromisoformat(event.payload["event_at"]).timestamp() * 1000), "message": body}])
                if result.get("rejectedLogEventsInfo"):
                    raise RuntimeError("CloudWatch rejected timestamp")
            status[destination] = "sent"
        except Exception:
            logging.getLogger(__name__).warning("Delivery failed: %s event=%s", destination, event.id)
            status[destination] = "failed"
    event.delivery = status
    return status


def main():
    engine = db.make_engine(Settings.from_env().database_url)
    db.init_db(engine)
    with Session(engine) as session:
        for event in session.scalars(select(db.CollectionEvent)):
            deliver(event)
            session.commit()
    engine.dispose()


if __name__ == "__main__":
    main()
