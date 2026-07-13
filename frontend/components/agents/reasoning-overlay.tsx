'use client';

import { useEffect, useState, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Brain, ArrowRight, RotateCcw } from 'lucide-react';
import { streamAgent } from '@/lib/api';
import type { DiagnoseJob, ReasoningStep, Citation } from '@/lib/types';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { FadeIn } from '@/components/animations/fade-in';
import { StepTimeline } from './step-timeline';
import { ReplayControls } from './replay-controls';
import { CitationChip } from '@/components/copilot/citation-chip';

interface ReasoningOverlayProps {
  jobId: string;
}

export function ReasoningOverlay({ jobId }: ReasoningOverlayProps) {
  const [job, setJob] = useState<DiagnoseJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [replayMode, setReplayMode] = useState(false);
  const [replayIndex, setReplayIndex] = useState(0);
  const [replaySpeed, setReplaySpeed] = useState(1);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const tag = params.get('tag') || 'P-101A';

    const steps: ReasoningStep[] = [];
    const citations: Citation[] = [];
    let fullText = '';
    let stepIndex = 0;

    const newJob: DiagnoseJob = {
      job_id: jobId,
      status: 'running',
      equipment_tag: tag,
      steps: [],
    };
    setJob(newJob);
    setLoading(false);

    const cancel = streamAgent('diagnose', `Diagnose equipment ${tag}. Analyze maintenance history, failure modes, vibration data, and provide a diagnosis with recommended actions.`, tag, {
      onToken: (text) => {
        fullText += text;
      },
      onCitation: (cit) => {
        citations.push({ ...cit, page: cit.page ?? 0, title: `Document ${cit.doc_id}`, snippet: '' });
      },
      onAgentTrigger: () => { },
      onReasoning: (content) => {
        const step: ReasoningStep = {
          id: `step-${stepIndex++}`,
          worker: 'reasoner',
          action: content.slice(0, 60),
          detail: content,
          timestamp: Date.now(),
          status: 'completed',
          duration_ms: 500 + Math.random() * 1500,
        };
        steps.push(step);
        setJob((prev) => prev ? { ...prev, steps: [...steps] } : prev);
      },
      onToolCall: (toolName, toolArgs) => {
        const step: ReasoningStep = {
          id: `step-${stepIndex++}`,
          worker: 'tool',
          action: `Calling ${toolName}`,
          detail: JSON.stringify(toolArgs),
          timestamp: Date.now(),
          status: 'running',
        };
        steps.push(step);
        setJob((prev) => prev ? { ...prev, steps: [...steps] } : prev);
      },
      onToolResult: (toolName) => {
        const lastTool = steps.findLast((s) => s.worker === 'tool' && s.status === 'running');
        if (lastTool) {
          lastTool.status = 'completed';
          lastTool.duration_ms = Date.now() - lastTool.timestamp;
          setJob((prev) => prev ? { ...prev, steps: [...steps] } : prev);
        }
      },
      onDone: () => {
        setJob((prev) => prev ? {
          ...prev,
          status: 'completed',
          steps: [...steps],
          result: {
            diagnosis: fullText,
            confidence: 0.85,
            recommended_actions: fullText
              .split('\n')
              .filter((l) => l.match(/^\s*[-*•\d]/))
              .map((l) => l.replace(/^[\s\-*•\d.)+]+/, '').trim())
              .filter((l) => l.length > 10)
              .slice(0, 5),
            supporting_evidence: citations,
          },
        } : prev);
      },
      onError: (err) => {
        setJob((prev) => prev ? {
          ...prev,
          status: 'failed',
          steps: [...steps, {
            id: `step-err`,
            worker: 'system',
            action: 'Error',
            detail: err.message,
            timestamp: Date.now(),
            status: 'failed',
          }],
        } : prev);
      },
    });

    return () => cancel();
  }, [jobId]);

  const handleReplay = useCallback(() => {
    setReplayMode(true);
    setReplayIndex(0);
  }, []);

  const handleReplayTick = useCallback(() => {
    if (!job) return;
    setReplayIndex((prev) => {
      if (prev >= job.steps.length - 1) {
        setReplayMode(false);
        return job.steps.length - 1;
      }
      return prev + 1;
    });
  }, [job]);

  if (loading || !job) {
    return (
      <div className="flex items-center justify-center h-64">
        <motion.div
          className="w-8 h-8 rounded-full border-2 border-signal border-t-transparent"
          animate={{ rotate: 360 }}
          transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
        />
      </div>
    );
  }

  const visibleSteps = replayMode ? job.steps.slice(0, replayIndex + 1) : job.steps;
  const completedSteps = visibleSteps.filter((s) => s.status === 'completed').length;
  const progress = job.steps.length > 0 ? (completedSteps / job.steps.length) * 100 : 0;

  return (
    <div className="p-6 space-y-6 max-w-4xl mx-auto">
      <FadeIn>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <motion.div
              className="w-11 h-11 rounded-xl bg-signal-soft border border-line flex items-center justify-center"
              animate={job.status === 'running' ? { rotate: [0, 5, -5, 0] } : {}}
              transition={{ duration: 2, repeat: Infinity }}
            >
              <Brain className="w-5 h-5 text-signal" />
            </motion.div>
            <div>
              <h1 className="text-xl font-bold text-ink">SEEKR Diagnose</h1>
              <p className="text-sm text-muted">
                Equipment: <span className="text-signal">{job.equipment_tag}</span>
                {' · '}Job: <span className="text-muted">{job.job_id}</span>
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge variant={job.status === 'completed' ? 'success' : job.status === 'failed' ? 'destructive' : 'warning'}>
              {job.status}
            </Badge>
            {job.status === 'completed' && (
              <Button variant="outline" size="sm" onClick={handleReplay}>
                <RotateCcw className="w-3.5 h-3.5" />
                Replay
              </Button>
            )}
          </div>
        </div>
      </FadeIn>

      <FadeIn delay={0.1}>
        <Progress value={progress} showLabel size="md" />
      </FadeIn>

      {replayMode && (
        <ReplayControls
          speed={replaySpeed}
          onSpeedChange={setReplaySpeed}
          onTick={handleReplayTick}
          isPlaying={replayMode}
          currentStep={replayIndex}
          totalSteps={job.steps.length}
        />
      )}

      <FadeIn delay={0.2}>
        <Card>
          <CardHeader>
            <h2 className="text-sm font-semibold text-ink">Reasoning Steps</h2>
          </CardHeader>
          <CardContent className="p-0">
            <StepTimeline steps={visibleSteps} activeIndex={replayMode ? replayIndex : undefined} />
          </CardContent>
        </Card>
      </FadeIn>

      {job.result && !replayMode && (
        <FadeIn delay={0.3}>
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-ink">Diagnosis Result</h2>
                <Badge variant="default">
                  Confidence: {Math.round(job.result.confidence * 100)}%
                </Badge>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <p className="text-sm text-ink leading-relaxed whitespace-pre-line">{job.result.diagnosis}</p>

              {job.result.recommended_actions.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">
                    Recommended Actions
                  </h3>
                  <ul className="space-y-2">
                    {job.result.recommended_actions.map((action, i) => (
                      <motion.li
                        key={i}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.4 + i * 0.1 }}
                        className="flex items-start gap-2 text-sm text-ink"
                      >
                        <ArrowRight className="w-4 h-4 text-signal mt-0.5 shrink-0" />
                        {action}
                      </motion.li>
                    ))}
                  </ul>
                </div>
              )}

              {job.result.supporting_evidence.length > 0 && (
                <div>
                  <h3 className="text-xs font-semibold text-muted uppercase tracking-wider mb-2">
                    Supporting Evidence
                  </h3>
                  <div className="flex flex-wrap gap-2">
                    {job.result.supporting_evidence.map((cit, i) => (
                      <CitationChip key={i} citation={cit} />
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </FadeIn>
      )}
    </div>
  );
}
