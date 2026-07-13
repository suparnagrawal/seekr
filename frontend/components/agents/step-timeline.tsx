'use client';

import { motion } from 'framer-motion';
import { CheckCircle2, Loader2, XCircle, Clock } from 'lucide-react';
import type { ReasoningStep } from '@/lib/types';
import { cn } from '@/lib/utils';

interface StepTimelineProps {
  steps: ReasoningStep[];
  activeIndex?: number;
}

const statusConfig = {
  completed: { icon: CheckCircle2, color: 'text-emerald-400', ring: 'ring-emerald-500/30' },
  running: { icon: Loader2, color: 'text-blue-400', ring: 'ring-blue-500/30' },
  failed: { icon: XCircle, color: 'text-red-400', ring: 'ring-red-500/30' },
  pending: { icon: Clock, color: 'text-zinc-500', ring: 'ring-zinc-700' },
};

const workerColors: Record<string, string> = {
  retriever: 'bg-cyan-500/20 text-cyan-300',
  analyzer: 'bg-violet-500/20 text-violet-300',
  reasoner: 'bg-amber-500/20 text-amber-300',
  recommender: 'bg-emerald-500/20 text-emerald-300',
};

export function StepTimeline({ steps, activeIndex }: StepTimelineProps) {
  return (
    <div className="divide-y divide-zinc-800/50">
      {steps.map((step, i) => {
        const config = statusConfig[step.status];
        const Icon = config.icon;
        const isActive = activeIndex === i;

        return (
          <motion.div
            key={step.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: i * 0.08 }}
            className={cn(
              'flex items-center gap-4 px-5 py-3.5 transition-colors',
              isActive && 'bg-blue-500/5',
            )}
          >
            <div className={cn('w-8 h-8 rounded-full flex items-center justify-center ring-2 shrink-0', config.ring)}>
              <Icon className={cn('w-4 h-4', config.color, step.status === 'running' && 'animate-spin')} />
            </div>

            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-zinc-200">{step.action}</span>
                <span className={cn('text-xs px-1.5 py-0.5 rounded', workerColors[step.worker] || 'bg-zinc-800 text-zinc-400')}>
                  {step.worker}
                </span>
              </div>
              <p className="text-xs text-zinc-500 mt-0.5 truncate">{step.detail}</p>
            </div>

            {step.duration_ms && (
              <span className="text-xs text-zinc-600 tabular-nums shrink-0">
                {(step.duration_ms / 1000).toFixed(1)}s
              </span>
            )}
          </motion.div>
        );
      })}
    </div>
  );
}
