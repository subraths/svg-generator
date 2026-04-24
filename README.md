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
