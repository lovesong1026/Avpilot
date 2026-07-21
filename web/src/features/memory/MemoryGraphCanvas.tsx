import { Graph } from "@antv/x6";
import { useEffect, useRef } from "react";

import type { MemoryGraph } from "../../entities/memory";

const colors = {
  source: { fill: "#fbf2dc", stroke: "#9c7b3c" },
  fragment: { fill: "#f4f1e9", stroke: "#877c66" },
  statement: { fill: "#edf3fa", stroke: "#54749c" },
  entity: { fill: "#e9f4eb", stroke: "#3f765c" },
};

export function MemoryGraphCanvas({ data }: { data: MemoryGraph }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const graph = new Graph({
      container,
      background: { color: "#fbfcfa" },
      grid: { visible: true, size: 18, type: "dot", args: { color: "#dce6dd", thickness: 1 } },
      panning: true,
      mousewheel: { enabled: true, modifiers: ["ctrl", "meta"], minScale: 0.35, maxScale: 2 },
      interacting: { nodeMovable: true, edgeMovable: false },
    });
    const layers = ["source", "fragment", "statement", "entity"] as const;
    const grouped = new Map(layers.map((kind) => [kind, data.nodes.filter((node) => node.kind === kind)]));
    const width = Math.max(container.clientWidth, 720);
    const columnWidth = width / layers.length;
    for (const [column, kind] of layers.entries()) {
      const nodes = grouped.get(kind) || [];
      nodes.forEach((node, row) => {
        const style = colors[node.kind];
        graph.addNode({
          id: node.id,
          x: column * columnWidth + 22,
          y: row * 92 + 34,
          width: Math.max(135, columnWidth - 44),
          height: 58,
          label: node.label.length > 24 ? `${node.label.slice(0, 24)}…` : node.label,
          attrs: {
            body: { fill: style.fill, stroke: style.stroke, strokeWidth: 1.2, rx: 14, ry: 14 },
            label: { fill: "#2f473c", fontSize: 12, textWrap: { width: -18, height: -12, ellipsis: true } },
          },
          data: node,
        });
      });
    }
    for (const edge of data.edges) {
      if (!graph.hasCell(edge.source) || !graph.hasCell(edge.target)) continue;
      graph.addEdge({
        id: edge.id,
        source: edge.source,
        target: edge.target,
        router: { name: "manhattan", args: { padding: 14 } },
        connector: { name: "rounded", args: { radius: 10 } },
        attrs: { line: { stroke: "#9eb0a5", strokeWidth: 1.1, targetMarker: { name: "block", width: 7, height: 5 } } },
        labels: edge.label ? [{ attrs: { label: { text: edge.label, fontSize: 10, fill: "#607168" } } }] : [],
      });
    }
    graph.zoomToFit({ padding: 24, maxScale: 1 });
    const resize = new ResizeObserver(() => {
      graph.resize(container.clientWidth, container.clientHeight);
      graph.zoomToFit({ padding: 24, maxScale: 1 });
    });
    resize.observe(container);
    return () => {
      resize.disconnect();
      graph.dispose();
    };
  }, [data]);

  return <div className="memory-graph-canvas" ref={containerRef} aria-label="可交互记忆图谱" />;
}
