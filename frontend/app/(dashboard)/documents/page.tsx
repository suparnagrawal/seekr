'use client';

import { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FolderCog, CheckCircle2, CloudUpload, File, AlertCircle, Loader2, RotateCcw } from 'lucide-react';
import { FadeIn } from '@/components/animations/fade-in';
import { useAuth } from '@/lib/auth-context';
import { PageTransition } from '@/components/animations/page-transition';
import { uploadDocument, getDocumentStatus, listDocuments, retryDocument } from '@/lib/api';
import { cn } from '@/lib/utils';

/** Ordered ingestion pipeline the backend drives a document through. */
const STAGES = ['UPLOADED', 'PARSED', 'EMBEDDED', 'GRAPH_BUILT', 'COMPLETED'] as const;
const STAGE_LABELS: Record<string, string> = {
  UPLOADED: 'Uploaded',
  QUEUED: 'Queued',
  PROCESSING: 'Parsing',
  PARSED: 'Parsed',
  EMBEDDING: 'Embedding',
  INDEXING: 'Indexing',
  EMBEDDED: 'Embedded',
  GRAPH_BUILDING: 'Extracting Graph',
  GRAPH_BUILT: 'Graph Built',
  COMPLETED: 'Indexed',
  FAILED: 'Failed',
};

function stageIndex(status: string): number {
  const s = status.toUpperCase();
  if (['UPLOADED', 'QUEUED'].includes(s)) return 0;
  if (['PROCESSING'].includes(s)) return 1;
  if (['PARSED', 'EMBEDDING', 'INDEXING'].includes(s)) return 2;
  if (['EMBEDDED', 'GRAPH_BUILDING'].includes(s)) return 3;
  if (['GRAPH_BUILT', 'COMPLETED'].includes(s)) return 4;
  return 0;
}

interface UploadedFile {
  id: string;
  name: string;
  size: number;
  status: 'uploading' | 'processing' | 'complete' | 'error';
  documentId?: string;
  stage?: string;          // backend overall_status
  graphStatus?: string | null;
  pageCount?: number | null;
  chunkCount?: number | null;
  error?: string;
}

export default function DocumentsPage() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const [activeMlGateway, setActiveMlGateway] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { hasPermission } = useAuth();

  useEffect(() => {
    const savedGateway = localStorage.getItem('seekr_ml_gateway');
    if (savedGateway) {
      setActiveMlGateway(savedGateway);
    }
  }, []);

  const handleGatewayChange = (val: string) => {
    setActiveMlGateway(val);
    localStorage.setItem('seekr_ml_gateway', val);
  };

  const mounted = useRef(true);
  const timers = useRef<Set<ReturnType<typeof setTimeout>>>(new Set());
  useEffect(() => {
    const timerSet = timers.current;
    return () => {
      mounted.current = false;
      timerSet.forEach(clearTimeout);
    };
  }, []);

  const patch = useCallback((id: string, next: Partial<UploadedFile>) => {
    setFiles((prev) => prev.map((f) => (f.id === id ? { ...f, ...next } : f)));
  }, []);

  const pollStatus = useCallback((id: string, documentId: string, attempt = 0) => {
    if (!mounted.current) return;
    getDocumentStatus(documentId)
      .then((s) => {
        if (!mounted.current) return;
        const overall = (s.overall_status || '').toUpperCase();
        const terminal = overall === 'COMPLETED' || overall === 'FAILED';
        patch(id, {
          status: overall === 'COMPLETED' ? 'complete' : overall === 'FAILED' ? 'error' : 'processing',
          stage: s.overall_status,
          graphStatus: s.graph_job_status,
          pageCount: s.page_count,
          chunkCount: s.chunk_count,
          error: overall === 'FAILED' ? (s.error_message || 'Ingestion failed') : undefined,
        });
        if (!terminal && attempt < 60) {
          const t = setTimeout(() => pollStatus(id, documentId, attempt + 1), 3000);
          timers.current.add(t);
        }
      })
      .catch(() => {
        // Status endpoint may 404 briefly right after upload — keep trying.
        if (mounted.current && attempt < 60) {
          const t = setTimeout(() => pollStatus(id, documentId, attempt + 1), 3000);
          timers.current.add(t);
        }
      });
  }, [patch]);

  // Load the existing library on mount and resume polling for any doc still
  // in-flight. Declared after pollStatus so it can reference it without hitting
  // the temporal dead zone.
  useEffect(() => {
    let active = true;
    listDocuments().then((docs) => {
      if (!active) return;
      const initialFiles = docs.map((d) => {
        const overall = (d.overall_status || '').toUpperCase();
        return {
          id: d.document_id,
          name: d.filename,
          size: 0,
          status: overall === 'COMPLETED' ? 'complete' : overall === 'FAILED' ? 'error' : 'processing',
          documentId: d.document_id,
          stage: d.overall_status,
          graphStatus: d.graph_job_status,
          pageCount: d.page_count,
          chunkCount: d.chunk_count,
          error: overall === 'FAILED' ? (d.error_message || 'Ingestion failed') : undefined,
        } as UploadedFile;
      });
      setFiles(initialFiles);
      initialFiles.forEach(f => {
        if (f.status === 'processing' && f.documentId) {
          pollStatus(f.id, f.documentId);
        }
      });
    }).catch(console.error);
    return () => { active = false; };
  }, [pollStatus]);

  const handleUpload = async (file: File) => {
    const id = `${file.name}-${Date.now()}`;
    setFiles((prev) => [...prev, { id, name: file.name, size: file.size, status: 'uploading' }]);

    try {
      const result = await uploadDocument(file, activeMlGateway || undefined);
      patch(id, { status: 'processing', documentId: result.document_id, stage: result.status || 'UPLOADED' });
      pollStatus(id, result.document_id);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      const isConnectionError = message.includes('Failed to fetch') || message.includes('NetworkError');
      patch(id, {
        status: 'error',
        error: isConnectionError ? 'Cannot reach the SEEKR API. Check NEXT_PUBLIC_API_URL and that the backend is awake.' : message,
      });
    }
  };

  const handleRetry = async (id: string, documentId: string) => {
    patch(id, { status: 'processing', error: undefined, stage: 'QUEUED' });
    try {
      await retryDocument(documentId, activeMlGateway || undefined);
      pollStatus(id, documentId);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Retry failed';
      patch(id, { status: 'error', error: message });
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    Array.from(e.dataTransfer.files).forEach(handleUpload);
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    Array.from(e.target.files || []).forEach(handleUpload);
  };

  return (
    <PageTransition>
      <div className="p-6 space-y-6 max-w-4xl mx-auto">
        <FadeIn>
          <p className="eyebrow">Ingestion · index pipeline</p>
          <div className="flex items-center gap-3 mt-2">
            <div className="w-10 h-10 rounded-md border border-line bg-signal-soft flex items-center justify-center">
              <FolderCog className="w-5 h-5 text-signal" />
            </div>
            <div>
              <h1 className="font-display text-3xl font-medium text-ink">Document Library</h1>
              <p className="text-sm text-muted">Feed engineering documents into the Seekr knowledge graph</p>
            </div>
          </div>
        </FadeIn>

        {hasPermission('documents:upload') && (
          <FadeIn delay={0.1}>
            <div className="mb-4 bg-base/50 border border-line rounded-md p-4">
              <label className="block text-sm font-medium text-ink mb-1">Custom ML Gateway URL (Optional)</label>
              <p className="text-xs text-muted mb-3">Provide a remote gateway url for offloading parsing and embedding tasks. For example, a Colab/Ngrok endpoint (<a href="https://colab.research.google.com/drive/1yeAxOD0O-DGugkl9oqxUaJORqQf_Ke_w?usp=sharing" target="_blank" rel="noreferrer" className="text-signal hover:underline">see example notebook</a>—clone it and add your <code>NGROK_AUTHTOKEN</code> as a secret): <code className="text-signal bg-signal/10 px-1 py-0.5 rounded">https://my-tunnel.ngrok-free.app</code>.</p>
              <input
                type="url"
                placeholder="https://..."
                value={activeMlGateway}
                onChange={(e) => handleGatewayChange(e.target.value)}
                className="w-full sm:w-2/3 md:w-1/2 bg-panel border border-line rounded-md px-3 py-2 text-sm text-ink focus:outline-none focus:border-signal focus:ring-1 focus:ring-signal"
              />
            </div>

            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              className={cn(
                'relative rounded-lg p-10 text-center transition-all overflow-hidden',
                dragOver ? 'border-2 border-signal bg-signal-soft' : 'border-2 border-dashed border-line hover:border-signal/50',
              )}
            >
              {dragOver && <div className="absolute inset-0 blueprint blueprint-drift pointer-events-none" />}
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={handleFileSelect}
                className="hidden"
                accept=".pdf,.doc,.docx,.txt,.csv,.xlsx"
              />
              <motion.div animate={dragOver ? { y: [-2, 2, -2] } : {}} transition={{ duration: 1, repeat: Infinity }}>
                <CloudUpload className={cn('w-11 h-11 mx-auto mb-3', dragOver ? 'text-signal' : 'text-faint')} />
              </motion.div>
              <p className="text-sm text-ink">
                Drop files here, or{' '}
                <button onClick={() => fileInputRef.current?.click()} className="text-signal font-medium hover:underline">
                  browse
                </button>
              </p>
              <p className="font-mono text-[0.62rem] text-faint mt-2 uppercase tracking-wider">pdf · doc · docx · txt · csv · xlsx</p>
            </div>
          </FadeIn>
        )}

        <AnimatePresence>
          {files.length > 0 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-2">
              <p className="eyebrow">Queue</p>
              {files.map((file) => (
                <DocumentRow key={file.id} file={file} onRetry={handleRetry} />
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        {files.length === 0 && (
          <FadeIn delay={0.2}>
            <div className="text-center py-12">
              <FolderCog className="w-12 h-12 mx-auto mb-3 text-line-strong" />
              <p className="text-sm text-muted">Upload documents above to start indexing.</p>
              <p className="font-mono text-[0.62rem] text-faint mt-1 uppercase tracking-wider">uploaded → parsed → embedded → indexed</p>
            </div>
          </FadeIn>
        )}
      </div>
    </PageTransition>
  );
}

function DocumentRow({ file, onRetry }: { file: UploadedFile; onRetry: (id: string, docId: string) => void }) {
  const isError = file.status === 'error';
  const isComplete = file.status === 'complete';
  const activeStep = isComplete ? STAGES.length - 1 : stageIndex(file.stage || 'UPLOADED');

  const meta: string[] = [];
  if (file.pageCount != null) meta.push(`${file.pageCount} pages`);
  if (file.chunkCount != null) meta.push(`${file.chunkCount} chunks`);
  if (file.graphStatus) meta.push(`graph ${file.graphStatus.toLowerCase()}`);

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      className="p-3.5 panel rounded-md"
    >
      <div className="flex items-center gap-3">
        <File className="w-4 h-4 text-faint shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm text-ink truncate">{file.name}</p>
          {file.documentId && <p className="font-mono text-[0.6rem] text-faint mt-0.5 truncate">id · {file.documentId}</p>}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className={cn(
            'font-mono text-[0.62rem] uppercase tracking-wider',
            isComplete ? 'text-mint' : isError ? 'text-ember' : 'text-signal',
          )}>
            {isError ? 'Failed' : STAGE_LABELS[(file.stage || 'UPLOADED').toUpperCase()] || file.stage || 'Uploading'}
          </span>
          {file.status === 'uploading' || file.status === 'processing' ? (
            <Loader2 className="w-4 h-4 text-signal animate-spin" />
          ) : isComplete ? (
            <CheckCircle2 className="w-4 h-4 text-mint" />
          ) : (
            <div className="flex items-center gap-1.5">
              {file.documentId && (
                <button
                  onClick={() => onRetry(file.id, file.documentId!)}
                  className="flex items-center justify-center p-1 rounded hover:bg-white/5 text-signal transition-colors group"
                  title="Retry ingestion pipeline"
                >
                  <RotateCcw className="w-3.5 h-3.5 group-active:-rotate-90 transition-transform" />
                </button>
              )}
              <AlertCircle className="w-4 h-4 text-ember" />
            </div>
          )}
        </div>
      </div>

      {!isError && (
        <div className="mt-3 flex items-center gap-1.5">
          {STAGES.map((stage, i) => {
            const done = i < activeStep || isComplete;
            const current = i === activeStep && !isComplete;
            return (
              <div key={stage} className="flex-1 flex flex-col items-center gap-1">
                <div className="w-full h-1 rounded-full overflow-hidden bg-base">
                  <motion.div
                    className={cn('h-full rounded-full', done ? 'bg-mint' : current ? 'bg-signal' : 'bg-transparent')}
                    initial={{ width: 0 }}
                    animate={{ width: done ? '100%' : current ? '60%' : '0%' }}
                    transition={{ duration: 0.6 }}
                  >
                    {current && <span className="block h-full animate-shimmer" />}
                  </motion.div>
                </div>
                <span className={cn(
                  'font-mono text-[0.56rem] uppercase tracking-wider',
                  done ? 'text-mint' : current ? 'text-signal' : 'text-faint',
                )}>
                  {STAGE_LABELS[stage]}
                </span>
              </div>
            );
          })}
        </div>
      )}

      {meta.length > 0 && !isError && (
        <p className="font-mono text-[0.6rem] text-muted mt-2">{meta.join('  ·  ')}</p>
      )}
      {isError && file.error && <p className="text-xs text-ember mt-2">{file.error}</p>}
    </motion.div>
  );
}
