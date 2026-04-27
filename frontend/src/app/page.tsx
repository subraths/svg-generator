"use client";

import { useEffect, useState } from "react";
import {
  enrichGraph,
  generateGraph,
  type EnrichResponse,
  type GenerateGraphResponse,
} from "@/lib/api";
import DiagramCanvas from "@/components/DiagramCanvas";

export default function Home() {
  const [topic, setTopic] = useState("How CPUs Work");
  const [loading, setLoading] = useState(false);
  const [generated, setGenerated] = useState<GenerateGraphResponse | null>(
    null,
  );
  const [enriched, setEnriched] = useState<EnrichResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [stepIndex, setStepIndex] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  const onRun = async () => {
    setLoading(true);
    setError(null);
    setGenerated(null);
    setEnriched(null);

    try {
      const g = await generateGraph(topic);
      setGenerated(g);

      const e = await enrichGraph(g.graph);
      setEnriched(e);
      setStepIndex(0);
      setIsPlaying(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  };

  const narrationOrder = enriched?.enriched.graph.narration_order ?? [];
  const maxIndex = narrationOrder.length > 0 ? narrationOrder.length - 1 : 0;
  const activeNodeId =
    narrationOrder.length > 0
      ? narrationOrder[Math.min(stepIndex, maxIndex)]
      : null;
  const activeEdgeKey =
    narrationOrder.length > 1 && stepIndex > 0
      ? `${narrationOrder[stepIndex - 1]}->${narrationOrder[stepIndex]}`
      : null;

  useEffect(() => {
    const narrationOrder = enriched?.enriched.graph.narration_order ?? [];
    if (!isPlaying || narrationOrder.length === 0) return;

    const maxIndex = narrationOrder.length - 1;
    const timer = setInterval(() => {
      setStepIndex((prev) => {
        if (prev >= maxIndex) {
          setIsPlaying(false); // stop at end
          return prev;
        }
        return prev + 1;
      });
    }, 1200);

    return () => clearInterval(timer);
  }, [isPlaying, enriched]);

  return (
    <main
      style={{
        maxWidth: 1000,
        margin: "40px auto",
        padding: 16,
        fontFamily: "sans-serif",
      }}
    >
      <h1>Interactive Diagram Engine (v2)</h1>

      <div style={{ display: "flex", gap: 8, marginTop: 16 }}>
        <input
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder="Enter a topic"
          style={{ flex: 1, padding: 10 }}
        />
        <button
          onClick={onRun}
          disabled={loading}
          className="px-4 py-2 bg-yellow-500 text-black rounded-lg hover:bg-yellow-600 disabled:bg-gray-400 disabled:cursor-not-allowed"
        >
          {loading ? "Running..." : "Generate"}
        </button>
      </div>

      {error && <p style={{ color: "crimson", marginTop: 12 }}>{error}</p>}
      <section style={{ marginTop: 24 }}>
        <h2>Diagram Preview</h2>

        <div className="flex justify-center items-center gap-4 mb-6">
          <button
            onClick={() => setStepIndex((s) => Math.max(0, s - 1))}
            disabled={!narrationOrder.length || stepIndex === 0 || loading}
            style={{ padding: "6px 10px" }}
          >
            Prev
          </button>
          <button
            onClick={() => setStepIndex((s) => Math.min(maxIndex, s + 1))}
            disabled={
              !narrationOrder.length || stepIndex >= maxIndex || loading
            }
            style={{ padding: "6px 10px" }}
          >
            Next
          </button>
          <button
            onClick={() => setIsPlaying((p) => !p)}
            disabled={!narrationOrder.length || loading}
            style={{ padding: "6px 10px" }}
          >
            {isPlaying ? "Pause" : "Play"}
          </button>

          <button
            onClick={() => {
              setStepIndex(0);
              setIsPlaying(false);
            }}
            disabled={!narrationOrder.length || loading}
            style={{ padding: "6px 10px" }}
          >
            Reset
          </button>

          <span style={{ fontSize: 14, color: "#475569" }}>
            Step {narrationOrder.length ? stepIndex + 1 : 0} /{" "}
            {narrationOrder.length}
          </span>
          {activeNodeId && (
            <code
              style={{
                background: "#333",
                padding: "2px 6px",
                borderRadius: 6,
              }}
            >
              active: {activeNodeId}
            </code>
          )}
        </div>

        <DiagramCanvas
          data={enriched?.enriched ?? null}
          activeNodeId={activeNodeId}
          activeEdgeKey={activeEdgeKey}
        />
      </section>

      <section style={{ marginTop: 24 }}>
        <h2>Pass 1: Generated Graph</h2>
        <pre
          style={{
            background: "#111",
            color: "#0f0",
            padding: 12,
            overflowX: "auto",
          }}
        >
          {generated ? JSON.stringify(generated, null, 2) : "No data yet"}
        </pre>
      </section>

      <section style={{ marginTop: 24 }}>
        <h2>Pass 2: Enriched Graph</h2>
        <pre
          style={{
            background: "#111",
            color: "#0ff",
            padding: 12,
            overflowX: "auto",
          }}
        >
          {enriched ? JSON.stringify(enriched, null, 2) : "No data yet"}
        </pre>
      </section>
    </main>
  );
}
