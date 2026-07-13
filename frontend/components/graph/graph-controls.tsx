'use client';

import { motion } from 'framer-motion';
import { Layers, Minus, Plus } from 'lucide-react';
import { getNodeColor } from '@/lib/utils';

interface GraphControlsProps {
  depth: number;
  onDepthChange: (depth: number) => void;
}

const LEGEND = [
  { type: 'equipment', label: 'Equipment' },
  { type: 'system', label: 'System' },
  { type: 'component', label: 'Component' },
  { type: 'procedure', label: 'Procedure' },
  { type: 'document', label: 'Document' },
  { type: 'failure_mode', label: 'Failure' },
];

export function GraphControls({ depth, onDepthChange }: GraphControlsProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="absolute top-4 right-4 z-10 hud rounded-md px-3 py-2 flex flex-col gap-2 max-w-[240px]"
    >
      <div className="flex items-center gap-2">
        <Layers className="w-3.5 h-3.5 text-signal" />
        <span className="font-mono text-[0.62rem] uppercase tracking-wider hud-text">Traversal depth</span>
        <div className="ml-auto flex items-center gap-1">
          <button
            onClick={() => onDepthChange(depth - 1)}
            disabled={depth <= 1}
            className="w-6 h-6 rounded flex items-center justify-center text-[#c9bfa8] hover:text-signal hover:bg-white/5 disabled:opacity-30 transition-colors"
          >
            <Minus className="w-3 h-3" />
          </button>
          <span className="w-5 text-center data-num text-sm text-[#e9e1d0]">{depth}</span>
          <button
            onClick={() => onDepthChange(depth + 1)}
            disabled={depth >= 5}
            className="w-6 h-6 rounded flex items-center justify-center text-[#c9bfa8] hover:text-signal hover:bg-white/5 disabled:opacity-30 transition-colors"
          >
            <Plus className="w-3 h-3" />
          </button>
        </div>
      </div>

      <div className="h-px bg-white/10" />

      <div className="grid grid-cols-2 gap-x-3 gap-y-1">
        {LEGEND.map((item) => (
          <div key={item.type} className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: getNodeColor(item.type) }} />
            <span className="text-[0.66rem] hud-text">{item.label}</span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
