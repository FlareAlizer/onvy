import { useMemo, useState } from 'react';
import { ArrowLeft, MessagesSquare } from 'lucide-react';
import { useStore } from '../../store';
import { PageHead } from '../../components/Shell';
import { Card, EmptyState, SectionHead } from '../../components/ui';
import { DialogDetail } from '../../components/DialogDetail';
import { DialogList } from '../employee/MyDialogs';
import { BarSeries, ChartCard, RankBars, StatTile } from '../../components/charts';
import { money, num, pct, times } from '../../lib/format';
import type { Dialog } from '../../types';

type Period = 'all' | '7' | '30';
type OutcomeFilter = 'all' | 'success' | 'lost';

export default function Analytics() {
  const { data, profile } = useStore();
  const L = profile.labels;
  const [open, setOpen] = useState<Dialog | null>(null);
  const [period, setPeriod] = useState<Period>('all');
  const [pointId, setPointId] = useState('all');
  const [employeeId, setEmployeeId] = useState('all');
  const [category, setCategory] = useState('all');
  const [outcome, setOutcome] = useState<OutcomeFilter>('all');
  const [onlyErrors, setOnlyErrors] = useState(false);
  const [onlyCues, setOnlyCues] = useState(false);

  const nameOf = (d: Dialog) => data.employees.find((e) => e.id === d.employeeId)?.name ?? '—';

  const categories = useMemo(() => {
    const used = new Set(data.dialogs.map((d) => d.category));
    return profile.categories.filter((c) => used.has(c));
  }, [data.dialogs, profile.categories]);

  const filtered = useMemo(() => {
    const now = new Date('2026-07-29').getTime();
    const days = period === 'all' ? Infinity : Number(period);
    return data.dialogs.filter((d) => {
      if (pointId !== 'all' && d.pointId !== pointId) return false;
      if (employeeId !== 'all' && d.employeeId !== employeeId) return false;
      if (category !== 'all' && d.category !== category) return false;
      if (outcome !== 'all' && d.outcome !== outcome) return false;
      if (onlyErrors && !d.moments.some((m) => m.type === 'miss')) return false;
      if (onlyCues && !d.hasCue) return false;
      if (days !== Infinity) {
        const age = (now - new Date(d.startedAt).getTime()) / 86_400_000;
        if (age > days) return false;
      }
      return true;
    });
  }, [data.dialogs, period, pointId, employeeId, category, outcome, onlyErrors, onlyCues]);

  const staffForPoint = useMemo(
    () => data.employees.filter((e) => pointId === 'all' || e.pointId === pointId),
    [data.employees, pointId],
  );

  if (open) {
    return (
      <>
        <button type="button" onClick={() => setOpen(null)} className="btn-quiet -ml-3 mb-4">
          <ArrowLeft size={16} /> К аналитике
        </button>
        <PageHead title={open.topic} subtitle={`${nameOf(open)} · ${open.category}`} />
        <DialogDetail dialog={open} who={nameOf(open)} />
      </>
    );
  }

  const wins = filtered.reduce((a, d) => a + d.moments.filter((m) => m.type === 'win').length, 0);
  const misses = filtered.reduce((a, d) => a + d.moments.filter((m) => m.type === 'miss').length, 0);
  const helps = filtered.reduce((a, d) => a + d.helpRequests, 0);
  const avgScript = filtered.length
    ? filtered.reduce((a, d) => a + d.scriptScore, 0) / filtered.length
    : 0;
  const avgResponse = filtered.length
    ? filtered.reduce((a, d) => a + d.responseSec, 0) / filtered.length
    : 0;

  const topFaq = [...data.faq].sort((a, b) => b.count - a.count);
  const errors = [...data.scriptErrors].sort((a, b) => b.count - a.count);
  const needTraining = [...data.employees]
    .filter((e) => e.stats.scriptCompliance < 85 || e.stats.autonomy < 75)
    .sort((a, b) => a.stats.scriptCompliance - b.stats.scriptCompliance);
  const byScript = [...data.employees].sort((a, b) => a.stats.scriptCompliance - b.stats.scriptCompliance);

  return (
    <>
      <PageHead
        title={`Аналитика ${L.interactionGenitivePlural}`}
        subtitle={`Что спрашивают ${L.clientPlural.toLowerCase()}, где сотрудники теряют результат и кому нужно обучение.`}
      />

      {/* Фильтры — один ряд над всем, что они охватывают */}
      <div className="mb-5 flex flex-wrap items-center gap-2.5">
        <select
          className="field w-auto min-w-[150px] py-2 text-[13px]"
          value={period}
          onChange={(e) => setPeriod(e.target.value as Period)}
        >
          <option value="all">Весь период</option>
          <option value="7">Последние 7 дней</option>
          <option value="30">Последние 30 дней</option>
        </select>
        <select
          className="field w-auto min-w-[170px] py-2 text-[13px]"
          value={pointId}
          onChange={(e) => {
            setPointId(e.target.value);
            setEmployeeId('all');
          }}
        >
          <option value="all">Все {L.locationPlural.toLowerCase()}</option>
          {data.points.map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </select>
        <select
          className="field w-auto min-w-[170px] py-2 text-[13px]"
          value={employeeId}
          onChange={(e) => setEmployeeId(e.target.value)}
        >
          <option value="all">Все сотрудники</option>
          {staffForPoint.map((e) => (
            <option key={e.id} value={e.id}>
              {e.name}
            </option>
          ))}
        </select>
        <select
          className="field w-auto min-w-[150px] py-2 text-[13px]"
          value={category}
          onChange={(e) => setCategory(e.target.value)}
        >
          <option value="all">Все категории</option>
          {categories.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </select>
        <select
          className="field w-auto min-w-[150px] py-2 text-[13px]"
          value={outcome}
          onChange={(e) => setOutcome(e.target.value as OutcomeFilter)}
        >
          <option value="all">Любой результат</option>
          <option value="success">{L.outcome}</option>
          <option value="lost">{L.outcomeLost}</option>
        </select>
        <label className="inline-flex cursor-pointer items-center gap-2 text-[13px] text-slate-600">
          <input
            type="checkbox"
            checked={onlyErrors}
            onChange={(e) => setOnlyErrors(e.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          />
          С ошибками
        </label>
        <label className="inline-flex cursor-pointer items-center gap-2 text-[13px] text-slate-600">
          <input
            type="checkbox"
            checked={onlyCues}
            onChange={(e) => setOnlyCues(e.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          />
          С подсказками Onvy
        </label>
        <span className="num text-[13px] text-muted">{filtered.length} в выборке</span>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
        <StatTile label="Разобрано" value={num(filtered.length)} hint="100 % записанных" />
        <StatTile label={L.script} value={pct(avgScript, 0)} hint="норма — 85 %" />
        <StatTile
          label="Средний ответ"
          value={`${avgResponse.toFixed(1).replace('.', ',')} сек`}
          hint="меньше — лучше"
        />
        <StatTile label="Удачных приёмов" value={num(wins)} hint="можно тиражировать" />
        <StatTile label="Ошибки / помощь" value={`${misses} / ${helps}`} hint="повод для теста" />
      </div>

      <section className="mt-4 grid gap-4 lg:grid-cols-2">
        <ChartCard
          title={`Частые вопросы ${L.clientGenitivePlural}`}
          hint="Сколько раз прозвучал вопрос и какая у него результативность"
          table={{
            head: ['Вопрос', 'Раз', 'Результативность', 'Ответ, сек'],
            rows: topFaq.map((f) => [f.question, f.count, pct(f.conversion, 0), f.avgResponseSec]),
          }}
        >
          <RankBars
            rows={topFaq.map((f) => ({
              label: f.question,
              value: f.count,
              sub: pct(f.conversion, 0),
              tone:
                f.conversion >= 55
                  ? 'var(--color-series-3)'
                  : f.conversion >= 30
                    ? 'var(--color-series-4)'
                    : 'var(--color-series-2)',
            }))}
            format={(v) => times(v)}
          />
          <p className="mt-4 text-[12px] leading-relaxed text-slate-500">
            Цвет полосы — результативность вопроса: зелёный выше 55 %, жёлтый 30–55 %, оранжевый ниже
            30 %. Значения продублированы цифрами справа.
          </p>
        </ChartCard>

        <ChartCard
          title={`Ошибки: ${L.script.toLowerCase()}`}
          hint="Сколько раз этап пропущен за месяц"
          table={{
            head: ['Ошибка', 'Раз', 'Потери, ₽'],
            rows: errors.map((e) => [e.label, e.count, e.costPerMonth ? num(e.costPerMonth) : '—']),
          }}
        >
          <RankBars
            rows={errors.map((e) => ({
              label: e.label,
              value: e.count,
              sub: e.costPerMonth ? money(e.costPerMonth, true) : undefined,
              tone: 'var(--color-series-2)',
            }))}
            format={(v) => times(v)}
          />
        </ChartCard>
      </section>

      <section className="mt-4 grid gap-4 lg:grid-cols-2">
        <ChartCard
          title={`${L.script} по сотрудникам`}
          hint="Кому нужно обучение в первую очередь"
          table={{ head: ['Сотрудник', 'Скрипт, %'], rows: byScript.map((e) => [e.name, e.stats.scriptCompliance]) }}
        >
          <BarSeries
            labels={byScript.map((e) => e.name.split(' ')[0])}
            values={byScript.map((e) => e.stats.scriptCompliance)}
            format={(v) => `${Math.round(v)}%`}
            height={210}
            maxValue={100}
          />
        </ChartCard>

        <ChartCard
          title="Скорость ответа"
          hint={`Секунды до ответа на вопрос ${L.clientGenitivePlural} — меньше значит лучше`}
          table={{ head: ['Сотрудник', 'Сек'], rows: data.employees.map((e) => [e.name, e.stats.responseSec]) }}
        >
          <BarSeries
            labels={data.employees.map((e) => e.name.split(' ')[0])}
            values={data.employees.map((e) => e.stats.responseSec)}
            color="var(--color-series-5)"
            format={(v) => v.toFixed(1).replace('.', ',')}
            height={210}
          />
        </ChartCard>
      </section>

      {needTraining.length > 0 && (
        <section className="mt-4">
          <SectionHead
            title="Кому нужно обучение"
            hint={`${L.script} ниже 85 % или самостоятельность ниже 75 %.`}
          />
          <Card>
            <div className="overflow-x-auto scroll-thin">
              <table className="w-full min-w-[560px]">
                <thead>
                  <tr className="border-b border-slate-200 bg-slate-50/70">
                    {['Сотрудник', L.script, 'Самостоятельность', `Обращения: ${L.helpTarget}`, 'Обучение'].map(
                      (h, i) => (
                        <th key={h} className={`label px-4 py-2.5 ${i === 0 ? 'text-left' : 'text-right'}`}>
                          {h}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {needTraining.map((e) => (
                    <tr key={e.id} className="border-b border-slate-100 last:border-0">
                      <td className="px-4 py-2.5 text-[14px] font-medium text-ink">{e.name}</td>
                      <td className="num px-4 py-2.5 text-right text-[13px] text-rose-600">
                        {e.stats.scriptCompliance} %
                      </td>
                      <td className="num px-4 py-2.5 text-right text-[13px] text-slate-600">
                        {e.stats.autonomy} %
                      </td>
                      <td className="num px-4 py-2.5 text-right text-[13px] text-slate-600">
                        {num(e.stats.helpRequests)}
                      </td>
                      <td className="num px-4 py-2.5 text-right text-[13px] text-slate-600">
                        {e.trainingDone} / {e.trainingTotal}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </Card>
        </section>
      )}

      <section className="mt-7">
        <SectionHead
          title="Разбор разговоров"
          hint="Откройте любой разговор, чтобы увидеть дорожку речи, расшифровку и отмеченные моменты."
        />
        {filtered.length === 0 ? (
          <EmptyState
            icon={<MessagesSquare size={22} />}
            title="В этой выборке ничего нет"
            hint="Смените фильтр или дождитесь окончания смены — записи появляются в течение часа."
          />
        ) : (
          <Card>
            <DialogList dialogs={filtered} onOpen={setOpen} nameOf={nameOf} />
          </Card>
        )}
      </section>
    </>
  );
}
