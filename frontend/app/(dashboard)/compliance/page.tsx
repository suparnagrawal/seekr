'use client';

import { ComplianceDashboard } from '@/components/compliance/compliance-dashboard';
import { PageTransition } from '@/components/animations/page-transition';

export default function CompliancePage() {
  return (
    <PageTransition>
      <ComplianceDashboard />
    </PageTransition>
  );
}
