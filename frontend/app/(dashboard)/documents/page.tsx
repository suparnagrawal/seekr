'use client';

import { useState, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FileText, CheckCircle2, CloudUpload, File, AlertCircle } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { FadeIn } from '@/components/animations/fade-in';
import { StaggerChildren, StaggerItem } from '@/components/animations/stagger-children';
import { useAuth } from '@/lib/auth-context';
import { PageTransition } from '@/components/animations/page-transition';
import { uploadDocument } from '@/lib/api';

interface UploadedFile {
  id: string;
  name: string;
  size: number;
  status: 'uploading' | 'processing' | 'complete' | 'error';
  progress: number;
  documentId?: string;
  error?: string;
}

export default function DocumentsPage() {
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const { hasPermission } = useAuth();

  const handleUpload = async (file: File) => {
    const id = `${file.name}-${Date.now()}`;
    const entry: UploadedFile = { id, name: file.name, size: file.size, status: 'uploading', progress: 50 };
    setFiles((prev) => [...prev, entry]);

    try {
      const result = await uploadDocument(file);
      setFiles((prev) =>
        prev.map((f) =>
          f.id === id ? { ...f, status: 'complete', progress: 100, documentId: result.document_id } : f,
        ),
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      const isConnectionError = message.includes('Failed to fetch') || message.includes('NetworkError');
      setFiles((prev) =>
        prev.map((f) =>
          f.id === id
            ? { ...f, status: 'error', progress: 0, error: isConnectionError ? 'Cannot reach the SEEKR API. Is the backend running and NEXT_PUBLIC_API_URL correct?' : message }
            : f,
        ),
      );
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
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-violet-500/20 to-purple-500/20 flex items-center justify-center">
              <FileText className="w-5 h-5 text-violet-400" />
            </div>
            <div>
              <h1 className="text-2xl font-bold text-zinc-100">Document Library</h1>
              <p className="text-sm text-zinc-500">Upload engineering documents to be indexed by SEEKR</p>
            </div>
          </div>
        </FadeIn>

        {hasPermission('documents:upload') && (
          <FadeIn delay={0.1}>
            <div
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
              className={`border-2 border-dashed rounded-xl p-8 text-center transition-all ${
                dragOver
                  ? 'border-blue-500 bg-blue-500/5'
                  : 'border-zinc-800 hover:border-zinc-700'
              }`}
            >
              <input
                ref={fileInputRef}
                type="file"
                multiple
                onChange={handleFileSelect}
                className="hidden"
                accept=".pdf,.doc,.docx,.txt,.csv,.xlsx"
              />
              <CloudUpload className={`w-10 h-10 mx-auto mb-3 ${dragOver ? 'text-blue-400' : 'text-zinc-600'}`} />
              <p className="text-sm text-zinc-300">
                Drag & drop files here, or{' '}
                <button onClick={() => fileInputRef.current?.click()} className="text-blue-400 hover:underline">
                  browse
                </button>
              </p>
              <p className="text-xs text-zinc-600 mt-1">PDF, DOC, DOCX, TXT, CSV, XLSX</p>
            </div>
          </FadeIn>
        )}

        <AnimatePresence>
          {files.length > 0 && (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-2">
              <h3 className="text-sm font-semibold text-zinc-400">Uploads</h3>
              {files.map((file) => (
                <motion.div
                  key={file.id}
                  initial={{ opacity: 0, y: 8 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-3 p-3 bg-zinc-900/50 border border-zinc-800 rounded-lg"
                >
                  <File className="w-4 h-4 text-zinc-500" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-zinc-300 truncate">{file.name}</p>
                    {file.status === 'uploading' && (
                      <div className="mt-1 h-1 bg-zinc-800 rounded-full overflow-hidden">
                        <motion.div
                          className="h-full bg-blue-500 rounded-full"
                          animate={{ width: `${file.progress}%` }}
                        />
                      </div>
                    )}
                    {file.status === 'error' && (
                      <p className="text-xs text-red-400 mt-0.5">{file.error}</p>
                    )}
                    {file.documentId && (
                      <p className="text-xs text-zinc-500 mt-0.5">ID: {file.documentId}</p>
                    )}
                  </div>
                  {file.status === 'complete' && <CheckCircle2 className="w-4 h-4 text-emerald-400" />}
                  {file.status === 'uploading' && <span className="text-xs text-zinc-500">{Math.round(file.progress)}%</span>}
                  {file.status === 'error' && <AlertCircle className="w-4 h-4 text-red-400" />}
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>

        <FadeIn delay={0.2}>
          <div className="text-center py-12 text-zinc-500">
            <FileText className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p className="text-sm">Upload documents above to start indexing.</p>
            <p className="text-xs mt-1">Uploaded documents will be processed and appear in the knowledge graph.</p>
          </div>
        </FadeIn>
      </div>
    </PageTransition>
  );
}
