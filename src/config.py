import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
MODEL_NAME = "openai/gpt-oss-120b"  # llama-3.3-70b-versatile or openai/gpt-oss-120b or qwen/qwen3-32b
MAX_ATTEMPTS = 5
MAX_PLANNER_ATTEMPTS = 3
CANVAS_W = 1200
CANVAS_H = 800
