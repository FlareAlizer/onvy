import { useMemo } from 'react';
import { ArrowRight, CalendarRange, Info, Target, TrendingDown, TrendingUp } from 'lucide-react';
import { useStore } from '../../store';
import { PageHead } from '../../components/Shell';
import { Card, Chip, EmptyState, SectionHead } from '../../components/ui';
import { ChartCard, StatTile } from '../../components/charts';
import { OnvyMark } from '../../components/Logo';
import { money, num } from '../../lib/format';
import type { PilotMetric } from '../../types';

function fmt(m: PilotMetric, v: number): string {
  if (m.unit === 'money') return money(v, true);
  if (m.unit === 'pct') return `${v.toFixed(v % 1 ? 1 : 0).replace('.', ',')} %`;
  if (m.unit === 'sec') return `${v.toFixed(1).replace('.', ',')} сек`;
  return num(v);
}

/** Изменение показателя в понятную сторону, без причинно-следственных обещаний. */
function delta(m: PilotMetric) {
  const diff = m.during - m.before;
  const improved = m.better === 'up' ? diff > 0 : diff < 0;
  const pp =
    m.unit === 'pct'
      ? `${diff > 0 ? '+' : '−'}${Math.abs(diff).toFixed(Math.abs(diff) % 1 ? 1 : 0).replace('.', ',')} п.п.`
      : m.before === 0
        ? '—'
        : `${diff > 0 ? '+' : '−'}${Math.abs(Math.round((diff / m.before) * 100))} %`;
  return { improved, label: pp, diff };
}

export default function PilotReport() {
  const { data, profile } = useStore();
  const L = profile.labels;
  const pilot = data.pilot;

  const direct = useMemo(() => pilot?.metrics.filter((m) => !m.external) ?? [], [pilot]);
  const external = useMemo(() => pilot?.metrics.filter((m) => m.external) ?? [], [pilot]);

  if (!pilot || pilot.metrics.length === 0) {
    return (
      <>
        <PageHead
          title="Отчёт пилота"
          subtitle="Сравнение показателей до и во время пилота — по всем отраслям в одном формате."
        />
        <EmptyState
          icon={<CalendarRange size={22} />}
          title="Пилот ещё не набрал данных"
          hint={
            pilot
              ? `Пилот запущен ${pilot.startedAt}. Отчёт наполнится после первых недель работы: нужны записанные ${L.interactionPlural.toLowerCase()} и пройденные тесты.`
              : 'Отчёт появится после первых смен: он сравнивает показатели до пилота и во время него.'
          }
        />
        {pilot && pilot.goals.length > 0 && (
          <Card className="mt-4 p-5">
            <h3 className="mb-3 text-[15px] font-semibold text-ink">Цели пилота</h3>
            <ul className="space-y-2.5">
              {pilot.goals.map((g) => (
                <li key={g} className="flex gap-2.5 text-[14px] leading-relaxed text-slate-700">
                  <Target size={15} className="mt-0.5 shrink-0 text-brand-600" />
                  {g}
                </li>
              ))}
            </ul>
          </Card>
        )}
      </>
    );
  }

  const improvedCount = pilot.metrics.filter((m) => delta(m).improved).length;

  return (
    <>
      <PageHead
        title="Отчёт пилота"
        subtitle={`${data.company?.name} · ${pilot.scope} · ${pilot.weeks} недель с ${pilot.startedAt}`}
        action={
          <Chip tone="brand">
            {improvedCount} из {pilot.metrics.length} показателей с положительной динамикой
          </Chip>
        }
      />

      {/* Шапка отчёта — продукт Onvy, настроенный под компанию */}
      <Card className="mb-4 overflow-hidden">
        <div className="flex flex-col gap-4 bg-ink p-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3.5">
            <OnvyMark size={44} />
            <div className="min-w-0">
              <p className="text-[17px] font-semibold tracking-tight text-white">
                Onvy · рабочее пространство {data.company?.name}
              </p>
              <p className="mt-0.5 text-[13px] text-slate-300">
                {L.industry} · платформа развития и поддержки линейного персонала
              </p>
            </div>
          </div>
          <div className="flex gap-6">
            <div>
              <p className="text-[11px] tracking-[0.08em] text-slate-400 uppercase">Период</p>
              <p className="num mt-0.5 text-[15px] font-semibold text-white">{pilot.weeks} нед</p>
            </div>
            <div>
              <p className="text-[11px] tracking-[0.08em] text-slate-400 uppercase">Охват</p>
              <p className="num mt-0.5 text-[15px] font-semibold text-white">{pilot.scope}</p>
            </div>
          </div>
        </div>
      </Card>

      {/* Оговорка о трактовке */}
      <div className="mb-5 flex items-start gap-3 rounded-lg border border-slate-200 bg-slate-50 p-3.5">
        <Info size={16} className="mt-0.5 shrink-0 text-slate-500" />
        <p className="text-[13px] leading-relaxed text-slate-600">
          Ниже показано наблюдаемое изменение показателей за период пилота. Это не доказательство
          причинно-следственной связи: на цифры влияют сезонность, состав команды и другие факторы.
          Устойчивость эффекта — гипотеза для дальнейшей проверки на полном периоде.
        </p>
      </div>

      {pilot.goals.length > 0 && (
        <section className="mb-6">
          <SectionHead title="Что проверяли" hint="Приоритеты, заданные при запуске пилота." />
          <div className="grid gap-3 sm:grid-cols-2">
            {pilot.goals.map((g) => (
              <Card key={g} className="flex items-start gap-3 p-4">
                <Target size={16} className="mt-0.5 shrink-0 text-brand-600" />
                <p className="text-[14px] leading-relaxed text-slate-700">{g}</p>
              </Card>
            ))}
          </div>
        </section>
      )}

      {/* Прямые измерения */}
      <section>
        <SectionHead
          eyebrow="Измеряет Onvy напрямую"
          title="Работа с клиентом и развитие команды"
          hint="Считается по расшифровкам разговоров и результатам обучения — без интеграций."
        />
        <div className="space-y-2.5">
          {direct.map((m) => {
            const d = delta(m);
            const max = Math.max(m.before, m.during) || 1;
            return (
              <Card key={m.key} className="p-4">
                <div className="grid items-center gap-4 sm:grid-cols-[1.2fr_2fr_auto]">
                  <p className="min-w-0 text-[14px] font-semibold text-ink">{m.label}</p>

                  <div className="min-w-0">
                    <div className="mb-1.5 flex items-center gap-2">
                      <span className="num w-20 shrink-0 text-[12px] text-slate-500">до пилота</span>
                      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full bg-slate-300"
                          style={{ width: `${(m.before / max) * 100}%` }}
                        />
                      </div>
                      <span className="num w-24 shrink-0 text-right text-[12px] text-slate-500">
                        {fmt(m, m.before)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="num w-20 shrink-0 text-[12px] text-slate-500">во время</span>
                      <div className="h-2.5 flex-1 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${(m.during / max) * 100}%`,
                            background: d.improved ? 'var(--color-good)' : 'var(--color-warn)',
                          }}
                        />
                      </div>
                      <span className="num w-24 shrink-0 text-right text-[13px] font-semibold text-ink">
                        {fmt(m, m.during)}
                      </span>
                    </div>
                  </div>

                  <span
                    className={`num inline-flex shrink-0 items-center justify-end gap-1 text-[13px] font-semibold ${
                      d.improved ? 'text-emerald-600' : 'text-amber-600'
                    }`}
                  >
                    {d.improved ? <TrendingUp size={14} /> : <TrendingDown size={14} />}
                    {d.label}
                  </span>
                </div>
              </Card>
            );
          })}
        </div>
      </section>

      {/* Бизнес-метрики */}
      {external.length > 0 && (
        <section className="mt-7">
          <SectionHead
            eyebrow="Из учётной системы"
            title="Бизнес-показатели"
            hint="Демо-данные · требуется интеграция с учётной системой. Приведены как контекст, а не как результат работы Onvy."
          />
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {external.map((m) => {
              const d = delta(m);
              return (
                <Card key={m.key} className="p-4">
                  <p className="label truncate">{m.label}</p>
                  <div className="mt-2 flex items-baseline gap-2">
                    <span className="num text-[13px] text-slate-500 line-through">{fmt(m, m.before)}</span>
                    <ArrowRight size={13} className="shrink-0 text-slate-300" />
                    <span className="figure text-[22px] leading-none font-semibold text-ink">
                      {fmt(m, m.during)}
                    </span>
                  </div>
                  <p
                    className={`num mt-2 inline-flex items-center gap-1 text-[12px] font-semibold ${
                      d.improved ? 'text-emerald-600' : 'text-amber-600'
                    }`}
                  >
                    {d.improved ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                    изменение за период {d.label}
                  </p>
                </Card>
              );
            })}
          </div>
        </section>
      )}

      {/* Сводка */}
      <section className="mt-7">
        <SectionHead title="Что дальше" />
        <div className="grid gap-3 sm:grid-cols-3">
          <StatTile
            label="Показателей с положительной динамикой"
            value={`${improvedCount} / ${pilot.metrics.length}`}
          />
          <StatTile
            label="Требуют проверки на полном периоде"
            value={pilot.metrics.length - improvedCount}
            hint="гипотезы для следующего этапа"
          />
          <StatTile label="Длительность пилота" value={`${pilot.weeks} нед`} hint={`с ${pilot.startedAt}`} />
        </div>
        <ChartCard
          title="Все показатели пилота"
          hint="Таблица для выгрузки и обсуждения"
          table={{
            head: ['Показатель', 'До', 'Во время', 'Изменение'],
            rows: pilot.metrics.map((m) => [
              `${m.label}${m.external ? ' (учётная система)' : ''}`,
              fmt(m, m.before),
              fmt(m, m.during),
              delta(m).label,
            ]),
          }}
        >
          <p className="py-8 text-center text-[13px] text-slate-500">
            Нажмите на значок таблицы справа сверху, чтобы увидеть все показатели списком.
          </p>
        </ChartCard>
      </section>
    </>
  );
}
