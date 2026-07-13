'use client';

import type { ReactNode } from 'react';
import { Sidebar } from './sidebar';
import { Header } from './header';
import { AssistantDock } from '@/components/copilot/assistant-dock';

export function AppShell({ children }: { children: ReactNode }) {
  return (
    <div className="flex h-screen overflow-hidden bg-base">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Header />
        <main className="flex-1 overflow-auto flex flex-col min-h-0">
          {children}
        </main>
      </div>
      <AssistantDock />
    </div>
  );
}
