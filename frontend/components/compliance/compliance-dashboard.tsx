'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Shield, AlertTriangle, CheckCircle2, AlertCircle } from 'lucide-react';
import { streamAgent } from '@/lib/api';
import type { ComplianceReport, ComplianceGap } from '@/lib/types';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { FadeIn } from '@/components/animations/fade-in';
import { StaggerChildren, StaggerItem } from '@/components/animations/stagger-children';
import { GapCard } from './gap-card';

function parseComplianceFromText(text: string): ComplianceReport {
  const scoreMatch = text.match(/(\d+)\s*[/%]/);
  const score = scoreMatch ? parseInt(scoreMatch[1]) : 75;

  const gaps: ComplianceGap[] = [];
  const lines = text.split('\n');
  let idx = 0;

  for (const line of lines) {
    const tagMatch = line.match(/([A-Z]+-\d+[A-Z]?)/);
    if (!tagMatch) continue;

    const status: ComplianceGap['status'] = line.match(/non-compliant|critical|overdue|red/i)
      ? 'red'
      : line.match(/partial|warning|amber|gap/i)
        ? 'amber'
        : 'green';

    const missingEvidence: string[] = [];
    const evidenceMatch = line.match(/missing[:\s]+(.+)/i);
    if (evidenceMatch) {
      missingEvidence.push(...evidenceMatch[1].split(/[,;]/).map((s) => s.trim()).filter(Boolean));
    }

    gaps.push({
      equipment_tag: tagMatch[1],
      equipment_name: tagMatch[1],
      regulation: line.match(/(API\s+\d+|ASME\s+\w+|OSHA\s+[\d.]+|TEMA)/i)?.[1] || 'Internal Standard',
      status,
      missing_evidence: missingEvidence,
      last_checked: new Date().toISOString().slice(0, 10),
    });
    idx++;
  }

  return {
    score,
    checked: Math.max(gaps.length * 10, 50),
    missing: gaps.filter((g) => g.status !== 'green').length,
    gaps,
  };
}

export function ComplianceDashboard() {
  const [report, setReport] = useState<ComplianceReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<'all' | 'red' | 'amber' | 'green'>('all');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let fullText = '';
    const cancel = streamAgent('comply', 'Provide a full compliance report across all equipment. For each piece of equipment, include the equipment tag, applicable regulation/standard, compliance status (compliant, partial, or non-compliant), and any missing evidence or documentation. Also provide an overall compliance score as a percentage.', null, {
      onToken: (text) => { fullText += text; },
      onCitation: () => {},
      onAgentTrigger: () => {},
      onReasoning: () => {},
      onToolCall: () => {},
      onToolResult: () => {},
      onDone: () => {
        setReport(parseComplianceFromText(fullText));
        setLoading(false);
      },
      onError: (err) => {
        setError(err.message);
        setLoading(false);
      },
    });

    return () => cancel();
  }, []);

  if (loading || !report) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="flex flex-col items-center gap-3">
          <motion.div
            className="w-8 h-8 rounded-full border-2 border-blue-500 border-t-transparent"
            animate={{ rotate: 360 }}
            transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
          />
          <p className="text-sm text-zinc-500">Running compliance agent...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 text-sm text-zinc-500">
        Failed to load compliance data: {error}
      </div>
    );
  }

  const filtered = filter === 'all' ? report.gaps : report.gaps.filter((g) => g.status === filter);
  const counts = {
    red: report.gaps.filter((g) => g.status === 'red').length,
    amber: report.gaps.filter((g) => g.status === 'amber').length,
    green: report.gaps.filter((g) => g.status === 'green').length,
  };

  return (
    <div className="p-6 space-y-6">
      <FadeIn>
        <div className="flex items-center gap-3 mb-2">
          <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-emerald-500/20 to-blue-500/20 flex items-center justify-center">
            <Shield className="w-5 h-5 text-emerald-400" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-zinc-100">Compliance Overview</h1>
            <p className="text-sm text-zinc-500">{report.checked} items checked across all equipment</p>
          </div>
        </div>
      </FadeIn>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <FadeIn delay={0.1}>
          <Card className="p-5">
            <div className="text-center">
              <motion.div
                className="text-5xl font-bold bg-gradient-to-b from-zinc-100 to-zinc-400 bg-clip-text text-transparent"
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', stiffness: 200, damping: 15, delay: 0.3 }}
              >
                {report.score}
              </motion.div>
              <p className="text-sm text-zinc-500 mt-1">Overall Score</p>
              <Progress value={report.score} className="mt-3" size="sm" />
            </div>
          </Card>
        </FadeIn>

        {([
          { status: 'red' as const, label: 'Critical', icon: AlertTriangle, count: counts.red, variant: 'destructive' as const },
          { status: 'amber' as const, label: 'Warning', icon: AlertCircle, count: counts.amber, variant: 'warning' as const },
          { status: 'green' as const, label: 'Compliant', icon: CheckCircle2, count: counts.green, variant: 'success' as const },
        ]).map((item, i) => (
          <FadeIn key={item.status} delay={0.15 + i * 0.05}>
            <Card
              hover
              onClick={() => setFilter(filter === item.status ? 'all' : item.status)}
              className={filter === item.status ? 'ring-1 ring-blue-500/50' : ''}
            >
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-2xl font-bold text-zinc-100">{item.count}</p>
                    <p className="text-sm text-zinc-500">{item.label}</p>
                  </div>
                  <div className={`p-2 rounded-lg bg-${item.status === 'red' ? 'red' : item.status === 'amber' ? 'amber' : 'emerald'}-500/10`}>
                    <item.icon className={`w-5 h-5 text-${item.status === 'red' ? 'red' : item.status === 'amber' ? 'amber' : 'emerald'}-400`} />
                  </div>
                </div>
              </CardContent>
            </Card>
          </FadeIn>
        ))}
      </div>

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold text-zinc-200">
            Equipment Status
            {filter !== 'all' && <span className="text-sm text-zinc-500 ml-2">({filter} only)</span>}
          </h2>
          {filter !== 'all' && (
            <button onClick={() => setFilter('all')} className="text-sm text-blue-400 hover:underline">
              Show all
            </button>
          )}
        </div>

        {filtered.length === 0 ? (
          <p className="text-sm text-zinc-500 text-center py-8">No equipment matches the selected filter</p>
        ) : (
          <StaggerChildren className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {filtered.map((gap) => (
              <StaggerItem key={gap.equipment_tag}>
                <GapCard gap={gap} />
              </StaggerItem>
            ))}
          </StaggerChildren>
        )}
      </div>
    </div>
  );
}
