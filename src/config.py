import os
try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional in minimal test environments
    def load_dotenv():
        return None


load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = "openai/gpt-oss-120b"  # llama-3.3-70b-versatile or openai/gpt-oss-120b or qwen/qwen3-32b
MAX_ATTEMPTS = 5
MAX_PLANNER_ATTEMPTS = 3
MAX_AGENTIC_ITERS = 5
CANVAS_W = 1200
CANVAS_H = 800

# Vision provider: "openrouter" or "gemini"
VISION_PROVIDER = os.getenv("VISION_PROVIDER", "gemini")

# OpenRouter settings (if used)
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_VISION_MODEL = os.getenv(
    "OPENROUTER_VISION_MODEL",
    "nvidia/nemotron-nano-12b-v2-vl:free",
)

# Gemini settings (direct)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_VISION_MODEL = os.getenv("GEMINI_VISION_MODEL", "gemini-1.5-flash")
GEMINI_TTS_MODEL = os.getenv("GEMINI_TTS_MODEL", "gemini-2.5-flash-preview-tts")
GEMINI_TTS_VOICE = os.getenv("GEMINI_TTS_VOICE", "Kore")
