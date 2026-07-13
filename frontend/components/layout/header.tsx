'use client';

import { useState, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { Search, Bell, X } from 'lucide-react';
import { cn } from '@/lib/utils';

export function Header() {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchFocused, setSearchFocused] = useState(false);
  const [showAlerts, setShowAlerts] = useState(false);
  const router = useRouter();

  const handleSearch = useCallback((e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      router.push(`/entity/${encodeURIComponent(searchQuery.trim())}`);
      setSearchQuery('');
    }
  }, [searchQuery, router]);

  return (
    <header className="h-14 border-b border-zinc-800 bg-zinc-950/60 backdrop-blur-xl flex items-center px-4 gap-4">
      <form onSubmit={handleSearch} className="flex-1 max-w-xl relative">
        <motion.div
          animate={{ scale: searchFocused ? 1.01 : 1 }}
          className="relative"
        >
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onFocus={() => setSearchFocused(true)}
            onBlur={() => setSearchFocused(false)}
            placeholder="Search equipment, documents, procedures..."
            className={cn(
              'w-full h-9 pl-10 pr-4 rounded-lg text-sm bg-zinc-900/50 border transition-all duration-200',
              'text-zinc-200 placeholder:text-zinc-500',
              searchFocused
                ? 'border-blue-500/50 ring-1 ring-blue-500/20'
                : 'border-zinc-800 hover:border-zinc-700',
            )}
          />
          <AnimatePresence>
            {searchFocused && searchQuery && (
              <motion.div
                initial={{ opacity: 0, y: 4 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: 4 }}
                className="absolute top-full left-0 right-0 mt-1 z-50"
              >
                <div className="bg-zinc-900 border border-zinc-700 rounded-lg shadow-2xl p-2">
                  <button
                    type="submit"
                    className="w-full text-left px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-800 rounded-md transition-colors"
                  >
                    Search for <span className="text-blue-400 font-medium">&quot;{searchQuery}&quot;</span>
                  </button>
                  <button
                    type="button"
                    onClick={() => {
                      router.push(`/entity/${encodeURIComponent(searchQuery.trim())}`);
                      setSearchQuery('');
                    }}
                    className="w-full text-left px-3 py-2 text-sm text-zinc-300 hover:bg-zinc-800 rounded-md transition-colors"
                  >
                    Go to entity <span className="text-cyan-400 font-medium">{searchQuery}</span>
                  </button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      </form>

      <div className="relative">
        <motion.button
          onClick={() => setShowAlerts(!showAlerts)}
          className="relative p-2 text-zinc-400 hover:text-zinc-200 transition-colors"
          whileTap={{ scale: 0.95 }}
        >
          <Bell className="w-5 h-5" />
        </motion.button>

        <AnimatePresence>
          {showAlerts && (
            <motion.div
              initial={{ opacity: 0, y: 8, scale: 0.95 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: 8, scale: 0.95 }}
              transition={{ duration: 0.2 }}
              className="absolute right-0 top-full mt-2 w-96 bg-zinc-900 border border-zinc-700 rounded-xl shadow-2xl z-50 overflow-hidden"
            >
              <div className="px-4 py-3 border-b border-zinc-800 flex items-center justify-between">
                <h3 className="text-sm font-semibold text-zinc-200">Alerts</h3>
                <button onClick={() => setShowAlerts(false)} className="text-zinc-500 hover:text-zinc-300">
                  <X className="w-4 h-4" />
                </button>
              </div>
              <div className="px-4 py-6">
                <p className="text-sm text-zinc-500 text-center">Alerts will appear here when the backend reports them.</p>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </header>
  );
}
