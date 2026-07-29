import { useMemo, useState } from 'react';
import {
  BookOpen,
  Check,
  FileText,
  Loader2,
  MessageCircleQuestion,
  Pencil,
  Plus,
  Sparkles,
  Trash2,
  TriangleAlert,
  Upload,
  Users,
} from 'lucide-react';
import { useStore } from '../../store';
import { PageHead } from '../../components/Shell';
import { Avatar, Card, Chip, EmptyState, Field, Modal, SectionHead } from '../../components/ui';
import { humanDate, num, plural, times } from '../../lib/format';
import type { Test, TestQuestion, TestSource } from '../../types';

const SOURCES: { id: TestSource; title: string; hint: string; icon: typeof Upload }[] = [
  {
    id: 'errors',
    title: 'По ошибкам сотрудников',
    hint: 'Onvy возьмёт реальные пробелы из разобранных разговоров — тест попадёт ровно в слабое место.',
    icon: Sparkles,
  },
  {
    id: 'questions',
    title: 'По частым вопросам',
    hint: 'Вопросы клиентов с низкой результативностью — то, на чём чаще всего теряется результат.',
    icon: MessageCircleQuestion,
  },
  {
    id: 'knowledge',
    title: 'Из базы знаний',
    hint: 'Материалы компании: стандарты, каталог, регламенты.',
    icon: BookOpen,
  },
  {
    id: 'file',
    title: 'Из файла',
    hint: 'Загрузите документ — вопросы соберутся по содержанию.',
    icon: Upload,
  },
  {
    id: 'prompt',
    title: 'По описанию',
    hint: 'Опишите словами, что должен знать сотрудник.',
    icon: Pencil,
  },
];

export default function TestGenerator() {
  const { data, profile, addTest, assignTest } = useStore();
  const L = profile.labels;
  const [source, setSource] = useState<TestSource>('errors');
  const [topic, setTopic] = useState('');
  const [fileName, setFileName] = useState('');
  const [knowledgeCat, setKnowledgeCat] = useState(profile.categories[0] ?? '');
  const [title, setTitle] = useState('');
  const [deadline, setDeadline] = useState('2026-08-12');
  const [passScore, setPassScore] = useState(70);
  const [busy, setBusy] = useState(false);
  const [draft, setDraft] = useState<TestQuestion[] | null>(null);
  const [assignTo, setAssignTo] = useState<string[]>([]);
  const [assigning, setAssigning] = useState<Test | null>(null);

  const canGenerate =
    source === 'errors'
      ? data.scriptErrors.length > 0
      : source === 'questions'
        ? data.faq.length > 0
        : source === 'knowledge'
          ? !!knowledgeCat
          : source === 'file'
            ? !!fileName
            : topic.trim().length > 4;

  const suggestedTitle = useMemo(() => {
    if (source === 'errors') return `Разбор частых ошибок: ${L.script.toLowerCase()}`;
    if (source === 'questions') return 'Ответы на частые вопросы';
    if (source === 'knowledge') return `${knowledgeCat}: проверка знаний`;
    if (source === 'file') return fileName.replace(/\.[^.]+$/, '');
    return topic.slice(0, 60);
  }, [source, fileName, topic, knowledgeCat, L.script]);

  const sourceDetail = useMemo(() => {
    if (source === 'errors') return `Ошибки сотрудников · ${L.script}`;
    if (source === 'questions') return 'Частые вопросы · низкая результативность';
    if (source === 'knowledge') return `База знаний · ${knowledgeCat}`;
    if (source === 'file') return `Файл · ${fileName}`;
    return `Описание руководителя`;
  }, [source, fileName, knowledgeCat, L.script]);

  /** Собирает вопросы из того, что платформа уже знает о команде. */
  const build = (): TestQuestion[] => {
    const qs: TestQuestion[] = [];
    const weakFaq = [...data.faq].sort((a, b) => a.conversion - b.conversion);

    if (source === 'errors') {
      data.scriptErrors.slice(0, 2).forEach((e, i) => {
        qs.push({
          id: `g${i}`,
          question: `Что происходит, если пропустить этап: «${e.label.toLowerCase()}»?`,
          options: [
            'Ничего критичного, клиент решает сам',
            'Падает результативность и качество обслуживания — этап обязателен',
            'Экономится время в час пик',
            'Это допустимо для опытных сотрудников',
          ],
          correct: 1,
          explain: `Ситуация зафиксирована ${times(e.count)} за месяц. Требуется поддержка: ${e.employees.join(', ')}.`,
          source: L.script,
        });
      });
      weakFaq.slice(0, 2).forEach((f, i) => {
        qs.push({
          id: `g${qs.length + i}`,
          question: `${L.client} спрашивает: «${f.question}». Как ответить?`,
          options: [
            'Ответить коротко и дать подумать',
            f.bestAnswer,
            'Предложить скидку, чтобы закрыть быстрее',
            `Переадресовать вопрос: ${L.helpTarget.toLowerCase()}`,
          ],
          correct: 1,
          explain: `Результативность вопроса сейчас ${Math.round(f.conversion)} %. Формулировка собрана из разговоров, которые закончились результатом.`,
          source: f.category,
        });
      });
    } else if (source === 'questions') {
      weakFaq.slice(0, 4).forEach((f, i) => {
        qs.push({
          id: `g${i}`,
          question: `${L.client} спрашивает: «${f.question}». Ваш ответ?`,
          options: [
            'Перечислить все характеристики по порядку',
            f.bestAnswer,
            'Уточнить бюджет',
            'Предложить вернуться позже',
          ],
          correct: 1,
          explain: f.verified
            ? `Ответ подтверждён. Результативность вопроса — ${Math.round(f.conversion)} %.`
            : 'Материал не подтверждён — перед публикацией теста уточните формулировку у ответственного.',
          source: f.category,
        });
      });
    } else {
      const inCat = data.faq.filter((f) => (source === 'knowledge' ? f.category === knowledgeCat : true));
      const pool = inCat.length ? inCat : data.faq;
      pool.slice(0, 3).forEach((f, i) => {
        qs.push({
          id: `g${i}`,
          question: `${L.client} спрашивает: «${f.question}». Ваш ответ?`,
          options: [
            'Ответить по памяти',
            f.bestAnswer,
            `Уточнить: ${L.helpTarget.toLowerCase()}`,
            'Предложить другой вариант',
          ],
          correct: 1,
          explain: 'Отвечайте пользой для клиента, а не перечислением фактов.',
          source: f.category,
        });
      });
      qs.push({
        id: 'g9',
        question: `${L.client} говорит, что ему нужно подумать. Что сделать?`,
        options: [
          'Попрощаться',
          'Назначить следующий шаг и зафиксировать договорённость',
          'Дать максимальную скидку',
          'Позвать руководителя',
        ],
        correct: 1,
        explain: 'Следующий шаг возвращает часть ушедших клиентов. Без него результат закрыт в ноль.',
        source: L.script,
      });
    }
    return qs;
  };

  const generate = () => {
    setBusy(true);
    setDraft(null);
    // Симуляция генерации — внешних AI-сервисов в прототипе нет.
    setTimeout(() => {
      setDraft(build());
      setTitle(suggestedTitle);
      setAssignTo(
        source === 'errors'
          ? data.employees.filter((e) => e.stats.scriptCompliance < 85).map((e) => e.id)
          : [],
      );
      setBusy(false);
    }, 1600);
  };

  const save = () => {
    if (!draft) return;
    const created = addTest({
      title: title.trim() || suggestedTitle,
      description:
        source === 'errors'
          ? `Собран по ${num(data.scriptErrors.reduce((a, e) => a + e.count, 0))} зафиксированным ситуациям в разговорах.`
          : source === 'questions'
            ? 'Собран из вопросов клиентов с самой низкой результативностью.'
            : source === 'knowledge'
              ? `Собран по материалам базы знаний: ${knowledgeCat}.`
              : source === 'file'
                ? `Загружен из файла «${fileName}».`
                : `Сгенерирован по описанию: ${topic}`,
      source,
      sourceDetail,
      createdBy: 'Вы',
      deadline,
      passScore,
      questions: draft,
      assignedTo: assignTo,
    });
    setDraft(null);
    setTopic('');
    setFileName('');
    setTitle('');
    setAssignTo([]);
    setAssigning(created);
  };

  const toggle = (id: string) =>
    setAssignTo((a) => (a.includes(id) ? a.filter((x) => x !== id) : [...a, id]));

  const editQuestion = (id: string, patch: Partial<TestQuestion>) =>
    setDraft((d) => d?.map((q) => (q.id === id ? { ...q, ...patch } : q)) ?? null);

  return (
    <>
      <PageHead
        title="Генератор тестов"
        subtitle="Обучение собирается из того, что платформа уже услышала в зале: реальные пробелы, а не абстрактная теория."
      />

      <Card className="p-5">
        <SectionHead eyebrow="Шаг 1" title="Откуда взять материал" />
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {SOURCES.map((s) => {
            const on = source === s.id;
            return (
              <button
                key={s.id}
                type="button"
                onClick={() => {
                  setSource(s.id);
                  setDraft(null);
                }}
                className={`rounded-xl border p-4 text-left transition ${
                  on ? 'border-brand-500 bg-brand-50/60' : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                }`}
              >
                <span
                  className={`mb-3 flex h-9 w-9 items-center justify-center rounded-lg ${
                    on ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-500'
                  }`}
                >
                  <s.icon size={17} />
                </span>
                <span className="block text-[14px] font-semibold text-ink">{s.title}</span>
                <span className="mt-1 block text-[12.5px] leading-relaxed text-slate-500">{s.hint}</span>
              </button>
            );
          })}
        </div>

        <div className="mt-5 border-t border-slate-100 pt-5">
          {source === 'errors' && (
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="label mb-2.5">Что попадёт в тест</p>
              {data.scriptErrors.length === 0 ? (
                <p className="text-[13px] text-slate-500">
                  Пока нет разобранных разговоров. Источник станет доступен после первых смен.
                </p>
              ) : (
                <ul className="space-y-2">
                  {data.scriptErrors.slice(0, 3).map((e) => (
                    <li key={e.id} className="flex items-start gap-2.5 text-[13px] text-slate-700">
                      <TriangleAlert size={14} className="mt-0.5 shrink-0 text-amber-500" />
                      <span>
                        {e.label} — <span className="num">{times(e.count)}</span> за месяц
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {source === 'questions' && (
            <div className="rounded-lg bg-slate-50 p-4">
              <p className="label mb-2.5">Вопросы с самой низкой результативностью</p>
              <ul className="space-y-2">
                {[...data.faq]
                  .sort((a, b) => a.conversion - b.conversion)
                  .slice(0, 4)
                  .map((f) => (
                    <li key={f.id} className="flex items-baseline justify-between gap-3 text-[13px]">
                      <span className="min-w-0 text-slate-700">«{f.question}»</span>
                      <span className="num shrink-0 font-semibold text-amber-700">{Math.round(f.conversion)} %</span>
                    </li>
                  ))}
              </ul>
            </div>
          )}

          {source === 'knowledge' && (
            <Field label="Раздел базы знаний" hint={`Структура зависит от отрасли: ${L.industry.toLowerCase()}`}>
              <select className="field" value={knowledgeCat} onChange={(e) => setKnowledgeCat(e.target.value)}>
                {profile.categories.map((c) => (
                  <option key={c}>{c}</option>
                ))}
              </select>
            </Field>
          )}

          {source === 'file' && (
            <Field label="Файл с материалом" hint="Демо-режим: файл не отправляется на сервер.">
              <label className="flex cursor-pointer items-center gap-3 rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-5 transition hover:border-brand-400 hover:bg-brand-50/40">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-white text-slate-500">
                  <FileText size={18} />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[14px] font-semibold text-ink">
                    {fileName || 'Выберите файл'}
                  </span>
                  <span className="block text-[12px] text-slate-500">
                    {fileName ? 'Файл готов к разбору' : 'PDF, DOCX, XLSX или TXT'}
                  </span>
                </span>
                <input
                  type="file"
                  className="sr-only"
                  accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.csv"
                  onChange={(e) => {
                    setFileName(e.target.files?.[0]?.name ?? '');
                    setDraft(null);
                  }}
                />
              </label>
            </Field>
          )}

          {source === 'prompt' && (
            <Field label="Что должен знать сотрудник" hint="Чем конкретнее описание, тем точнее вопросы.">
              <textarea
                className="field min-h-[96px] resize-y"
                value={topic}
                onChange={(e) => {
                  setTopic(e.target.value);
                  setDraft(null);
                }}
                placeholder={`Например: ${profile.testSources[0] ?? 'стандарт работы с клиентом'}`}
              />
            </Field>
          )}

          <div className="mt-4 flex flex-wrap items-end gap-3">
            <Field label="Срок">
              <input
                className="field num w-auto"
                type="date"
                value={deadline}
                onChange={(e) => setDeadline(e.target.value)}
              />
            </Field>
            <Field label="Проходной балл">
              <select
                className="field w-auto"
                value={passScore}
                onChange={(e) => setPassScore(Number(e.target.value))}
              >
                {[60, 70, 80, 90, 100].map((v) => (
                  <option key={v} value={v}>
                    {v} %
                  </option>
                ))}
              </select>
            </Field>
            <button type="button" className="console-btn-primary" disabled={!canGenerate || busy} onClick={generate}>
              {busy ? <Loader2 size={16} className="animate-spin" /> : <Sparkles size={16} />}
              {busy ? 'Собираем вопросы…' : 'Сгенерировать тест'}
            </button>
          </div>
        </div>
      </Card>

      {/* Черновик */}
      {draft && (
        <Card className="mt-4 p-5">
          <SectionHead
            eyebrow="Шаг 2"
            title="Проверьте и отредактируйте"
            hint="Вопросы можно изменить, лишние убрать, затем назначить сотрудникам."
          />

          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Название теста">
              <input className="field" value={title} onChange={(e) => setTitle(e.target.value)} />
            </Field>
            <Field label="Источник">
              <input className="field num" value={sourceDetail} readOnly />
            </Field>
          </div>

          <ul className="mt-4 space-y-3">
            {draft.map((q, qi) => (
              <li key={q.id} className="rounded-xl border border-slate-200 p-4">
                <div className="mb-3 flex items-start justify-between gap-3">
                  <span className="num mt-2 text-slate-500">{qi + 1}.</span>
                  <textarea
                    className="field min-h-[52px] flex-1 resize-y text-[14px] font-semibold"
                    value={q.question}
                    onChange={(e) => editQuestion(q.id, { question: e.target.value })}
                  />
                  <button
                    type="button"
                    className="btn-quiet mt-1 shrink-0 rounded-md p-1.5 text-slate-300 hover:text-rose-600"
                    onClick={() => setDraft(draft.filter((x) => x.id !== q.id))}
                  >
                    <Trash2 size={14} />
                    <span className="sr-only">Убрать вопрос</span>
                  </button>
                </div>
                <ul className="space-y-1.5">
                  {q.options.map((o, oi) => (
                    <li key={oi} className="flex items-center gap-2.5">
                      <button
                        type="button"
                        onClick={() => editQuestion(q.id, { correct: oi })}
                        title="Отметить как верный"
                        className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-[9px] font-semibold transition ${
                          oi === q.correct
                            ? 'bg-emerald-500 text-white'
                            : 'bg-slate-200 text-slate-500 hover:bg-slate-300'
                        }`}
                      >
                        {oi === q.correct ? <Check size={9} strokeWidth={4} /> : String.fromCharCode(65 + oi)}
                      </button>
                      <input
                        className={`field py-1.5 text-[13px] ${oi === q.correct ? 'border-emerald-300 bg-emerald-50' : ''}`}
                        value={o}
                        onChange={(e) =>
                          editQuestion(q.id, {
                            options: q.options.map((x, xi) => (xi === oi ? e.target.value : x)),
                          })
                        }
                      />
                    </li>
                  ))}
                </ul>
                <div className="mt-2.5 flex flex-wrap items-center gap-2">
                  <Chip tone="neutral">Источник: {q.source}</Chip>
                </div>
                <textarea
                  className="field mt-2 min-h-[52px] resize-y text-[12.5px]"
                  value={q.explain}
                  onChange={(e) => editQuestion(q.id, { explain: e.target.value })}
                  placeholder="Пояснение, которое увидит сотрудник"
                />
              </li>
            ))}
          </ul>

          <div className="mt-5 border-t border-slate-100 pt-5">
            <p className="label mb-2.5">Кому назначить</p>
            {data.employees.length === 0 ? (
              <p className="text-[13px] text-slate-500">
                В штате пока никого — тест можно сохранить и назначить позже.
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {data.employees.map((e) => {
                  const on = assignTo.includes(e.id);
                  return (
                    <button
                      key={e.id}
                      type="button"
                      onClick={() => toggle(e.id)}
                      className={`inline-flex items-center gap-2 rounded-lg border px-2.5 py-1.5 text-[13px] transition ${
                        on
                          ? 'border-brand-500 bg-brand-50 text-brand-900'
                          : 'border-slate-200 text-slate-600 hover:border-slate-300'
                      }`}
                    >
                      <Avatar name={e.name} size={22} />
                      {e.name}
                      {on && <Check size={13} className="text-brand-600" />}
                    </button>
                  );
                })}
              </div>
            )}
            <div className="mt-5 flex flex-wrap gap-2">
              <button type="button" className="console-btn-primary" disabled={draft.length === 0} onClick={save}>
                Сохранить и назначить
              </button>
              <button type="button" className="btn-ghost" onClick={() => setDraft(null)}>
                Отменить
              </button>
            </div>
          </div>
        </Card>
      )}

      {/* Существующие тесты */}
      <section className="mt-7">
        <SectionHead title="Программы обучения" hint="Результаты обновляются сразу после прохождения." />
        {data.tests.length === 0 ? (
          <EmptyState
            icon={<Sparkles size={22} />}
            title="Тестов пока нет"
            hint="Соберите первый — быстрее всего работает вариант «по ошибкам сотрудников»."
          />
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {data.tests.map((t) => {
              const done = Object.keys(t.results).length;
              const avg = done
                ? Math.round(Object.values(t.results).reduce((a, b) => a + b, 0) / done)
                : 0;
              const outcome = data.trainingOutcomes.find((o) => o.testId === t.id);
              return (
                <Card key={t.id} className="flex flex-col p-5">
                  <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
                    <Chip tone="brand">{t.sourceDetail}</Chip>
                    <span className="num text-[12px] text-slate-500">{humanDate(t.createdAt)}</span>
                  </div>
                  <h3 className="text-[16px] leading-snug font-semibold text-ink">{t.title}</h3>
                  <p className="mt-1.5 flex-1 text-[13px] leading-relaxed text-slate-500">{t.description}</p>

                  <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-1.5 text-[12px] text-slate-500">
                    <span className="num">
                      {t.questions.length} {plural(t.questions.length, 'вопрос', 'вопроса', 'вопросов')}
                    </span>
                    <span className="num">до {t.deadline}</span>
                    <span className="num">проходной {t.passScore} %</span>
                    <span className="num">
                      назначен {t.assignedTo.length}{' '}
                      {plural(t.assignedTo.length, 'сотруднику', 'сотрудникам', 'сотрудникам')}
                    </span>
                    {done > 0 && (
                      <span className="num font-semibold text-emerald-700">
                        прошли {done} · средний {avg} %
                      </span>
                    )}
                  </div>

                  {outcome && (
                    <div className="mt-3 rounded-lg bg-slate-50 p-3">
                      <p className="text-[12px] text-slate-500">Изменение после обучения</p>
                      <p className="num mt-1 text-[13px] font-semibold text-ink">
                        {outcome.metricLabel}: {outcome.before} → {outcome.after}
                        {outcome.unit === 'pct' ? ' %' : ''}
                      </p>
                      {outcome.repeated && (
                        <p className="mt-1 text-[12px] text-amber-700">
                          Ситуация повторялась — части команды нужна дополнительная поддержка.
                        </p>
                      )}
                    </div>
                  )}

                  <button type="button" className="btn-ghost mt-4 w-full" onClick={() => setAssigning(t)}>
                    <Users size={15} /> Кому назначен
                  </button>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      <Modal
        open={!!assigning}
        onClose={() => setAssigning(null)}
        title="Назначение теста"
        subtitle={assigning?.title}
        width="max-w-lg"
      >
        {assigning && (
          <>
            {data.employees.length === 0 ? (
              <p className="text-[14px] text-slate-500">В штате пока никого.</p>
            ) : (
              <ul className="space-y-1.5">
                {data.employees.map((e) => {
                  const on = assigning.assignedTo.includes(e.id);
                  const score = assigning.results[e.id];
                  return (
                    <li key={e.id}>
                      <button
                        type="button"
                        onClick={() => {
                          const next = on
                            ? assigning.assignedTo.filter((x) => x !== e.id)
                            : [...assigning.assignedTo, e.id];
                          assignTest(assigning.id, next);
                          setAssigning({ ...assigning, assignedTo: next });
                        }}
                        className={`flex w-full items-center gap-3 rounded-lg border p-2.5 text-left transition ${
                          on ? 'border-brand-400 bg-brand-50/60' : 'border-slate-200 hover:bg-slate-50'
                        }`}
                      >
                        <Avatar name={e.name} size={32} />
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-[14px] font-semibold text-ink">{e.name}</span>
                          <span className="block text-[12px] text-slate-500">{e.position}</span>
                        </span>
                        {score !== undefined && (
                          <Chip tone={score >= assigning.passScore ? 'good' : 'warn'}>{score} %</Chip>
                        )}
                        <span
                          className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-md border-2 ${
                            on ? 'border-brand-600 bg-brand-600 text-white' : 'border-slate-300'
                          }`}
                        >
                          {on ? <Check size={12} strokeWidth={3.5} /> : <Plus size={12} className="text-slate-500" />}
                        </span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
            <button type="button" className="console-btn-primary mt-5 w-full" onClick={() => setAssigning(null)}>
              Готово
            </button>
          </>
        )}
      </Modal>
    </>
  );
}
