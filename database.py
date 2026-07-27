# database.py
# MySQL connection setup using SQLAlchemy

import os
import tempfile
from urllib.parse import quote_plus
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Safety net: agar koi is file ko app.py se pehle import kar le, tab bhi
# .env yahin se load ho jaayegi. load_dotenv() dobara call karna harmless hai.
load_dotenv()

# .env se MySQL credentials read honge
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "resume_matcher")

# Aiven (aur zyadatar managed cloud MySQL) SSL/TLS require karte hain.
# DB_SSL_CA env var me poora CA certificate (.pem file ka pura content) paste karo.
DB_SSL_CA = os.getenv("DB_SSL_CA", "")

# quote_plus zaroori hai agar password me @, #, %, : jaise special characters hon,
# warna URL string galat parse hoti hai aur connection fail ho jaata hai
DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{quote_plus(DB_PASSWORD)}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

connect_args = {}
if DB_SSL_CA:
    # Certificate content ko temp file me likhna padta hai kyunki pymysql
    # ek file PATH expect karta hai, seedha string content nahi.
    ca_file = os.path.join(tempfile.gettempdir(), "aiven_ca.pem")
    with open(ca_file, "w") as f:
        f.write(DB_SSL_CA)
    connect_args = {"ssl": {"ca": ca_file}}
    print("[DB] SSL CA certificate configured.")

print(f"[DB] Connecting as user='{DB_USER}' host='{DB_HOST}' db='{DB_NAME}' "
      f"(password set: {bool(DB_PASSWORD)}, ssl: {bool(DB_SSL_CA)})")

# pool_pre_ping=True taaki dead connections apne aap refresh ho jaayein
engine = create_engine(DATABASE_URL, pool_pre_ping=True, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency: har request ke liye ek DB session deta hai"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()