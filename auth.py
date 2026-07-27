# auth.py
# Password hashing + JWT token banana/verify karna

import os
import bcrypt
from datetime import datetime, timedelta, timezone
from jose import jwt, JWTError
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from database import get_db
import models

SECRET_KEY = os.getenv("SECRET_KEY", "please-change-this-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 din tak login yaad rahega

# auto_error=False -> agar token nahi bheja to error nahi, None milega
# isse app WITHOUT login bhi kaam karta rahega (cross/close button waala flow)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login", auto_error=False)


def hash_password(password: str) -> str:
    # bcrypt sirf 72 bytes tak hi support karta hai, isliye safety ke liye truncate
    pwd_bytes = password.encode("utf-8")[:72]
    hashed = bcrypt.hashpw(pwd_bytes, bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pwd_bytes = plain_password.encode("utf-8")[:72]
    return bcrypt.checkpw(pwd_bytes, hashed_password.encode("utf-8"))


def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """REQUIRED auth - agar token invalid/missing hai to 401 error"""
    if not token:
        raise HTTPException(status_code=401, detail="Login required")
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.query(models.User).filter(models.User.id == payload.get("user_id")).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def get_optional_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    """OPTIONAL auth - login na ho to bhi None return karega, error nahi dega.
    Isi wajah se cross (X) dabakar app bina login use ho sakta hai."""
    if not token:
        return None
    payload = decode_token(token)
    if not payload:
        return None
    return db.query(models.User).filter(models.User.id == payload.get("user_id")).first()