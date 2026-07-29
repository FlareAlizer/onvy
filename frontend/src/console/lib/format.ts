const nf = new Intl.NumberFormat('ru-RU');

export const num = (v: number) => nf.format(Math.round(v));

/** Крупные суммы сжимаем до «10,4 млн» — в плитках и на осях. */
export function money(v: number, compact = false): string {
  if (compact) {
    if (Math.abs(v) >= 1_000_000) return `${(v / 1_000_000).toFixed(1).replace('.', ',')} млн ₽`;
    if (Math.abs(v) >= 10_000) return `${Math.round(v / 1000)} тыс ₽`;
  }
  return `${nf.format(Math.round(v))} ₽`;
}

export const pct = (v: number, digits = 1) =>
  `${v.toFixed(digits).replace('.', ',').replace(',0', '')} %`;

export function initials(name: string): string {
  return name
    .split(' ')
    .filter(Boolean)
    .slice(0, 2)
    .map((p) => p[0]?.toUpperCase() ?? '')
    .join('');
}

export function mmss(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = Math.round(sec % 60);
  return `${m}:${String(s).padStart(2, '0')}`;
}

export function humanDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'long', year: 'numeric' });
}

export function humanDateTime(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })}, ${d.toLocaleTimeString(
    'ru-RU',
    { hour: '2-digit', minute: '2-digit' },
  )}`;
}

/** Склонение: 3 диалога / 5 диалогов */
export function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10;
  const mod100 = n % 100;
  if (mod10 === 1 && mod100 !== 11) return one;
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 10 || mod100 >= 20)) return few;
  return many;
}

/** «312 раз», «134 раза», «1 раз» */
export const times = (n: number) => `${num(n)} ${plural(n, 'раз', 'раза', 'раз')}`;

/** Метки последних 14 дней для оси X. */
export function lastDays(n: number): string[] {
  const out: string[] = [];
  const today = new Date('2026-07-29');
  for (let i = n - 1; i >= 0; i -= 1) {
    const d = new Date(today);
    d.setDate(d.getDate() - i);
    out.push(d.toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' }));
  }
  return out;
}
