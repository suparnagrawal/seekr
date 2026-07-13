'use client';

import { motion } from 'framer-motion';
import type { ReactNode } from 'react';

interface PulseGlowProps {
  children: ReactNode;
  color?: string;
  active?: boolean;
  className?: string;
}

export function PulseGlow({ children, color = 'rgba(59,130,246,0.3)', active = true, className }: PulseGlowProps) {
  if (!active) return <div className={className}>{children}</div>;

  return (
    <motion.div
      className={className}
      animate={{
        boxShadow: [
          `0 0 0 0 ${color}`,
          `0 0 20px 4px ${color}`,
          `0 0 0 0 ${color}`,
        ],
      }}
      transition={{
        duration: 2,
        repeat: Infinity,
        ease: 'easeInOut',
      }}
    >
      {children}
    </motion.div>
  );
}
