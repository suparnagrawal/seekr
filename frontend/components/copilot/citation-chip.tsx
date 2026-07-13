'use client';

import { motion } from 'framer-motion';
import { FileText } from 'lucide-react';
import type { Citation } from '@/lib/types';

interface CitationChipProps {
  citation: Citation;
}

export function CitationChip({ citation }: CitationChipProps) {
  const isUnknown = citation.doc_id === 'unknown' || !citation.doc_id;
  return (
    <motion.button
      initial={{ opacity: 0, scale: 0.85 }}
      animate={{ opacity: 1, scale: 1 }}
      whileHover={{ y: -1 }}
      className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-md font-mono text-[0.66rem] bg-mint-soft text-mint border border-mint/25 hover:border-mint/50 transition-colors"
      title={citation.title || `Document ${citation.doc_id}`}
    >
      <FileText className="w-3 h-3" />
      <span>{isUnknown ? 'source pending' : citation.doc_id}</span>
      {citation.page > 0 && <span className="opacity-60">p.{citation.page}</span>}
    </motion.button>
  );
}
