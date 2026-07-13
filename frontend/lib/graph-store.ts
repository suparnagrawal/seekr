import { create } from 'zustand';
import type { GraphData, GraphNode, GraphEdge } from './types';

interface GraphState {
  graphData: GraphData | null;
  centeredNode: string | null;
  depth: number;
  selectedNode: GraphNode | null;
  highlightedNodes: Set<string>;
  highlightedEdges: Set<string>;
  isLoading: boolean;

  setGraphData: (data: GraphData) => void;
  setCenteredNode: (nodeId: string) => void;
  setDepth: (depth: number) => void;
  selectNode: (node: GraphNode | null) => void;
  highlightConnected: (nodeId: string) => void;
  clearHighlights: () => void;
  setLoading: (loading: boolean) => void;
  expandNode: (nodeId: string, newNodes: GraphNode[], newEdges: GraphEdge[]) => void;
}

export const useGraphStore = create<GraphState>((set, get) => ({
  graphData: null,
  centeredNode: null,
  depth: 2,
  selectedNode: null,
  highlightedNodes: new Set(),
  highlightedEdges: new Set(),
  isLoading: false,

  setGraphData: (data) => set({ graphData: data, centeredNode: data.center }),

  setCenteredNode: (nodeId) => set({ centeredNode: nodeId }),

  setDepth: (depth) => set({ depth: Math.max(1, Math.min(5, depth)) }),

  selectNode: (node) => set({ selectedNode: node }),

  highlightConnected: (nodeId) => {
    const { graphData } = get();
    if (!graphData) return;

    const nodeSet = new Set<string>([nodeId]);
    const edgeSet = new Set<string>();

    graphData.edges.forEach((edge) => {
      if (edge.source === nodeId || edge.target === nodeId) {
        nodeSet.add(edge.source);
        nodeSet.add(edge.target);
        edgeSet.add(edge.id);
      }
    });

    set({ highlightedNodes: nodeSet, highlightedEdges: edgeSet });
  },

  clearHighlights: () => set({ highlightedNodes: new Set(), highlightedEdges: new Set() }),

  setLoading: (loading) => set({ isLoading: loading }),

  expandNode: (nodeId, newNodes, newEdges) => {
    const { graphData } = get();
    if (!graphData) return;

    const existingNodeIds = new Set(graphData.nodes.map((n) => n.id));
    const existingEdgeIds = new Set(graphData.edges.map((e) => e.id));

    const filteredNodes = newNodes.filter((n) => !existingNodeIds.has(n.id));
    const filteredEdges = newEdges.filter((e) => !existingEdgeIds.has(e.id));

    set({
      graphData: {
        ...graphData,
        nodes: [...graphData.nodes, ...filteredNodes],
        edges: [...graphData.edges, ...filteredEdges],
      },
    });
  },
}));
