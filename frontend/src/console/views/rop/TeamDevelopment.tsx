import { useMemo, useState } from 'react';
import {
  ArrowRight,
  BookOpen,
  Check,
  Clock,
  Eye,
  GraduationCap,
  HandHelping,
  Lightbulb,
  Lock,
  Quote,
  Shield,
  Sparkles,
  TrendingDown,
  TrendingUp,
  Users,
} from 'lucide-react';
import { useStore } from '../../store';
import { PageHead } from '../../components/Shell';
import { Avatar, Card, Chip, EmptyState, Modal, Progress, SectionHead } from '../../components/ui';
import { BarSeries, ChartCard, StatTile } from '../../components/charts';
import { num, times } from '../../lib/format';

/** Формулировки о людях — про развитие, а не про наказание. */
function readinessLabel(v: number): { label: string; tone: 'good' | 'warn' | 'neutral' } {
  if (v >= 90) return { label: 'Готов к самостоятельной работе', tone: 'good' };
  if (v >= 60) return { label: 'В процессе адаптации', tone: 'warn' };
  return { label: 'Требуется поддержка', tone: 'neutral' };
}

export default function TeamDevelopment({ onGoTo }: { onGoTo: (tab: string) => void }) {
  const { data, profile, promotePractice } = useStore();
  const L = profile.labels;
  const [privacyOpen, setPrivacyOpen] = useState(false);
  const A = data.adaptation;

  const byReadiness = useMemo(
    () => [...data.employees].sort((a, b) => a.onboarding - b.onboarding),
    [data.employees],
  );

  const needSupport = byReadiness.filter((e) => e.onboarding < 90);
  const avgTestScore = useMemo(() => {
    const all = data.tests.flatMap((t) => Object.values(t.results));
    return all.length ? Math.round(all.reduce((a, b) => a + b, 0) / all.length) : 0;
  }, [data.tests]);

  const requiredDone = useMemo(() => {
    let assigned = 0;
    let passed = 0;
    data.tests.forEach((t) => {
      t.assignedTo.forEach((id) => {
        assigned += 1;
        if ((t.results[id] ?? 0) >= t.passScore) passed += 1;
      });
    });
    return { assigned, passed, share: assigned ? (passed / assigned) * 100 : 0 };
  }, [data.tests]);

  /** Темы с наибольшим количеством затруднений — по разобранным разговорам. */
  const hardTopics = useMemo(() => {
    const counts = new Map<string, number>();
    data.dialogs.forEach((d) =>
      d.moments
        .filter((m) => m.type === 'miss' || m.type === 'help')
        .forEach(() => counts.set(d.category, (counts.get(d.category) ?? 0) + 1)),
    );
    data.scriptErrors.forEach((e) => counts.set(e.label, (counts.get(e.label) ?? 0) + e.count));
    return [...counts.entries()].sort((a, b) => b[1] - a[1]).slice(0, 6);
  }, [data.dialogs, data.scriptErrors]);

  /** Разброс знаний между точками — единообразие стандартов. */
  const pointSpread = useMemo(() => [...data.points].sort((a, b) => b.training - a.training), [data.points]);
  const spread =
    pointSpread.length > 1
      ? pointSpread[0].scriptCompliance - pointSpread[pointSpread.length - 1].scriptCompliance
      : 0;

  const staleKnowledge = data.faq.filter((f) => f.status === 'outdated' || !f.verified);

  if (data.employees.length === 0) {
    return (
      <>
        <PageHead
          title="Развитие команды"
          subtitle="Адаптация, обучение и стандарты — как быстро люди выходят на самостоятельную работу."
        />
        <EmptyState
          icon={<Users size={22} />}
          title="Команда ещё не подключена"
          hint={`Раздел наполнится, когда ${L.employeePlural.toLowerCase()} проведут первые смены. Обучение и тесты в пилот не входят.`}
        />
      </>
    );
  }

  return (
    <>
      <PageHead
        title="Развитие команды"
        subtitle="Насколько команда знает стандарты, как идёт адаптация и что уже изменилось после обучения."
        action={
          <button type="button" className="btn-ghost" onClick={() => setPrivacyOpen(true)}>
            <Shield size={15} /> Данные и приватность
          </button>
        }
      />

      {/* Готовность и адаптация */}
      <section>
        <SectionHead
          eyebrow="Измеряет Onvy"
          title="Готовность к самостоятельной работе"
          hint="Показатели считаются по расшифровкам разговоров и результатам обучения."
        />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <StatTile
            label="Готовы работать самостоятельно"
            value={`${data.employees.filter((e) => e.onboarding >= 90).length} / ${data.employees.length}`}
            hint={`${needSupport.length} требуется поддержка`}
          />
          <StatTile
            label="Обязательные модули"
            value={`${requiredDone.passed} / ${requiredDone.assigned}`}
            hint={`завершено ${Math.round(requiredDone.share)} %`}
            icon={<GraduationCap size={16} />}
          />
          <StatTile label="Средний результат обучения" value={`${avgTestScore} %`} />
          <StatTile
            label="Единообразие стандартов"
            value={`${Math.round(spread)} п.п.`}
            hint="разброс между точками"
          />
        </div>
      </section>

      {A && (
        <section className="mt-7">
          <SectionHead
            title="Метрики адаптации"
            hint="Как быстро новый сотрудник выходит на самостоятельную смену."
          />
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <Card className="p-4">
              <p className="label">До самостоятельной смены</p>
              <p className="figure mt-1.5 text-[26px] leading-none font-semibold text-ink">{A.daysToSolo} дн</p>
              <p className="num mt-2 inline-flex items-center gap-1 text-[12px] font-semibold text-emerald-700">
                <TrendingDown size={12} /> было {A.daysToSoloBefore} дн
              </p>
              <p className="mt-1 text-[11px] text-slate-500">наблюдаемая динамика за пилот</p>
            </Card>
            <StatTile
              label="Завершение онбординга"
              value={`${A.completion} %`}
              hint={`${A.requiredModules} обязательных модуля`}
            />
            <StatTile
              label="Первая проверка знаний"
              value={`${A.firstCheckScore} %`}
              hint="средний результат новичка"
            />
            <StatTile
              label="Соблюдение стандартов"
              value={`${A.earlyCompliance} %`}
              hint="первые две недели"
            />
          </div>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <Card className="p-4">
              <div className="flex items-center gap-3">
                <HandHelping size={16} className="shrink-0 text-slate-500" />
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] text-slate-600">
                    Обращений новичка к опытным коллегам за смену
                  </p>
                  <p className="num mt-0.5 text-[15px] font-semibold text-ink">{A.noviceHelpPerShift}</p>
                </div>
              </div>
            </Card>
            <Card className="p-4">
              <div className="flex items-center gap-3">
                <Clock size={16} className="shrink-0 text-slate-500" />
                <div className="min-w-0 flex-1">
                  <p className="text-[13px] text-slate-600">Повторяющиеся сложности после обучения</p>
                  <p className="num mt-0.5 text-[15px] font-semibold text-ink">{A.repeatedErrors}</p>
                </div>
              </div>
            </Card>
          </div>
          <p className="mt-3 text-[12px] text-muted">
            Демо-данные пилотного контура. Показатели рассчитаны на тестовой выборке и требуют
            подтверждения на полном периоде.
          </p>
        </section>
      )}

      {/* Цепочка обучения */}
      <section className="mt-7">
        <SectionHead
          title="Что дало обучение"
          hint="Цепочка: сложность в разговоре → выявленный пробел → назначенный тест → прохождение → изменение поведения."
        />
        {data.trainingOutcomes.length === 0 ? (
          <EmptyState
            icon={<Sparkles size={22} />}
            title="Программы обучения ещё не завершены"
            hint="Как только назначенные тесты будут пройдены, здесь появится изменение показателей."
            action={
              <button type="button" className="console-btn-primary" onClick={() => onGoTo('tests')}>
                Собрать тест
              </button>
            }
          />
        ) : (
          <div className="space-y-3">
            {data.trainingOutcomes.map((o) => {
              const test = data.tests.find((t) => t.id === o.testId);
              const passed = test ? Object.values(test.results).filter((v) => v >= test.passScore).length : 0;
              const delta = o.after - o.before;
              const improved = o.better === 'up' ? delta > 0 : delta < 0;
              return (
                <Card key={o.testId} className="p-5">
                  <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
                    <div className="min-w-0">
                      <p className="label mb-1.5">Причина назначения</p>
                      <p className="text-[14px] leading-relaxed text-ink">{o.reason}</p>
                      <p className="num mt-2 text-[12px] text-slate-500">Источник: {o.origin}</p>

                      <div className="mt-4 flex flex-wrap items-center gap-2 text-[12px]">
                        <Chip tone="neutral">{test?.title ?? 'Тест'}</Chip>
                        <ArrowRight size={13} className="text-slate-300" />
                        <Chip tone="brand">
                          назначен {test?.assignedTo.length ?? 0}
                        </Chip>
                        <ArrowRight size={13} className="text-slate-300" />
                        <Chip tone={passed > 0 ? 'good' : 'neutral'}>прошли {passed}</Chip>
                        <ArrowRight size={13} className="text-slate-300" />
                        <Chip tone={improved ? 'good' : 'warn'}>
                          {improved ? 'положительная динамика' : 'без изменений'}
                        </Chip>
                      </div>
                    </div>

                    <div className="rounded-lg bg-slate-50 p-4">
                      <p className="label mb-2">{o.metricLabel}</p>
                      <div className="flex items-baseline gap-3">
                        <span className="figure text-[15px] text-slate-500 line-through">
                          {o.before}
                          {o.unit === 'pct' ? ' %' : ''}
                        </span>
                        <ArrowRight size={14} className="text-slate-500" />
                        <span
                          className={`figure text-[26px] leading-none font-semibold ${
                            improved ? 'text-emerald-600' : 'text-amber-600'
                          }`}
                        >
                          {o.after}
                          {o.unit === 'pct' ? ' %' : ''}
                        </span>
                      </div>
                      <p className="mt-2 inline-flex items-center gap-1 text-[12px] font-semibold text-slate-600">
                        {improved ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                        изменение за период
                      </p>
                      {o.repeated ? (
                        <p className="mt-2 text-[12px] leading-relaxed text-amber-700">
                          Ситуация повторялась после обучения — части команды нужна дополнительная
                          поддержка.
                        </p>
                      ) : (
                        <p className="mt-2 text-[12px] leading-relaxed text-slate-500">
                          Повторов после обучения не зафиксировано. Гипотеза требует проверки на более
                          длинном периоде.
                        </p>
                      )}
                    </div>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      {/* Лучшие практики */}
      <section className="mt-7">
        <SectionHead
          title="Лучшие практики"
          hint="Onvy находит не только сложности. Удачные формулировки можно превратить в учебный материал и распространить на другие точки."
        />
        {data.bestPractices.length === 0 ? (
          <EmptyState
            icon={<Lightbulb size={22} />}
            title="Практики появятся после первых смен"
            hint="Система отмечает формулировки, которые чаще других приводят к результату."
          />
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {data.bestPractices.map((p) => {
              const author = data.employees.find((e) => e.id === p.employeeId);
              const point = data.points.find((pt) => pt.id === p.pointId);
              return (
                <Card key={p.id} className="flex flex-col p-5">
                  <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
                    <h3 className="min-w-0 text-[15px] leading-snug font-semibold text-ink">
                      {p.title}
                    </h3>
                    <Chip tone="neutral">{p.category}</Chip>
                  </div>

                  <blockquote className="flex gap-2.5 rounded-lg bg-emerald-50 p-3.5">
                    <Quote size={15} className="mt-0.5 shrink-0 text-emerald-600" />
                    <p className="text-[14px] leading-relaxed text-emerald-950 italic">{p.quote}</p>
                  </blockquote>

                  <p className="mt-3 flex-1 text-[13px] leading-relaxed text-slate-600">{p.effect}</p>

                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3 border-t border-slate-100 pt-3.5">
                    <span className="flex min-w-0 items-center gap-2">
                      <Avatar name={author?.name ?? '—'} size={26} />
                      <span className="min-w-0">
                        <span className="block truncate text-[13px] font-semibold text-ink">
                          {author?.name ?? '—'}
                        </span>
                        <span className="block truncate text-[11px] text-slate-500">{point?.name}</span>
                      </span>
                    </span>
                    {p.inTraining ? (
                      <Chip tone="good" icon={<Check size={11} />}>
                        В учебном материале
                      </Chip>
                    ) : (
                      <button
                        type="button"
                        className="btn-ghost px-3 py-1.5 text-[12px]"
                        onClick={() => promotePractice(p.id)}
                      >
                        <Sparkles size={13} /> В обучение
                      </button>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      {/* Темы затруднений и точки */}
      <section className="mt-7 grid gap-4 lg:grid-cols-2">
        <ChartCard
          title="Темы, вызывающие затруднения"
          hint="Где команде чаще всего нужна поддержка"
          table={{ head: ['Тема', 'Случаев'], rows: hardTopics.map(([k, v]) => [k, v]) }}
        >
          <div className="space-y-3">
            {hardTopics.map(([label, count]) => {
              const max = hardTopics[0]?.[1] ?? 1;
              return (
                <div key={label}>
                  <div className="mb-1.5 flex items-baseline justify-between gap-3">
                    <span className="min-w-0 truncate text-[13px] font-medium text-slate-700">{label}</span>
                    <span className="num shrink-0 text-[13px] font-semibold text-ink">{times(count)}</span>
                  </div>
                  <div className="h-2 overflow-hidden rounded-full bg-slate-100">
                    <div
                      className="h-full rounded-full bg-[var(--color-series-4)]"
                      style={{ width: `${(count / max) * 100}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          <button type="button" className="btn-ghost mt-4 w-full" onClick={() => onGoTo('tests')}>
            Собрать тест по этим темам
          </button>
        </ChartCard>

        <ChartCard
          title="Знания по точкам"
          hint="Где стандарты применяются единообразно, а где нужна поддержка"
          table={{
            head: [L.location, 'Обучение, %', 'Скрипт, %'],
            rows: pointSpread.map((p) => [p.name, p.training, p.scriptCompliance]),
          }}
        >
          <BarSeries
            labels={pointSpread.map((p) => p.name.split(' ').slice(-1)[0])}
            values={pointSpread.map((p) => p.training)}
            format={(v) => `${Math.round(v)}%`}
            height={210}
            maxValue={100}
          />
        </ChartCard>
      </section>

      {/* Кому нужна поддержка */}
      <section className="mt-7">
        <SectionHead
          title="Готовность сотрудников"
          hint="Формулировки описывают этап развития, а не оценку человека."
        />
        <Card className="overflow-hidden">
          <div className="overflow-x-auto scroll-thin">
            <table className="w-full min-w-[720px]">
              <thead>
                <tr className="border-b border-slate-200 bg-slate-50/70">
                  {['Сотрудник', 'Статус', 'Онбординг', 'Обучение', 'Первая проверка', 'Динамика'].map((h, i) => (
                    <th key={h} className={`label px-4 py-2.5 ${i === 0 ? 'text-left' : 'text-right'}`}>
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {byReadiness.map((e) => {
                  const st = readinessLabel(e.onboarding);
                  const scores = data.tests
                    .filter((t) => t.assignedTo.includes(e.id) && t.results[e.id] !== undefined)
                    .map((t) => t.results[e.id]);
                  const first = scores.length ? scores[0] : null;
                  return (
                    <tr key={e.id} className="border-b border-slate-100 last:border-0">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <Avatar name={e.name} size={32} />
                          <div className="min-w-0">
                            <p className="truncate text-[14px] font-semibold text-ink">{e.name}</p>
                            <p className="truncate text-[12px] text-slate-500">{e.position}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <Chip tone={st.tone}>{st.label}</Chip>
                      </td>
                      <td className="px-4 py-3">
                        <div className="ml-auto flex w-24 items-center gap-2">
                          <Progress
                            value={e.onboarding}
                            height={6}
                            tone={e.onboarding >= 90 ? 'good' : e.onboarding >= 60 ? 'warn' : 'brand'}
                          />
                          <span className="num w-9 shrink-0 text-right text-[12px] text-slate-500">
                            {e.onboarding}%
                          </span>
                        </div>
                      </td>
                      <td className="num px-4 py-3 text-right text-[13px] text-slate-600">
                        {e.trainingDone} / {e.trainingTotal}
                      </td>
                      <td className="num px-4 py-3 text-right text-[13px] text-slate-600">
                        {first === null ? '—' : `${first} %`}
                      </td>
                      <td className="num px-4 py-3 text-right text-[13px] text-emerald-700">
                        {e.onboarding >= 90 ? 'стабильно' : 'положительная'}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Card>
      </section>

      {/* Рекомендации руководителю */}
      <section className="mt-7 grid gap-4 lg:grid-cols-2">
        <Card className="p-5">
          <h3 className="mb-3 flex items-center gap-2 text-[15px] font-semibold text-ink">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-brand-50 text-brand-700">
              <Lightbulb size={14} />
            </span>
            Рекомендации
          </h3>
          <ul className="space-y-2.5">
            {[
              needSupport.length > 0 &&
                `${needSupport.map((e) => e.name.split(' ')[0]).join(', ')} — требуется поддержка: назначьте обязательный модуль по теме «${hardTopics[0]?.[0] ?? 'стандарты'}».`,
              spread > 8 &&
                `Разброс стандартов между точками ${Math.round(spread)} п.п. Возьмите практику лидера и перенесите её в обучение.`,
              data.bestPractices.some((p) => !p.inTraining) &&
                'Есть удачные практики, ещё не превращённые в учебный материал — это самый дешёвый способ поднять средний уровень.',
              staleKnowledge.length > 0 &&
                `${staleKnowledge.length} материала базы знаний устарели или не подтверждены — сотрудники по ним не получают автоматический ответ.`,
            ]
              .filter(Boolean)
              .map((s) => (
                <li key={String(s)} className="flex gap-2.5 text-[14px] leading-relaxed text-slate-700">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-500" />
                  {s}
                </li>
              ))}
          </ul>
        </Card>

        <Card className="p-5">
          <h3 className="mb-3 flex items-center gap-2 text-[15px] font-semibold text-ink">
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-amber-50 text-amber-600">
              <BookOpen size={14} />
            </span>
            Материалы, требующие обновления
          </h3>
          {staleKnowledge.length === 0 ? (
            <p className="text-[14px] text-slate-500">Все материалы актуальны и подтверждены.</p>
          ) : (
            <ul className="space-y-2.5">
              {staleKnowledge.map((f) => (
                <li key={f.id} className="flex items-start justify-between gap-3">
                  <span className="min-w-0">
                    <span className="block truncate text-[13px] font-medium text-ink">«{f.question}»</span>
                    <span className="num block text-[11px] text-slate-500">
                      {f.source} · обновлено {f.updatedAt}
                    </span>
                  </span>
                  <Chip tone="warn">{f.status === 'outdated' ? 'устарело' : 'не подтверждено'}</Chip>
                </li>
              ))}
            </ul>
          )}
          <button type="button" className="btn-ghost mt-4 w-full" onClick={() => onGoTo('knowledge')}>
            Открыть базу знаний
          </button>
        </Card>
      </section>

      {/* Приватность */}
      <Modal
        open={privacyOpen}
        onClose={() => setPrivacyOpen(false)}
        title="Данные сотрудников и приватность"
        subtitle="Как устроена работа с записями — что предусмотрено в продукте."
        width="max-w-2xl"
      >
        <div className="space-y-3">
          {[
            {
              icon: Clock,
              title: 'Когда ведётся анализ',
              text: 'Только во время смены, после того как сотрудник сам нажал «Начать смену». Вне смены бейдж не пишет.',
            },
            {
              icon: Eye,
              title: 'Уведомлён ли сотрудник',
              text: 'Статус записи виден сотруднику постоянно на его главном экране: подключение, микрофон и активная смена.',
            },
            {
              icon: BookOpen,
              title: 'Какие данные сохраняются',
              text: 'Расшифровка разговора, отметки о стандартах и агрегированные показатели. Аудио в прототипе не хранится.',
            },
            {
              icon: Lock,
              title: 'Кто видит расшифровки',
              text: 'Сотрудник — свои разговоры. Руководитель — по своей зоне ответственности. Доступ настраивается по точкам и ролям.',
            },
            {
              icon: Shield,
              title: 'Обезличивание и хранение',
              text: 'Для сводной аналитики используются обезличенные показатели. Срок хранения расшифровок задаётся политикой компании.',
            },
            {
              icon: GraduationCap,
              title: 'Что для обучения, а что для управления',
              text: 'Разбор конкретных реплик используется для развития сотрудника. В управленческую аналитику попадают агрегаты по командам и точкам.',
            },
          ].map((b) => (
            <div key={b.title} className="flex gap-3 rounded-lg border border-slate-200 p-3.5">
              <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-slate-100 text-slate-500">
                <b.icon size={15} />
              </span>
              <div className="min-w-0">
                <p className="text-[14px] font-semibold text-ink">{b.title}</p>
                <p className="mt-0.5 text-[13px] leading-relaxed text-slate-600">{b.text}</p>
              </div>
            </div>
          ))}
          <p className="rounded-lg bg-slate-50 p-3.5 text-[12.5px] leading-relaxed text-slate-500">
            Это описание того, как продукт спроектирован. Конкретные сроки хранения, состав данных и
            матрица доступа настраиваются при внедрении и фиксируются в договоре — прототип их не
            реализует.
          </p>
        </div>
      </Modal>

      <p className="mt-6 text-[12px] text-muted">
        Демо-данные пилотного контура · {num(data.employees.length)} сотрудников,{' '}
        {num(data.dialogs.length)} разобранных {L.interactionGenitivePlural}. Показатели тестовые и требуют
        подтверждения на полном периоде.
      </p>
    </>
  );
}
