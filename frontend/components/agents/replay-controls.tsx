'use client';

import { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';
import { Play, Pause, SkipForward, SkipBack } from 'lucide-react';
import { Button } from '@/components/ui/button';

interface ReplayControlsProps {
  speed: number;
  onSpeedChange: (speed: number) => void;
  onTick: () => void;
  isPlaying: boolean;
  currentStep: number;
  totalSteps: number;
}

export function ReplayControls({ speed, onSpeedChange, onTick, isPlaying, currentStep, totalSteps }: ReplayControlsProps) {
  const intervalRef = useRef<ReturnType<typeof setInterval>>(undefined);

  useEffect(() => {
    if (isPlaying) {
      intervalRef.current = setInterval(onTick, 1500 / speed);
      return () => clearInterval(intervalRef.current);
    }
  }, [isPlaying, speed, onTick]);

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      className="flex items-center gap-3 bg-zinc-900/90 backdrop-blur-sm border border-zinc-800 rounded-lg px-4 py-2"
    >
      <span className="text-xs text-zinc-500">Replay</span>

      <div className="flex items-center gap-1">
        {[0.5, 1, 2].map((s) => (
          <Button
            key={s}
            variant={speed === s ? 'default' : 'ghost'}
            size="sm"
            className="h-7 px-2 text-xs"
            onClick={() => onSpeedChange(s)}
          >
            {s}x
          </Button>
        ))}
      </div>

      <div className="flex-1 mx-2">
        <div className="h-1.5 bg-zinc-800 rounded-full overflow-hidden">
          <motion.div
            className="h-full bg-blue-500 rounded-full"
            animate={{ width: `${((currentStep + 1) / totalSteps) * 100}%` }}
            transition={{ duration: 0.3 }}
          />
        </div>
      </div>

      <span className="text-xs text-zinc-400 tabular-nums">
        {currentStep + 1}/{totalSteps}
      </span>
    </motion.div>
  );
}
