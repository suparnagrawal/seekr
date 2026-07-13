'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { motion, AnimatePresence } from 'framer-motion';
import { User, Lock, ArrowRight, AlertTriangle, ShieldCheck, TerminalSquare } from 'lucide-react';
import { useAuth } from '@/lib/auth-context';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import type { Role } from '@/lib/types';

const DEMO_ACCOUNTS: { role: Role; username: string; password: string; label: string; scope: string }[] = [
  { role: 'engineer', username: 'engineer', password: 'eng123', label: 'Engineer', scope: 'full · diagnostics · risk' },
  { role: 'technician', username: 'technician', password: 'tech123', label: 'Technician', scope: 'field · inspections' },
  { role: 'compliance_officer', username: 'compliance_officer', password: 'comp123', label: 'Compliance', scope: 'audit · regulation' },
  { role: 'admin', username: 'admin', password: 'admin123', label: 'Administrator', scope: 'system · users' },
];

const BOOT_LOG = [
  'mounting qdrant vector store … ok',
  'linking neo4j knowledge graph … ok',
  'warming fused retrieval pipeline … ok',
  'supervisor · asset · diagnose · comply … ready',
  'awaiting operator credential …',
];

export default function LoginPage() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [bootLine, setBootLine] = useState(0);
  const { login, isAuthenticated, isLoading, authMode, devLoginAvailable } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && isAuthenticated) router.replace('/');
  }, [isAuthenticated, isLoading, router]);

  useEffect(() => {
    if (bootLine >= BOOT_LOG.length - 1) return;
    const t = setTimeout(() => setBootLine((n) => n + 1), 520);
    return () => clearTimeout(t);
  }, [bootLine]);

  const submit = async (user?: string, pass?: string) => {
    const u = user ?? username;
    const p = pass ?? password;
    if (!u || !p) { setError('Enter operator credentials'); return; }
    setLoading(true);
    setError('');
    const res = await login(u, p);
    if (res.ok) router.push('/');
    else { setError(res.error); setLoading(false); }
  };

  const demoLogin = (a: typeof DEMO_ACCOUNTS[0]) => {
    setUsername(a.username);
    setPassword(a.password);
    submit(a.username, a.password);
  };

  return (
    <div className="min-h-screen grid lg:grid-cols-[1.05fr_1fr] bg-base">
      {/* Left — control terminal */}
      <div className="relative hidden lg:flex flex-col justify-between overflow-hidden border-r border-line p-12 scanlines">
        <div className="absolute inset-0 blueprint blueprint-drift opacity-70" />
        <div
          className="absolute inset-0"
          style={{ background: 'radial-gradient(90% 60% at 20% 0%, var(--glow), transparent 60%)' }}
        />

        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="relative flex items-center gap-3"
        >
          <div className="relative flex items-center justify-center w-10 h-10">
            <span className="absolute inset-0 rounded-md border border-signal/60 rotate-45" />
            <span className="absolute inset-[7px] rounded-full bg-signal animate-signal" />
          </div>
          <div>
            <p className="font-display text-2xl font-semibold tracking-tight text-ink leading-none">Seekr</p>
            <p className="eyebrow mt-1">Industrial Knowledge Intelligence</p>
          </div>
        </motion.div>

        <div className="relative">
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.15 }}
            className="font-display text-[3.4rem] leading-[1.03] font-light text-ink max-w-lg"
          >
            Every manual, sensor, and failure — <span className="text-signal italic">one reasoning graph.</span>
          </motion.h2>
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 0.5 }}
            className="mt-6 text-muted max-w-md leading-relaxed"
          >
            Fused dense + graph retrieval, cited answers, and specialist agents for asset,
            diagnostic, and compliance intelligence.
          </motion.p>
        </div>

        {/* Boot log */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6 }}
          className="relative panel rounded-lg p-4 max-w-md"
        >
          <div className="flex items-center gap-2 mb-2">
            <TerminalSquare className="w-3.5 h-3.5 text-signal" />
            <span className="eyebrow">boot sequence</span>
          </div>
          <div className="space-y-1 font-mono text-xs text-muted min-h-[6.5rem]">
            {BOOT_LOG.slice(0, bootLine + 1).map((line, i) => (
              <motion.div
                key={line}
                initial={{ opacity: 0, x: -6 }}
                animate={{ opacity: 1, x: 0 }}
                className="flex gap-2"
              >
                <span className="text-signal">›</span>
                <span className={i === bootLine ? 'text-ink' : ''}>{line}</span>
              </motion.div>
            ))}
          </div>
        </motion.div>
      </div>

      {/* Right — auth */}
      <div className="relative flex items-center justify-center p-6 sm:p-12">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="w-full max-w-sm"
        >
          <div className="mb-8">
            <p className="eyebrow">Access · authenticate</p>
            <h1 className="font-display text-3xl font-medium text-ink mt-2">Operator sign-in</h1>
            <div className="mt-3 inline-flex items-center gap-2 rounded-full border border-line bg-base/40 px-2.5 py-1">
              <ShieldCheck className={`w-3.5 h-3.5 ${authMode === 'real' ? 'text-mint' : 'text-signal'}`} />
              <span className="font-mono text-[0.62rem] uppercase tracking-wider text-muted">
                {authMode === 'real' ? 'JWT · identity provider' : 'dev tokens · local'}
              </span>
            </div>
          </div>

          <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="space-y-4">
            <div className="space-y-1.5">
              <label className="eyebrow">Username</label>
              <div className="relative">
                <User className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-faint" />
                <Input value={username} onChange={(e) => setUsername(e.target.value)} placeholder="operator id" className="pl-10" />
              </div>
            </div>
            <div className="space-y-1.5">
              <label className="eyebrow">Passphrase</label>
              <div className="relative">
                <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-faint" />
                <Input type="password" value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" className="pl-10" />
              </div>
            </div>

            <AnimatePresence>
              {error && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  className="flex items-center gap-2 text-sm text-ember bg-ember-soft border border-ember/20 px-3 py-2 rounded-md"
                >
                  <AlertTriangle className="w-4 h-4 shrink-0" />
                  {error}
                </motion.div>
              )}
            </AnimatePresence>

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? (
                <motion.span className="w-4 h-4 border-2 border-base border-t-transparent rounded-full" animate={{ rotate: 360 }} transition={{ duration: 0.9, repeat: Infinity, ease: 'linear' }} />
              ) : (
                <>Authenticate <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" /></>
              )}
            </Button>
          </form>

          {devLoginAvailable && (
            <div className="mt-8 pt-6 border-t border-line">
              <div className="flex items-center justify-between mb-3">
                <p className="eyebrow">Dev roles</p>
                <span className="font-mono text-[0.58rem] text-faint uppercase tracking-wider">unsigned · local only</span>
              </div>
              <div className="grid grid-cols-2 gap-2">
                {DEMO_ACCOUNTS.map((a, i) => (
                  <motion.button
                    key={a.role}
                    initial={{ opacity: 0, y: 8 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.4 + i * 0.06 }}
                    onClick={() => demoLogin(a)}
                    className="group text-left p-3 rounded-md border border-line hover:border-signal/50 hover:bg-signal-soft transition-all"
                  >
                    <span className="block text-sm font-medium text-ink">{a.label}</span>
                    <span className="block font-mono text-[0.6rem] text-faint mt-0.5">{a.scope}</span>
                  </motion.button>
                ))}
              </div>
            </div>
          )}
        </motion.div>
      </div>
    </div>
  );
}
