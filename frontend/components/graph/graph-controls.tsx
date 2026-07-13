'use client';

import { motion } from 'framer-motion';
import { Layers, Minus, Plus } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface GraphControlsProps {
  depth: number;
  onDepthChange: (depth: number) => void;
}

export function GraphControls({ depth, onDepthChange }: GraphControlsProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      className="absolute top-4 right-4 flex items-center gap-2 bg-zinc-900/90 backdrop-blur-sm border border-zinc-800 rounded-lg px-3 py-2 z-10"
    >
      <Layers className="w-4 h-4 text-zinc-400" />
      <span className="text-xs text-zinc-400">Depth</span>
      <div className="flex items-center gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="w-6 h-6"
          onClick={() => onDepthChange(depth - 1)}
          disabled={depth <= 1}
        >
          <Minus className="w-3 h-3" />
        </Button>
        <span className="w-6 text-center text-sm font-medium text-zinc-200 tabular-nums">{depth}</span>
        <Button
          variant="ghost"
          size="icon"
          className="w-6 h-6"
          onClick={() => onDepthChange(depth + 1)}
          disabled={depth >= 5}
        >
          <Plus className="w-3 h-3" />
        </Button>
      </div>

      <div className="ml-2 flex gap-1">
        {[
          { type: 'equipment', color: '#3b82f6', label: 'Equipment' },
          { type: 'document', color: '#8b5cf6', label: 'Document' },
          { type: 'procedure', color: '#10b981', label: 'Procedure' },
          { type: 'system', color: '#f59e0b', label: 'System' },
          { type: 'component', color: '#06b6d4', label: 'Component' },
          { type: 'failure_mode', color: '#ef4444', label: 'Failure' },
        ].map((item) => (
          <div key={item.type} className="flex items-center gap-1 px-1.5" title={item.label}>
            <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }} />
            <span className="text-[10px] text-zinc-500 hidden xl:inline">{item.label}</span>
          </div>
        ))}
      </div>
    </motion.div>
  );
}
