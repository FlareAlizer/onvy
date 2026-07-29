/** Детерминированный шум — дорожки разговоров одинаковы при каждой загрузке. */
export function seeded(seed: number) {
  let s = seed;
  return () => {
    s = (s * 1664525 + 1013904223) % 4294967296;
    return s / 4294967296;
  };
}

export function makeWave(seed: number, len = 120): number[] {
  const rnd = seeded(seed);
  const out: number[] = [];
  let level = 0.4;
  for (let i = 0; i < len; i += 1) {
    // Речь идёт всплесками: фраза — пауза — фраза.
    const phrase = Math.sin((i / len) * Math.PI * 7) * 0.3 + 0.55;
    level = level * 0.55 + (rnd() * phrase + 0.08) * 0.45;
    out.push(Math.min(1, Math.max(0.06, level)));
  }
  return out;
}

export function daily(seed: number, base: number): number[] {
  const rnd = seeded(seed);
  return Array.from({ length: 14 }, (_, i) => {
    const weekend = i % 7 === 5 || i % 7 === 6 ? 1.35 : 1;
    return Math.round(base * weekend * (0.65 + rnd() * 0.7));
  });
}

export const PERIOD_LABEL: Record<string, string> = {
  day: 'на день',
  week: 'на неделю',
  month: 'на месяц',
};
