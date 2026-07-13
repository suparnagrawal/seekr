'use client';

import { forwardRef, type ButtonHTMLAttributes } from 'react';
import { cn } from '@/lib/utils';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'default' | 'destructive' | 'outline' | 'secondary' | 'ghost' | 'link';
  size?: 'default' | 'sm' | 'lg' | 'icon';
}

const variantStyles: Record<string, string> = {
  default:
    'bg-signal text-base font-semibold hover:bg-signal-bright shadow-[0_6px_20px_-8px_var(--signal)]',
  destructive: 'bg-ember text-white font-semibold hover:brightness-110',
  outline: 'border border-line-strong bg-transparent text-ink hover:bg-surface hover:border-signal/50',
  secondary: 'bg-surface text-ink border border-line hover:border-line-strong hover:bg-panel',
  ghost: 'text-muted hover:bg-surface hover:text-ink',
  link: 'text-signal underline-offset-4 hover:underline',
};

const sizeStyles: Record<string, string> = {
  default: 'h-10 px-4 text-sm',
  sm: 'h-8 px-3 text-xs',
  lg: 'h-12 px-6 text-base',
  icon: 'h-9 w-9',
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'default', size = 'default', disabled, ...props }, ref) => {
    return (
      <button
        ref={ref}
        className={cn(
          'group relative inline-flex items-center justify-center gap-2 rounded-md transition-all duration-200 overflow-hidden',
          'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal/60 focus-visible:ring-offset-2 focus-visible:ring-offset-base',
          'active:scale-[0.98] disabled:pointer-events-none disabled:opacity-45',
          variantStyles[variant],
          sizeStyles[size],
          className,
        )}
        disabled={disabled}
        {...props}
      />
    );
  },
);
Button.displayName = 'Button';
