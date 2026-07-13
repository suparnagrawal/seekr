'use client';

import { useEffect, useRef, useCallback, useState } from 'react';
import cytoscape, { type Core, type EventObject } from 'cytoscape';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { Minus, Plus, Maximize2, RotateCcw, Crosshair } from 'lucide-react';
import { useGraphStore } from '@/lib/graph-store';
import { fetchGraph } from '@/lib/api';
import { config } from '@/lib/config';
import { getNodeColor } from '@/lib/utils';
import { Button } from '@/components/ui/button';
import { GraphControls } from './graph-controls';
import { NodeTooltip } from './node-tooltip';
import type { GraphNode } from '@/lib/types';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const CYTOSCAPE_STYLE: any[] = [
  {
    selector: 'node',
    style: {
      'background-color': 'data(color)',
      label: 'data(label)',
      color: '#e4e4e7',
      'font-size': '11px',
      'text-valign': 'bottom',
      'text-margin-y': 8,
      'text-max-width': '120px',
      'text-wrap': 'ellipsis',
      width: 'data(size)',
      height: 'data(size)',
      'border-width': 2,
      'border-color': 'data(borderColor)',
      'overlay-opacity': 0,
      'transition-property': 'background-color, border-color, width, height, opacity',
      'transition-duration': 400,
      opacity: 0,
    },
  },
  {
    selector: 'node.revealed',
    style: {
      opacity: 1,
    },
  },
  {
    selector: 'node:selected',
    style: {
      'border-color': '#3b82f6',
      'border-width': 3,
      'background-color': '#3b82f6',
    },
  },
  {
    selector: 'node.highlighted',
    style: {
      'border-color': '#60a5fa',
      'border-width': 3,
    },
  },
  {
    selector: 'node.dimmed',
    style: {
      opacity: 0.25,
    },
  },
  {
    selector: 'edge',
    style: {
      width: 2,
      'line-color': '#3f3f46',
      'target-arrow-color': '#3f3f46',
      'target-arrow-shape': 'triangle',
      'curve-style': 'bezier',
      label: 'data(label)',
      'font-size': '9px',
      color: '#71717a',
      'text-rotation': 'autorotate',
      'text-margin-y': -10,
      'overlay-opacity': 0,
      'transition-property': 'line-color, target-arrow-color, width, opacity',
      'transition-duration': 400,
      opacity: 0,
    },
  },
  {
    selector: 'edge.revealed',
    style: {
      opacity: 1,
    },
  },
  {
    selector: 'edge.low-confidence',
    style: {
      'line-style': 'dashed',
      'line-dash-pattern': [6, 4],
      'line-color': '#52525b',
      'target-arrow-color': '#52525b',
    },
  },
  {
    selector: 'edge.highlighted',
    style: {
      'line-color': '#60a5fa',
      'target-arrow-color': '#60a5fa',
      width: 3,
    },
  },
  {
    selector: 'edge.dimmed',
    style: {
      opacity: 0.15,
    },
  },
];

export function GraphExplorer() {
  const containerRef = useRef<HTMLDivElement>(null);
  const cyRef = useRef<Core | null>(null);
  const router = useRouter();
  const [tooltip, setTooltip] = useState<{ node: GraphNode; x: number; y: number } | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const {
    graphData, centeredNode, depth, selectedNode,
    highlightedNodes, highlightedEdges,
    setGraphData, selectNode, highlightConnected, clearHighlights,
    setDepth, setLoading, isLoading,
  } = useGraphStore();

  const loadGraph = useCallback(async (tag: string, d: number) => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchGraph(tag, d);
      if (data.nodes.length === 0) {
        setError(`No graph data found for ${tag}. The backend may not have indexed any documents yet.`);
      }
      setGraphData(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load graph');
    } finally {
      setLoading(false);
    }
  }, [setGraphData, setLoading]);

  useEffect(() => {
    loadGraph(config.defaultEntityTag, depth);
  }, [depth, loadGraph]);

  useEffect(() => {
    if (!containerRef.current || !graphData || graphData.nodes.length === 0) return;

    const cy = cytoscape({
      container: containerRef.current,
      style: CYTOSCAPE_STYLE,
      layout: { name: 'cose', animate: false, randomize: false, nodeDimensionsIncludeLabels: true, idealEdgeLength: () => 120, nodeRepulsion: () => 8000, padding: 50 } as cytoscape.LayoutOptions,
      elements: [
        ...graphData.nodes.map((node) => ({
          data: {
            id: node.id,
            label: node.label,
            color: getNodeColor(node.type),
            borderColor: node.id === graphData.center ? '#3b82f6' : getNodeColor(node.type),
            size: node.id === graphData.center ? 48 : node.type === 'equipment' ? 40 : 32,
            nodeType: node.type,
            tag: node.tag,
            ...node.properties,
          },
        })),
        ...graphData.edges.map((edge) => ({
          data: {
            id: edge.id,
            source: edge.source,
            target: edge.target,
            label: edge.relationship.replace(/_/g, ' '),
            confidence: edge.confidence,
          },
          classes: edge.confidence < 0.7 ? 'low-confidence' : '',
        })),
      ],
      minZoom: 0.3,
      maxZoom: 3,
      wheelSensitivity: 0.3,
    });

    cyRef.current = cy;

    const nodes = cy.nodes();
    const centerNode = cy.getElementById(graphData.center);
    const sortedNodes = nodes.sort((a, b) => {
      const distA = a.position().x !== undefined ? Math.sqrt((a.position().x - (centerNode.position().x || 0)) ** 2 + (a.position().y - (centerNode.position().y || 0)) ** 2) : 0;
      const distB = b.position().x !== undefined ? Math.sqrt((b.position().x - (centerNode.position().x || 0)) ** 2 + (b.position().y - (centerNode.position().y || 0)) ** 2) : 0;
      return distA - distB;
    });

    sortedNodes.forEach((node, i) => {
      setTimeout(() => {
        node.addClass('revealed');
        const connectedEdges = node.connectedEdges();
        connectedEdges.forEach((edge) => {
          const src = edge.source();
          const tgt = edge.target();
          if (src.hasClass('revealed') && tgt.hasClass('revealed')) {
            edge.addClass('revealed');
          }
        });
      }, i * 60);
    });

    cy.on('tap', 'node', (evt: EventObject) => {
      const nodeData = evt.target.data();
      const graphNode = graphData.nodes.find((n) => n.id === nodeData.id);
      if (graphNode) {
        selectNode(graphNode);
        highlightConnected(graphNode.id);
      }
    });

    cy.on('tap', (evt: EventObject) => {
      if (evt.target === cy) {
        selectNode(null);
        clearHighlights();
        setTooltip(null);
      }
    });

    cy.on('dbltap', 'node', (evt: EventObject) => {
      const tag = evt.target.data('tag');
      if (tag) router.push(`/entity/${encodeURIComponent(tag)}`);
    });

    cy.on('mouseover', 'node', (evt: EventObject) => {
      const nodeData = evt.target.data();
      const graphNode = graphData.nodes.find((n) => n.id === nodeData.id);
      if (graphNode) {
        const pos = evt.target.renderedPosition();
        setTooltip({ node: graphNode, x: pos.x, y: pos.y });
      }
      evt.target.style('cursor', 'pointer');
    });

    cy.on('mouseout', 'node', () => {
      setTooltip(null);
    });

    return () => {
      cy.destroy();
      cyRef.current = null;
    };
  }, [graphData, router, selectNode, highlightConnected, clearHighlights]);

  useEffect(() => {
    const cy = cyRef.current;
    if (!cy || highlightedNodes.size === 0) {
      cy?.nodes().removeClass('dimmed highlighted');
      cy?.edges().removeClass('dimmed highlighted');
      return;
    }

    cy.nodes().forEach((node) => {
      if (highlightedNodes.has(node.id())) {
        node.addClass('highlighted').removeClass('dimmed');
      } else {
        node.addClass('dimmed').removeClass('highlighted');
      }
    });

    cy.edges().forEach((edge) => {
      if (highlightedEdges.has(edge.id())) {
        edge.addClass('highlighted').removeClass('dimmed');
      } else {
        edge.addClass('dimmed').removeClass('highlighted');
      }
    });
  }, [highlightedNodes, highlightedEdges]);

  const handleZoomIn = () => cyRef.current?.zoom({ level: (cyRef.current.zoom() || 1) * 1.3, renderedPosition: { x: (containerRef.current?.offsetWidth || 0) / 2, y: (containerRef.current?.offsetHeight || 0) / 2 } });
  const handleZoomOut = () => cyRef.current?.zoom({ level: (cyRef.current.zoom() || 1) / 1.3, renderedPosition: { x: (containerRef.current?.offsetWidth || 0) / 2, y: (containerRef.current?.offsetHeight || 0) / 2 } });
  const handleFit = () => cyRef.current?.fit(undefined, 50);
  const handleCenter = () => { if (centeredNode) cyRef.current?.getElementById(centeredNode).select(); cyRef.current?.center(cyRef.current?.getElementById(centeredNode || '')); };

  const toggleFullscreen = () => {
    if (!containerRef.current?.parentElement) return;
    if (!document.fullscreenElement) {
      containerRef.current.parentElement.requestFullscreen();
      setIsFullscreen(true);
    } else {
      document.exitFullscreen();
      setIsFullscreen(false);
    }
  };

  return (
    <div className="relative bg-zinc-950 w-full" style={{ height: 'calc(100vh - 56px)' }}>
      <div ref={containerRef} style={{ width: '100%', height: '100%' }} />

      {isLoading && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          className="absolute inset-0 flex items-center justify-center bg-zinc-950/60 backdrop-blur-sm z-20"
        >
          <div className="flex flex-col items-center gap-3">
            <motion.div
              className="w-10 h-10 rounded-full border-2 border-blue-500 border-t-transparent"
              animate={{ rotate: 360 }}
              transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
            />
            <p className="text-sm text-zinc-400">Loading knowledge graph...</p>
          </div>
        </motion.div>
      )}

      {error && !isLoading && (
        <div className="absolute inset-0 flex items-center justify-center z-20">
          <div className="bg-zinc-900 border border-zinc-700 rounded-lg p-6 max-w-md text-center">
            <p className="text-sm text-zinc-400 mb-3">{error}</p>
            <Button variant="outline" size="sm" onClick={() => loadGraph(config.defaultEntityTag, depth)}>
              Retry
            </Button>
          </div>
        </div>
      )}

      <div className="absolute bottom-4 left-4 flex items-center gap-1 z-10">
        <Button variant="secondary" size="icon" onClick={handleZoomIn} title="Zoom in">
          <Plus className="w-4 h-4" />
        </Button>
        <Button variant="secondary" size="icon" onClick={handleZoomOut} title="Zoom out">
          <Minus className="w-4 h-4" />
        </Button>
        <Button variant="secondary" size="icon" onClick={handleFit} title="Fit to view">
          <RotateCcw className="w-4 h-4" />
        </Button>
        <Button variant="secondary" size="icon" onClick={handleCenter} title="Center on focus">
          <Crosshair className="w-4 h-4" />
        </Button>
        <Button variant="secondary" size="icon" onClick={toggleFullscreen} title="Fullscreen">
          <Maximize2 className="w-4 h-4" />
        </Button>
      </div>

      <GraphControls depth={depth} onDepthChange={setDepth} />

      <AnimatePresence>
        {tooltip && (
          <NodeTooltip node={tooltip.node} x={tooltip.x} y={tooltip.y} />
        )}
      </AnimatePresence>
    </div>
  );
}
