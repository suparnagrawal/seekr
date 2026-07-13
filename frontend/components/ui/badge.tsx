import { cn } from '@/lib/utils';

interface BadgeProps {
  children: React.ReactNode;
  variant?: 'default' | 'success' | 'warning' | 'destructive' | 'outline';
  className?: string;
}

const variantStyles: Record<string, string> = {
  default: 'bg-signal-soft text-signal border-signal/30',
  success: 'bg-mint-soft text-mint border-mint/30',
  warning: 'bg-signal-soft text-signal border-signal/30',
  destructive: 'bg-ember-soft text-ember border-ember/30',
  outline: 'bg-transparent text-muted border-line-strong',
};

export function Badge({ children, variant = 'default', className }: BadgeProps) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-full border px-2.5 py-0.5 font-mono text-[0.68rem] uppercase tracking-wider',
        variantStyles[variant],
        className,
      )}
    >
      {children}
    </span>
  );
}
