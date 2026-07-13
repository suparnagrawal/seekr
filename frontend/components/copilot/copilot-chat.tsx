'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Send, Loader2, Sparkles, StopCircle } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { streamQuery } from '@/lib/api';
import type { CopilotMessage, Citation } from '@/lib/types';
import { MessageBubble } from './message-bubble';
import { cn } from '@/lib/utils';

interface CopilotChatProps {
  entityTag: string;
}

export function CopilotChat({ entityTag }: CopilotChatProps) {
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
      onToolCall: () => {},
      onToolResult: () => {},
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

  const suggestedQueries = [
    `What is the maintenance history of ${entityTag}?`,
    `What are the known failure modes for ${entityTag}?`,
    `Show compliance status for ${entityTag}`,
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
            <motion.div
              className="w-12 h-12 rounded-2xl bg-gradient-to-br from-blue-500/20 to-cyan-500/20 flex items-center justify-center mb-4"
              animate={{ rotate: [0, 5, -5, 0] }}
              transition={{ duration: 4, repeat: Infinity }}
            >
              <Sparkles className="w-6 h-6 text-blue-400" />
            </motion.div>
            <h3 className="text-lg font-semibold text-zinc-200 mb-1">SEEKR Ask</h3>
            <p className="text-sm text-zinc-500 mb-6">
              Ask anything about <span className="text-blue-400 font-medium">{entityTag}</span>
            </p>
            <div className="space-y-2 w-full max-w-sm">
              {suggestedQueries.map((q, i) => (
                <motion.button
                  key={i}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.2 + i * 0.1 }}
                  onClick={() => { setInput(q); inputRef.current?.focus(); }}
                  className="w-full text-left px-4 py-2.5 text-sm text-zinc-400 bg-zinc-900/50 border border-zinc-800 rounded-lg hover:border-zinc-700 hover:text-zinc-300 transition-all"
                >
                  {q}
                </motion.button>
              ))}
            </div>
          </motion.div>
        ) : (
          <AnimatePresence initial={false}>
            {messages.map((msg) => (
              <MessageBubble key={msg.id} message={msg} entityTag={entityTag} />
            ))}
          </AnimatePresence>
        )}
      </div>

      <div className="border-t border-zinc-800 px-4 py-3">
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={`Ask SEEKR about ${entityTag}...`}
            rows={1}
            className={cn(
              'flex-1 resize-none rounded-lg px-4 py-2.5 text-sm',
              'bg-zinc-900/50 border border-zinc-800 text-zinc-200 placeholder:text-zinc-500',
              'focus:outline-none focus:ring-2 focus:ring-blue-500/40 focus:border-blue-500',
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
