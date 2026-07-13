'use client';

import { use } from 'react';
import { ReasoningOverlay } from '@/components/agents/reasoning-overlay';
import { PageTransition } from '@/components/animations/page-transition';

export default function DiagnoseJobPage({ params }: { params: Promise<{ jobId: string }> }) {
  const { jobId } = use(params);

  return (
    <PageTransition>
      <ReasoningOverlay jobId={jobId} />
    </PageTransition>
  );
}
