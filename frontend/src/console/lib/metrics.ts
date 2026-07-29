import type { MetricDef, MetricUnit } from '../industryProfiles';
import type { Employee, SalesPoint } from '../types';
import { money, num, pct } from './format';

/** Единый формат значения метрики — цифры совпадают на всех экранах. */
export function formatMetric(value: number, unit: MetricUnit, compact = false): string {
  switch (unit) {
    case 'money':
      return money(value, compact);
    case 'pct':
      return pct(value);
    case 'sec':
      return `${value.toFixed(1).replace('.', ',')} сек`;
    default:
      return num(value);
  }
}

/** Значение метрики у сотрудника: сначала ядро, затем отраслевые. */
export function employeeMetric(e: Employee, key: string): number {
  if (key in e.stats) return e.stats[key as keyof Employee['stats']];
  return e.industry[key] ?? 0;
}

/** Значение метрики у точки. */
export function pointMetric(p: SalesPoint, key: string): number {
  if (key in p && typeof (p as unknown as Record<string, unknown>)[key] === 'number') {
    return (p as unknown as Record<string, number>)[key];
  }
  return p.industry[key] ?? 0;
}

/** Достигнута ли цель с учётом направления метрики. */
export function kpiReached(def: MetricDef, current: number, target: number): boolean {
  return def.lowerIsBetter ? current <= target : current >= target;
}

/**
 * Прогресс к цели, 0–100 %. Для метрик, где меньше — лучше,
 * прогресс считается от превышения, а не от абсолютного значения.
 */
export function kpiProgress(def: MetricDef, current: number, target: number): number {
  if (!target) return 0;
  if (def.lowerIsBetter) {
    if (current <= target) return 100;
    return Math.max(0, Math.min(100, (target / current) * 100));
  }
  return Math.max(0, Math.min(100, (current / target) * 100));
}

/** Тон для показателя относительно нормы. */
export function toneFor(value: number, target: number, lowerIsBetter = false): 'good' | 'warn' | 'bad' {
  const ratio = lowerIsBetter ? target / Math.max(value, 0.001) : value / Math.max(target, 0.001);
  if (ratio >= 1) return 'good';
  if (ratio >= 0.85) return 'warn';
  return 'bad';
}
