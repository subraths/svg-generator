from fastapi import FastAPI
from app.schemas import GenerateGraphRequest, GenerateGraphResponse
from app.services.generator import generate_graph_for_topic
from app.services.classifier import classify_topic
from pydantic import BaseModel
from app.schemas import DiagramType
from app.schemas import EnrichRequest, EnrichResponse
from app.services.enricher import enrich_graph
from fastapi.middleware.cors import CORSMiddleware
from app.services.validator import validate_and_repair_graph

app = FastAPI(title="Interactive Diagram Engine API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ClassifyRequest(BaseModel):
    topic: str


class ClassifyResponse(BaseModel):
    topic: str
    type: DiagramType


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/generate-graph", response_model=GenerateGraphResponse)
def generate_graph(payload: GenerateGraphRequest):
    graph = generate_graph_for_topic(payload.topic)
    return GenerateGraphResponse(graph=graph)


@app.post("/classify", response_model=ClassifyResponse)
def classify(payload: ClassifyRequest):
    return ClassifyResponse(topic=payload.topic, type=classify_topic(payload.topic))


@app.post("/enrich-graph", response_model=EnrichResponse)
def enrich(payload: EnrichRequest):
    # Re-validate incoming graph because clients may send malformed payloads.
    safe_graph = validate_and_repair_graph(payload.graph)
    enriched = enrich_graph(safe_graph)
    return EnrichResponse(enriched=enriched)
