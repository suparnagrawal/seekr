'use client';

import { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { X, Sparkles } from 'lucide-react';
import { CopilotChat } from './copilot-chat';

/**
 * Global "Ask Seekr" assistant — a floating launcher available on every
 * dashboard route that slides in a copilot drawer. Toggle with ⌘K / Ctrl+K,
 * close with Esc. Runs an un-focused query (no entity tag) so it can answer
 * across all equipment, documents, and compliance.
 */
export function AssistantDock() {
  const [open, setOpen] = useState(false);

  const toggle = useCallback(() => setOpen((o) => !o), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        toggle();
      } else if (e.key === 'Escape') {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [toggle]);

  return (
    <>
      {/* Launcher */}
      <div className="fixed bottom-6 right-6 z-[60] flex flex-col items-end gap-2">
        <AnimatePresence>
          {!open && (
            <motion.button
              initial={{ scale: 0, opacity: 0, rotate: -30 }}
              animate={{ scale: 1, opacity: 1, rotate: 0 }}
              exit={{ scale: 0, opacity: 0 }}
              whileHover={{ scale: 1.06 }}
              whileTap={{ scale: 0.94 }}
              transition={{ type: 'spring', stiffness: 320, damping: 22 }}
              onClick={toggle}
              className="group relative flex items-center gap-2.5 h-12 pl-3.5 pr-4 rounded-full bg-signal text-base font-medium shadow-[0_10px_30px_-8px_var(--signal)]"
              title="Ask Seekr (⌘K)"
            >
              <span className="absolute inset-0 rounded-full border border-signal-bright animate-signal" />
              <Sparkles className="w-[18px] h-[18px] relative z-10" />
              <span className="relative z-10 text-sm">Ask Seekr</span>
              <kbd className="relative z-10 hidden sm:inline font-mono text-[0.6rem] bg-base/25 rounded px-1.5 py-0.5">⌘K</kbd>
            </motion.button>
          )}
        </AnimatePresence>
      </div>

      {/* Drawer */}
      <AnimatePresence>
        {open && (
          <>
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
              className="fixed inset-0 z-[65] bg-base-deep/50 backdrop-blur-[2px]"
            />
            <motion.aside
              initial={{ x: '100%', opacity: 0.6 }}
              animate={{ x: 0, opacity: 1 }}
              exit={{ x: '100%', opacity: 0.6 }}
              transition={{ type: 'spring', stiffness: 320, damping: 34 }}
              className="fixed top-0 right-0 z-[70] h-full w-[440px] max-w-[94vw] flex flex-col bg-surface border-l border-line shadow-[-24px_0_60px_-30px_var(--shadow)]"
            >
              <div className="flex items-center justify-between px-5 h-14 border-b border-line shrink-0">
                <div className="flex items-center gap-2.5">
                  <div className="relative flex items-center justify-center w-7 h-7">
                    <span className="absolute inset-0 rounded-md border border-signal/50 rotate-45" />
                    <Sparkles className="w-3.5 h-3.5 text-signal relative z-10" />
                  </div>
                  <div className="leading-none">
                    <p className="font-display text-lg text-ink">Seekr Assistant</p>
                    <p className="eyebrow mt-0.5">global · cited</p>
                  </div>
                </div>
                <button
                  onClick={() => setOpen(false)}
                  className="p-2 rounded-md text-muted hover:text-ink hover:bg-base/40 transition-colors"
                  title="Close (Esc)"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="flex-1 min-h-0">
                <CopilotChat entityTag={null} />
              </div>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
