'use client';

import { motion } from 'framer-motion';
import { GraphExplorer } from '@/components/graph/graph-explorer';
import { useGraphStore } from '@/lib/graph-store';
import { NodeSidePanel } from '@/components/entity/node-side-panel';
import { AnimatePresence } from 'framer-motion';

export default function DashboardPage() {
  const selectedNode = useGraphStore((s) => s.selectedNode);

  return (
    <div className="flex flex-1 min-h-0">
      <div className="flex-1 relative">
        <GraphExplorer />
      </div>

      <AnimatePresence>
        {selectedNode && (
          <motion.div
            key={selectedNode.id}
            initial={{ width: 0, opacity: 0 }}
            animate={{ width: 420, opacity: 1 }}
            exit={{ width: 0, opacity: 0 }}
            transition={{ duration: 0.3, ease: [0.25, 0.46, 0.45, 0.94] }}
            className="border-l border-zinc-800 overflow-hidden"
          >
            <NodeSidePanel tag={selectedNode.tag} label={selectedNode.label} />
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
