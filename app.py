# app.py
import os
import json
from dotenv import load_dotenv

# IMPORTANT: .env file sabse pehle load honi chahiye, kisi bhi local module
# (database, models, auth) import hone se pehle. Warna wo modules os.getenv()
# call karte waqt khaali/empty values utha lete hain (jaise DB_PASSWORD="").
load_dotenv()

from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from groq import Groq
from pypdf import PdfReader
from docx import Document
from sqlalchemy.orm import Session

from database import engine, get_db, Base
import models
import schemas
from auth import (
    hash_password,
    verify_password,
    create_access_token,
    get_current_user,
    get_optional_user,
)

my_api_key = os.getenv("GROQ_API_KEY")
if not my_api_key:
    # Crash na karke sirf warning print karte hain, taaki poora app na gir jaye
    # sirf kyunki ek env var missing hai — Render logs mein clearly dikhega.
    print("[WARNING] GROQ_API_KEY environment variable set nahi hai! "
          "/analyze route fail hoga jab tak Render dashboard me isse set na karein.")

client = Groq(api_key=my_api_key) if my_api_key else None
model = "openai/gpt-oss-120b"

# Tables agar exist nahi karti to bana degi (MySQL database pehle se bani honi chahiye).
# Agar DB unreachable hai (galat DB_HOST, ya database public access allow nahi karta),
# to app crash nahi karega — sirf error log hoga aur DB-related routes fail honge.
try:
    Base.metadata.create_all(bind=engine)
    print("[DB] Tables ready.")
except Exception as e:
    print(f"[WARNING] Database se connect nahi ho paaya, DB features kaam nahi karenge: {e}")

app = FastAPI()

# Frontend se connect karne ke liye CORS allow karein
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------
# FRONTEND SERVE KARNA
# ---------------------------
FRONTEND_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")


@app.get("/")
def serve_frontend():
    """index.html ko root path par serve karta hai, taaki frontend + backend
    ek hi Render URL se chalein."""
    return FileResponse(FRONTEND_PATH)


# ---------------------------
# Helper functions for PDF/DOCX
# ---------------------------
def extract_text_from_file(file: UploadFile) -> str:
    text = ""
    if file.filename.endswith(".pdf"):
        reader = PdfReader(file.file)
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
    elif file.filename.endswith(".docx"):
        doc = Document(file.file)
        for p in doc.paragraphs:
            if p.text.strip():
                text += p.text + "\n"
    return text


# ---------------------------
# AUTH ROUTES
# ---------------------------
@app.post("/signup", response_model=schemas.TokenResponse)
def signup(data: schemas.SignupRequest, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.email == data.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered hai, login karein")

    new_user = models.User(
        name=data.name,
        email=data.email,
        hashed_password=hash_password(data.password),
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    token = create_access_token({"user_id": new_user.id})
    return schemas.TokenResponse(access_token=token, user=new_user)


@app.post("/login", response_model=schemas.TokenResponse)
def login(data: schemas.LoginRequest, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == data.email).first()
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Email ya password galat hai")

    token = create_access_token({"user_id": user.id})
    return schemas.TokenResponse(access_token=token, user=user)


@app.get("/me", response_model=schemas.UserResponse)
def get_me(current_user: models.User = Depends(get_current_user)):
    return current_user


@app.get("/history", response_model=list[schemas.HistoryItem])
def get_history(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Logged-in user ki work history (pehle ke resume analysis results)"""
    records = (
        db.query(models.AnalysisHistory)
        .filter(models.AnalysisHistory.user_id == current_user.id)
        .order_by(models.AnalysisHistory.created_at.desc())
        .all()
    )
    result = []
    for r in records:
        result.append(
            schemas.HistoryItem(
                id=r.id,
                candidate_name=r.candidate_name,
                match_score=r.match_score,
                matching_skills=json.loads(r.matching_skills or "[]"),
                missing_skills=json.loads(r.missing_skills or "[]"),
                verdict=r.verdict,
                created_at=r.created_at,
            )
        )
    return result


# ---------------------------
# RESUME ANALYSIS ROUTE
# ---------------------------
@app.post("/analyze")
async def analyze_resumes(
    job_description: str = Form(...),
    resumes: list[UploadFile] = File(...),
    current_user: models.User | None = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """
    Login zaroori nahi hai (cross button dabakar bhi use ho sakta hai).
    Agar user logged in hai to result uski history me MySQL me save ho jaayega.
    """
    try:
        if client is None:
            raise HTTPException(
                status_code=500,
                detail="GROQ_API_KEY set nahi hai. Render dashboard me Environment Variables me isse add karein.",
            )

        results = []
        for file in resumes:
            resume_text = extract_text_from_file(file)

            prompt = f"""
            Analyze this resume against the Job Description.
            JOB DESCRIPTION: {job_description}
            RESUME TEXT: {resume_text}

            Return JSON format:
            {{
                "candidate_name": "Name",
                "match_score": 85,
                "matching_skills": ["Python", "FastAPI"],
                "missing_skills": ["AWS"],
                "verdict": "Short summary of candidate suitability"
            }}
            """

            response = client.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"},
            )

            data = json.loads(response.choices[0].message.content)
            results.append(data)

            # Sirf logged-in users ke liye history save hogi
            if current_user:
                record = models.AnalysisHistory(
                    user_id=current_user.id,
                    job_description=job_description,
                    candidate_name=data.get("candidate_name"),
                    match_score=data.get("match_score"),
                    matching_skills=json.dumps(data.get("matching_skills", [])),
                    missing_skills=json.dumps(data.get("missing_skills", [])),
                    verdict=data.get("verdict"),
                )
                db.add(record)

        if current_user:
            db.commit()

        # High score waale candidates pehle dikhane ke liye
        results.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        return {"status": "success", "data": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))