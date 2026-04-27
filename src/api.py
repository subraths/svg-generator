from __future__ import annotations

import json
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from src.lesson_models import GenerateLessonRequest
from src.lesson_pipeline import generate_lesson
from src.lesson_pipeline import AUDIO_SEGMENT_RE

BASE_DIR = Path("data/lessons")
FRONTEND_DIST_DIR = Path("frontend/dist")
LEGACY_STATIC_DIR = Path("web")
LESSON_ID_RE = re.compile(r"^[a-z0-9_-]+$")
LESSON_DIR_CACHE: dict[str, Path] = {}

app = FastAPI(title="AI Tutor SVG Lesson API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_DIST_DIR.exists() and (FRONTEND_DIST_DIR / "assets").exists():
    app.mount(
        "/assets",
        StaticFiles(directory=str(FRONTEND_DIST_DIR / "assets")),
        name="assets",
    )
elif LEGACY_STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(LEGACY_STATIC_DIR)), name="static")


def _safe_lesson_dir(lesson_id: str) -> Path:
    if not LESSON_ID_RE.fullmatch(lesson_id):
        raise HTTPException(status_code=400, detail="Invalid lesson id format")
    cached = LESSON_DIR_CACHE.get(lesson_id)
    if cached and (cached / "lesson.json").exists():
        return cached

    if BASE_DIR.exists():
        for lesson_json in BASE_DIR.glob("*/lesson.json"):
            LESSON_DIR_CACHE[lesson_json.parent.name] = lesson_json.parent.resolve()

    resolved = LESSON_DIR_CACHE.get(lesson_id)
    if resolved and (resolved / "lesson.json").exists():
        return resolved
    raise HTTPException(status_code=404, detail="Lesson not found")


def _load_lesson_payload(lesson_dir: Path) -> dict:
    lesson_file = lesson_dir / "lesson.json"
    if not lesson_file.exists():
        raise HTTPException(status_code=404, detail="Lesson not found")
    return json.loads(lesson_file.read_text(encoding="utf-8"))


@app.get("/")
def index():
    index_path = (
        FRONTEND_DIST_DIR / "index.html"
        if (FRONTEND_DIST_DIR / "index.html").exists()
        else LEGACY_STATIC_DIR / "index.html"
    )
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend not found")
    return FileResponse(index_path)


@app.post("/lesson/generate")
def create_lesson(req: GenerateLessonRequest):
    bundle = generate_lesson(req.topic, difficulty=req.difficulty, use_llm=req.use_llm)
    LESSON_DIR_CACHE[bundle.lesson_id] = Path(bundle.svg_path).resolve().parent
    return {
        "lesson_id": bundle.lesson_id,
        "lesson": bundle.lesson.model_dump(by_alias=True),
        "svg_url": f"/diagram/{bundle.lesson_id}.svg",
        "audio_base_url": f"/audio/{bundle.lesson_id}",
    }


@app.get("/lesson/{lesson_id}")
def get_lesson(lesson_id: str):
    lesson_dir = _safe_lesson_dir(lesson_id)
    payload = _load_lesson_payload(lesson_dir)
    payload["svg_url"] = f"/diagram/{lesson_id}.svg"
    payload["audio_base_url"] = f"/audio/{lesson_id}"
    return payload


@app.get("/diagram/{lesson_id}.svg")
def get_diagram(lesson_id: str):
    lesson_dir = _safe_lesson_dir(lesson_id)
    svg_path = lesson_dir / "diagram.svg"
    if not svg_path.exists():
        raise HTTPException(status_code=404, detail="SVG not found")
    return FileResponse(svg_path, media_type="image/svg+xml")


@app.get("/audio/{lesson_id}/{segment}")
def get_audio_segment(lesson_id: str, segment: str):
    if not AUDIO_SEGMENT_RE.fullmatch(segment):
        raise HTTPException(status_code=400, detail="Invalid segment format")
    lesson_dir = _safe_lesson_dir(lesson_id)
    payload = _load_lesson_payload(lesson_dir)
    sync_map = payload.get("lesson", {}).get("sync_map", [])
    allowed_segments = {seg.get("audio_chunk") for seg in sync_map if isinstance(seg, dict)}
    if segment not in allowed_segments:
        raise HTTPException(status_code=404, detail="Audio segment not found")
    audio_path = (lesson_dir / "audio" / segment).resolve()
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio segment not found")
    return FileResponse(audio_path, media_type="audio/wav")
