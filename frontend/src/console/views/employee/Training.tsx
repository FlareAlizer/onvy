import { useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  BookOpen,
  Check,
  FileText,
  GraduationCap,
  RotateCcw,
  Sparkles,
  Trophy,
  X,
} from 'lucide-react';
import { useStore } from '../../store';
import { PageHead } from '../../components/Shell';
import { Card, Chip, EmptyState, Progress, SectionHead } from '../../components/ui';
import CountUp from '../../components/CountUp';
import { humanDate, num, plural } from '../../lib/format';
import type { Test } from '../../types';

const SOURCE_LABEL: Record<string, { label: string; icon: typeof FileText }> = {
  file: { label: 'Из файла', icon: FileText },
  prompt: { label: 'По описанию', icon: BookOpen },
  errors: { label: 'По ошибкам', icon: Sparkles },
  questions: { label: 'По частым вопросам', icon: Sparkles },
  knowledge: { label: 'Из базы знаний', icon: BookOpen },
};

function TestRunner({ test, onExit }: { test: Test; onExit: () => void }) {
  const { me, recordTestResult } = useStore();
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, number>>({});
  const [checked, setChecked] = useState(false);
  const [finished, setFinished] = useState(false);

  const q = test.questions[step];
  const picked = answers[q?.id ?? ''];
  const isLast = step === test.questions.length - 1;

  const score = Math.round(
    (test.questions.filter((qq) => answers[qq.id] === qq.correct).length / test.questions.length) * 100,
  );

  const next = () => {
    if (!checked) {
      setChecked(true);
      return;
    }
    if (isLast) {
      if (me) recordTestResult(test.id, me.id, score);
      setFinished(true);
      return;
    }
    setStep(step + 1);
    setChecked(false);
  };

  const restart = () => {
    setStep(0);
    setAnswers({});
    setChecked(false);
    setFinished(false);
  };

  if (finished) {
    const passed = score >= test.passScore;
    return (
      <Card className="mx-auto max-w-2xl p-7 text-center">
        <div
          className={`mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-xl ${
            passed ? 'bg-emerald-50 text-emerald-600' : 'bg-amber-50 text-amber-600'
          }`}
        >
          {passed ? <Trophy size={26} /> : <RotateCcw size={26} />}
        </div>
        <h2 className="text-[24px] font-semibold tracking-tight text-ink">
          {passed ? 'Тест пройден' : 'Почти получилось'}
        </h2>
        <p className="mt-1.5 text-[15px] text-slate-500">
          {passed
            ? 'Результат засчитан, опыт начислен. Приёмы из теста работают в зале — используйте их уже сегодня.'
            : `Для зачёта нужно ${test.passScore} %. Разберите ошибки ниже и пройдите ещё раз — попытки не ограничены.`}
        </p>

        <p className="figure mt-6 text-[52px] leading-none font-semibold text-ink">
          <CountUp to={score} suffix=" %" />
        </p>
        <p className="mt-1 text-[13px] text-slate-500">
          {test.questions.filter((qq) => answers[qq.id] === qq.correct).length} из{' '}
          {test.questions.length} верно
        </p>
        {passed && (
          <p className="num mt-3 inline-block rounded-md bg-brand-50 px-3 py-1.5 text-[13px] font-semibold text-brand-800">
            +{score * 2} XP
          </p>
        )}

        <ul className="mt-6 space-y-2.5 text-left">
          {test.questions.map((qq) => {
            const ok = answers[qq.id] === qq.correct;
            return (
              <li
                key={qq.id}
                className={`rounded-lg border p-3.5 ${ok ? 'border-emerald-200 bg-emerald-50/50' : 'border-rose-200 bg-rose-50/50'}`}
              >
                <div className="flex gap-2.5">
                  <span
                    className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-white ${ok ? 'bg-emerald-500' : 'bg-rose-500'}`}
                  >
                    {ok ? <Check size={12} strokeWidth={3} /> : <X size={12} strokeWidth={3} />}
                  </span>
                  <div className="min-w-0">
                    <p className="text-[14px] font-semibold text-ink">{qq.question}</p>
                    {!ok && (
                      <p className="mt-1 text-[13px] text-slate-600">
                        Верно: <span className="font-semibold">{qq.options[qq.correct]}</span>
                      </p>
                    )}
                    <p className="mt-1 text-[13px] leading-relaxed text-slate-500">{qq.explain}</p>
                  </div>
                </div>
              </li>
            );
          })}
        </ul>

        <div className="mt-6 flex justify-center gap-2">
          <button type="button" className="btn-ghost" onClick={restart}>
            <RotateCcw size={15} /> Пройти заново
          </button>
          <button type="button" className="console-btn-primary" onClick={onExit}>
            К обучению
          </button>
        </div>
      </Card>
    );
  }

  return (
    <Card className="mx-auto max-w-2xl p-6">
      <div className="mb-5">
        <div className="mb-2 flex items-center justify-between">
          <span className="label">
            Вопрос {step + 1} из {test.questions.length}
          </span>
          <button type="button" onClick={onExit} className="btn-quiet -mr-2 rounded-md p-1.5">
            <X size={16} />
            <span className="sr-only">Выйти из теста</span>
          </button>
        </div>
        <Progress value={((step + (checked ? 1 : 0)) / test.questions.length) * 100} height={6} />
      </div>

      <h2 className="text-[19px] leading-snug font-semibold text-ink">{q.question}</h2>

      <ul className="mt-5 space-y-2.5">
        {q.options.map((o, i) => {
          const isPicked = picked === i;
          const isCorrect = i === q.correct;
          const tone = !checked
            ? isPicked
              ? 'border-brand-400 bg-brand-50/60'
              : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
            : isCorrect
              ? 'border-emerald-300 bg-emerald-50'
              : isPicked
                ? 'border-rose-300 bg-rose-50'
                : 'border-slate-200 opacity-60';
          return (
            <li key={o}>
              <button
                type="button"
                disabled={checked}
                onClick={() => setAnswers({ ...answers, [q.id]: i })}
                className={`flex w-full items-start gap-3 rounded-lg border p-3.5 text-left transition ${tone}`}
              >
                <span
                  className={`mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 text-[10px] font-semibold ${
                    checked && isCorrect
                      ? 'border-emerald-500 bg-emerald-500 text-white'
                      : checked && isPicked
                        ? 'border-rose-500 bg-rose-500 text-white'
                        : isPicked
                          ? 'border-brand-600 bg-brand-600 text-white'
                          : 'border-slate-300 text-transparent'
                  }`}
                >
                  {checked && isCorrect ? (
                    <Check size={11} strokeWidth={3.5} />
                  ) : checked && isPicked ? (
                    <X size={11} strokeWidth={3.5} />
                  ) : (
                    String.fromCharCode(65 + i)
                  )}
                </span>
                <span className="text-[14px] leading-relaxed text-ink">{o}</span>
              </button>
            </li>
          );
        })}
      </ul>

      {checked && (
        <div className="mt-4 rounded-lg bg-slate-50 p-3.5">
          <p className="text-[13px] leading-relaxed text-slate-600">
            <span className="font-semibold text-ink">Почему так: </span>
            {q.explain}
          </p>
        </div>
      )}

      <button
        type="button"
        className="console-btn-primary mt-5 w-full"
        disabled={picked === undefined}
        onClick={next}
      >
        {!checked ? 'Проверить' : isLast ? 'Завершить тест' : 'Следующий вопрос'}
        {checked && !isLast && <ArrowRight size={16} />}
      </button>
    </Card>
  );
}

export default function Training() {
  const { me, data } = useStore();
  const [running, setRunning] = useState<Test | null>(null);
  if (!me) return null;

  const assigned = data.tests.filter((t) => t.assignedTo.includes(me.id));
  const done = assigned.filter((t) => (t.results[me.id] ?? 0) >= t.passScore);
  const todo = assigned.filter((t) => (t.results[me.id] ?? 0) < t.passScore);

  if (running) {
    return (
      <>
        <button type="button" onClick={() => setRunning(null)} className="btn-quiet -ml-3 mb-4">
          <ArrowLeft size={16} /> Обучение
        </button>
        <TestRunner test={running} onExit={() => setRunning(null)} />
      </>
    );
  }

  return (
    <>
      <PageHead
        title="Обучение"
        subtitle="Короткие тесты от руководителя. Они собраны из ваших же диалогов — то, что реально мешает продавать."
      />

      {/* Онбординг */}
      <Card className="p-5">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-700">
              <GraduationCap size={22} />
            </div>
            <div>
              <h2 className="text-[15px] font-semibold text-ink">Онбординг</h2>
              <p className="mt-0.5 text-[13px] text-slate-500">
                {me.onboarding >= 100
                  ? 'Программа пройдена — вы работаете в полную силу.'
                  : `Пройдено ${done.length} из ${assigned.length} ${plural(assigned.length, 'теста', 'тестов', 'тестов')}. До самостоятельной работы осталось немного.`}
              </p>
            </div>
          </div>
          <div className="w-full sm:w-64">
            <div className="mb-1.5 flex items-baseline justify-between">
              <span className="label">Готовность</span>
              <span className="num text-[15px] font-semibold text-ink">{me.onboarding}%</span>
            </div>
            <Progress
              value={me.onboarding}
              tone={me.onboarding >= 90 ? 'good' : me.onboarding >= 50 ? 'warn' : 'bad'}
            />
          </div>
        </div>
      </Card>

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {[
          { label: 'Назначено', value: assigned.length },
          { label: 'Пройдено', value: done.length },
          { label: 'Опыт', value: `${num(me.xp)} XP` },
        ].map((s) => (
          <Card key={s.label} className="p-4">
            <p className="label">{s.label}</p>
            <p className="figure mt-1.5 text-[24px] leading-none font-semibold text-ink">{s.value}</p>
          </Card>
        ))}
      </div>

      <section className="mt-7">
        <SectionHead title="Нужно пройти" />
        {todo.length === 0 ? (
          <EmptyState
            icon={<Trophy size={22} />}
            title="Всё пройдено"
            hint="Новые тесты появятся, когда руководитель их назначит — обычно после разбора диалогов за неделю."
          />
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {todo.map((t) => {
              const S = SOURCE_LABEL[t.source];
              const attempt = t.results[me.id];
              return (
                <Card key={t.id} className="flex flex-col p-5">
                  <div className="mb-2 flex items-start justify-between gap-3">
                    <Chip tone="brand" icon={<S.icon size={11} />}>
                      {S.label}
                    </Chip>
                    {attempt !== undefined && <Chip tone="warn">Попытка: {attempt} %</Chip>}
                  </div>
                  <h3 className="text-[16px] leading-snug font-semibold text-ink">{t.title}</h3>
                  <p className="mt-1.5 flex-1 text-[13px] leading-relaxed text-slate-500">{t.description}</p>
                  <p className="num mt-2 text-[11.5px] text-slate-500">Источник: {t.sourceDetail}</p>
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
                    <span className="num text-[12px] text-slate-500">
                      {t.questions.length}{' '}
                      {plural(t.questions.length, 'вопрос', 'вопроса', 'вопросов')} · до {t.deadline} ·
                      проходной {t.passScore} %
                    </span>
                    <button type="button" className="console-btn-primary" onClick={() => setRunning(t)}>
                      {attempt !== undefined ? 'Пройти заново' : 'Начать'}
                      <ArrowRight size={15} />
                    </button>
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </section>

      {done.length > 0 && (
        <section className="mt-7">
          <SectionHead title="Пройдено" />
          <Card>
            <ul className="divide-y divide-slate-100">
              {done.map((t) => (
                <li key={t.id} className="flex flex-wrap items-center gap-3 px-4 py-3.5">
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-md bg-emerald-50 text-emerald-600">
                    <Check size={15} strokeWidth={3} />
                  </span>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-[14px] font-semibold text-ink">{t.title}</p>
                    <p className="text-[12px] text-slate-500">Назначен {humanDate(t.createdAt)}</p>
                  </div>
                  <span className="num text-[15px] font-semibold text-emerald-600">{t.results[me.id]} %</span>
                  <button type="button" className="btn-ghost px-3 py-1.5 text-[12px]" onClick={() => setRunning(t)}>
                    Повторить
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        </section>
      )}
    </>
  );
}
