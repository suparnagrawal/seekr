'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { motion } from 'framer-motion';
import { Activity, Shield, TrendingUp, Loader2 } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useAuth } from '@/lib/auth-context';

interface AgentInvokeBarProps {
  tag: string;
}

export function AgentInvokeBar({ tag }: AgentInvokeBarProps) {
  const [diagnosing, setDiagnosing] = useState(false);
  const router = useRouter();
  const { hasPermission } = useAuth();

  const handleDiagnose = () => {
    setDiagnosing(true);
    const jobId = `diag-${Date.now()}`;
    router.push(`/agents/diagnose/${jobId}?tag=${encodeURIComponent(tag)}`);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: -4 }}
      animate={{ opacity: 1, y: 0 }}
      className="px-5 py-3 border-b border-zinc-800 flex items-center gap-2 overflow-x-auto"
    >
      <span className="text-xs text-zinc-500 shrink-0">Agents:</span>

      {hasPermission('agents:diagnose') && (
        <Button
          variant="outline"
          size="sm"
          onClick={handleDiagnose}
          disabled={diagnosing}
          className="shrink-0"
        >
          {diagnosing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Activity className="w-3.5 h-3.5" />}
          Diagnose
        </Button>
      )}

      {hasPermission('agents:comply') && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => router.push('/compliance')}
          className="shrink-0"
        >
          <Shield className="w-3.5 h-3.5" />
          Compliance
        </Button>
      )}

      {hasPermission('agents:risk') && (
        <Button
          variant="outline"
          size="sm"
          onClick={() => router.push(`/entity/${encodeURIComponent(tag)}?tab=risk`)}
          className="shrink-0"
        >
          <TrendingUp className="w-3.5 h-3.5" />
          Risk Assessment
        </Button>
      )}
    </motion.div>
  );
}
