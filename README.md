# svg-generator

Generate educational SVG diagrams using LLMs, validate them, render PNGs, and compare baseline vs planner-guided generation.

## Setup

```bash
uv sync
# or: pip install -e .
```

Set env:

```bash
export GROQ_API_KEY=...
```

## Single run

```bash
python -m src.main
```

- Configure topic/mode in `src/main.py`:
  - `TOPIC = "..."`
  - `USE_PLANNER = True|False`

Outputs:

- `svg/*.svg`
- `img/*.png`
- `reports/*.json`
- planner mode also writes `*_plan*.json`

## Batch compare (v1 vs v2)

```bash
python -m src.run_batch
```

Outputs:

- `reports/batch_compare_<timestamp>.csv`
- per-run reports in `reports/`
- SVG/PNG artifacts in `svg/` and `img/`

## Metrics

```bash
python -m src.metrics
# or
python -m src.metrics reports/batch_compare_<timestamp>.csv
```

Outputs:

- `reports/summary_<timestamp>.json`
- console summary with mode-wise comparison and deltas

## FastAPI lesson API + interactive browser player

Run API server:

```bash
uv run uvicorn src.api:app --reload
# or
python -m uvicorn src.api:app --reload
```

Open:

- `http://127.0.0.1:8000/` (interactive player UI)

Core endpoints:

- `POST /lesson/generate`
  - body: `{"topic":"Photosynthesis","difficulty":"beginner","use_llm":true}`
  - returns lesson JSON + SVG URL + audio base URL
- `GET /lesson/{id}`
- `GET /diagram/{id}.svg`
- `GET /audio/{id}/{segment}`

Generated lesson assets are stored in:

- `data/lessons/<lesson_id>/lesson.json`
- `data/lessons/<lesson_id>/diagram.svg`
- `data/lessons/<lesson_id>/audio/*.wav`

## Structured pipeline evaluation

```bash
python -m src.evaluate_pipeline
```

Outputs:

- `reports/evaluation_<timestamp>.csv`
- `reports/evaluation_<timestamp>.json`

## Validation checks (SVG)

Current validator checks:

- XML validity
- minimum group count
- duplicate group IDs
- rectangle overlap detection
- connector count
- arrow marker presence and marker-end usage

## Planner checks (Plan JSON)

Current planner validation checks:

- nodes/edges schema presence
- minimum node count
- numeric geometry
- bounds within canvas
- spacing/overlap
- unique node IDs
- valid edge references
