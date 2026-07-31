
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = (
    "postgresql+psycopg2://lms_hqze_user:6pQyAYaNDW8rnYR5L44uv9XToQDWotpH"
    "@dpg-d9m65fe7bikc73a5phm0-a.oregon-postgres.render.com:5432/lms_hqze"
)

engine = create_engine(DATABASE_URL)

Session = sessionmaker(bind=engine)

db_session = Session()

Base = declarative_base()