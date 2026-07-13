'use client';

import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { ChevronDown, AlertTriangle, AlertCircle, CheckCircle2, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import type { ComplianceGap } from '@/lib/types';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { cn, formatDate } from '@/lib/utils';

interface GapCardProps {
  gap: ComplianceGap;
}

const statusConfig = {
  red: {
    icon: AlertTriangle,
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    border: 'border-red-500/20',
    badge: 'destructive' as const,
    label: 'Critical',
  },
  amber: {
    icon: AlertCircle,
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
    border: 'border-amber-500/20',
    badge: 'warning' as const,
    label: 'Warning',
  },
  green: {
    icon: CheckCircle2,
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    border: 'border-emerald-500/20',
    badge: 'success' as const,
    label: 'Compliant',
  },
};

export function GapCard({ gap }: GapCardProps) {
  const [expanded, setExpanded] = useState(false);
  const config = statusConfig[gap.status];
  const Icon = config.icon;

  return (
    <Card className={cn('transition-all', expanded && 'ring-1 ring-zinc-700')}>
      <CardContent className="p-4">
        <div
          className="flex items-center gap-3 cursor-pointer"
          onClick={() => setExpanded(!expanded)}
        >
          <div className={cn('w-9 h-9 rounded-lg flex items-center justify-center shrink-0', config.bg)}>
            <Icon className={cn('w-4 h-4', config.color)} />
          </div>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <span className="text-sm font-medium text-zinc-200 truncate">{gap.equipment_name}</span>
              <Badge variant={config.badge}>{config.label}</Badge>
            </div>
            <p className="text-xs text-zinc-500 mt-0.5">{gap.regulation}</p>
          </div>
          <motion.div
            animate={{ rotate: expanded ? 180 : 0 }}
            transition={{ duration: 0.2 }}
          >
            <ChevronDown className="w-4 h-4 text-zinc-500" />
          </motion.div>
        </div>

        <AnimatePresence>
          {expanded && (
            <motion.div
              initial={{ height: 0, opacity: 0 }}
              animate={{ height: 'auto', opacity: 1 }}
              exit={{ height: 0, opacity: 0 }}
              transition={{ duration: 0.2 }}
              className="overflow-hidden"
            >
              <div className="pt-3 mt-3 border-t border-zinc-800 space-y-3">
                {gap.missing_evidence.length > 0 ? (
                  <div>
                    <p className="text-xs font-medium text-zinc-400 mb-1.5">Missing Evidence</p>
                    <ul className="space-y-1">
                      {gap.missing_evidence.map((item, i) => (
                        <li key={i} className="flex items-start gap-2 text-sm text-zinc-300">
                          <span className="text-red-500 mt-0.5">•</span>
                          {item}
                        </li>
                      ))}
                    </ul>
                  </div>
                ) : (
                  <p className="text-sm text-emerald-400">All evidence documentation is up to date.</p>
                )}

                <div className="flex items-center justify-between text-xs text-zinc-500">
                  <span>Last checked: {formatDate(gap.last_checked)}</span>
                  <Link
                    href={`/entity/${encodeURIComponent(gap.equipment_tag)}`}
                    className="flex items-center gap-1 text-blue-400 hover:underline"
                  >
                    View details <ExternalLink className="w-3 h-3" />
                  </Link>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </CardContent>
    </Card>
  );
}
