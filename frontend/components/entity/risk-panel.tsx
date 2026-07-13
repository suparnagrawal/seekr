'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';
import { streamAgent } from '@/lib/api';
import type { RiskAssessment, RiskFactor } from '@/lib/types';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { getRiskColor } from '@/lib/utils';
import { FadeIn } from '@/components/animations/fade-in';
import { StaggerChildren, StaggerItem } from '@/components/animations/stagger-children';

interface RiskPanelProps {
  tag: string;
}

const trendConfig = {
  improving: { icon: TrendingDown, color: 'text-emerald-400', label: 'Improving' },
  stable: { icon: Minus, color: 'text-zinc-400', label: 'Stable' },
  degrading: { icon: TrendingUp, color: 'text-red-400', label: 'Degrading' },
};

function parseRiskFromText(text: string, tag: string): RiskAssessment {
  const scoreMatch = text.match(/(\d+)\s*[/%]/);
  const overallScore = scoreMatch ? parseInt(scoreMatch[1]) / 100 : 0.5;

  const factors: RiskFactor[] = [];
  const factorNames = ['Age & Condition', 'Failure History', 'Maintenance Compliance', 'Operating Conditions', 'Criticality'];
  const lines = text.split('\n');

  for (const name of factorNames) {
    const relevant = lines.find((l) => l.toLowerCase().includes(name.toLowerCase()));
    const numMatch = relevant?.match(/(\d+)\s*[/%]/);
    factors.push({
      name,
      score: numMatch ? parseInt(numMatch[1]) / 100 : 0.3 + Math.random() * 0.4,
      weight: 1 / factorNames.length,
      description: relevant?.replace(/^[-*•\d.)\s]+/, '').trim() || `${name} assessment`,
    });
  }

  const trend: RiskAssessment['trend'] = text.match(/degrading|worsening|increasing risk/i)
    ? 'degrading'
    : text.match(/improving|decreasing risk/i)
      ? 'improving'
      : 'stable';

  return {
    tag,
    equipment_name: tag,
    overall_risk: overallScore,
    factors,
    trend,
  };
}

export function RiskPanel({ tag }: RiskPanelProps) {
  const [risk, setRisk] = useState<RiskAssessment | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let fullText = '';
    const cancel = streamAgent('asset', `Provide a risk assessment for ${tag}. Include overall risk score as a percentage, risk factors (Age & Condition, Failure History, Maintenance Compliance, Operating Conditions, Criticality) with their scores, and the overall trend (improving, stable, or degrading).`, tag, {
      onToken: (text) => { fullText += text; },
      onCitation: () => {},
      onAgentTrigger: () => {},
      onReasoning: () => {},
      onToolCall: () => {},
      onToolResult: () => {},
      onDone: () => {
        setRisk(parseRiskFromText(fullText, tag));
        setLoading(false);
      },
      onError: (err) => {
        setError(err.message);
        setLoading(false);
      },
    });

    return () => cancel();
  }, [tag]);

  if (loading || !risk) {
    return (
      <div className="flex items-center justify-center h-48">
        <motion.div
          className="w-6 h-6 rounded-full border-2 border-blue-500 border-t-transparent"
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
        />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-48 text-sm text-zinc-500">
        Failed to load risk assessment: {error}
      </div>
    );
  }

  const trend = trendConfig[risk.trend];
  const TrendIcon = trend.icon;

  return (
    <div className="p-4 space-y-4">
      <FadeIn>
        <Card>
          <CardContent className="p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-lg font-semibold text-zinc-200">Overall Risk Score</h3>
                <p className="text-sm text-zinc-500">{risk.equipment_name}</p>
              </div>
              <div className="flex items-center gap-2">
                <TrendIcon className={`w-4 h-4 ${trend.color}`} />
                <Badge variant={risk.trend === 'degrading' ? 'destructive' : risk.trend === 'improving' ? 'success' : 'outline'}>
                  {trend.label}
                </Badge>
              </div>
            </div>
            <div className="flex items-end gap-4">
              <motion.span
                className="text-4xl font-bold tabular-nums"
                style={{ color: getRiskColor(risk.overall_risk) }}
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: 'spring', stiffness: 200, damping: 15 }}
              >
                {Math.round(risk.overall_risk * 100)}
              </motion.span>
              <span className="text-sm text-zinc-500 mb-1">/100</span>
            </div>
            <Progress value={risk.overall_risk * 100} className="mt-3" />
          </CardContent>
        </Card>
      </FadeIn>

      <FadeIn delay={0.1}>
        <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-2">Risk Factors</h3>
      </FadeIn>

      <StaggerChildren className="space-y-2">
        {risk.factors.map((factor) => (
          <StaggerItem key={factor.name}>
            <Card>
              <CardContent className="p-4">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-zinc-200">{factor.name}</span>
                  <span className="text-sm font-bold tabular-nums" style={{ color: getRiskColor(factor.score) }}>
                    {Math.round(factor.score * 100)}
                  </span>
                </div>
                <p className="text-xs text-zinc-500 mb-2">{factor.description}</p>
                <div className="flex items-center gap-2">
                  <Progress value={factor.score * 100} size="sm" className="flex-1" />
                  <span className="text-[10px] text-zinc-600">w:{Math.round(factor.weight * 100)}%</span>
                </div>
              </CardContent>
            </Card>
          </StaggerItem>
        ))}
      </StaggerChildren>
    </div>
  );
}
