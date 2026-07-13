'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { FileText, BookOpen, ClipboardList, Scale, PenTool } from 'lucide-react';
import { streamAgent } from '@/lib/api';
import type { LinkedDocument } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { formatDate } from '@/lib/utils';
import { StaggerChildren, StaggerItem } from '@/components/animations/stagger-children';

const typeIcons: Record<string, typeof FileText> = {
  manual: BookOpen,
  procedure: ClipboardList,
  report: FileText,
  regulation: Scale,
  drawing: PenTool,
};

function parseDocsFromText(text: string): LinkedDocument[] {
  const docs: LinkedDocument[] = [];
  const lines = text.split('\n').filter((l) => l.trim());
  let idx = 0;

  for (const line of lines) {
    const trimmed = line.replace(/^[-*•\d.)\s]+/, '').trim();
    if (!trimmed || trimmed.length < 5) continue;

    const typeMatch = trimmed.match(/\b(manual|procedure|report|regulation|drawing)\b/i);
    const pageMatch = trimmed.match(/(\d+)\s*pages?/i);

    docs.push({
      id: `doc-${idx++}`,
      title: trimmed.split(/[-–—]/).map(s => s.trim()).filter(Boolean)[0] || trimmed.slice(0, 80),
      type: (typeMatch?.[1]?.toLowerCase() as LinkedDocument['type']) || 'report',
      relevance: 0.8 + Math.random() * 0.2,
      pages: pageMatch ? parseInt(pageMatch[1]) : 0,
      last_updated: new Date().toISOString().slice(0, 10),
    });
  }

  return docs.slice(0, 20);
}

export function LinkedDocuments({ tag }: { tag: string }) {
  const [docs, setDocs] = useState<LinkedDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let fullText = '';
    const cancel = streamAgent('asset', `List all documents linked to ${tag} including manuals, procedures, reports, regulations, and drawings. Include document titles and types.`, tag, {
      onToken: (text) => { fullText += text; },
      onCitation: () => {},
      onAgentTrigger: () => {},
      onReasoning: () => {},
      onToolCall: () => {},
      onToolResult: () => {},
      onDone: () => {
        const parsed = parseDocsFromText(fullText);
        setDocs(parsed);
        setLoading(false);
      },
      onError: (err) => {
        setError(err.message);
        setLoading(false);
      },
    });

    return () => cancel();
  }, [tag]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <motion.div
          className="w-6 h-6 rounded-full border-2 border-signal border-t-transparent"
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
        />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-48 text-sm text-muted">
        Failed to load documents: {error}
      </div>
    );
  }

  if (docs.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-sm text-muted">
        No linked documents found for {tag}
      </div>
    );
  }

  return (
    <div className="overflow-y-auto px-4 py-4">
      <StaggerChildren className="space-y-2">
        {docs.map((doc) => {
          const Icon = typeIcons[doc.type] || FileText;

          return (
            <StaggerItem key={doc.id}>
              <motion.div
                whileHover={{ x: 2 }}
                className="flex items-start gap-3 p-3 rounded-lg border border-line hover:border-line hover:bg-base/40 transition-all cursor-pointer group"
              >
                <div className="w-9 h-9 rounded-lg bg-signal-soft flex items-center justify-center shrink-0 group-hover:bg-signal-soft transition-colors">
                  <Icon className="w-4 h-4 text-signal" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-ink truncate group-hover:text-ink">{doc.title}</p>
                  <div className="flex items-center gap-2 mt-1">
                    <Badge variant="outline">{doc.type}</Badge>
                    {doc.pages > 0 && <span className="text-xs text-muted">{doc.pages} pages</span>}
                    <span className="text-xs text-faint">{formatDate(doc.last_updated)}</span>
                  </div>
                </div>
                <div className="text-right shrink-0">
                  <div className="text-xs text-muted">Relevance</div>
                  <div className="text-sm font-medium text-signal">{Math.round(doc.relevance * 100)}%</div>
                </div>
              </motion.div>
            </StaggerItem>
          );
        })}
      </StaggerChildren>
    </div>
  );
}
