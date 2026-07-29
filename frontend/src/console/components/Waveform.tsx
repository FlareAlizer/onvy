import { useMemo } from 'react';
import { Check, AlertTriangle, HandHelping } from 'lucide-react';
import type { DialogMoment, MomentType } from '../types';

/** Цвета моментов — общие для дорожки, маркеров и мини-волны. */
const MOMENT_COLOR: Record<MomentType, string> = {
  win: 'var(--color-good)',
  miss: 'var(--color-bad)',
  help: 'var(--color-warn)',
};

const MARKER_CLASS: Record<MomentType, string> = {
  win: 'bg-emerald-500 hover:bg-emerald-600',
  miss: 'bg-rose-500 hover:bg-rose-600',
  help: 'bg-amber-500 hover:bg-amber-600',
};

const GUIDE_CLASS: Record<MomentType, string> = {
  win: 'bg-emerald-200',
  miss: 'bg-rose-200',
  help: 'bg-amber-200',
};

/**
 * Живой эквалайзер — уровень микрофона на бейдже.
 * Это тот же мотив дорожки речи, что и в разборе диалога, только в реальном времени.
 */
export function LiveBars({
  active,
  bars = 14,
  height = 28,
  color = 'currentColor',
  className = '',
}: {
  active: boolean;
  bars?: number;
  height?: number;
  color?: string;
  className?: string;
}) {
  // Фазы разведены, чтобы полосы не пульсировали в унисон.
  const phases = useMemo(
    () => Array.from({ length: bars }, (_, i) => ((i * 137.5) % 100) / 100),
    [bars],
  );
  return (
    <div
      className={`flex items-center gap-[3px] ${className}`}
      style={{ height }}
      aria-hidden
    >
      {phases.map((p, i) => (
        <span
          key={i}
          className={`w-[3px] rounded-full ${active ? 'bar-live' : ''}`}
          style={{
            height: '100%',
            background: color,
            opacity: active ? 0.35 + p * 0.65 : 0.28,
            transform: active ? undefined : `scaleY(${0.18 + p * 0.22})`,
            animationDelay: `${-p * 1.1}s`,
            animationDuration: `${0.85 + p * 0.5}s`,
          }}
        />
      ))}
    </div>
  );
}

/**
 * Дорожка разговора: амплитуда речи по времени с закреплёнными на ней
 * моментами, которые нашёл AI. Клик по маркеру ведёт к реплике в расшифровке.
 */
export function DialogTrack({
  wave,
  moments,
  activeMomentId,
  onSelectMoment,
  height = 96,
}: {
  wave: number[];
  moments: DialogMoment[];
  activeMomentId?: string | null;
  onSelectMoment?: (m: DialogMoment) => void;
  height?: number;
}) {
  const tinted = useMemo(() => {
    // Каждой полосе назначаем тон ближайшего момента, если он рядом.
    return wave.map((amp, i) => {
      const at = (i / (wave.length - 1)) * 100;
      const near = moments.find((m) => Math.abs(m.at - at) <= 2.6);
      return { amp, type: near?.type ?? null, id: near?.id ?? null };
    });
  }, [wave, moments]);

  return (
    <div className="relative pt-8" style={{ height: height + 32 }}>
      {/* Маркеры моментов */}
      {moments.map((m) => {
        const Icon = m.type === 'win' ? Check : m.type === 'miss' ? AlertTriangle : HandHelping;
        return (
          <button
            key={m.id}
            type="button"
            onClick={() => onSelectMoment?.(m)}
            title={m.title}
            className={`absolute top-0 z-10 flex h-6 w-6 -translate-x-1/2 items-center justify-center rounded-full border-2 border-white text-white transition ${
              MARKER_CLASS[m.type]
            } ${activeMomentId === m.id ? 'ring-4 ring-brand-500/25 scale-110' : ''}`}
            style={{ left: `${m.at}%` }}
          >
            <Icon size={12} strokeWidth={3} />
            <span className="sr-only">{m.title}</span>
          </button>
        );
      })}

      {/* Тонкие вертикальные направляющие от маркера к дорожке */}
      {moments.map((m) => (
        <span
          key={`g-${m.id}`}
          aria-hidden
          className={`absolute top-6 w-px ${GUIDE_CLASS[m.type]}`}
          style={{ left: `${m.at}%`, height: 8 }}
        />
      ))}

      <div className="flex items-center gap-px" style={{ height }}>
        {tinted.map((b, i) => (
          <span
            key={i}
            className="flex-1 rounded-full transition-colors"
            style={{
              height: `${Math.max(6, b.amp * 100)}%`,
              background: b.type ? MOMENT_COLOR[b.type] : '#cbd5e1',
              opacity: b.type ? 0.9 : 0.75,
            }}
          />
        ))}
      </div>
    </div>
  );
}

/** Компактная дорожка для строки в списке диалогов. */
export function MiniWave({
  wave,
  moments,
  width = 120,
  height = 26,
}: {
  wave: number[];
  moments: DialogMoment[];
  width?: number;
  height?: number;
}) {
  const step = Math.max(1, Math.floor(wave.length / 34));
  const sampled = wave.filter((_, i) => i % step === 0).slice(0, 34);
  return (
    <div className="flex items-center gap-[2px]" style={{ width, height }} aria-hidden>
      {sampled.map((amp, i) => {
        const at = (i / (sampled.length - 1)) * 100;
        const near = moments.find((m) => Math.abs(m.at - at) <= 4);
        return (
          <span
            key={i}
            className="flex-1 rounded-full"
            style={{
              height: `${Math.max(10, amp * 100)}%`,
              background: near ? MOMENT_COLOR[near.type] : '#d3dae4',
            }}
          />
        );
      })}
    </div>
  );
}
