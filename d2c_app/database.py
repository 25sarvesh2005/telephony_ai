import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from d2c_app.config import d2c_settings

engine = create_engine(
    d2c_settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in d2c_settings.DATABASE_URL else {},
    echo=False,
)

D2CSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
D2CBase = declarative_base()


def get_d2c_db():
    db = D2CSessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_d2c_db():
    D2CBase.metadata.create_all(bind=engine)
