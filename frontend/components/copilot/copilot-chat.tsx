'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Loader2, Cpu, StopCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { streamQuery } from '@/lib/api';
import type { CopilotMessage, Citation } from '@/lib/types';
import { MessageBubble } from './message-bubble';
import { cn } from '@/lib/utils';

interface CopilotChatProps {
  entityTag?: string | null;
}

export function CopilotChat({ entityTag = null }: CopilotChatProps) {
  const [messages, setMessages] = useState<CopilotMessage[]>([]);
  const [input, setInput] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const cancelRef = useRef<(() => void) | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const handleSend = useCallback(() => {
    const query = input.trim();
    if (!query || isStreaming) return;

    const userMsg: CopilotMessage = {
      id: `msg-${Date.now()}`,
      role: 'user',
      content: query,
      timestamp: Date.now(),
    };

    const assistantId = `msg-${Date.now() + 1}`;
    const assistantMsg: CopilotMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      citations: [],
      reasoning_steps: [],
      timestamp: Date.now(),
      streaming: true,
    };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setInput('');
    setIsStreaming(true);

    const citations: Citation[] = [];
    const reasoningSteps: string[] = [];

    cancelRef.current = streamQuery(query, entityTag, {
      onToken: (text) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: m.content + text } : m,
          ),
        );
      },
      onCitation: (cit) => {
        citations.push({ ...cit, page: cit.page ?? 0, title: `Document ${cit.doc_id}`, snippet: '' });
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, citations: [...citations] } : m,
          ),
        );
      },
      onAgentTrigger: (trigger) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, agent_trigger: trigger as CopilotMessage['agent_trigger'] } : m,
          ),
        );
      },
      onReasoning: (content) => {
        reasoningSteps.push(content);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, reasoning_steps: [...reasoningSteps] } : m,
          ),
        );
      },
      onToolCall: () => { },
      onToolResult: () => { },
      onDone: () => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, streaming: false } : m,
          ),
        );
        setIsStreaming(false);
      },
      onError: (err) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: m.content || `Error: ${err.message}`, streaming: false }
              : m,
          ),
        );
        setIsStreaming(false);
      },
    });
  }, [input, isStreaming, entityTag]);

  const handleStop = () => {
    cancelRef.current?.();
    setIsStreaming(false);
    setMessages((prev) =>
      prev.map((m) => (m.streaming ? { ...m, streaming: false } : m)),
    );
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const suggestedQueries = entityTag
    ? [
      `What is the maintenance history of ${entityTag}?`,
      `What are the known failure modes for ${entityTag}?`,
      `Show compliance status for ${entityTag}`,
    ]
    : [
      'Which assets have overdue maintenance?',
      'Summarize the highest-risk equipment right now.',
      'What compliance gaps need attention this week?',
    ];

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-4">
        {messages.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex flex-col items-center justify-center h-full text-center px-4"
          >
            <div className="relative w-12 h-12 mb-4">
              <span className="absolute inset-0 rounded-md border border-mint/40 rotate-45" />
              <div className="absolute inset-0 flex items-center justify-center">
                <Cpu className="w-5 h-5 text-mint" />
              </div>
            </div>
            <p className="eyebrow mb-1">Copilot · cited answers</p>
            <h3 className="font-display text-xl text-ink mb-1">Ask Seekr</h3>
            <p className="text-sm text-muted mb-6">
              {entityTag
                ? <>anything about <span className="text-signal font-mono">{entityTag}</span></>
                : 'anything across your equipment, documents & compliance'}
            </p>
            <div className="space-y-2 w-full max-w-sm">
              {suggestedQueries.map((q, i) => (
                <motion.button
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.2 + i * 0.08 }}
                  onClick={() => { setInput(q); inputRef.current?.focus(); }}
                  className="group w-full flex items-center gap-2 text-left px-4 py-2.5 text-sm text-muted bg-base/40 border border-line rounded-md hover:border-signal/40 hover:text-ink transition-all"
                >
                  <span className="text-signal opacity-50 group-hover:opacity-100 font-mono">›</span>
                  {q}
                </motion.button>
              ))}
            </div>
          </motion.div>
        ) : (
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} entityTag={entityTag ?? ''} />
            ))}
          </AnimatePresence>
        )}
      </div>

      <div className="border-t border-line px-4 py-3">
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={entityTag ? `Ask about ${entityTag}…` : 'Ask Seekr anything…'}
            rows={1}
            className={cn(
              'flex-1 resize-none rounded-md px-4 py-2.5 text-sm',
              'bg-base/40 border border-line text-ink placeholder:text-faint',
              'focus:outline-none focus:ring-2 focus:ring-signal/25 focus:border-signal',
              'min-h-[42px] max-h-32',
            )}
            style={{ height: 'auto' }}
            onInput={(e) => {
              const el = e.currentTarget;
              el.style.height = 'auto';
              el.style.height = Math.min(el.scrollHeight, 128) + 'px';
            }}
          />
          {isStreaming ? (
            <Button variant="destructive" size="icon" onClick={handleStop} title="Stop generating">
              <StopCircle className="w-4 h-4" />
            </Button>
          ) : (
            <Button
              size="icon"
              onClick={handleSend}
              disabled={!input.trim()}
              title="Send message"
            >
              {isStreaming ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
