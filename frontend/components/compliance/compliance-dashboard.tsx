'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Shield, AlertTriangle, CheckCircle2, AlertCircle } from 'lucide-react';
import { streamAgent } from '@/lib/api';
import type { ComplianceReport, ComplianceGap } from '@/lib/types';
import { Card, CardContent } from '@/components/ui/card';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';
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
        <div className="flex flex-col items-center gap-4">
          <div className="relative w-10 h-10">
            <motion.span className="absolute inset-0 rounded-full border border-signal/40" animate={{ scale: [1, 1.6], opacity: [0.7, 0] }} transition={{ duration: 1.5, repeat: Infinity }} />
            <div className="absolute inset-[30%] rounded-full bg-signal animate-signal" />
          </div>
          <p className="font-mono text-xs uppercase tracking-widest text-muted">running compliance agent…</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-64 text-sm text-muted">
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

  const statCards = [
    { status: 'red' as const, label: 'Critical', icon: AlertTriangle, count: counts.red, tone: 'text-ember', chip: 'bg-ember-soft' },
    { status: 'amber' as const, label: 'Warning', icon: AlertCircle, count: counts.amber, tone: 'text-signal', chip: 'bg-signal-soft' },
    { status: 'green' as const, label: 'Compliant', icon: CheckCircle2, count: counts.green, tone: 'text-mint', chip: 'bg-mint-soft' },
  ];

  return (
    <div className="p-6 space-y-6">
      <FadeIn>
        <p className="eyebrow">Regulatory · continuous audit</p>
        <div className="flex items-center gap-3 mt-2">
          <div className="w-10 h-10 rounded-md border border-line bg-mint-soft flex items-center justify-center">
            <Shield className="w-5 h-5 text-mint" />
          </div>
          <div>
            <h1 className="font-display text-3xl font-medium text-ink">Compliance Overview</h1>
            <p className="text-sm text-muted">{report.checked} checks across the asset base</p>
          </div>
        </div>
      </FadeIn>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <FadeIn delay={0.1}>
          <Card ticked className="p-6">
            <div className="text-center">
              <p className="eyebrow mb-2">overall score</p>
              <motion.div
                className="font-display text-6xl font-light text-ink data-num"
                initial={{ scale: 0.6, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ type: 'spring', stiffness: 200, damping: 16, delay: 0.3 }}
              >
                {report.score}
              </motion.div>
              <Progress value={report.score} className="mt-4" size="sm" />
            </div>
          </Card>
        </FadeIn>

        {statCards.map((item, i) => (
          <FadeIn key={item.status} delay={0.15 + i * 0.05}>
            <Card
              hover
              onClick={() => setFilter(filter === item.status ? 'all' : item.status)}
              className={filter === item.status ? 'border-signal/50 shadow-[0_18px_50px_-30px_var(--shadow)]' : ''}
            >
              <CardContent className="p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className={cn('font-display text-4xl font-light data-num', item.tone)}>{item.count}</p>
                    <p className="eyebrow mt-1">{item.label}</p>
                  </div>
                  <div className={cn('p-2.5 rounded-md border border-line', item.chip)}>
                    <item.icon className={cn('w-5 h-5', item.tone)} />
                  </div>
                </div>
              </CardContent>
            </Card>
          </FadeIn>
        ))}
      </div>

      <div>
        <div className="flex items-center justify-between mb-4">
          <h2 className="font-display text-xl text-ink">
            Equipment Status
            {filter !== 'all' && <span className="text-sm font-sans text-faint ml-2">· {filter} only</span>}
          </h2>
          {filter !== 'all' && (
            <button onClick={() => setFilter('all')} className="text-sm text-signal hover:underline">
              Show all
            </button>
          )}
        </div>

        {filtered.length === 0 ? (
          <p className="text-sm text-muted text-center py-8">No equipment matches the selected filter</p>
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
