from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base


DATABASE_URL = (
    "postgresql+psycopg2://lms_n7z0_user:ZvgsQkya3MHJyFUmuBfixzPz3o1Ro8Vg"
    "@dpg-d9u19dijobas73e23mpg-a.oregon-postgres.render.com:5432/lms_n7z0"
)

engine = create_engine(DATABASE_URL)

Session = sessionmaker(bind=engine)

db_session = Session()

Base = declarative_base()