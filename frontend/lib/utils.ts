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

export function getNodeColor(type: string): string {
  const colors: Record<string, string> = {
    equipment: '#3b82f6',
    document: '#8b5cf6',
    procedure: '#10b981',
    system: '#f59e0b',
    component: '#06b6d4',
    failure_mode: '#ef4444',
  };
  return colors[type] || '#6b7280';
}

export function getStatusColor(status: 'red' | 'amber' | 'green'): string {
  const colors = { red: '#ef4444', amber: '#f59e0b', green: '#10b981' };
  return colors[status];
}

export function getRiskColor(score: number): string {
  if (score >= 0.7) return '#ef4444';
  if (score >= 0.4) return '#f59e0b';
  return '#10b981';
}
