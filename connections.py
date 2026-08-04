from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = (
    "postgresql+psycopg2://lms_397f_user:1zY0vMRHTsNR9Th2zBBfBrtfMTk7GCCb"
    "@dpg-d9ordtrncjis73egne70-a.oregon-postgres.render.com:5432/lms_397f"
)

engine = create_engine(DATABASE_URL)

Session = sessionmaker(bind=engine)

db_session = Session()

Base = declarative_base()