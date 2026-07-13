'use client';

import { use, useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { ArrowLeft, Network } from 'lucide-react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { NodeSidePanel } from '@/components/entity/node-side-panel';
import { GraphExplorer } from '@/components/graph/graph-explorer';
import { useGraphStore } from '@/lib/graph-store';
import { fetchGraph } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { FadeIn } from '@/components/animations/fade-in';
import { RiskPanel } from '@/components/entity/risk-panel';

export default function EntityPage({ params }: { params: Promise<{ tag: string }> }) {
  const { tag } = use(params);
  const decodedTag = decodeURIComponent(tag);
  const { setGraphData, graphData } = useGraphStore();
  const [showGraph, setShowGraph] = useState(true);

  useEffect(() => {
    fetchGraph(decodedTag).then(setGraphData).catch(() => {});
  }, [decodedTag, setGraphData]);

  const nodeLabel = graphData?.nodes.find((n) => n.tag === decodedTag)?.label || decodedTag;

  return (
    <div className="flex h-full">
      <div className="flex-1 flex flex-col">
        <FadeIn>
          <div className="flex items-center gap-3 px-4 py-3 border-b border-zinc-800">
            <Link href="/">
              <Button variant="ghost" size="sm">
                <ArrowLeft className="w-4 h-4" />
                Back to Graph
              </Button>
            </Link>
            <div className="h-4 w-px bg-zinc-700" />
            <div className="flex items-center gap-2">
              <Network className="w-4 h-4 text-blue-400" />
              <span className="text-sm font-medium text-zinc-300">{nodeLabel}</span>
            </div>
          </div>
        </FadeIn>

        {showGraph && (
          <div className="flex-1 relative">
            <GraphExplorer />
          </div>
        )}
      </div>

      <motion.div
        initial={{ x: 20, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        className="w-[440px] border-l border-zinc-800 flex flex-col"
      >
        <NodeSidePanel tag={decodedTag} label={nodeLabel} />
      </motion.div>
    </div>
  );
}
