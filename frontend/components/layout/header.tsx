'use client';

import { useState, useCallback, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Bell, X, Sun, Moon, Activity } from 'lucide-react';
import { cn } from '@/lib/utils';
import { useTheme } from '@/lib/theme-context';
import { checkLiveness } from '@/lib/api';

type LinkState = 'live' | 'down' | 'checking';

export function Header() {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);
  const [showAlerts, setShowAlerts] = useState(false);
  const [link, setLink] = useState<LinkState>('checking');
  const router = useRouter();
  const { theme, toggle } = useTheme();

  useEffect(() => {
    let active = true;
    const ping = async () => {
      try { await checkLiveness(); if (active) setLink('live'); }
      catch { if (active) setLink('down'); }
    };
    ping();
    const id = setInterval(ping, 20000);
    return () => { active = false; clearInterval(id); };
  }, []);

  const handleSearch = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/entity/${encodeURIComponent(searchQuery.trim())}`);
      setSearchQuery('');
    }
  }, [searchQuery, router]);

  const linkColor = link === 'live' ? 'bg-mint' : link === 'down' ? 'bg-ember' : 'bg-signal';
  const linkLabel = link === 'live' ? 'API online' : link === 'down' ? 'API offline' : 'probing';

  return (
    <header className="relative z-50 h-14 border-b border-line bg-surface/60 backdrop-blur-xl flex items-center px-4 gap-3">
      <form onSubmit={handleSearch} className="flex-1 max-w-xl relative">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-faint" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => setSearchFocused(true)}
            onBlur={() => setTimeout(() => setSearchFocused(false), 120)}
            placeholder="Locate equipment, document, or procedure…"
            className={cn(
              'w-full h-9 pl-10 pr-16 rounded-md text-sm bg-base/40 border transition-all duration-200',
              'text-ink placeholder:text-faint font-sans',
              searchFocused ? 'border-signal ring-2 ring-signal/20' : 'border-line hover:border-line-strong',
            )}
          />
          <kbd className="absolute right-3 top-1/2 -translate-y-1/2 font-mono text-[0.6rem] text-faint border border-line rounded px-1.5 py-0.5">
            ⏎ GO
          </kbd>
          <AnimatePresence>
            {searchFocused && searchQuery && (
              <motion.div
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 4 }}
                className="absolute top-full left-0 right-0 mt-2 z-50"
              >
                <div className="panel panel-glow rounded-md p-1.5">
                  <button
                    type="submit"
                    className="w-full flex items-center gap-2 text-left px-3 py-2 text-sm text-muted hover:bg-signal-soft hover:text-ink rounded transition-colors"
                  >
                    <Search className="w-3.5 h-3.5" />
                    Open entity <span className="font-mono text-signal">{searchQuery}</span>
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </form>

      {/* Link status */}
      <div className="hidden sm:flex items-center gap-2 px-2.5 h-9 rounded-md border border-line bg-base/30">
        <span className="relative flex w-2 h-2">
          <span className={cn('absolute inline-flex h-full w-full rounded-full opacity-70', linkColor)} />
          <span className={cn('relative inline-flex rounded-full h-2 w-2', linkColor, link !== 'down' && 'animate-signal')} />
        </span>
        <span className="font-mono text-[0.62rem] uppercase tracking-wider text-muted">{linkLabel}</span>
      </div>

      <button
        onClick={toggle}
        className="relative p-2 rounded-md text-muted hover:text-signal hover:bg-base/40 transition-colors"
        title={theme === 'dark' ? 'Switch to light' : 'Switch to dark'}
      >
        <AnimatePresence mode="wait" initial={false}>
          <motion.span
            key={theme}
            initial={{ rotate: -90, opacity: 0 }}
            animate={{ rotate: 0, opacity: 1 }}
            exit={{ rotate: 90, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="block"
          >
            {theme === 'dark' ? <Sun className="w-[18px] h-[18px]" /> : <Moon className="w-[18px] h-[18px]" />}
          </motion.span>
        </AnimatePresence>
      </button>

      <div className="relative">
        <button
          onClick={() => setShowAlerts(!showAlerts)}
          className="relative p-2 rounded-md text-muted hover:text-ink hover:bg-base/40 transition-colors"
          title="Alerts"
        >
          <Bell className="w-[18px] h-[18px]" />
        </button>
        <AnimatePresence>
          {showAlerts && (
            <motion.div
              initial={{ opacity: 0, y: 8, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.97 }}
              transition={{ duration: 0.2 }}
              className="absolute right-0 top-full mt-2 w-96 panel panel-glow rounded-lg z-50 overflow-hidden"
            >
              <div className="px-4 py-3 border-b border-line flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Activity className="w-4 h-4 text-signal" />
                  <h3 className="text-sm font-semibold text-ink">Signal Feed</h3>
                </div>
                <button onClick={() => setShowAlerts(false)} className="text-faint hover:text-ink">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="px-4 py-8 text-center">
                <p className="text-sm text-muted">No active alerts.</p>
                <p className="font-mono text-[0.62rem] text-faint mt-1 uppercase tracking-wider">
                  backend telemetry will surface here
                </p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </header>
  );
}
