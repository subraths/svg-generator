const API_BASE = process.env.NEXT_PUBLIC_API_BASE!;

export type DiagramType =
  | "pipeline"
  | "hierarchy"
  | "cycle"
  | "comparison"
  | "network"
  | "timeline";

export interface Concept {
  id: string;
  label: string;
  group?: string | null;
}

export interface Relationship {
  from: string;
  to: string;
  type:
    | "causes"
    | "defines"
    | "contains"
    | "leads_to"
    | "compares"
    | "depends_on";
}

export interface Subtopic {
  id: string;
  label: string;
  explanation?: string | null;
}

export interface ConceptGraph {
  title: string;
  type: DiagramType;
  concepts: Concept[];
  relationships: Relationship[];
  subtopics: Subtopic[];
  narration_order: string[];
}

export interface GenerateGraphResponse {
  graph: ConceptGraph;
}

export interface EnrichResponse {
  enriched: {
    graph: ConceptGraph;
    node_styles: Record<string, { importance: "high" | "medium" | "low" }>;
    edge_styles: Record<
      string,
      {
        semantic:
          | "causal"
          | "definitional"
          | "associative"
          | "comparative"
          | "temporal";
      }
    >;
  };
}

export async function generateGraph(
  topic: string,
): Promise<GenerateGraphResponse> {
  const res = await fetch(`${API_BASE}/generate-graph`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ topic }),
  });
  if (!res.ok) throw new Error("Failed to generate graph");
  return res.json();
}

export async function enrichGraph(
  graph: ConceptGraph,
): Promise<EnrichResponse> {
  const res = await fetch(`${API_BASE}/enrich-graph`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ graph }),
  });
  if (!res.ok) throw new Error("Failed to enrich graph");
  return res.json();
}
