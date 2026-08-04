from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

DATABASE_URL = (
    "postgresql+psycopg2://lms_383r_user:V2uGtsh9WtpZhU4yNxqeXtNs29n4chN7"
    "@dpg-d9m8pd7qj5pc73abfbrg-a.oregon-postgres.render.com:5432/lms_383r"
)

# DATABASE_URL = "mysql+pymysql://root:2480@localhost:3306/mywork"

engine = create_engine(DATABASE_URL)

Session = sessionmaker(bind=engine)

db_session = Session()

Base = declarative_base()