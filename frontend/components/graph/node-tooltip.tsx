'use client';

import { motion } from 'framer-motion';
import type { GraphNode } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { getNodeColor } from '@/lib/utils';

interface NodeTooltipProps {
  node: GraphNode;
  x: number;
  y: number;
}

export function NodeTooltip({ node, x, y }: NodeTooltipProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.9 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.9 }}
      transition={{ duration: 0.15 }}
      className="absolute z-30 pointer-events-none"
      style={{ left: x + 16, top: y - 10 }}
    >
      <div className="bg-zinc-900/95 backdrop-blur-sm border border-zinc-700 rounded-lg px-3 py-2 shadow-xl max-w-xs">
        <div className="flex items-center gap-2 mb-1">
          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: getNodeColor(node.type) }} />
          <span className="text-sm font-medium text-zinc-200">{node.label}</span>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="outline">{node.tag}</Badge>
          <span className="text-xs text-zinc-500 capitalize">{node.type.replace(/_/g, ' ')}</span>
        </div>
        {node.confidence !== undefined && node.confidence < 1 && (
          <p className="mt-1 text-xs text-zinc-500">
            Confidence: {Math.round(node.confidence * 100)}%
          </p>
        )}
        <p className="mt-1 text-[10px] text-zinc-600">Double-click to open details</p>
      </div>
    </motion.div>
  );
}
