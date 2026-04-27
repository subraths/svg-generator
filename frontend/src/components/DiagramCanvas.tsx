"use client";

import { useEffect, useMemo, useRef } from "react";
import * as d3 from "d3";
import type { EnrichResponse } from "@/lib/api";

type Props = {
  data: EnrichResponse["enriched"] | null;
  activeNodeId?: string | null;
  activeEdgeKey?: string | null; // "from->to"
  width?: number;
  height?: number;
};

type PositionedNode = {
  id: string;
  label: string;
  x: number;
  y: number;
  importance: "high" | "medium" | "low";
};

type PositionedEdge = {
  key: string; // "from->to"
  from: string;
  to: string;
  semantic:
    | "causal"
    | "definitional"
    | "associative"
    | "comparative"
    | "temporal";
};

export default function DiagramCanvas({
  data,
  activeNodeId = null,
  activeEdgeKey = null,
  width = 900,
  height = 420,
}: Props) {
  const ref = useRef<SVGSVGElement | null>(null);

  const { nodes, edges } = useMemo(() => {
    if (!data)
      return { nodes: [] as PositionedNode[], edges: [] as PositionedEdge[] };

    const concepts = data.graph.concepts;
    const n = concepts.length;

    const leftPad = 90;
    const rightPad = 90;
    const usableW = width - leftPad - rightPad;
    const stepX = n > 1 ? usableW / (n - 1) : 0;
    const centerY = height / 2;

    const nodes: PositionedNode[] = concepts.map((c, i) => ({
      id: c.id,
      label: c.label,
      x: leftPad + i * stepX,
      y: centerY,
      importance: data.node_styles[c.id]?.importance ?? "low",
    }));

    const edges: PositionedEdge[] = data.graph.relationships.map((r) => {
      const key = `${r.from}->${r.to}`;
      return {
        key,
        from: r.from,
        to: r.to,
        semantic: data.edge_styles[key]?.semantic ?? "associative",
      };
    });

    return { nodes, edges };
  }, [data, width, height]);

  useEffect(() => {
    const svgEl = ref.current;
    if (!svgEl) return;

    const svg = d3.select(svgEl);
    svg.selectAll("*").remove();

    svg
      .append("rect")
      .attr("x", 0)
      .attr("y", 0)
      .attr("width", width)
      .attr("height", height)
      .attr("fill", "#fff")
      .attr("rx", 12);

    svg
      .append("defs")
      .append("marker")
      .attr("id", "arrow")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 18)
      .attr("refY", 0)
      .attr("markerWidth", 7)
      .attr("markerHeight", 7)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-5L10,0L0,5")
      .attr("fill", "#94a3b8");

    const nodeById = new Map(nodes.map((n) => [n.id, n]));

    const edgeGroup = svg.append("g");
    edgeGroup
      .selectAll("line")
      .data(edges)
      .enter()
      .append("line")
      .attr("x1", (e) => nodeById.get(e.from)?.x ?? 0)
      .attr("y1", (e) => nodeById.get(e.from)?.y ?? 0)
      .attr("x2", (e) => nodeById.get(e.to)?.x ?? 0)
      .attr("y2", (e) => nodeById.get(e.to)?.y ?? 0)
      .attr("stroke", (e) => {
        if (e.semantic === "causal") return "#60a5fa";
        if (e.semantic === "definitional") return "#34d399";
        if (e.semantic === "comparative") return "#f59e0b";
        if (e.semantic === "temporal") return "#a78bfa";
        return "#94a3b8";
      })
      .attr("stroke-width", 2)
      .attr("marker-end", "url(#arrow)")
      .attr("opacity", activeNodeId ? 0.35 : 0.8);

    const edgeLines = edgeGroup
      .selectAll("line")
      .data(edges)
      .enter()
      .append("line")
      .attr("x1", (e) => nodeById.get(e.from)?.x ?? 0)
      .attr("y1", (e) => nodeById.get(e.from)?.y ?? 0)
      .attr("x2", (e) => nodeById.get(e.to)?.x ?? 0)
      .attr("y2", (e) => nodeById.get(e.to)?.y ?? 0)
      .attr("stroke", (e) => {
        if (e.semantic === "causal") return "#60a5fa";
        if (e.semantic === "definitional") return "#34d399";
        if (e.semantic === "comparative") return "#f59e0b";
        if (e.semantic === "temporal") return "#a78bfa";
        return "#94a3b8";
      })
      .attr("stroke-width", 2)
      .attr("marker-end", "url(#arrow)")
      .attr("opacity", 0);

    edgeLines
      .transition()
      .duration(450)
      .ease(d3.easeCubicOut)
      .attr("stroke-width", (e) =>
        activeEdgeKey && e.key === activeEdgeKey ? 4 : 2,
      )
      .attr("opacity", (e) => {
        if (!activeNodeId && !activeEdgeKey) return 0.8;
        if (activeEdgeKey && e.key === activeEdgeKey) return 1;
        return 0.15;
      });

    const edgeLabels = edgeGroup
      .selectAll("text")
      .data(edges)
      .enter()
      .append("text")
      .attr(
        "x",
        (e) =>
          ((nodeById.get(e.from)?.x ?? 0) + (nodeById.get(e.to)?.x ?? 0)) / 2,
      )
      .attr(
        "y",
        (e) =>
          ((nodeById.get(e.from)?.y ?? 0) + (nodeById.get(e.to)?.y ?? 0)) / 2 -
          10,
      )
      .attr("fill", "#cbd5e1")
      .attr("font-size", 11)
      .attr("text-anchor", "middle")
      .attr("opacity", 0)
      .text((e) => e.semantic);

    edgeLabels
      .transition()
      .duration(450)
      .ease(d3.easeCubicOut)
      .attr("opacity", (e) => {
        if (!activeNodeId && !activeEdgeKey) return 1;
        if (activeEdgeKey && e.key === activeEdgeKey) return 1;
        return 0.2;
      });

    const nodeGroup = svg.append("g");

    const circles = nodeGroup
      .selectAll("circle")
      .data(nodes)
      .enter()
      .append("circle")
      .attr("cx", (d) => d.x)
      .attr("cy", (d) => d.y)
      .attr("r", 10)
      .attr("fill", (d) =>
        d.importance === "high"
          ? "#1d4ed8"
          : d.importance === "medium"
            ? "#0ea5e9"
            : "#334155",
      )
      .attr("stroke", "#cbd5e1")
      .attr("stroke-width", 1.5)
      .attr("opacity", 0.5);

    circles
      .transition()
      .duration(500)
      .ease(d3.easeCubicOut)
      .attr("r", (d) => {
        const base =
          d.importance === "high" ? 28 : d.importance === "medium" ? 24 : 20;
        return activeNodeId === d.id ? base + 4 : base;
      })
      .attr("stroke", (d) => (activeNodeId === d.id ? "#f8fafc" : "#cbd5e1"))
      .attr("stroke-width", (d) => (activeNodeId === d.id ? 4 : 1.5))
      .attr("opacity", (d) => {
        if (!activeNodeId) return 1;
        return d.id === activeNodeId ? 1 : 0.35;
      });

    const labels = nodeGroup
      .selectAll("text")
      .data(nodes)
      .enter()
      .append("text")
      .attr("x", (d) => d.x)
      .attr("y", (d) => d.y + 4)
      .attr("text-anchor", "middle")
      .attr("fill", "white")
      .attr("font-size", 12)
      .attr("font-weight", 600)
      .attr("opacity", 0)
      .text((d) => d.label);

    labels
      .transition()
      .duration(500)
      .ease(d3.easeCubicOut)
      .attr("opacity", (d) => {
        if (!activeNodeId) return 1;
        return d.id === activeNodeId ? 1 : 0.45;
      });
  }, [nodes, edges, width, height, activeNodeId, activeEdgeKey]);

  return <svg ref={ref} width={width} height={height} />;
}
