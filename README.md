## SVG Generator (Agentic)

This project generates SVG diagrams from a topic using an LLM planner + generator + validation/repair loop.

### Setup

- Python via `uv`
- Create a `.env` file with required keys

Example:

```bash
OPENROUTER_API_KEY=...
GROQ_API_KEY=...
# (Optional) Gemini (used by explanation/speech features on newer branches)
GEMINI_API_KEY=...

# Vision QA resilience (optional)
VISION_FAIL_OPEN=true
VISION_RETRIES=3
VISION_REQUEST_TIMEOUT_S=60
VISION_RETRY_BACKOFF_S=2
```

### Run

```bash
uv sync
uv run python -m src.main
```

### Outputs

- `reports/*.json` plan + reports
- `svg/*.svg` generated SVG iterations
- `img/*.png` rendered PNGs for visual QA

### Note on vision feedback stability

The visual QA step calls an external vision provider via OpenRouter.
Free tiers can intermittently return 5xx/504 or close connections.

By default, the repo is configured to **fail-open** on provider/network errors:
- The run continues and still produces SVG outputs.

If you want provider failures to count as failures (and keep iterating), set:

```bash
VISION_FAIL_OPEN=false
```
