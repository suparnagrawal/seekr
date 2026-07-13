'use client';

import { motion } from 'framer-motion';
import type { GraphNode } from '@/lib/types';
import { getNodeColor } from '@/lib/utils';

interface NodeTooltipProps {
  node: GraphNode;
  x: number;
  y: number;
}

export function NodeTooltip({ node, x, y }: NodeTooltipProps) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.92 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.92 }}
      transition={{ duration: 0.14 }}
      className="absolute z-30 pointer-events-none"
      style={{ left: x + 16, top: y - 10 }}
    >
      <div className="hud rounded-md px-3 py-2 shadow-xl max-w-xs">
        <div className="flex items-center gap-2 mb-1.5">
          <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: getNodeColor(node.type) }} />
          <span className="text-sm font-medium text-[#f3ecdd]">{node.label}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="font-mono text-[0.62rem] uppercase tracking-wider border border-white/15 rounded px-1.5 py-0.5 text-[#c9bfa8]">
            {node.tag}
          </span>
          <span className="text-xs hud-text capitalize">{node.type.replace(/_/g, ' ')}</span>
        </div>
        {node.confidence !== undefined && node.confidence < 1 && (
          <p className="mt-1.5 font-mono text-[0.62rem] hud-text">
            confidence · {Math.round(node.confidence * 100)}%
          </p>
        )}
        <p className="mt-1 text-[0.62rem] text-[#8a8069]">double-click → open detail</p>
      </div>
    </motion.div>
  );
}
