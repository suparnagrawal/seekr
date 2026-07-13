'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Waypoints, ShieldCheck, FolderCog, ChevronLeft, ChevronRight, LogOut,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useAuth } from '@/lib/auth-context';

const NAV_ITEMS = [
  { href: '/', icon: Waypoints, label: 'Graph Explorer', code: 'G-01', permission: 'graph:read' },
  { href: '/compliance', icon: ShieldCheck, label: 'Compliance', code: 'C-02', permission: 'compliance:read' },
  { href: '/documents', icon: FolderCog, label: 'Documents', code: 'D-03', permission: 'graph:read' },
];

function ReactorMark() {
  return (
    <div className="relative flex items-center justify-center w-9 h-9 shrink-0">
      <span className="absolute inset-0 rounded-md border border-signal/50 rotate-45" />
      <span className="absolute inset-[6px] rounded-full bg-signal animate-signal" />
      <span className="absolute inset-0 rounded-md border border-line" />
    </div>
  );
}

export function Sidebar() {
  const [collapsed, setCollapsed] = useState(false);
  const pathname = usePathname();
  const { user, logout, hasPermission } = useAuth();

  const filteredItems = NAV_ITEMS.filter((item) => hasPermission(item.permission));
  const initials = (user?.display_name || 'U').split(' ').map((s) => s[0]).slice(0, 2).join('');

  return (
    <motion.aside
      initial={false}
      animate={{ width: collapsed ? 76 : 248 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className="relative z-30 flex flex-col h-full border-r border-line bg-surface/70 backdrop-blur-xl"
    >
      {/* Wordmark */}
      <div className="flex items-center gap-3 px-4 h-16 border-b border-line">
        <ReactorMark />
        <AnimatePresence>
          {!collapsed && (
            <motion.div
              initial={{ opacity: 0, x: -8 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -8 }}
              transition={{ duration: 0.2 }}
              className="leading-none"
            >
              <h1 className="font-display text-[1.55rem] font-semibold tracking-tight text-ink">
                SEEKR
              </h1>
              <p className="eyebrow mt-1">Knowledge Foundry</p>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <div className="px-4 pt-5 pb-2">
        {!collapsed && <p className="eyebrow">Navigation</p>}
      </div>

      <nav className="flex-1 px-3 space-y-1">
        {filteredItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== '/' && pathname.startsWith(item.href));
          return (
            <Link key={item.href} href={item.href}>
              <motion.div
                className={cn(
                  'group relative flex items-center gap-3 px-3 py-2.5 rounded-md text-sm transition-colors',
                  isActive ? 'text-signal' : 'text-muted hover:text-ink hover:bg-base/40',
                )}
                whileTap={{ scale: 0.98 }}
              >
                {isActive && (
                  <motion.div
                    layoutId="sidebar-active"
                    className="absolute inset-0 rounded-md bg-signal-soft border border-signal/25"
                    transition={{ type: 'spring', stiffness: 380, damping: 32 }}
                  />
                )}
                {isActive && (
                  <motion.span
                    layoutId="sidebar-rail"
                    className="absolute left-0 top-1.5 bottom-1.5 w-[3px] rounded-full bg-signal"
                    transition={{ type: 'spring', stiffness: 380, damping: 32 }}
                  />
                )}
                <item.icon className="w-[18px] h-[18px] shrink-0 relative z-10" />
                <AnimatePresence>
                  {!collapsed && (
                    <motion.span
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                      exit={{ opacity: 0, x: -8 }}
                      className="relative z-10 flex-1 whitespace-nowrap font-medium"
                    >
                      {item.label}
                    </motion.span>
                  )}
                </AnimatePresence>
                {!collapsed && (
                  <span className="relative z-10 font-mono text-[0.62rem] text-faint">{item.code}</span>
                )}
              </motion.div>
            </Link>
          );
        })}
      </nav>

      {/* User */}
      <div className="border-t border-line p-3">
        <div className={cn('flex items-center gap-3 px-2 py-1.5', collapsed && 'justify-center')}>
          <div className="w-9 h-9 rounded-md border border-line-strong bg-base/60 flex items-center justify-center shrink-0">
            <span className="font-mono text-xs font-semibold text-signal uppercase">{initials}</span>
          </div>
          <AnimatePresence>
            {!collapsed && (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex-1 min-w-0"
              >
                <p className="text-sm font-medium text-ink truncate">{user?.display_name}</p>
                <p className="font-mono text-[0.62rem] text-faint uppercase tracking-wider">{user?.role?.replace('_', ' ')}</p>
              </motion.div>
            )}
          </AnimatePresence>
          {!collapsed && (
            <button onClick={logout} className="text-faint hover:text-ember transition-colors" title="Sign out">
              <LogOut className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      <button
        onClick={() => setCollapsed(!collapsed)}
        className="absolute -right-3 top-[68px] w-6 h-6 rounded-full bg-panel border border-line-strong flex items-center justify-center text-muted hover:text-signal hover:border-signal/50 transition-colors z-40"
        title={collapsed ? 'Expand' : 'Collapse'}
      >
        {collapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronLeft className="w-3 h-3" />}
      </button>
    </motion.aside>
  );
}
