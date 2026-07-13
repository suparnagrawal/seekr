'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { MessageCircle, Clock, FileText, Zap, ChevronDown } from 'lucide-react';
import { cn } from '@/lib/utils';
import { CopilotChat } from '@/components/copilot/copilot-chat';
import { MaintenanceTimeline } from './maintenance-timeline';
import { LinkedDocuments } from './linked-documents';
import { AgentInvokeBar } from './agent-invoke-bar';

interface NodeSidePanelProps {
  tag: string;
  label: string;
}

type Tab = 'chat' | 'maintenance' | 'documents';

const TABS: { id: Tab; icon: typeof MessageCircle; label: string }[] = [
  { id: 'chat', icon: MessageCircle, label: 'SEEKR Ask' },
  { id: 'maintenance', icon: Clock, label: 'Maintenance' },
  { id: 'documents', icon: FileText, label: 'Documents' },
];

export function NodeSidePanel({ tag, label }: NodeSidePanelProps) {
  const [activeTab, setActiveTab] = useState<Tab>('chat');

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.4, ease: [0.25, 0.46, 0.45, 0.94] }}
      className="flex flex-col h-full bg-zinc-950"
    >
      <div className="px-5 py-4 border-b border-zinc-800">
        <h2 className="text-lg font-semibold text-zinc-100">{label}</h2>
        <p className="text-sm text-zinc-500 mt-0.5">Tag: {tag}</p>
      </div>

      <AgentInvokeBar tag={tag} />

      <div className="flex border-b border-zinc-800">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'relative flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors',
              activeTab === tab.id
                ? 'text-blue-400'
                : 'text-zinc-500 hover:text-zinc-300',
            )}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
            {activeTab === tab.id && (
              <motion.div
                layoutId="entity-tab"
                className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-500"
                transition={{ type: 'spring', stiffness: 350, damping: 30 }}
              />
            )}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-hidden">
        {activeTab === 'chat' && <CopilotChat entityTag={tag} />}
        {activeTab === 'maintenance' && <MaintenanceTimeline tag={tag} />}
        {activeTab === 'documents' && <LinkedDocuments tag={tag} />}
      </div>
    </motion.div>
  );
}
