'use client';

import { useEffect, useState } from 'react';
import { motion } from 'framer-motion';
import { Wrench, Eye, RotateCcw, Gauge, AlertTriangle } from 'lucide-react';
import { streamAgent } from '@/lib/api';
import type { MaintenanceEvent } from '@/lib/types';
import { Badge } from '@/components/ui/badge';
import { formatDate } from '@/lib/utils';
import { StaggerChildren, StaggerItem } from '@/components/animations/stagger-children';

const typeConfig: Record<string, { icon: typeof Wrench; color: string }> = {
  inspection: { icon: Eye, color: 'text-signal' },
  repair: { icon: Wrench, color: 'text-signal' },
  replacement: { icon: RotateCcw, color: 'text-signal' },
  calibration: { icon: Gauge, color: 'text-mint' },
  incident: { icon: AlertTriangle, color: 'text-ember' },
};

const severityVariant: Record<string, 'default' | 'success' | 'warning' | 'destructive'> = {
  low: 'success',
  medium: 'warning',
  high: 'destructive',
  critical: 'destructive',
};

function parseMaintenanceFromText(text: string): MaintenanceEvent[] {
  const events: MaintenanceEvent[] = [];
  const lines = text.split('\n').filter((l) => l.trim());
  let idx = 0;

  for (const line of lines) {
    const dateMatch = line.match(/(\d{4}-\d{2}-\d{2})/);
    const typeMatch = line.match(/\b(inspection|repair|replacement|calibration|incident)\b/i);
    if (dateMatch || typeMatch) {
      events.push({
        id: `maint-${idx++}`,
        date: dateMatch?.[1] || new Date().toISOString().slice(0, 10),
        type: (typeMatch?.[1]?.toLowerCase() as MaintenanceEvent['type']) || 'inspection',
        description: line.replace(/^[-*•]\s*/, '').trim(),
        severity: line.match(/critical/i) ? 'critical' : line.match(/high/i) ? 'high' : line.match(/medium/i) ? 'medium' : 'low',
      });
    }
  }

  return events;
}

export function MaintenanceTimeline({ tag }: { tag: string }) {
  const [events, setEvents] = useState<MaintenanceEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let fullText = '';
    const cancel = streamAgent('asset', `List all maintenance events for ${tag} with dates, types (inspection, repair, replacement, calibration, incident), descriptions, and severity levels. Format each as a line with the date.`, tag, {
      onToken: (text) => { fullText += text; },
      onCitation: () => {},
      onAgentTrigger: () => {},
      onReasoning: () => {},
      onToolCall: () => {},
      onToolResult: () => {},
      onDone: () => {
        const parsed = parseMaintenanceFromText(fullText);
        setEvents(parsed);
        setLoading(false);
      },
      onError: (err) => {
        setError(err.message);
        setLoading(false);
      },
    });

    return () => cancel();
  }, [tag]);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-48">
        <motion.div
          className="w-6 h-6 rounded-full border-2 border-signal border-t-transparent"
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
        />
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center h-48 text-sm text-muted">
        Failed to load maintenance history: {error}
      </div>
    );
  }

  if (events.length === 0) {
    return (
      <div className="flex items-center justify-center h-48 text-sm text-muted">
        No maintenance events found for {tag}
      </div>
    );
  }

  return (
    <div className="overflow-y-auto px-4 py-4">
      <StaggerChildren className="relative">
        <div className="absolute left-[19px] top-2 bottom-2 w-px bg-base" />

        {events.map((event) => {
          const config = typeConfig[event.type] || typeConfig.inspection;
          const Icon = config.icon;

          return (
            <StaggerItem key={event.id} className="relative flex gap-4 pb-6 last:pb-0">
              <div className="relative z-10 mt-1">
                <div className="w-10 h-10 rounded-full bg-panel border border-line flex items-center justify-center">
                  <Icon className={`w-4 h-4 ${config.color}`} />
                </div>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-ink capitalize">{event.type}</span>
                  {event.severity && (
                    <Badge variant={severityVariant[event.severity]}>{event.severity}</Badge>
                  )}
                </div>
                <p className="text-sm text-muted mt-1 leading-relaxed">{event.description}</p>
                <div className="flex items-center gap-3 mt-2 text-xs text-muted">
                  <span>{formatDate(event.date)}</span>
                  {event.technician && <span>by {event.technician}</span>}
                </div>
              </div>
            </StaggerItem>
          );
        })}
      </StaggerChildren>
    </div>
  );
}
