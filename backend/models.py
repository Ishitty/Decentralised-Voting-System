import os

from sqlalchemy import Column, Integer, LargeBinary, String, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


# ---------------------------------------------------------
# DATABASE CONFIG
# ---------------------------------------------------------
DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL environment variable is missing. "
        "Example: mysql+pymysql://user:password@host:3306/database"
    )


# Some hosting services provide mysql:// instead of mysql+pymysql://
if DATABASE_URL.startswith("mysql://"):
    DATABASE_URL = DATABASE_URL.replace(
        "mysql://",
        "mysql+pymysql://",
        1,
    )


# ---------------------------------------------------------
# ENGINE + BASE
# ---------------------------------------------------------
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=280,
)

Base = declarative_base()


# ---------------------------------------------------------
# MODELS
# ---------------------------------------------------------
class Admin(Base):
    __tablename__ = "admin"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(300), nullable=False)
    face_encoding = Column(LargeBinary, nullable=False)


class Voter(Base):
    __tablename__ = "voters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    enrollment = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)
    face_encoding = Column(LargeBinary, nullable=False)


# ---------------------------------------------------------
# CREATE TABLES
# ---------------------------------------------------------
Base.metadata.create_all(bind=engine)


# ---------------------------------------------------------
# SESSION FACTORY
# ---------------------------------------------------------
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)

print("Database connected and models ready")