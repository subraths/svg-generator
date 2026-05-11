from src.groq_pool import GroqClientPool
from src.planner import generate_layout_plan
from src.agentic_loop import generate_with_agentic_feedback

TOPIC = "Photosynthesis"

pool = GroqClientPool.from_env()
plan = generate_layout_plan(pool, TOPIC, min_nodes=6)

svg_text, report = generate_with_agentic_feedback(
    pool=pool,
    topic=TOPIC,
    plan=plan,
    max_iters=3,
    out_base="agentic_demo",
)

print("Done. Final SVG saved.")
