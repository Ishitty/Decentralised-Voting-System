# backend/models.py
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.dialects.mysql import LONGBLOB
import urllib.parse

# ---------------------------------------------------------
#   DATABASE CONFIG
# ---------------------------------------------------------
MYSQL_USER = "root"
# MYSQL_PASSWORD = "myishusql1924"
MYSQL_PASSWORD = "myishusql1924"
MYSQL_HOST = "127.0.0.1"
MYSQL_PORT = "3306"
MYSQL_DB = "decentralised_voting"

encoded_pass = urllib.parse.quote_plus(MYSQL_PASSWORD)

DATABASE_URL = (
    f"mysql+pymysql://{MYSQL_USER}:{encoded_pass}@"
    f"{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DB}"
)

# ---------------------------------------------------------
#   ENGINE + BASE
# ---------------------------------------------------------
engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()

# ---------------------------------------------------------
#   MODELS
# ---------------------------------------------------------
class Admin(Base):
    __tablename__ = "admin"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(100), unique=True, nullable=False)
    password_hash = Column(String(300), nullable=False)

    # Face embedding (128 floats ≈ 512 bytes, but we keep LONGBLOB for future)
    face_encoding = Column(LONGBLOB, nullable=False)


class Voter(Base):
    __tablename__ = "voters"

    id = Column(Integer, primary_key=True, autoincrement=True)
    enrollment = Column(String(50), unique=True, nullable=False)
    name = Column(String(100), nullable=False)

    # Face embedding
    face_encoding = Column(LONGBLOB, nullable=False)


# ---------------------------------------------------------
#   CREATE TABLES IF NOT EXISTS
# ---------------------------------------------------------
Base.metadata.create_all(engine)

# ---------------------------------------------------------
#   SESSION FACTORY
# ---------------------------------------------------------
SessionLocal = sessionmaker(bind=engine)

print("✅ Database connected & models ready")
