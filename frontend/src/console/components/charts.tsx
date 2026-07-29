import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { Table2, ChartNoAxesColumn } from 'lucide-react';

export const SERIES = ['#0284c7', '#eb6834', '#1baf7a', '#eda100', '#7c5cd6'] as const;

const GRID = '#e8edf3';
const AXIS = '#c8d2de';
const MUTED = '#8a97a8';

function useSize<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [w, setW] = useState(0);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(e.contentRect.width));
    ro.observe(el);
    setW(el.clientWidth);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

/**
 * Обёртка графика: заголовок, легенда и переключатель «график / таблица».
 * Таблица — обязательный близнец каждого графика: значения читаются без цвета.
 */
export function ChartCard({
  title,
  hint,
  legend,
  table,
  children,
  action,
}: {
  title: string;
  hint?: string;
  legend?: { label: string; color: string }[];
  table: { head: string[]; rows: (string | number)[][] };
  children: ReactNode;
  action?: ReactNode;
}) {
  const [view, setView] = useState<'chart' | 'table'>('chart');
  return (
    <section className="card p-5">
      <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-[15px] font-semibold text-ink">{title}</h3>
          {hint && <p className="mt-0.5 text-[13px] text-slate-500">{hint}</p>}
        </div>
        <div className="flex items-center gap-2">
          {action}
          <button
            type="button"
            onClick={() => setView(view === 'chart' ? 'table' : 'chart')}
            className="btn-quiet rounded-md p-1.5"
            title={view === 'chart' ? 'Показать таблицей' : 'Показать графиком'}
          >
            {view === 'chart' ? <Table2 size={16} /> : <ChartNoAxesColumn size={16} />}
            <span className="sr-only">
              {view === 'chart' ? 'Показать таблицей' : 'Показать графиком'}
            </span>
          </button>
        </div>
      </div>

      {legend && legend.length > 1 && view === 'chart' && (
        <div className="mb-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">
          {legend.map((l) => (
            <span key={l.label} className="inline-flex items-center gap-1.5 text-[12px] text-slate-600">
              <span className="h-2 w-2 rounded-full" style={{ background: l.color }} />
              {l.label}
            </span>
          ))}
        </div>
      )}

      {view === 'chart' ? (
        children
      ) : (
        <div className="-mx-1 overflow-x-auto scroll-thin">
          <table className="w-full min-w-[380px] text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                {table.head.map((h, i) => (
                  <th
                    key={h}
                    className={`label pb-2 ${i === 0 ? 'text-left' : 'text-right'} font-semibold`}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {table.rows.map((r, ri) => (
                <tr key={ri} className="border-b border-slate-100 last:border-0">
                  {r.map((c, ci) => (
                    <td
                      key={ci}
                      className={`py-2 ${ci === 0 ? 'text-left text-slate-700' : 'num text-right text-ink'}`}
                    >
                      {c}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

interface Tip {
  x: number;
  y: number;
  title: string;
  rows: { label: string; value: string; color?: string }[];
}

function Tooltip({ tip, width }: { tip: Tip | null; width: number }) {
  if (!tip) return null;
  const left = Math.min(Math.max(tip.x, 70), Math.max(70, width - 70));
  return (
    <div
      className="pointer-events-none absolute z-20 -translate-x-1/2 -translate-y-full rounded-lg bg-ink px-3 py-2 text-white shadow-lg"
      style={{ left, top: tip.y - 10 }}
    >
      <p className="mb-1 text-[11px] font-semibold text-white/60">{tip.title}</p>
      {tip.rows.map((r) => (
        <p key={r.label} className="flex items-center gap-2 text-[12px] whitespace-nowrap">
          {r.color && <span className="h-2 w-2 rounded-full" style={{ background: r.color }} />}
          <span className="text-white/70">{r.label}</span>
          <span className="num ml-auto font-semibold">{r.value}</span>
        </p>
      ))}
    </div>
  );
}

export interface Series {
  label: string;
  color: string;
  values: number[];
}

/** Линейный график с перекрестием. Одна ось значений — никогда не две. */
export function TrendChart({
  labels,
  series,
  height = 220,
  format = (v: number) => String(Math.round(v)),
  area = true,
}: {
  labels: string[];
  series: Series[];
  height?: number;
  format?: (v: number) => string;
  area?: boolean;
}) {
  const [ref, w] = useSize<HTMLDivElement>();
  const [tip, setTip] = useState<Tip | null>(null);
  const padL = 52;
  const padR = 12;
  const padT = 12;
  const padB = 26;
  const innerW = Math.max(10, w - padL - padR);
  const innerH = height - padT - padB;

  const all = series.flatMap((s) => s.values);
  const max = Math.max(...all, 1);
  const min = Math.min(...all, 0);
  const span = max - min || 1;
  const niceMax = max + span * 0.12;
  const niceMin = Math.max(0, min - span * 0.08);
  const range = niceMax - niceMin || 1;

  const x = (i: number) => padL + (i / Math.max(1, labels.length - 1)) * innerW;
  const y = (v: number) => padT + innerH - ((v - niceMin) / range) * innerH;

  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => niceMin + t * range);

  const onMove = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const i = Math.round(((px - padL) / innerW) * (labels.length - 1));
    const idx = Math.max(0, Math.min(labels.length - 1, i));
    setTip({
      x: x(idx),
      y: y(Math.max(...series.map((s) => s.values[idx] ?? 0))),
      title: labels[idx],
      rows: series.map((s) => ({ label: s.label, value: format(s.values[idx] ?? 0), color: s.color })),
    });
  };

  const hoverIdx = tip ? labels.indexOf(tip.title) : -1;

  return (
    <div
      ref={ref}
      className="relative"
      onMouseMove={onMove}
      onMouseLeave={() => setTip(null)}
      style={{ height }}
    >
      {w > 0 && (
        <svg width={w} height={height} role="img" aria-label={series.map((s) => s.label).join(', ')}>
          {ticks.map((t, i) => (
            <g key={i}>
              <line x1={padL} x2={w - padR} y1={y(t)} y2={y(t)} stroke={GRID} strokeWidth={1} />
              <text x={padL - 10} y={y(t) + 4} textAnchor="end" fontSize={11} fill={MUTED} className="num">
                {format(t)}
              </text>
            </g>
          ))}
          <line x1={padL} x2={w - padR} y1={y(niceMin)} y2={y(niceMin)} stroke={AXIS} strokeWidth={1} />

          {area && series.length === 1 && (
            <path
              d={`M ${x(0)} ${y(niceMin)} ${series[0].values
                .map((v, i) => `L ${x(i)} ${y(v)}`)
                .join(' ')} L ${x(labels.length - 1)} ${y(niceMin)} Z`}
              fill={series[0].color}
              opacity={0.08}
            />
          )}

          {series.map((s) => (
            <path
              key={s.label}
              d={s.values.map((v, i) => `${i === 0 ? 'M' : 'L'} ${x(i)} ${y(v)}`).join(' ')}
              fill="none"
              stroke={s.color}
              strokeWidth={2}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          ))}

          {hoverIdx >= 0 && (
            <>
              <line
                x1={x(hoverIdx)}
                x2={x(hoverIdx)}
                y1={padT}
                y2={padT + innerH}
                stroke={AXIS}
                strokeWidth={1}
              />
              {series.map((s) => (
                <circle
                  key={s.label}
                  cx={x(hoverIdx)}
                  cy={y(s.values[hoverIdx] ?? 0)}
                  r={4.5}
                  fill={s.color}
                  stroke="#fff"
                  strokeWidth={2}
                />
              ))}
            </>
          )}

          {labels.map((l, i) =>
            i % Math.ceil(labels.length / 7) === 0 || i === labels.length - 1 ? (
              <text
                key={l + i}
                x={x(i)}
                y={height - 8}
                textAnchor={i === 0 ? 'start' : i === labels.length - 1 ? 'end' : 'middle'}
                fontSize={11}
                fill={MUTED}
              >
                {l}
              </text>
            ) : null,
          )}
        </svg>
      )}
      <Tooltip tip={tip} width={w} />
    </div>
  );
}

/** Вертикальные столбцы — одна серия, один цвет. */
export function BarSeries({
  labels,
  values,
  color = SERIES[0],
  height = 200,
  format = (v: number) => String(Math.round(v)),
  highlight,
  maxValue,
}: {
  labels: string[];
  values: number[];
  color?: string;
  height?: number;
  format?: (v: number) => string;
  highlight?: number;
  /** Потолок оси. Для процентов задаём 100, иначе ось уезжает выше предела шкалы. */
  maxValue?: number;
}) {
  const [ref, w] = useSize<HTMLDivElement>();
  const [tip, setTip] = useState<Tip | null>(null);
  const padL = 52;
  const padR = 8;
  const padT = 10;
  const padB = 26;
  const innerW = Math.max(10, w - padL - padR);
  const innerH = height - padT - padB;
  const max = maxValue ?? Math.max(...values, 1) * 1.12;
  const slot = innerW / values.length;
  const barW = Math.max(4, Math.min(34, slot - 6)); // 2px+ зазор между столбцами
  const ticks = [0, 0.5, 1].map((t) => t * max);

  return (
    <div ref={ref} className="relative" style={{ height }} onMouseLeave={() => setTip(null)}>
      {w > 0 && (
        <svg width={w} height={height}>
          {ticks.map((t, i) => (
            <g key={i}>
              <line
                x1={padL}
                x2={w - padR}
                y1={padT + innerH - (t / max) * innerH}
                y2={padT + innerH - (t / max) * innerH}
                stroke={i === 0 ? AXIS : GRID}
                strokeWidth={1}
              />
              <text
                x={padL - 10}
                y={padT + innerH - (t / max) * innerH + 4}
                textAnchor="end"
                fontSize={11}
                fill={MUTED}
                className="num"
              >
                {format(t)}
              </text>
            </g>
          ))}
          {values.map((v, i) => {
            const h = Math.max(2, (v / max) * innerH);
            const bx = padL + i * slot + (slot - barW) / 2;
            const on = highlight === i;
            return (
              <rect
                key={i}
                x={bx}
                y={padT + innerH - h}
                width={barW}
                height={h}
                rx={4}
                fill={color}
                opacity={highlight === undefined || on ? 1 : 0.32}
                onMouseEnter={() =>
                  setTip({
                    x: bx + barW / 2,
                    y: padT + innerH - h,
                    title: labels[i],
                    rows: [{ label: 'Значение', value: format(v), color }],
                  })
                }
              />
            );
          })}
          {labels.map((l, i) =>
            i % Math.ceil(labels.length / 7) === 0 || i === labels.length - 1 ? (
              <text
                key={l + i}
                x={padL + i * slot + slot / 2}
                y={height - 8}
                textAnchor="middle"
                fontSize={11}
                fill={MUTED}
              >
                {l}
              </text>
            ) : null,
          )}
        </svg>
      )}
      <Tooltip tip={tip} width={w} />
    </div>
  );
}

/**
 * Горизонтальный рейтинг с прямыми подписями значений.
 * Прямые подписи здесь обязательны: они снимают требование к контрасту заливки.
 */
export function RankBars({
  rows,
  format = (v: number) => String(Math.round(v)),
  color = SERIES[0],
  max: maxProp,
}: {
  rows: { label: string; value: number; sub?: string; tone?: string }[];
  format?: (v: number) => string;
  color?: string;
  max?: number;
}) {
  const max = maxProp ?? Math.max(...rows.map((r) => r.value), 1);
  return (
    <ul className="space-y-3">
      {rows.map((r) => (
        <li key={r.label}>
          <div className="mb-1.5 flex items-baseline justify-between gap-3">
            <span className="min-w-0 truncate text-[13px] font-medium text-slate-700">{r.label}</span>
            <span className="num shrink-0 text-[13px] font-semibold text-ink">{format(r.value)}</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
              <div
                className="h-full rounded-full transition-[width] duration-700"
                style={{ width: `${(r.value / max) * 100}%`, background: r.tone ?? color }}
              />
            </div>
            {r.sub && <span className="num w-16 shrink-0 text-right text-[11px] text-slate-500">{r.sub}</span>}
          </div>
        </li>
      ))}
    </ul>
  );
}

/** Кольцо для доли — не больше четырёх сегментов, зазор 2px поверхностью. */
export function Donut({
  segments,
  size = 148,
  centerLabel,
  centerValue,
}: {
  segments: { label: string; value: number; color: string }[];
  size?: number;
  centerLabel: string;
  centerValue: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const total = segments.reduce((a, s) => a + s.value, 0) || 1;
  const r = size / 2 - 12;
  const c = 2 * Math.PI * r;
  let offset = 0;

  return (
    <div className="flex items-center gap-5">
      <div className="relative shrink-0" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          {segments.map((s, i) => {
            const len = (s.value / total) * c;
            const el = (
              <circle
                key={s.label}
                cx={size / 2}
                cy={size / 2}
                r={r}
                fill="none"
                stroke={s.color}
                strokeWidth={hover === i ? 20 : 16}
                strokeDasharray={`${Math.max(0, len - 3)} ${c - Math.max(0, len - 3)}`}
                strokeDashoffset={-offset}
                strokeLinecap="butt"
                className="transition-[stroke-width]"
                onMouseEnter={() => setHover(i)}
                onMouseLeave={() => setHover(null)}
              />
            );
            offset += len;
            return el;
          })}
        </svg>
        <div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center">
          <span className="figure text-2xl font-semibold text-ink">{centerValue}</span>
          <span className="mt-0.5 text-[11px] text-slate-500">{centerLabel}</span>
        </div>
      </div>
      <ul className="min-w-0 flex-1 space-y-2">
        {segments.map((s, i) => (
          <li
            key={s.label}
            className="flex items-center gap-2 text-[13px]"
            onMouseEnter={() => setHover(i)}
            onMouseLeave={() => setHover(null)}
          >
            <span className="h-2.5 w-2.5 shrink-0 rounded-full" style={{ background: s.color }} />
            <span className="min-w-0 truncate text-slate-600">{s.label}</span>
            <span className="num ml-auto font-semibold text-ink">{s.value}</span>
            <span className="num w-11 shrink-0 text-right text-slate-500">
              {Math.round((s.value / total) * 100)}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Компактная искровая линия для строк таблицы. */
export function Spark({
  values,
  width = 76,
  height = 26,
  color = SERIES[0],
}: {
  values: number[];
  width?: number;
  height?: number;
  color?: string;
}) {
  const max = Math.max(...values, 1);
  const min = Math.min(...values, 0);
  const span = max - min || 1;
  const d = values
    .map((v, i) => {
      const x = (i / Math.max(1, values.length - 1)) * (width - 2) + 1;
      const y = height - 2 - ((v - min) / span) * (height - 4);
      return `${i === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
    })
    .join(' ');
  return (
    <svg width={width} height={height} aria-hidden className="shrink-0">
      <path d={d} fill="none" stroke={color} strokeWidth={1.75} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Плитка показателя. Крупная цифра — пропорциональные знаки, не табличные. */
export function StatTile({
  label,
  value,
  delta,
  hint,
  icon,
  spark,
}: {
  label: string;
  value: ReactNode;
  delta?: { value: string; good: boolean };
  hint?: string;
  icon?: ReactNode;
  spark?: number[];
}) {
  return (
    <div className="card p-4">
      <div className="mb-2 flex items-start justify-between gap-2">
        <p className="label">{label}</p>
        {icon && <span className="text-slate-300">{icon}</span>}
      </div>
      <p className="figure text-[26px] leading-none font-semibold text-ink">{value}</p>
      <div className="mt-2.5 flex items-end justify-between gap-2">
        <div className="min-w-0">
          {delta && (
            <span
              className={`num inline-flex items-center gap-1 text-[12px] font-semibold ${
                delta.good ? 'text-emerald-600' : 'text-rose-600'
              }`}
            >
              {delta.good ? '↑' : '↓'} {delta.value}
            </span>
          )}
          {hint && <p className="truncate text-[12px] text-slate-500">{hint}</p>}
        </div>
        {spark && <Spark values={spark} />}
      </div>
    </div>
  );
}

/** Хук на случай, если график должен перерисоваться после смены вкладки. */
export function useMounted() {
  const [m, setM] = useState(false);
  useEffect(() => setM(true), []);
  return m;
}
