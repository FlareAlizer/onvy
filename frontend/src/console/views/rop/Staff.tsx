import { useMemo, useState } from 'react';
import {
  ArrowLeft,
  BluetoothOff,
  GraduationCap,
  HandHelping,
  Target,
  Trash2,
  TrendingUp,
  Users,
  Wifi,
} from 'lucide-react';
import { useStore } from '../../store';
import { Avatar, Card, Chip, EmptyState, Field, Modal, Progress, SectionHead } from '../../components/ui';
import { PageHead } from '../../components/Shell';
import { ChartCard, RankBars, Spark, StatTile, TrendChart } from '../../components/charts';
import { DialogList } from '../employee/MyDialogs';
import { DialogDetail } from '../../components/DialogDetail';
import { lastDays, money, num, pct, plural, times } from '../../lib/format';
import { employeeMetric, formatMetric, kpiProgress, kpiReached } from '../../lib/metrics';
import { findMetric } from '../../industryProfiles';
import { PERIOD_LABEL } from '../../demo/shared';
import type { Dialog, Employee, KpiPeriod } from '../../types';

function KpiDialog({
  open,
  onClose,
  targets,
}: {
  open: boolean;
  onClose: () => void;
  targets: Employee[];
}) {
  const { setKpi, profile } = useStore();
  const metrics = profile.kpiMetrics;
  const [metric, setMetric] = useState(metrics[1]?.key ?? 'deals');
  const [period, setPeriod] = useState<KpiPeriod>('day');
  const [target, setTarget] = useState('5');
  const [note, setNote] = useState('');
  const [saved, setSaved] = useState(false);

  const def = findMetric(profile, metric);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const value = Number(target.replace(/\s/g, '').replace(',', '.'));
    if (!Number.isFinite(value) || value <= 0) return;
    targets.forEach((t) => {
      // Дневные и недельные цели считаем от месячного факта, чтобы прогресс был честным.
      const raw = employeeMetric(t, metric);
      const current =
        def.unit === 'count' && period !== 'month' ? Math.round(raw / (period === 'day' ? 20 : 4)) : raw;
      setKpi({ employeeId: t.id, metric, period, target: value, current, setBy: 'Вы', note: note.trim() || undefined });
    });
    setSaved(true);
    setTimeout(() => {
      setSaved(false);
      onClose();
    }, 1100);
  };

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Поставить KPI"
      subtitle={targets.length === 1 ? targets[0].name : `${targets.length} сотрудникам — цель применится к каждому`}
      width="max-w-lg"
    >
      <form onSubmit={submit} className="space-y-4">
        <Field label="Показатель" hint={`Список зависит от отрасли: ${profile.labels.industry.toLowerCase()}`}>
          <select className="field" value={metric} onChange={(e) => setMetric(e.target.value)}>
            <optgroup label="Ядро Onvy">
              {metrics.slice(0, 9).map((m) => (
                <option key={m.key} value={m.key}>
                  {m.label}
                </option>
              ))}
            </optgroup>
            {metrics.length > 9 && (
              <optgroup label={profile.labels.industry}>
                {metrics.slice(9).map((m) => (
                  <option key={m.key} value={m.key}>
                    {m.label}
                  </option>
                ))}
              </optgroup>
            )}
          </select>
        </Field>

        <Field label="Период">
          <div className="grid grid-cols-3 gap-2">
            {(['day', 'week', 'month'] as KpiPeriod[]).map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => setPeriod(p)}
                className={`rounded-lg border px-3 py-2.5 text-[13px] font-semibold transition ${
                  period === p
                    ? 'border-brand-500 bg-brand-50 text-brand-800'
                    : 'border-slate-200 text-slate-600 hover:border-slate-300'
                }`}
              >
                {PERIOD_LABEL[p].replace('на ', '')}
              </button>
            ))}
          </div>
        </Field>

        <Field
          label="Цель"
          hint={
            def.lowerIsBetter
              ? 'Для этого показателя цель — не превышать значение'
              : 'Значение, которое нужно достичь за период'
          }
        >
          <input
            className="field num"
            value={target}
            onChange={(e) => setTarget(e.target.value)}
            inputMode="decimal"
            required
          />
        </Field>

        <Field label="Комментарий" hint="Необязательно — сотрудник увидит его рядом с целью">
          <textarea
            className="field min-h-[74px] resize-y"
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Что именно нужно изменить в работе"
          />
        </Field>

        <div className="flex gap-2 pt-1">
          <button type="button" className="btn-ghost flex-1" onClick={onClose}>
            Отмена
          </button>
          <button type="submit" className="console-btn-primary flex-1">
            {saved ? 'Цель поставлена' : 'Поставить цель'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

function EmployeeProfile({ employee, onBack }: { employee: Employee; onBack: () => void }) {
  const { data, removeKpi, profile } = useStore();
  const L = profile.labels;
  const [kpiOpen, setKpiOpen] = useState(false);
  const [openDialog, setOpenDialog] = useState<Dialog | null>(null);

  const point = data.points.find((p) => p.id === employee.pointId);
  const kpis = data.kpis.filter((k) => k.employeeId === employee.id);
  const dialogs = data.dialogs.filter((d) => d.employeeId === employee.id);
  const tests = data.tests.filter((t) => t.assignedTo.includes(employee.id));
  const labels = lastDays(14);

  const myErrors = useMemo(() => {
    const counts = new Map<string, number>();
    dialogs.forEach((d) =>
      d.moments.filter((m) => m.type === 'miss').forEach((m) => counts.set(m.title, (counts.get(m.title) ?? 0) + 1)),
    );
    return [...counts.entries()].sort((a, b) => b[1] - a[1]);
  }, [dialogs]);

  if (openDialog) {
    return (
      <>
        <button type="button" onClick={() => setOpenDialog(null)} className="btn-quiet -ml-3 mb-4">
          <ArrowLeft size={16} /> К карточке сотрудника
        </button>
        <PageHead title={openDialog.topic} subtitle={`${employee.name} · ${openDialog.category}`} />
        <DialogDetail dialog={openDialog} who={employee.name} />
      </>
    );
  }

  return (
    <>
      <button type="button" onClick={onBack} className="btn-quiet -ml-3 mb-4">
        <ArrowLeft size={16} /> Все сотрудники
      </button>

      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div className="flex items-center gap-4">
          <Avatar name={employee.name} size={52} />
          <div className="min-w-0">
            <h1 className="text-[24px] leading-tight font-semibold tracking-tight text-ink">
              {employee.name}
            </h1>
            <p className="mt-1 text-[14px] text-slate-500">
              {employee.position} · {point?.name} · в компании с{' '}
              {new Date(employee.hiredAt).toLocaleDateString('ru-RU', { month: 'long', year: 'numeric' })}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Chip
            tone={employee.badgeOnline ? 'good' : 'bad'}
            icon={employee.badgeOnline ? <Wifi size={11} /> : <BluetoothOff size={11} />}
          >
            {employee.badgeOnline ? 'Бейдж в эфире' : 'Бейдж не в эфире'}
          </Chip>
          <button type="button" className="console-btn-primary" onClick={() => setKpiOpen(true)}>
            <Target size={15} /> Поставить KPI
          </button>
        </div>
      </div>

      {/* Оценка не только по выручке */}
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label={L.script} value={pct(employee.stats.scriptCompliance, 0)} hint="норма — 85 %" />
        <StatTile label="Решено самостоятельно" value={pct(employee.stats.autonomy, 0)} />
        <StatTile
          label="Скорость ответа"
          value={`${employee.stats.responseSec.toFixed(1).replace('.', ',')} сек`}
          hint="меньше — лучше"
        />
        <StatTile
          label="Обучение"
          value={`${employee.trainingDone} / ${tests.length || employee.trainingTotal}`}
          hint={`онбординг ${employee.onboarding} %`}
        />
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile
          label="Выручка за месяц"
          value={money(employee.stats.revenue, true)}
          hint="демо-данные · учётная система"
          spark={employee.daily}
        />
        <StatTile
          label={L.outcomePlural}
          value={num(employee.stats.deals)}
          hint={`из ${num(employee.stats.dialogs)} ${plural(employee.stats.dialogs, ...L.interactionForms)}`}
        />
        <StatTile label="Средний чек" value={money(employee.stats.avgCheck)} />
        <StatTile
          label="Результативность"
          value={pct(employee.stats.conversion)}
          hint={`точка ${pct(point?.conversion ?? 0)}`}
        />
      </div>

      <section className="mt-4 grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        <ChartCard
          title="Выручка по дням"
          hint="Последние две недели · демо-данные"
          table={{ head: ['День', 'Выручка, ₽'], rows: labels.map((l, i) => [l, num(employee.daily[i] ?? 0)]) }}
        >
          <TrendChart
            labels={labels}
            series={[{ label: 'Выручка', color: 'var(--color-series-1)', values: employee.daily }]}
            format={(v) => (v >= 1000 ? `${Math.round(v / 1000)}к` : String(Math.round(v)))}
          />
        </ChartCard>

        <Card className="p-5">
          <h3 className="text-[15px] font-semibold text-ink">
            Показатели: {L.industry.toLowerCase()}
          </h3>
          <p className="mt-0.5 mb-4 text-[13px] text-slate-500">Специфика отрасли</p>
          <ul className="space-y-2.5">
            {profile.metrics.map((m) => (
              <li key={m.key} className="flex items-baseline justify-between gap-3">
                <span className="min-w-0 truncate text-[13px] text-slate-600">{m.label}</span>
                <span className="num shrink-0 text-[13px] font-semibold text-ink">
                  {formatMetric(employeeMetric(employee, m.key), m.unit, true)}
                </span>
              </li>
            ))}
          </ul>
          <div className="mt-4 flex items-center gap-2 border-t border-slate-100 pt-4 text-[13px] text-slate-600">
            <HandHelping size={15} className="shrink-0 text-slate-500" />
            Обращений к {L.helpTargetDative}: {num(employee.stats.helpRequests)}
          </div>
        </Card>
      </section>

      {/* Цели */}
      <section className="mt-7">
        <SectionHead
          title="Цели сотрудника"
          hint="Сотрудник видит эти цели на своём главном экране."
          action={
            <button type="button" className="btn-ghost" onClick={() => setKpiOpen(true)}>
              <Target size={15} /> Добавить цель
            </button>
          }
        />
        {kpis.length === 0 ? (
          <EmptyState icon={<Target size={22} />} title="Целей нет" hint="Поставьте первую цель — она сразу появится у сотрудника." />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {kpis.map((k) => {
              const def = findMetric(profile, k.metric);
              const share = kpiProgress(def, k.current, k.target);
              const done = kpiReached(def, k.current, k.target);
              return (
                <Card key={k.id} className="p-4">
                  <div className="mb-3 flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="truncate text-[14px] font-semibold text-ink">{def.label}</p>
                      <p className="mt-0.5 text-[12px] text-slate-500">{PERIOD_LABEL[k.period]}</p>
                    </div>
                    <button
                      type="button"
                      className="btn-quiet shrink-0 rounded-md p-1.5 text-slate-300 hover:text-rose-600"
                      onClick={() => removeKpi(k.id)}
                    >
                      <Trash2 size={14} />
                      <span className="sr-only">Снять цель</span>
                    </button>
                  </div>
                  <div className="mb-2 flex items-baseline gap-1.5">
                    <span className="figure text-[20px] leading-none font-semibold text-ink">
                      {formatMetric(k.current, def.unit, true)}
                    </span>
                    <span className="num text-[13px] text-slate-500">
                      {def.lowerIsBetter ? 'при цели' : 'из'} {formatMetric(k.target, def.unit, true)}
                    </span>
                  </div>
                  <Progress value={share} tone={done ? 'good' : share >= 70 ? 'warn' : 'brand'} />
                  {k.note && <p className="mt-2.5 text-[12px] text-slate-500">{k.note}</p>}
                </Card>
              );
            })}
          </div>
        )}
      </section>

      {/* Характеристика */}
      <section className="mt-7 grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <h3 className="mb-3 flex items-center gap-2 text-[15px] font-semibold text-ink">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-emerald-50 text-emerald-600">
              <TrendingUp size={14} />
            </span>
            Сильные стороны
          </h3>
          {employee.strengths.length === 0 ? (
            <p className="text-[14px] text-slate-500">Данных пока недостаточно.</p>
          ) : (
            <ul className="space-y-2.5">
              {employee.strengths.map((s) => (
                <li key={s} className="flex gap-2.5 text-[14px] leading-relaxed text-slate-700">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500" />
                  {s}
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card className="p-5">
          <h3 className="mb-3 flex items-center gap-2 text-[15px] font-semibold text-ink">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-amber-50 text-amber-600">
              <Target size={14} />
            </span>
            Зоны роста
          </h3>
          {employee.growthAreas.length === 0 ? (
            <p className="text-[14px] text-slate-500">Данных пока недостаточно.</p>
          ) : (
            <ul className="space-y-2.5">
              {employee.growthAreas.map((s) => (
                <li key={s} className="flex gap-2.5 text-[14px] leading-relaxed text-slate-700">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                  {s}
                </li>
              ))}
            </ul>
          )}
        </Card>
      </section>

      {/* Вопросы, ошибки, тесты */}
      <section className="mt-4 grid gap-4 lg:grid-cols-2">
        {employee.topRequests.length > 0 && (
          <ChartCard
            title="Частые вопросы к нему"
            table={{
              head: ['Вопрос', 'Раз', 'Результативность'],
              rows: employee.topRequests.map((r) => [r.label, r.count, pct(r.conversion, 0)]),
            }}
          >
            <RankBars
              rows={employee.topRequests.map((r) => ({
                label: r.label,
                value: r.count,
                sub: pct(r.conversion, 0),
              }))}
              format={(v) => times(v)}
            />
          </ChartCard>
        )}

        <Card className="p-5">
          <h3 className="mb-3 text-[15px] font-semibold text-ink">Ошибки и результаты тестов</h3>
          {myErrors.length > 0 && (
            <ul className="mb-4 space-y-2">
              {myErrors.map(([label, count]) => (
                <li key={label} className="flex items-baseline justify-between gap-3 text-[13px]">
                  <span className="min-w-0 text-slate-600">{label}</span>
                  <span className="num shrink-0 font-semibold text-rose-700">{times(count)}</span>
                </li>
              ))}
            </ul>
          )}
          {tests.length === 0 ? (
            <p className="text-[14px] text-slate-500">Тесты не назначены.</p>
          ) : (
            <ul className="space-y-2 border-t border-slate-100 pt-3">
              {tests.map((t) => {
                const score = t.results[employee.id];
                return (
                  <li key={t.id} className="flex items-center gap-3 text-[13px]">
                    <GraduationCap size={14} className="shrink-0 text-slate-500" />
                    <span className="min-w-0 flex-1 truncate text-slate-700">{t.title}</span>
                    {score === undefined ? (
                      <Chip tone="neutral">не пройден</Chip>
                    ) : (
                      <Chip tone={score >= t.passScore ? 'good' : 'warn'}>{score} %</Chip>
                    )}
                  </li>
                );
              })}
            </ul>
          )}
        </Card>
      </section>

      {employee.topItems.length > 0 && (
        <section className="mt-4">
          <ChartCard
            title={`${L.items}: что продаёт`}
            table={{
              head: ['Позиция', 'Кол-во', 'Выручка, ₽'],
              rows: employee.topItems.map((p) => [p.name, p.qty, num(p.revenue)]),
            }}
          >
            <RankBars
              rows={employee.topItems.map((p) => ({ label: p.name, value: p.revenue, sub: `${p.qty} шт` }))}
              format={(v) => money(v, true)}
            />
          </ChartCard>
        </section>
      )}

      {dialogs.length > 0 && (
        <section className="mt-7">
          <SectionHead title={`Последние ${L.interactionPlural.toLowerCase()}`} />
          <Card>
            <DialogList dialogs={dialogs} onOpen={setOpenDialog} />
          </Card>
        </section>
      )}

      <KpiDialog open={kpiOpen} onClose={() => setKpiOpen(false)} targets={[employee]} />
    </>
  );
}

export default function Staff() {
  const { data, profile } = useStore();
  const L = profile.labels;
  const [selected, setSelected] = useState<Employee | null>(null);
  const [pointId, setPointId] = useState('all');
  const [bulkOpen, setBulkOpen] = useState(false);
  const [sort, setSort] = useState<'revenue' | 'conversion' | 'onboarding' | 'script'>('revenue');

  const list = useMemo(() => {
    const filtered = data.employees.filter((e) => pointId === 'all' || e.pointId === pointId);
    return [...filtered].sort((a, b) => {
      if (sort === 'revenue') return b.stats.revenue - a.stats.revenue;
      if (sort === 'conversion') return b.stats.conversion - a.stats.conversion;
      if (sort === 'script') return a.stats.scriptCompliance - b.stats.scriptCompliance;
      return a.onboarding - b.onboarding;
    });
  }, [data.employees, pointId, sort]);

  if (selected) {
    const fresh = data.employees.find((e) => e.id === selected.id) ?? selected;
    return <EmployeeProfile employee={fresh} onBack={() => setSelected(null)} />;
  }

  return (
    <>
      <PageHead
        title="Сотрудники и KPI"
        subtitle={`Весь штат: результат, качество разговоров, обучение и самостоятельность. Нажмите на строку, чтобы открыть карточку.`}
        action={
          data.employees.length > 0 ? (
            <button type="button" className="console-btn-primary" onClick={() => setBulkOpen(true)}>
              <Target size={15} /> Поставить KPI всем
            </button>
          ) : undefined
        }
      />

      {data.employees.length === 0 ? (
        <EmptyState
          icon={<Users size={22} />}
          title="В штате пока никого"
          hint={`${L.employeePlural} появятся здесь, как только зарегистрируются по коду компании.`}
        />
      ) : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <select
              className="field w-auto min-w-[180px] py-2 text-[13px]"
              value={pointId}
              onChange={(e) => setPointId(e.target.value)}
            >
              <option value="all">Все {L.locationPlural.toLowerCase()}</option>
              {data.points.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}
                </option>
              ))}
            </select>
            <select
              className="field w-auto min-w-[190px] py-2 text-[13px]"
              value={sort}
              onChange={(e) => setSort(e.target.value as typeof sort)}
            >
              <option value="revenue">Сначала по выручке</option>
              <option value="conversion">Сначала по результативности</option>
              <option value="script">Сначала слабый скрипт</option>
              <option value="onboarding">Сначала кто хуже обучен</option>
            </select>
          </div>

          <Card className="overflow-hidden">
            <div className="overflow-x-auto scroll-thin">
              <table className="w-full min-w-[1000px]">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/70">
                    {[
                      'Сотрудник',
                      'Бейдж',
                      'Выручка',
                      L.outcomePlural,
                      'Средний чек',
                      'Результативность',
                      L.script,
                      'Обучение',
                      'Динамика',
                    ].map((h, i) => (
                      <th key={h} className={`label px-3 py-2.5 ${i === 0 ? 'text-left' : 'text-right'}`}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {list.map((e) => {
                    const point = data.points.find((p) => p.id === e.pointId);
                    return (
                      <tr
                        key={e.id}
                        onClick={() => setSelected(e)}
                        className="cursor-pointer border-b border-slate-100 transition last:border-0 hover:bg-slate-50"
                      >
                        <td className="px-3 py-3">
                          <div className="flex items-center gap-3">
                            <Avatar name={e.name} size={34} />
                            <div className="min-w-0">
                              <p className="truncate text-[14px] font-semibold text-ink">{e.name}</p>
                              <p className="truncate text-[12px] text-slate-500">
                                {e.position} · {point?.name}
                              </p>
                            </div>
                          </div>
                        </td>
                        <td className="px-3 py-3 text-right">
                          <span
                            className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-semibold ${
                              e.badgeOnline ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'
                            }`}
                          >
                            {e.badgeOnline ? <Wifi size={11} /> : <BluetoothOff size={11} />}
                            {e.badgeOnline ? `${e.badgeBattery}%` : 'офлайн'}
                          </span>
                        </td>
                        <td className="num px-3 py-3 text-right text-[13px] font-semibold text-ink">
                          {money(e.stats.revenue, true)}
                        </td>
                        <td className="num px-3 py-3 text-right text-[13px] text-slate-600">
                          {num(e.stats.deals)}
                        </td>
                        <td className="num px-3 py-3 text-right text-[13px] text-slate-600">
                          {money(e.stats.avgCheck, true)}
                        </td>
                        <td className="num px-3 py-3 text-right text-[13px] text-slate-600">
                          {pct(e.stats.conversion)}
                        </td>
                        <td className="px-3 py-3 text-right">
                          <span
                            className={`num text-[13px] font-semibold ${
                              e.stats.scriptCompliance >= 85
                                ? 'text-emerald-700'
                                : e.stats.scriptCompliance >= 75
                                  ? 'text-amber-700'
                                  : 'text-rose-700'
                            }`}
                          >
                            {e.stats.scriptCompliance} %
                          </span>
                        </td>
                        <td className="px-3 py-3">
                          <div className="ml-auto flex w-24 items-center gap-2">
                            <Progress
                              value={e.onboarding}
                              height={6}
                              tone={e.onboarding >= 90 ? 'good' : e.onboarding >= 50 ? 'warn' : 'bad'}
                            />
                            <span className="num w-9 shrink-0 text-right text-[12px] text-slate-500">
                              {e.onboarding}%
                            </span>
                          </div>
                        </td>
                        <td className="px-3 py-3">
                          <div className="flex justify-end">
                            <Spark values={e.daily} />
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>

          <p className="mt-3 text-[12px] text-muted">
            Выручка, чек и количество {L.outcomePlural.toLowerCase()} — демо-данные, требуется интеграция
            с учётной системой. Качество разговоров, обучение и бейджи Onvy измеряет напрямую.
          </p>

          <KpiDialog open={bulkOpen} onClose={() => setBulkOpen(false)} targets={list} />
        </>
      )}
    </>
  );
}
