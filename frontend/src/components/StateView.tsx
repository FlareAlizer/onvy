// Три состояния, которые обязаны быть честными, а не спрятанными: загрузка,
// пусто, ошибка сети. Используются и на входе, и во всех вкладках управляющего —
// вайфай чайханы моргает, и это норма жизни продукта, а не крайний случай.

import type { ReactNode } from 'react';
import { Loader2, WifiOff } from 'lucide-react';

export function LoadingState({ label = 'Загружаю…' }: { label?: string }) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 py-16 text-stone-400">
      <Loader2 size={28} className="animate-spin" />
      <p className="text-base">{label}</p>
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-4 py-16 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-amber-500/15 text-amber-300">
        <WifiOff size={26} />
      </div>
      <p className="max-w-xs text-base leading-relaxed text-stone-300">{message}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="rounded-2xl bg-stone-800 px-6 py-3 text-base font-medium text-stone-50 transition-transform duration-150 ease-out active:scale-[0.97]"
        >
          Повторить
        </button>
      )}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-3 py-16 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-stone-800 text-stone-400">
        {icon}
      </div>
      <h3 className="text-lg font-semibold text-stone-100">{title}</h3>
      {description && (
        <p className="max-w-xs text-sm leading-relaxed text-stone-400">{description}</p>
      )}
      {action}
    </div>
  );
}
