# app.py
import os
import json
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from pydantic import BaseModel
from pypdf import PdfReader
from docx import Document

load_dotenv()
my_api_key = os.getenv("GROQ_API_KEY")
if not my_api_key:
    raise ValueError("GROQ_API_KEY Missing!")

client = Groq(api_key=my_api_key)
model = "openai/gpt-oss-120b"

app = FastAPI()

# Frontend se connect karne ke liye CORS allow karein
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper functions for PDF/DOCX
def extract_text_from_file(file: UploadFile) -> str:
    text = ""
    if file.filename.endswith(".pdf"):
        reader = PdfReader(file.file)
        for page in reader.pages:
            t = page.extract_text()
            if t: text += t + "\n"
    elif file.filename.endswith(".docx"):
        doc = Document(file.file)
        for p in doc.paragraphs:
            if p.text.strip(): text += p.text + "\n"
    return text

@app.post("/analyze")
async def analyze_resumes(
    job_description: str = Form(...),
    resumes: list[UploadFile] = File(...)
):
    try:
        results = []
        for file in resumes:
            resume_text = extract_text_from_file(file)
            
            # Simple AI prompt for matching
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
                response_format={"type": "json_object"}
            )
            
            data = json.loads(response.choices[0].message.content)
            results.append(data)

        # High score waale candidates pehle dikhane ke liye
        results.sort(key=lambda x: x.get("match_score", 0), reverse=True)
        return {"status": "success", "data": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))