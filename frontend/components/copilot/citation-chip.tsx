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
      className="inline-flex items-start gap-1.5 px-2.5 py-1.5 rounded-md font-mono text-[0.66rem] bg-mint-soft text-mint border border-mint/25 hover:border-mint/50 transition-colors text-left"
      title={citation.title || citation.filename}
    >
      <FileText className="w-3 h-3 mt-0.5 shrink-0" />
      <div className="flex flex-col gap-0.5">
        <span className="font-medium">{isUnknown ? 'source pending' : citation.filename}</span>
        <div className="flex gap-2 opacity-75">
          {citation.page_numbers && citation.page_numbers.length > 0 && (
            <span>
              Page{citation.page_numbers.length > 1 ? 's' : ''} {citation.page_numbers.join(', ')}
            </span>
          )}
          {citation.chunk_index !== undefined && (
            <span className="text-[0.6rem]">Chunk {citation.chunk_index}</span>
          )}
        </div>
        {citation.headings && citation.headings.length > 0 && (
          <span className="opacity-60 truncate max-w-[150px]">{citation.headings[citation.headings.length - 1]}</span>
        )}
      </div>
    </motion.button>
  );
}
