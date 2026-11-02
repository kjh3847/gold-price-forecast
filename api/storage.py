from sqlalchemy.orm import Session
from gold_service import db
from gold_service.config import Settings


def get_session():
    engine = db.make_engine(Settings.from_env().database_url)
    db.init_db(engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()
