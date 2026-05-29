import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = "openai/gpt-oss-120b"  # llama-3.3-70b-versatile or openai/gpt-oss-120b or qwen/qwen3-32b
MAX_ATTEMPTS = 5
MAX_PLANNER_ATTEMPTS = 3
CANVAS_W = 1200
CANVAS_H = 800


# OpenRouter settings (if used)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_VISION_MODEL = os.getenv(
    "OPENROUTER_VISION_MODEL",
    "nvidia/nemotron-nano-12b-v2-vl:free",
)

# Gemini settings (directgenerate_speechVISION_PROVIDER)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Vision model
VISION_MODEL = os.getenv("VISION_MODEL", "gemini-1.5-flash")


# Speech model
SPEECH_MODEL = os.getenv("SPEECH_MODEL", "gemini-3.1-flash-tts-preview")
