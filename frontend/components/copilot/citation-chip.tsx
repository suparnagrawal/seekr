'use client';

import { motion } from 'framer-motion';
import { FileText } from 'lucide-react';
import type { Citation } from '@/lib/types';

interface CitationChipProps {
  citation: Citation;
}

export function CitationChip({ citation }: CitationChipProps) {
  return (
    <motion.button
      initial={{ opacity: 0, scale: 0.8 }}
      animate={{ opacity: 1, scale: 1 }}
      whileHover={{ scale: 1.05 }}
      className="inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-xs font-medium bg-violet-500/15 text-violet-300 border border-violet-500/25 hover:bg-violet-500/25 transition-colors"
      title={citation.title || `Document ${citation.doc_id}`}
    >
      <FileText className="w-3 h-3" />
      <span>{citation.doc_id}</span>
      <span className="text-violet-500">p.{citation.page}</span>
    </motion.button>
  );
}
