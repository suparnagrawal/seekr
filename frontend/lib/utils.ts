import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatDate(date: string | Date): string {
  return new Intl.DateTimeFormat('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  }).format(new Date(date));
}

export function formatRelativeTime(date: string | Date): string {
  const now = Date.now();
  const then = new Date(date).getTime();
  const diff = now - then;
  const minutes = Math.floor(diff / 60000);
  const hours = Math.floor(diff / 3600000);
  const days = Math.floor(diff / 86400000);

  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes}m ago`;
  if (hours < 24) return `${hours}h ago`;
  if (days < 7) return `${days}d ago`;
  return formatDate(date);
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + '…';
}

/**
 * Knowledge-graph node palette — a warm-biased industrial spectrum tuned to
 * read on both the light (paper) and dark (graphite) canvases.
 */
export function getNodeColor(type: string): string {
  const colors: Record<string, string> = {
    equipment: '#f5a524',    // signal amber (the hero type)
    system: '#ff6a3d',       // ember orange
    component: '#ffd166',    // gold
    procedure: '#3fd6b0',    // mint
    document: '#9fb4c7',     // steel / neutral
    failure_mode: '#ff5470', // hot alarm
  };
  return colors[type] || '#8b8477';
}

export function getStatusColor(status: 'red' | 'amber' | 'green'): string {
  const colors = { red: '#ff5470', amber: '#f5a524', green: '#3fd6b0' };
  return colors[status];
}

export function getRiskColor(score: number): string {
  if (score >= 0.7) return '#ff5470';
  if (score >= 0.4) return '#f5a524';
  return '#3fd6b0';
}
