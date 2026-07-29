import { useState } from 'react';
import { ArrowLeft, Check, Copy, HandHelping, MapPin, Radio, Store, UserRound, Users } from 'lucide-react';
import { useStore } from '../../store';
import { PageHead } from '../../components/Shell';
import { Avatar, Card, Chip, EmptyState, Progress, SectionHead } from '../../components/ui';
import { BarSeries, ChartCard, RankBars, StatTile } from '../../components/charts';
import { money, num, pct } from '../../lib/format';
import { formatMetric, pointMetric } from '../../lib/metrics';
import type { SalesPoint } from '../../types';

function PointCard({ point, onBack }: { point: SalesPoint; onBack: () => void }) {
  const { data, profile } = useStore();
  const L = profile.labels;
  const staff = data.employees.filter((e) => e.pointId === point.id);
  const online = staff.filter((e) => e.badgeOnline).length;
  const planShare = point.plan ? (point.revenue / point.plan) * 100 : 0;
  const dialogs = data.dialogs.filter((d) => d.pointId === point.id);

  return (
    <>
      <button type="button" onClick={onBack} className="btn-quiet -ml-3 mb-4">
        <ArrowLeft size={16} /> Все {L.locationPlural.toLowerCase()}
      </button>

      <PageHead
        title={point.name}
        subtitle={`${point.city}, ${point.address} · руководитель: ${point.manager || '—'}`}
        action={
          <Chip tone={planShare >= 100 ? 'good' : planShare >= 85 ? 'warn' : 'bad'}>
            План {Math.round(planShare)} %
          </Chip>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label={L.script} value={pct(point.scriptCompliance, 0)} hint="норма — 85 %" />
        <StatTile label="Обучение" value={pct(point.training, 0)} hint="прогресс команды" />
        <StatTile
          label={`Обращения: ${L.helpTarget.toLowerCase()}`}
          value={num(point.helpRequests)}
          hint="за месяц"
        />
        <StatTile label="Бейджи в эфире" value={`${online} / ${staff.length}`} />
      </div>

      <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <StatTile label="Выручка" value={money(point.revenue, true)} hint={`план ${money(point.plan, true)}`} />
        <StatTile label={L.interactionPlural} value={num(point.interactions)} />
        <StatTile label="Средний чек" value={money(point.avgCheck, true)} />
        <StatTile label="Результативность" value={pct(point.conversion)} />
      </div>

      {profile.metrics.length > 0 && (
        <section className="mt-4">
          <SectionHead title={`Показатели: ${L.industry.toLowerCase()}`} />
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {profile.metrics.map((m) => (
              <Card key={m.key} className="p-4">
                <p className="label truncate">{m.label}</p>
                <p className="figure mt-1.5 text-[22px] leading-none font-semibold text-ink">
                  {formatMetric(pointMetric(point, m.key), m.unit, true)}
                </p>
                <p className="mt-1.5 text-[11px] text-slate-500">
                  {m.external ? 'нужна учётная система' : 'измеряет Onvy'}
                </p>
              </Card>
            ))}
          </div>
        </section>
      )}

      <section className="mt-4 grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <h3 className="mb-3 text-[15px] font-semibold text-ink">Команда точки</h3>
          {staff.length === 0 ? (
            <p className="text-[14px] text-slate-500">Сотрудники ещё не подключились.</p>
          ) : (
            <ul className="space-y-2.5">
              {staff.map((e) => (
                <li key={e.id} className="flex items-center gap-3">
                  <Avatar name={e.name} size={32} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate text-[14px] font-semibold text-ink">{e.name}</span>
                    <span className="block text-[12px] text-slate-500">{e.position}</span>
                  </span>
                  <span className="num shrink-0 text-[13px] text-slate-600">{e.stats.scriptCompliance} %</span>
                  <span
                    className={`h-2.5 w-2.5 shrink-0 rounded-full ${e.badgeOnline ? 'bg-emerald-500' : 'bg-slate-300'}`}
                    title={e.badgeOnline ? 'Бейдж в эфире' : 'Бейдж не в эфире'}
                  />
                </li>
              ))}
            </ul>
          )}
        </Card>

        <Card className="p-5">
          <h3 className="mb-3 text-[15px] font-semibold text-ink">{L.zones}</h3>
          <div className="flex flex-wrap gap-1.5">
            {point.zones.length === 0 ? (
              <p className="text-[14px] text-slate-500">Зоны не заданы.</p>
            ) : (
              point.zones.map((z) => (
                <span key={z} className="rounded-md bg-slate-100 px-2.5 py-1.5 text-[12px] font-medium text-slate-600">
                  {z}
                </span>
              ))
            )}
          </div>
          <div className="mt-4 border-t border-slate-100 pt-4">
            <p className="label mb-2">Выполнение плана</p>
            <Progress
              value={planShare}
              tone={planShare >= 100 ? 'good' : planShare >= 85 ? 'warn' : 'bad'}
              height={10}
            />
            <p className="num mt-2 text-[13px] text-slate-600">
              {money(point.revenue, true)} из {money(point.plan, true)}
            </p>
          </div>
          <div className="mt-4 flex items-center gap-2 border-t border-slate-100 pt-4 text-[13px] text-slate-600">
            <HandHelping size={15} className="shrink-0 text-slate-500" />
            {num(dialogs.length)} разобранных {L.interactionGenitivePlural} за период
          </div>
        </Card>
      </section>
    </>
  );
}

export default function Points() {
  const { data, profile } = useStore();
  const L = profile.labels;
  const [copied, setCopied] = useState(false);
  const [selected, setSelected] = useState<SalesPoint | null>(null);
  const { points, employees } = data;

  if (selected) {
    const fresh = points.find((p) => p.id === selected.id) ?? selected;
    return <PointCard point={fresh} onBack={() => setSelected(null)} />;
  }

  const totalRevenue = points.reduce((a, p) => a + p.revenue, 0);
  const totalPlan = points.reduce((a, p) => a + p.plan, 0);
  const totalInteractions = points.reduce((a, p) => a + p.interactions, 0);
  const ranked = [...points].sort((a, b) => b.revenue - a.revenue);

  const copyCode = () => {
    if (!data.company) return;
    navigator.clipboard?.writeText(data.company.joinCode);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <>
      <PageHead
        title="Торговые точки"
        subtitle={`Сравнение по результату, качеству разговоров и покрытию бейджами. Здесь же — код для подключения ${L.employeePlural.toLowerCase()}.`}
      />

      <Card className="mb-5 p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="label mb-1">Код компании</p>
            <p className="text-[13px] text-slate-500">
              Сотрудник вводит его при регистрации — так он попадает в вашу сеть и выбирает свою точку.
            </p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <code className="num rounded-lg border border-slate-200 bg-slate-50 px-3.5 py-2.5 text-[15px] font-semibold text-ink">
              {data.company?.joinCode}
            </code>
            <button type="button" className="btn-ghost" onClick={copyCode}>
              {copied ? <Check size={15} /> : <Copy size={15} />}
              {copied ? 'Скопировано' : 'Копировать'}
            </button>
          </div>
        </div>
      </Card>

      {points.length === 0 ? (
        <EmptyState
          icon={<Store size={22} />}
          title={`${L.locationPlural} пока нет`}
          hint={`Добавьте точку, чтобы закрепить за ней ${L.employeePlural.toLowerCase()} и увидеть её показатели.`}
        />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatTile
              label={`${L.locationPlural} в сети`}
              value={points.length}
              hint={`${employees.length} человек в штате`}
            />
            <StatTile label="Выручка сети" value={money(totalRevenue, true)} hint={`план ${money(totalPlan, true)}`} />
            <StatTile
              label="Выполнение плана"
              value={pct((totalRevenue / (totalPlan || 1)) * 100, 0)}
              hint="демо-данные · учётная система"
            />
            <StatTile
              label={L.interactionPlural}
              value={num(totalInteractions)}
              hint="записаны и разобраны"
            />
          </div>

          <section className="mt-4 grid gap-4 lg:grid-cols-2">
            <ChartCard
              title={`Выручка: ${L.locationPlural.toLowerCase()}`}
              hint="За текущий месяц · демо-данные"
              table={{
                head: [L.location, 'Выручка, ₽', 'План, ₽'],
                rows: ranked.map((p) => [p.name, num(p.revenue), num(p.plan)]),
              }}
            >
              <RankBars
                rows={ranked.map((p) => ({
                  label: p.name,
                  value: p.revenue,
                  sub: pct((p.revenue / (p.plan || 1)) * 100, 0),
                  tone:
                    p.revenue >= p.plan
                      ? 'var(--color-series-3)'
                      : p.revenue / (p.plan || 1) >= 0.85
                        ? 'var(--color-series-4)'
                        : 'var(--color-series-2)',
                }))}
                format={(v) => money(v, true)}
              />
              <p className="mt-4 text-[12px] leading-relaxed text-slate-500">
                Цвет — выполнение плана: зелёный от 100 %, жёлтый 85–100 %, оранжевый ниже 85 %. Процент
                продублирован цифрой справа.
              </p>
            </ChartCard>

            <ChartCard
              title={`${L.script}: сравнение точек`}
              hint="Единообразие стандартов между локациями"
              table={{
                head: [L.location, 'Скрипт, %', 'Обучение, %'],
                rows: ranked.map((p) => [p.name, p.scriptCompliance, p.training]),
              }}
            >
              <BarSeries
                labels={ranked.map((p) => p.name.split(' ').slice(-1)[0])}
                values={ranked.map((p) => p.scriptCompliance)}
                format={(v) => `${Math.round(v)}%`}
                height={220}
                maxValue={100}
              />
            </ChartCard>
          </section>

          <section className="mt-7">
            <SectionHead
              title={`${L.locationPlural} подробно`}
              hint="Нажмите на карточку, чтобы открыть локацию."
            />
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {ranked.map((p) => {
                const staff = employees.filter((e) => e.pointId === p.id);
                const online = staff.filter((e) => e.badgeOnline).length;
                const planShare = p.plan ? (p.revenue / p.plan) * 100 : 0;
                return (
                  <button
                    key={p.id}
                    type="button"
                    onClick={() => setSelected(p)}
                    className="card p-5 text-left transition hover:border-brand-300 hover:bg-brand-50/20"
                  >
                    <div className="mb-3 flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <h3 className="truncate text-[15px] font-semibold text-ink">{p.name}</h3>
                        <p className="mt-0.5 flex items-center gap-1.5 truncate text-[12px] text-slate-500">
                          <MapPin size={12} className="shrink-0" />
                          {p.city}, {p.address}
                        </p>
                      </div>
                      <Chip tone={planShare >= 100 ? 'good' : planShare >= 85 ? 'warn' : 'bad'}>
                        {Math.round(planShare)}%
                      </Chip>
                    </div>

                    <div className="mb-3">
                      <div className="mb-1.5 flex items-baseline justify-between">
                        <span className="num text-[13px] font-semibold text-ink">{money(p.revenue, true)}</span>
                        <span className="num text-[12px] text-slate-500">план {money(p.plan, true)}</span>
                      </div>
                      <Progress value={planShare} tone={planShare >= 100 ? 'good' : planShare >= 85 ? 'warn' : 'bad'} />
                    </div>

                    <dl className="grid grid-cols-3 gap-2 border-t border-slate-100 pt-3">
                      {[
                        [L.script, `${p.scriptCompliance} %`],
                        ['Обучение', `${p.training} %`],
                        ['Чек', money(p.avgCheck, true)],
                      ].map(([k, v]) => (
                        <div key={k} className="min-w-0">
                          <dt className="truncate text-[11px] text-slate-500">{k}</dt>
                          <dd className="num mt-0.5 text-[13px] font-semibold text-ink">{v}</dd>
                        </div>
                      ))}
                    </dl>

                    <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5 border-t border-slate-100 pt-3 text-[12px] text-slate-500">
                      <span className="inline-flex items-center gap-1.5">
                        <Users size={13} className="text-slate-500" />
                        {staff.length} в команде
                      </span>
                      <span
                        className={`inline-flex items-center gap-1.5 font-semibold ${
                          online === staff.length && staff.length > 0
                            ? 'text-emerald-600'
                            : online === 0
                              ? 'text-rose-600'
                              : 'text-amber-600'
                        }`}
                      >
                        <Radio size={13} />
                        {online} из {staff.length} в эфире
                      </span>
                      <span className="inline-flex items-center gap-1.5">
                        <UserRound size={13} className="text-slate-500" />
                        {p.manager || '—'}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
          </section>
        </>
      )}
    </>
  );
}
