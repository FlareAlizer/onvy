import { useEffect, useState } from 'react';
import {
  AlertTriangle,
  Award,
  BookOpen,
  Flame,
  Gauge,
  GraduationCap,
  HandHelping,
  Loader2,
  MessageSquareQuote,
  Target,
  TrendingUp,
} from 'lucide-react';
import { useStore, KPI_METRIC_META } from '../../store';
import { EmployeeBadgePanel } from '../../components/BadgePanel';
import { PageHead } from '../../components/Shell';
import { Card, Chip, EmptyState, Progress, SectionHead } from '../../components/ui';
import { ChartCard, RankBars, StatTile, TrendChart } from '../../components/charts';
import CountUp from '../../components/CountUp';
import { lastDays, money, num, pct, plural, times } from '../../lib/format';
import { employeeMetric, formatMetric, kpiProgress, kpiReached } from '../../lib/metrics';
import { PERIOD_LABEL } from '../../emptyState';
import { fetchEmployeeKpis, getSession, type KpiMetric, type KpiOut } from '../../../lib/api';

export default function MyStats({ onOpenTraining }: { onOpenTraining: () => void }) {
  const { me, data, profile } = useStore();
  const L = profile.labels;
  const [myKpis, setMyKpis] = useState<KpiOut[] | null>(null);
  const [kpiError, setKpiError] = useState<string | null>(null);

  // Свои цели — из настоящего API, не из локальной догадки: только там
  // прогресс посчитан по реальным сменам (app/services/stats.py).
  useEffect(() => {
    if (!me) return;
    const venueId = getSession()?.venueId;
    if (!venueId) return;
    setMyKpis(null);
    setKpiError(null);
    fetchEmployeeKpis(venueId, Number(me.id))
      .then(setMyKpis)
      .catch(() => setKpiError('Не удалось загрузить цели'));
  }, [me?.id]);

  if (!me) return null;

  const point = data.points.find((p) => p.id === me.pointId);
  const peers = data.employees.filter((e) => e.pointId === me.pointId);
  const rank =
    [...peers].sort((a, b) => b.stats.revenue - a.stats.revenue).findIndex((e) => e.id === me.id) + 1;
  const topRequest = me.topRequests[0];
  const labels = lastDays(14);
  const hasData = me.stats.dialogs > 0;

  const pendingTests = data.tests.filter(
    (t) => t.assignedTo.includes(me.id) && (t.results[me.id] ?? 0) < t.passScore,
  );
  const freshKnowledge = [...data.faq]
    .filter((f) => f.status !== 'draft')
    .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt))
    .slice(0, 3);

  return (
    <>
      <PageHead
        title={`Здравствуйте, ${me.name.split(' ')[0]}`}
        subtitle={
          hasData
            ? `${point?.name ?? L.location} · ${me.position} · ${rank} место по выручке на точке из ${peers.length}`
            : `${point?.name ?? L.location} · ${me.position}`
        }
        action={
          <div className="flex flex-wrap items-center gap-2">
            <Chip tone="brand" icon={<Award size={12} />}>
              Уровень {me.level}
            </Chip>
            <Chip tone="neutral" icon={<Flame size={12} />}>
              {num(me.xp)} XP
            </Chip>
          </div>
        }
      />

      <EmployeeBadgePanel />

      {/* Цели показываем всегда, а не только после первой смены: их ставят
          заранее, и сотрудник должен увидеть норму ещё до выхода в зал. */}
      <section className="mt-6">
        <SectionHead
          eyebrow="Поставил руководитель"
          title="Мои цели"
          hint={`Прогресс обновляется после каждого закрытого ${L.interactionGenitive}.`}
        />
        {kpiError ? (
          <EmptyState icon={<AlertTriangle size={22} />} title="Не удалось загрузить цели" hint={kpiError} />
        ) : myKpis === null ? (
          <div className="flex justify-center py-10 text-slate-400">
            <Loader2 size={22} className="animate-spin" />
          </div>
        ) : myKpis.length === 0 ? (
          <EmptyState
            icon={<Target size={22} />}
            title="Целей пока нет"
            hint="Руководитель ещё не назначил вам KPI. Как только это произойдёт, цели появятся здесь."
          />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {myKpis.map((k) => {
              const def = KPI_METRIC_META[k.metric as KpiMetric] ?? { key: k.metric, label: k.metric, unit: 'count' as const };
              const hasCurrent = k.current !== null;
              const share = hasCurrent ? kpiProgress(def, k.current as number, Number(k.target)) : 0;
              const done = hasCurrent ? kpiReached(def, k.current as number, Number(k.target)) : false;
              return (
                <Card key={k.id} className="p-4">
                  <div className="mb-3 flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-[14px] font-semibold text-ink">{def.label}</p>
                      <p className="mt-0.5 text-[12px] text-slate-500">
                        {PERIOD_LABEL[k.period]}
                        {def.lowerIsBetter ? ' · цель — не превышать' : ''}
                      </p>
                    </div>
                    {hasCurrent && (
                      <Chip tone={done ? 'good' : share >= 70 ? 'warn' : 'neutral'}>
                        {Math.round(share)}%
                      </Chip>
                    )}
                  </div>
                  <div className="mb-2 flex items-baseline gap-1.5">
                    <span className="figure text-[22px] leading-none font-semibold text-ink">
                      {hasCurrent ? formatMetric(k.current as number, def.unit, true) : '—'}
                    </span>
                    <span className="num text-[13px] text-slate-500">
                      {def.lowerIsBetter ? 'при цели' : 'из'} {formatMetric(Number(k.target), def.unit, true)}
                    </span>
                  </div>
                  {hasCurrent ? (
                    <Progress value={share} tone={done ? 'good' : share >= 70 ? 'warn' : 'brand'} />
                  ) : (
                    <p className="text-[12px] text-slate-400">Данных за период ещё нет</p>
                  )}
                  {k.note && (
                    <p className="mt-2.5 border-l-2 border-slate-200 pl-2.5 text-[12px] text-slate-500">
                      {k.note}
                    </p>
                  )}
                </Card>
              );
            })}
          </div>
        )}
      </section>

      {!hasData ? (
        <div className="mt-6">
          <EmptyState
            icon={<Gauge size={22} />}
            title="Статистика появится после первой смены"
            hint="Возьмите телефон с гарнитурой и выходите в зал. Цифры считаются по настоящим сменам — придуманных здесь не будет."
          />
        </div>
      ) : (
        <>
          {/* Показатели */}
          <section className="mt-7">
            <SectionHead title="Показатели за месяц" />
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <StatTile
                label="Выручка"
                value={<CountUp to={me.stats.revenue / 1_000_000} decimals={1} suffix=" млн ₽" />}
                hint="нет источника · нужна учётная система"
                spark={me.daily}
              />
              <StatTile
                label={L.outcomePlural}
                value={<CountUp to={me.stats.deals} />}
                hint={`из ${num(me.stats.dialogs)} ${plural(me.stats.dialogs, ...L.interactionForms)}`}
              />
              <StatTile
                label="Средний чек"
                value={<CountUp to={me.stats.avgCheck} suffix=" ₽" />}
                hint="нет источника · нужна учётная система"
              />
              <StatTile
                label="Результативность"
                value={<CountUp to={me.stats.conversion} decimals={1} suffix=" %" />}
                hint={`по точке ${pct(point?.conversion ?? 0)}`}
              />
            </div>
          </section>

          {/* Динамика и качество */}
          <section className="mt-4 grid gap-4 lg:grid-cols-[1.55fr_1fr]">
            <ChartCard
              title="Выручка по дням"
              hint="Последние две недели · нет источника"
              table={{ head: ['День', 'Выручка, ₽'], rows: labels.map((l, i) => [l, num(me.daily[i] ?? 0)]) }}
            >
              <TrendChart
                labels={labels}
                series={[{ label: 'Выручка', color: 'var(--color-series-1)', values: me.daily }]}
                format={(v) => (v >= 1000 ? `${Math.round(v / 1000)}к` : String(Math.round(v)))}
              />
            </ChartCard>

            <Card className="p-5">
              <h3 className="text-[15px] font-semibold text-ink">Качество работы</h3>
              <p className="mt-0.5 mb-4 text-[13px] text-slate-500">
                Измеряется Onvy по расшифровкам {L.interactionGenitivePlural}
              </p>
              <div className="space-y-4">
                {[
                  { label: L.script, value: me.stats.scriptCompliance, target: 85, text: pct(me.stats.scriptCompliance) },
                  { label: 'Решено самостоятельно', value: me.stats.autonomy, target: 80, text: pct(me.stats.autonomy) },
                  {
                    label: 'Скорость ответа',
                    value: Math.max(0, 100 - me.stats.responseSec * 12),
                    target: 62,
                    text: `${me.stats.responseSec.toFixed(1).replace('.', ',')} сек`,
                  },
                ].map((m) => (
                  <div key={m.label}>
                    <div className="mb-1.5 flex items-baseline justify-between gap-2">
                      <span className="min-w-0 truncate text-[13px] font-medium text-slate-700">{m.label}</span>
                      <span className="num shrink-0 text-[13px] font-semibold text-ink">{m.text}</span>
                    </div>
                    <Progress
                      value={m.value}
                      tone={m.value >= m.target ? 'good' : m.value >= m.target * 0.85 ? 'warn' : 'bad'}
                    />
                  </div>
                ))}
                <div className="flex items-center gap-2 border-t border-slate-100 pt-3 text-[13px] text-slate-600">
                  <HandHelping size={15} className="shrink-0 text-slate-500" />
                  Обращений к {L.helpTargetDative}: {num(me.stats.helpRequests)} за месяц
                </div>
              </div>
            </Card>
          </section>

          {/* Отраслевые показатели */}
          {profile.metrics.length > 0 && (
            <section className="mt-4">
              <SectionHead
                title={`Показатели: ${L.industry.toLowerCase()}`}
                hint="Специфика вашей отрасли — их же руководитель может ставить как цели."
              />
              <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                {profile.metrics.map((m) => (
                  <Card key={m.key} className="p-4">
                    <p className="label truncate">{m.label}</p>
                    <p className="figure mt-1.5 text-[22px] leading-none font-semibold text-ink">
                      {formatMetric(employeeMetric(me, m.key), m.unit, true)}
                    </p>
                    {m.external && (
                      <p className="mt-1.5 text-[11px] text-slate-500">нужна учётная система</p>
                    )}
                  </Card>
                ))}
              </div>
            </section>
          )}

          {/* Что продаю и о чём спрашивают */}
          <section className="mt-4 grid gap-4 lg:grid-cols-2">
            <ChartCard
              title={`Мои ${L.items.toLowerCase()}`}
              hint="Топ позиций за месяц"
              table={{
                head: ['Позиция', 'Кол-во', 'Выручка, ₽'],
                rows: me.topItems.map((p) => [p.name, p.qty, num(p.revenue)]),
              }}
            >
              <RankBars
                rows={me.topItems.map((p) => ({ label: p.name, value: p.revenue, sub: `${p.qty} шт` }))}
                format={(v) => money(v, true)}
              />
            </ChartCard>

            <ChartCard
              title={`О чём спрашивают ${L.clientPlural.toLowerCase()}`}
              hint="Самые частые вопросы и их результативность"
              table={{
                head: ['Вопрос', 'Раз', 'Результативность'],
                rows: me.topRequests.map((r) => [r.label, r.count, pct(r.conversion, 0)]),
              }}
            >
              <RankBars
                rows={me.topRequests.map((r) => ({
                  label: r.label,
                  value: r.count,
                  sub: pct(r.conversion, 0),
                  tone:
                    r.conversion >= 55
                      ? 'var(--color-series-3)'
                      : r.conversion >= 30
                        ? 'var(--color-series-4)'
                        : 'var(--color-series-2)',
                }))}
                format={(v) => times(v)}
              />
              {topRequest && (
                <div className="mt-4 flex items-start gap-2.5 rounded-lg bg-brand-50 p-3.5">
                  <MessageSquareQuote size={16} className="mt-0.5 shrink-0 text-brand-600" />
                  <p className="text-[13px] leading-relaxed text-brand-900">
                    Чаще всего вас спрашивают: «{topRequest.label}» — {times(topRequest.count)},
                    результативность {pct(topRequest.conversion, 0)}. Отработайте этот вопрос до
                    автоматизма.
                  </p>
                </div>
              )}
            </ChartCard>
          </section>

          {/* Сильные стороны и рост */}
          <section className="mt-4 grid gap-4 lg:grid-cols-2">
            <Card className="p-5">
              <h3 className="mb-3 flex items-center gap-2 text-[15px] font-semibold text-ink">
                <span className="flex h-6 w-6 items-center justify-center rounded-md bg-emerald-50 text-emerald-600">
                  <TrendingUp size={14} />
                </span>
                Что получается хорошо
              </h3>
              <ul className="space-y-2.5">
                {me.strengths.map((s) => (
                  <li key={s} className="flex gap-2.5 text-[14px] leading-relaxed text-slate-700">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500" />
                    {s}
                  </li>
                ))}
              </ul>
            </Card>

            <Card className="p-5">
              <h3 className="mb-3 flex items-center gap-2 text-[15px] font-semibold text-ink">
                <span className="flex h-6 w-6 items-center justify-center rounded-md bg-amber-50 text-amber-600">
                  <Target size={14} />
                </span>
                Что исправить
              </h3>
              <ul className="space-y-2.5">
                {me.growthAreas.map((s) => (
                  <li key={s} className="flex gap-2.5 text-[14px] leading-relaxed text-slate-700">
                    <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                    {s}
                  </li>
                ))}
              </ul>
            </Card>
          </section>
        </>
      )}

      {/* Задачи обучения и обновления базы */}
      <section className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <h3 className="mb-3 flex items-center gap-2 text-[15px] font-semibold text-ink">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-brand-50 text-brand-700">
              <GraduationCap size={14} />
            </span>
            Задачи обучения
          </h3>
          {pendingTests.length === 0 ? (
            <p className="text-[14px] text-slate-500">Всё пройдено. Новые тесты назначит руководитель.</p>
          ) : (
            <ul className="space-y-2.5">
              {pendingTests.map((t) => (
                <li key={t.id} className="flex items-center gap-3 rounded-lg bg-slate-50 p-3">
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[14px] font-semibold text-ink">{t.title}</span>
                    <span className="num block text-[12px] text-slate-500">
                      до {t.deadline} · проходной {t.passScore} %
                    </span>
                  </span>
                  <button type="button" className="btn-ghost shrink-0 px-3 py-1.5 text-[12px]" onClick={onOpenTraining}>
                    Пройти
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="p-5">
          <h3 className="mb-3 flex items-center gap-2 text-[15px] font-semibold text-ink">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-slate-100 text-slate-500">
              <BookOpen size={14} />
            </span>
            Обновления базы знаний
          </h3>
          {freshKnowledge.length === 0 ? (
            <p className="text-[14px] text-slate-500">База знаний пока пуста.</p>
          ) : (
            <ul className="space-y-2.5">
              {freshKnowledge.map((f) => (
                <li key={f.id} className="rounded-lg bg-slate-50 p-3">
                  <div className="flex items-start justify-between gap-2">
                    <p className="min-w-0 text-[13px] font-semibold text-ink">«{f.question}»</p>
                    <span className="num shrink-0 text-[11px] text-slate-500">{f.updatedAt}</span>
                  </div>
                  <p className="mt-1 text-[13px] leading-relaxed text-slate-600">{f.bestAnswer}</p>
                  {!f.verified && (
                    <Chip tone="warn">
                      {f.status === 'outdated' ? 'Данные устарели' : 'Не подтверждено'}
                    </Chip>
                  )}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>
    </>
  );
}
