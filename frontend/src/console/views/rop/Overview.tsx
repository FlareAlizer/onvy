import { useMemo } from 'react';
import { Gauge, GraduationCap, HandHelping, Target, TriangleAlert } from 'lucide-react';
import { useStore } from '../../store';
import { RopBadgePanel } from '../../components/BadgePanel';
import { PageHead } from '../../components/Shell';
import { Card, Chip, EmptyState, Progress, SectionHead } from '../../components/ui';
import { ChartCard, Donut, RankBars, StatTile, TrendChart } from '../../components/charts';
import CountUp from '../../components/CountUp';
import { lastDays, money, num, pct, plural } from '../../lib/format';
import { employeeMetric, formatMetric, kpiProgress, kpiReached } from '../../lib/metrics';
import { findMetric } from '../../industryProfiles';

const EXTERNAL_NOTE = 'Демо-данные · требуется интеграция с учётной системой';

export default function Overview({ onGoTo }: { onGoTo: (tab: string) => void }) {
  const { data, session, profile } = useStore();
  const L = profile.labels;
  const { employees, points, dialogs, kpis } = data;

  const totals = useMemo(() => {
    const revenue = employees.reduce((a, e) => a + e.stats.revenue, 0);
    const deals = employees.reduce((a, e) => a + e.stats.deals, 0);
    const talks = employees.reduce((a, e) => a + e.stats.dialogs, 0);
    const plan = points.reduce((a, p) => a + p.plan, 0);
    const n = employees.length || 1;
    return {
      revenue,
      deals,
      talks,
      plan,
      avgCheck: deals ? revenue / deals : 0,
      conversion: talks ? (deals / talks) * 100 : 0,
      script: employees.reduce((a, e) => a + e.stats.scriptCompliance, 0) / n,
      response: employees.reduce((a, e) => a + e.stats.responseSec, 0) / n,
      autonomy: employees.reduce((a, e) => a + e.stats.autonomy, 0) / n,
      help: employees.reduce((a, e) => a + e.stats.helpRequests, 0),
      training: employees.reduce((a, e) => a + e.onboarding, 0) / n,
      badges: (employees.filter((e) => e.badgeOnline).length / n) * 100,
      errors: dialogs.reduce((a, d) => a + d.moments.filter((m) => m.type === 'miss').length, 0),
    };
  }, [employees, points, dialogs]);

  const teamDaily = useMemo(
    () =>
      employees.length === 0
        ? []
        : Array.from({ length: 14 }, (_, i) => employees.reduce((a, e) => a + (e.daily[i] ?? 0), 0)),
    [employees],
  );

  const leaders = useMemo(
    () => [...employees].sort((a, b) => b.stats.revenue - a.stats.revenue),
    [employees],
  );

  const kpiHealth = useMemo(() => {
    if (kpis.length === 0) return { done: 0, risk: 0, share: 0 };
    let done = 0;
    let risk = 0;
    kpis.forEach((k) => {
      const def = findMetric(profile, k.metric);
      if (kpiReached(def, k.current, k.target)) done += 1;
      else if (kpiProgress(def, k.current, k.target) < 70) risk += 1;
    });
    return { done, risk, share: (done / kpis.length) * 100 };
  }, [kpis, profile]);

  const alerts = useMemo(() => {
    const out: { text: string; tone: 'warn' | 'bad'; go: string }[] = [];
    const weak = employees.filter((e) => e.stats.scriptCompliance < 80);
    if (weak.length)
      out.push({
        tone: 'bad',
        text: `${weak.map((e) => e.name.split(' ')[0]).join(', ')} — ${L.script.toLowerCase()} ниже 80 %. Соберите тест по стандарту.`,
        go: 'tests',
      });
    const offline = employees.filter((e) => !e.badgeOnline);
    if (offline.length)
      out.push({
        tone: 'warn',
        text: `${offline.length} ${offline.length === 1 ? 'бейдж не в эфире' : 'бейджа не в эфире'} — эти ${L.interactionPlural.toLowerCase()} не попадут в аналитику.`,
        go: 'staff',
      });
    const behind = points.filter((p) => p.plan > 0 && p.revenue / p.plan < 0.85);
    if (behind.length)
      out.push({
        tone: 'warn',
        text: `${behind.map((p) => p.name).join(', ')} отстаёт от плана месяца.`,
        go: 'points',
      });
    const unverified = data.faq.filter((f) => !f.verified).length;
    if (unverified)
      out.push({
        tone: 'warn',
        text: `${unverified} материала в базе знаний не подтверждены — Onvy не отвечает по ним автоматически.`,
        go: 'knowledge',
      });
    return out;
  }, [employees, points, data.faq, L]);

  const labels = lastDays(14);
  const outcomeSplit = {
    success: dialogs.filter((d) => d.outcome === 'success').length,
    lost: dialogs.filter((d) => d.outcome === 'lost').length,
    consult: dialogs.filter((d) => d.outcome === 'consult').length,
  };

  if (employees.length === 0) {
    return (
      <>
        <PageHead
          title={`Здравствуйте, ${session?.name.split(' ')[0] ?? ''}`}
          subtitle="Показатели считаются по настоящим сменам — придуманных цифр здесь не будет."
        />
        <RopBadgePanel />
        <div className="mt-6">
          <EmptyState
            icon={<Target size={22} />}
            title="Данных пока нет"
            hint={`Заведите смену в разделе «Состав и доступы»: там выдаются PIN и пароли. После первых смен здесь появятся показатели и разбор ${L.interactionGenitivePlural}.`}
            action={
              <button type="button" className="console-btn-primary" onClick={() => onGoTo('staff')}>
                Состав и доступы
              </button>
            }
          />
        </div>
      </>
    );
  }

  return (
    <>
      <PageHead
        title={`Здравствуйте, ${session?.name.split(' ')[0] ?? ''}`}
        subtitle={`${data.company?.name} · ${L.industry} · ${points.length} ${plural(points.length, ...L.locationForms)} · ${employees.length} в штате`}
        action={
          totals.plan > 0 ? (
            <Chip tone={totals.revenue >= totals.plan ? 'good' : 'warn'}>
              План месяца {pct((totals.revenue / totals.plan) * 100, 0)}
            </Chip>
          ) : undefined
        }
      />

      <RopBadgePanel />

      {alerts.length > 0 && (
        <section className="mt-4 space-y-2">
          {alerts.map((a) => (
            <button
              key={a.text}
              type="button"
              onClick={() => onGoTo(a.go)}
              className={`flex w-full items-start gap-3 rounded-lg border p-3.5 text-left transition ${
                a.tone === 'bad'
                  ? 'border-rose-200 bg-rose-50 hover:bg-rose-100/70'
                  : 'border-amber-200 bg-amber-50 hover:bg-amber-100/70'
              }`}
            >
              <TriangleAlert
                size={16}
                className={`mt-0.5 shrink-0 ${a.tone === 'bad' ? 'text-rose-600' : 'text-amber-600'}`}
              />
              <span
                className={`text-[13px] leading-relaxed ${a.tone === 'bad' ? 'text-rose-900' : 'text-amber-900'}`}
              >
                {a.text}
              </span>
            </button>
          ))}
        </section>
      )}

      {/* Прямые метрики Onvy */}
      <section className="mt-6">
        <SectionHead
          eyebrow="Измеряет Onvy напрямую"
          title="Качество работы в зале"
          hint="Эти показатели считаются по расшифровкам разговоров и не требуют интеграций."
        />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatTile
            label={L.script}
            value={<CountUp to={totals.script} decimals={0} suffix=" %" />}
            hint="норма — 85 %"
            icon={<Gauge size={16} />}
          />
          <StatTile
            label="Скорость ответа"
            value={<CountUp to={totals.response} decimals={1} suffix=" сек" />}
            hint="меньше — лучше"
          />
          <StatTile
            label="Решено самостоятельно"
            value={<CountUp to={totals.autonomy} decimals={0} suffix=" %" />}
            hint={`без обращения к ${L.helpTargetDative}`}
          />
          <StatTile
            label={`Обращения: ${L.helpTarget.toLowerCase()}`}
            value={<CountUp to={totals.help} />}
            hint="за месяц"
            icon={<HandHelping size={16} />}
          />
        </div>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatTile
            label={L.interactionPlural}
            value={<CountUp to={totals.talks} />}
            hint="записано и разобрано"
          />
          <StatTile label="Ошибок в разговорах" value={<CountUp to={totals.errors} />} hint="повод для теста" />
          <StatTile
            label="Прогресс обучения"
            value={<CountUp to={totals.training} decimals={0} suffix=" %" />}
            icon={<GraduationCap size={16} />}
          />
          <StatTile
            label="Покрытие бейджами"
            value={<CountUp to={totals.badges} decimals={0} suffix=" %" />}
            hint="сотрудников в эфире"
          />
        </div>
      </section>

      {/* Бизнес-метрики */}
      <section className="mt-7">
        <SectionHead eyebrow="Из учётной системы" title="Продажи" hint={EXTERNAL_NOTE} />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatTile
            label="Выручка"
            value={<CountUp to={totals.revenue / 1_000_000} decimals={1} suffix=" млн ₽" />}
            hint={totals.plan ? `план ${money(totals.plan, true)}` : undefined}
            spark={teamDaily}
          />
          <StatTile
            label={L.outcomePlural}
            value={<CountUp to={totals.deals} />}
            hint={`из ${num(totals.talks)} ${plural(totals.talks, ...L.interactionForms)}`}
          />
          <StatTile label="Средний чек" value={<CountUp to={totals.avgCheck} suffix=" ₽" />} />
          <StatTile
            label="Результативность"
            value={<CountUp to={totals.conversion} decimals={1} suffix=" %" />}
            hint={`${L.interaction.toLowerCase()} → ${L.outcome.toLowerCase()}`}
          />
        </div>
      </section>

      <section className="mt-4 grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        <ChartCard
          title="Выручка сети по дням"
          hint={`Последние две недели · ${EXTERNAL_NOTE.toLowerCase()}`}
          table={{ head: ['День', 'Выручка, ₽'], rows: labels.map((l, i) => [l, num(teamDaily[i] ?? 0)]) }}
        >
          <TrendChart
            labels={labels}
            series={[{ label: 'Выручка сети', color: 'var(--color-series-1)', values: teamDaily }]}
            format={(v) => (v >= 1000 ? `${Math.round(v / 1000)}к` : String(Math.round(v)))}
          />
        </ChartCard>

        <Card className="p-5">
          <h3 className="text-[15px] font-semibold text-ink">Выполнение KPI</h3>
          <p className="mt-0.5 mb-4 text-[13px] text-slate-500">
            {kpis.length} {kpis.length === 1 ? 'цель' : 'целей'} назначено {L.employeePlural.toLowerCase()}
          </p>
          <div className="mb-4 flex items-baseline gap-2">
            <span className="figure text-[34px] leading-none font-semibold text-ink">
              {Math.round(kpiHealth.share)}%
            </span>
            <span className="text-[13px] text-slate-500">целей закрыто</span>
          </div>
          <Progress
            value={kpiHealth.share}
            tone={kpiHealth.share >= 70 ? 'good' : kpiHealth.share >= 40 ? 'warn' : 'bad'}
            height={10}
          />
          <div className="mt-4 grid grid-cols-2 gap-3">
            <div className="rounded-lg bg-emerald-50 p-3">
              <p className="figure text-[20px] leading-none font-semibold text-emerald-700">{kpiHealth.done}</p>
              <p className="mt-1 text-[12px] text-emerald-800">выполнено</p>
            </div>
            <div className="rounded-lg bg-rose-50 p-3">
              <p className="figure text-[20px] leading-none font-semibold text-rose-700">{kpiHealth.risk}</p>
              <p className="mt-1 text-[12px] text-rose-800">под угрозой</p>
            </div>
          </div>
          <button type="button" className="btn-ghost mt-4 w-full" onClick={() => onGoTo('staff')}>
            Управлять KPI
          </button>
        </Card>
      </section>

      {/* Отраслевые показатели */}
      {profile.metrics.length > 0 && (
        <section className="mt-4">
          <SectionHead
            title={`Показатели: ${L.industry.toLowerCase()}`}
            hint="Специфика отрасли — среднее по всем сотрудникам."
          />
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {profile.metrics.map((m) => {
              const avg =
                employees.reduce((a, e) => a + employeeMetric(e, m.key), 0) / (employees.length || 1);
              return (
                <Card key={m.key} className="p-4">
                  <p className="label truncate">{m.label}</p>
                  <p className="figure mt-1.5 text-[22px] leading-none font-semibold text-ink">
                    {formatMetric(avg, m.unit, true)}
                  </p>
                  <p className="mt-1.5 text-[11px] text-slate-500">
                    {m.external ? 'нужна учётная система' : 'измеряет Onvy'}
                  </p>
                </Card>
              );
            })}
          </div>
        </section>
      )}

      <section className="mt-4 grid gap-4 lg:grid-cols-[1.5fr_1fr]">
        <ChartCard
          title={`Кто сколько продал`}
          hint="Выручка за месяц по каждому сотруднику"
          table={{
            head: ['Сотрудник', 'Выручка, ₽', L.outcomePlural, 'Результативность'],
            rows: leaders.map((e) => [e.name, num(e.stats.revenue), e.stats.deals, pct(e.stats.conversion)]),
          }}
          action={
            <button type="button" className="btn-quiet text-[12px]" onClick={() => onGoTo('staff')}>
              Все сотрудники
            </button>
          }
        >
          <RankBars
            rows={leaders.map((e) => ({ label: e.name, value: e.stats.revenue, sub: `${e.stats.deals} шт` }))}
            format={(v) => money(v, true)}
          />
        </ChartCard>

        <Card className="p-5">
          <h3 className="mb-4 text-[15px] font-semibold text-ink">
            Чем заканчиваются {L.interactionPlural.toLowerCase()}
          </h3>
          {dialogs.length === 0 ? (
            <p className="text-[14px] text-slate-500">Разобранных разговоров пока нет.</p>
          ) : (
            <Donut
              segments={[
                { label: L.outcome, value: outcomeSplit.success, color: 'var(--color-series-3)' },
                { label: L.outcomeLost, value: outcomeSplit.lost, color: 'var(--color-series-2)' },
                { label: 'Без результата', value: outcomeSplit.consult, color: 'var(--color-series-4)' },
              ].filter((s) => s.value > 0)}
              centerValue={pct((outcomeSplit.success / dialogs.length) * 100, 0)}
              centerLabel="с результатом"
            />
          )}
          <button type="button" className="btn-ghost mt-5 w-full" onClick={() => onGoTo('analytics')}>
            Разбор {L.interactionGenitivePlural}
          </button>
        </Card>
      </section>
    </>
  );
}
