'use client';

import { motion } from 'framer-motion';
import { Bot, User, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import type { CopilotMessage } from '@/lib/types';
import { CitationChip } from './citation-chip';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';

interface MessageBubbleProps {
  message: CopilotMessage;
  entityTag: string;
}

export function MessageBubble({ message, entityTag }: MessageBubbleProps) {
  const isUser = message.role === 'user';

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={cn('flex gap-3', isUser && 'flex-row-reverse')}
    >
      <div className={cn(
        'w-8 h-8 rounded-full flex items-center justify-center shrink-0',
        isUser
          ? 'bg-gradient-to-br from-violet-500 to-fuchsia-500'
          : 'bg-gradient-to-br from-blue-500 to-cyan-400',
      )}>
        {isUser ? <User className="w-4 h-4 text-white" /> : <Bot className="w-4 h-4 text-white" />}
      </div>

      <div className={cn('max-w-[80%] space-y-2', isUser && 'text-right')}>
        <div className={cn(
          'rounded-2xl px-4 py-3 text-sm leading-relaxed',
          isUser
            ? 'bg-blue-600 text-white rounded-tr-sm'
            : 'bg-zinc-800/80 text-zinc-200 rounded-tl-sm border border-zinc-700/50',
        )}>
          <p className="whitespace-pre-wrap">{message.content}</p>
          {message.streaming && (
            <motion.span
              className="inline-block w-2 h-4 bg-blue-400 ml-0.5"
              animate={{ opacity: [1, 0] }}
              transition={{ duration: 0.8, repeat: Infinity }}
            />
          )}
        </div>

        {message.citations && message.citations.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {message.citations.map((cit, i) => (
              <CitationChip key={`${cit.doc_id}-${i}`} citation={cit} />
            ))}
          </div>
        )}

        {message.agent_trigger && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
          >
            <Link href={`/agents/diagnose/${message.agent_trigger.job_id}`}>
              <Badge variant="warning" className="cursor-pointer hover:bg-amber-500/30 transition-colors">
                <ExternalLink className="w-3 h-3" />
                Agent triggered: {message.agent_trigger.worker}
              </Badge>
            </Link>
          </motion.div>
        )}
      </div>
    </motion.div>
  );
}
