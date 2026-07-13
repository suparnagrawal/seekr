'use client';

import { motion } from 'framer-motion';

/** Full-screen boot sequence shown while the session hydrates. */
export function BootLoader() {
  return (
    <div className="fixed inset-0 flex items-center justify-center bg-base blueprint">
      <div className="flex flex-col items-center gap-5">
        <div className="relative w-14 h-14">
          <motion.span
            className="absolute inset-0 rounded-full border border-signal/40"
            animate={{ scale: [1, 1.6], opacity: [0.7, 0] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: 'easeOut' }}
          />
          <motion.span
            className="absolute inset-0 rounded-full border border-signal/40"
            animate={{ scale: [1, 1.6], opacity: [0.7, 0] }}
            transition={{ duration: 1.6, repeat: Infinity, ease: 'easeOut', delay: 0.8 }}
          />
          <div className="absolute inset-[22%] rounded-full bg-signal animate-signal" />
        </div>
        <p className="eyebrow">Seekr · initializing</p>
      </div>
    </div>
  );
}
