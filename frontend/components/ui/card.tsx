import { cn } from '@/lib/utils';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  hover?: boolean;
  ticked?: boolean;
  onClick?: () => void;
}

export function Card({ children, className, hover = false, ticked = false, onClick }: CardProps) {
  return (
    <div
      className={cn(
        'relative rounded-lg panel',
        ticked && 'ticked',
        hover && 'transition-all duration-300 hover:border-signal/40 hover:shadow-[0_18px_50px_-30px_var(--shadow)]',
        onClick && 'cursor-pointer',
        className,
      )}
      onClick={onClick}
    >
      {children}
    </div>
  );
}

export function CardHeader({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('px-5 py-4 border-b border-line', className)}>{children}</div>;
}

export function CardContent({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('px-5 py-4', className)}>{children}</div>;
}

export function CardFooter({ children, className }: { children: React.ReactNode; className?: string }) {
  return <div className={cn('px-5 py-3 border-t border-line', className)}>{children}</div>;
}
