from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

path = "mysql+pymysql://root:2480@localhost/project_2"

engine = create_engine(path)

Session = sessionmaker(bind=engine)

db_session = Session()

Base = declarative_base()