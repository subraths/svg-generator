from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.lesson_models import GenerateLessonRequest
from src.lesson_pipeline import generate_lesson

BASE_DIR = Path("data/lessons")
STATIC_DIR = Path("web")

app = FastAPI(title="AI Tutor SVG Lesson API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    index_path = STATIC_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(index_path)


@app.post("/lesson/generate")
def create_lesson(req: GenerateLessonRequest):
    bundle = generate_lesson(req.topic, difficulty=req.difficulty, use_llm=req.use_llm)
    return {
        "lesson_id": bundle.lesson_id,
        "lesson": bundle.lesson.model_dump(by_alias=True),
        "svg_url": f"/diagram/{bundle.lesson_id}.svg",
        "audio_base_url": f"/audio/{bundle.lesson_id}",
    }


@app.get("/lesson/{lesson_id}")
def get_lesson(lesson_id: str):
    lesson_file = BASE_DIR / lesson_id / "lesson.json"
    if not lesson_file.exists():
        raise HTTPException(status_code=404, detail="Lesson not found")
    payload = json.loads(lesson_file.read_text(encoding="utf-8"))
    payload["svg_url"] = f"/diagram/{lesson_id}.svg"
    payload["audio_base_url"] = f"/audio/{lesson_id}"
    return payload


@app.get("/diagram/{lesson_id}.svg")
def get_diagram(lesson_id: str):
    svg_path = BASE_DIR / lesson_id / "diagram.svg"
    if not svg_path.exists():
        raise HTTPException(status_code=404, detail="SVG not found")
    return FileResponse(svg_path, media_type="image/svg+xml")


@app.get("/audio/{lesson_id}/{segment}")
def get_audio_segment(lesson_id: str, segment: str):
    audio_path = BASE_DIR / lesson_id / "audio" / segment
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio segment not found")
    return FileResponse(audio_path, media_type="audio/wav")
