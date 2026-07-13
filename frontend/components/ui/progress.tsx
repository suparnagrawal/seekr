'use client';

import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';

interface ProgressProps {
  value: number;
  max?: number;
  className?: string;
  color?: string;
  showLabel?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const sizeStyles = {
  sm: 'h-1.5',
  md: 'h-2.5',
  lg: 'h-4',
};

export function Progress({ value, max = 100, className, color, showLabel = false, size = 'md' }: ProgressProps) {
  const percentage = Math.min(100, Math.max(0, (value / max) * 100));

  const barColor =
    color ??
    (percentage >= 80 ? 'bg-mint' : percentage >= 50 ? 'bg-signal' : 'bg-ember');

  return (
    <div className={cn('flex items-center gap-3', className)}>
      <div className={cn('flex-1 overflow-hidden rounded-full bg-base/60 border border-line', sizeStyles[size])}>
        <motion.div
          className={cn('h-full rounded-full relative', barColor)}
          initial={{ width: 0 }}
          animate={{ width: `${percentage}%` }}
          transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }}
        >
          <span className="absolute inset-0 animate-shimmer opacity-60" />
        </motion.div>
      </div>
      {showLabel && (
        <span className="data-num text-sm text-ink">{Math.round(percentage)}%</span>
      )}
    </div>
  );
}
