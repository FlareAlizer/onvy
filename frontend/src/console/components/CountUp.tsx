import { useEffect, useMemo, useRef } from 'react';

/** Плавное замедление к финальному значению. */
const easeOut = (t: number) => 1 - Math.pow(1 - t, 3);

/**
 * Число, которое доезжает до значения при появлении плитки.
 * Идея из react-bits, реализация на requestAnimationFrame: форматирование ru-RU
 * и уважение к prefers-reduced-motion.
 */
export default function CountUp({
  to,
  from = 0,
  duration = 1100,
  className = '',
  decimals = 0,
  prefix = '',
  suffix = '',
}: {
  to: number;
  from?: number;
  /** Длительность в миллисекундах. */
  duration?: number;
  className?: string;
  decimals?: number;
  prefix?: string;
  suffix?: string;
}) {
  const ref = useRef<HTMLSpanElement>(null);

  const format = useMemo(() => {
    const nf = new Intl.NumberFormat('ru-RU', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
    return (v: number) => `${prefix}${nf.format(v)}${suffix}`;
  }, [decimals, prefix, suffix]);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      el.textContent = format(to);
      return;
    }

    let raf = 0;
    let start = 0;
    const tick = (now: number) => {
      if (!start) start = now;
      const t = Math.min(1, (now - start) / duration);
      el.textContent = format(from + (to - from) * easeOut(t));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);

    // В фоновой вкладке кадры не идут. Показать 0 вместо реальной цифры нельзя —
    // поэтому по истечении анимации значение проставляется в любом случае.
    const settle = window.setTimeout(() => {
      el.textContent = format(to);
    }, duration + 120);

    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(settle);
    };
  }, [to, from, duration, format]);

  // Начальное значение рендерим сразу — плитка не мигает пустотой.
  return (
    <span ref={ref} className={className}>
      {format(from)}
    </span>
  );
}
