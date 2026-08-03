import { useMemo, useState } from 'react';
import {
  BookOpen,
  Clock,
  FileText,
  Search,
  ShieldAlert,
  ThumbsUp,
  TrendingDown,
  TrendingUp,
  TriangleAlert,
} from 'lucide-react';
import { useStore } from '../store';
import { PageHead } from '../components/Shell';
import { Card, Chip, EmptyState, SectionHead } from '../components/ui';
import { money, pct, times } from '../lib/format';
import type { KnowledgeStatus } from '../types';

const STATUS_META: Record<KnowledgeStatus, { label: string; tone: 'good' | 'warn' | 'neutral' }> = {
  published: { label: 'Опубликовано', tone: 'good' },
  draft: { label: 'Черновик', tone: 'neutral' },
  outdated: { label: 'Устарело', tone: 'warn' },
};

/**
 * Общая база знаний. Сотрудник ищет здесь готовый ответ,
 * руководитель видит, где ответы проседают, и что чинить обучением.
 */
export default function Knowledge({ role }: { role: 'rop' | 'employee' }) {
  const { data, profile } = useStore();
  const L = profile.labels;
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState('all');
  const [onlyWeak, setOnlyWeak] = useState(false);

  const categories = useMemo(() => {
    const used = new Set(data.faq.map((f) => f.category));
    return profile.categories.filter((c) => used.has(c));
  }, [data.faq, profile.categories]);

  const faq = useMemo(() => {
    const q = query.trim().toLowerCase();
    return [...data.faq]
      .sort((a, b) => b.count - a.count)
      .filter((f) => (category === 'all' ? true : f.category === category))
      .filter((f) => (onlyWeak ? f.conversion < 40 || !f.verified || f.status === 'outdated' : true))
      .filter(
        (f) => !q || f.question.toLowerCase().includes(q) || f.bestAnswer.toLowerCase().includes(q),
      );
  }, [data.faq, query, category, onlyWeak]);

  const needsAttention = data.faq.filter((f) => !f.verified || f.status === 'outdated').length;

  return (
    <>
      <PageHead
        title="База знаний"
        subtitle={
          role === 'employee'
            ? `Готовые ответы на частые вопросы ${L.clientGenitivePlural}. Формулировки собраны из разговоров, которые закончились результатом.`
            : `${L.catalog}, стандарты и ответы. Здесь же видно, какие ответы проседают — из них удобно собирать тесты.`
        }
      />

      {needsAttention > 0 && (
        <div className="mb-4 flex items-start gap-3 rounded-lg border border-amber-200 bg-amber-50 p-3.5">
          <ShieldAlert size={16} className="mt-0.5 shrink-0 text-amber-600" />
          <p className="text-[13px] leading-relaxed text-amber-900">
            {needsAttention} материала требуют внимания: данные устарели или не подтверждены
            ответственным. Onvy не отвечает по ним автоматически — сотрудник получит указание уточнить у{' '}
            {L.helpTargetGenitive}.
          </p>
        </div>
      )}

      {/* Фильтры — один ряд над всем, что они охватывают */}
      <div className="mb-5 flex flex-wrap items-center gap-3">
        <div className="relative min-w-[220px] flex-1 sm:max-w-sm">
          <Search size={17} className="absolute top-1/2 left-3.5 -translate-y-1/2 text-slate-500" />
          <input
            className="field pl-10"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Найти вопрос или ответ…"
            type="search"
          />
        </div>
        <select
          className="field w-auto min-w-[170px] py-2 text-[13px]"
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
        <label className="inline-flex cursor-pointer items-center gap-2 text-[13px] text-slate-600">
          <input
            type="checkbox"
            checked={onlyWeak}
            onChange={(e) => setOnlyWeak(e.target.checked)}
            className="h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
          />
          Только проблемные
        </label>
      </div>

      {faq.length === 0 ? (
        <EmptyState
          icon={<BookOpen size={22} />}
          title={data.faq.length === 0 ? 'База знаний пуста' : 'Ничего не нашлось'}
          hint={
            data.faq.length === 0
              ? `${L.catalog} загружается файлом в разделе «Стоп-лист и смена». Частые вопросы соберутся здесь сами — из того, что спрашивали в зале.`
              : 'Попробуйте другую формулировку или снимите фильтр.'
          }
        />
      ) : (
        <div className="grid gap-3 lg:grid-cols-2">
          {faq.map((f) => {
            const st = STATUS_META[f.status];
            return (
              <Card key={f.id} className="p-5">
                <div className="mb-2 flex flex-wrap items-start justify-between gap-2">
                  <h3 className="min-w-0 text-[15px] leading-snug font-semibold text-ink">
                    «{f.question}»
                  </h3>
                  <Chip tone={f.conversion >= 55 ? 'good' : f.conversion >= 30 ? 'warn' : 'bad'}>
                    {pct(f.conversion, 0)}
                  </Chip>
                </div>

                <div className="mb-3 flex flex-wrap items-center gap-x-3 gap-y-1.5">
                  <Chip tone="neutral">{f.category}</Chip>
                  <Chip tone={st.tone}>{st.label}</Chip>
                  <span className="num text-[12px] text-slate-500">{times(f.count)} за месяц</span>
                  <span
                    className={`num inline-flex items-center gap-1 text-[12px] font-semibold ${
                      f.trend > 0 ? 'text-amber-600' : 'text-emerald-600'
                    }`}
                  >
                    {f.trend > 0 ? <TrendingUp size={12} /> : <TrendingDown size={12} />}
                    {f.trend > 0 ? '+' : ''}
                    {f.trend} %
                  </span>
                  <span className="num inline-flex items-center gap-1 text-[12px] text-slate-500">
                    <Clock size={12} /> ответ {f.avgResponseSec.toFixed(1).replace('.', ',')} сек
                  </span>
                </div>

                {!f.verified && (
                  <div className="mb-2.5 flex items-start gap-2 rounded-md border border-amber-200 bg-amber-50 p-2.5">
                    <TriangleAlert size={14} className="mt-0.5 shrink-0 text-amber-600" />
                    <p className="text-[12.5px] leading-relaxed text-amber-900">
                      Информация не подтверждена. Onvy не отвечает по ней автоматически — уточните у{' '}
                      {L.helpTargetGenitive}.
                    </p>
                  </div>
                )}

                <div className="rounded-lg bg-emerald-50 p-3.5">
                  <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold tracking-[0.06em] text-emerald-700 uppercase">
                    <ThumbsUp size={12} /> Как отвечать
                  </p>
                  <p className="text-[14px] leading-relaxed text-emerald-950">{f.bestAnswer}</p>
                </div>

                {role === 'rop' && (
                  <div className="mt-2.5 rounded-lg bg-amber-50 p-3.5">
                    <p className="mb-1 flex items-center gap-1.5 text-[11px] font-semibold tracking-[0.06em] text-amber-700 uppercase">
                      <TriangleAlert size={12} /> Где проседает
                    </p>
                    <p className="text-[14px] leading-relaxed text-amber-950">{f.weakSpot}</p>
                  </div>
                )}

                <p className="num mt-2.5 text-[11px] text-slate-500">
                  Источник: {f.source} · обновлено {f.updatedAt}
                </p>
              </Card>
            );
          })}
        </div>
      )}

      {/* Загруженные источники */}
      {data.knowledgeFiles.length > 0 && (
        <section className="mt-8">
          <SectionHead
            title="Загруженные источники"
            hint="Демо-данные · файлы не разбираются по-настоящему, показана симуляция обработки."
          />
          <Card>
            <ul className="divide-y divide-slate-100">
              {data.knowledgeFiles.map((f) => (
                <li key={f.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3.5">
                  <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-slate-100 text-slate-500">
                    <FileText size={15} />
                  </span>
                  <div className="min-w-0 flex-1 basis-full sm:basis-auto">
                    <p className="truncate text-[14px] font-semibold text-ink">{f.name}</p>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {f.categories.map((c) => (
                        <span
                          key={c}
                          className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[11px] text-slate-600"
                        >
                          {c}
                        </span>
                      ))}
                    </div>
                  </div>
                  <span className="num text-[12px] text-slate-500">{f.records} записей</span>
                  <span className="num w-24 shrink-0 text-right text-[12px] text-slate-500">
                    {f.uploadedAt}
                  </span>
                </li>
              ))}
            </ul>
          </Card>
        </section>
      )}

      {/* Ошибки скрипта — только руководителю */}
      {role === 'rop' && data.scriptErrors.length > 0 && (
        <section className="mt-8">
          <SectionHead
            title={`Ошибки: ${L.script.toLowerCase()}`}
            hint="Сколько раз этап пропущен и во что это обходится, если суммы известны."
          />
          <Card>
            <ul className="divide-y divide-slate-100">
              {[...data.scriptErrors]
                .sort((a, b) => b.count - a.count)
                .map((e) => (
                  <li key={e.id} className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3.5">
                    <div className="min-w-0 flex-1 basis-full sm:basis-auto">
                      <p className="text-[14px] font-semibold text-ink">{e.label}</p>
                      <p className="mt-0.5 truncate text-[12px] text-slate-500">
                        Чаще всего: {e.employees.join(', ')}
                      </p>
                    </div>
                    <span className="num text-[13px] text-slate-500">{times(e.count)}</span>
                    {e.costPerMonth > 0 && (
                      <span className="num w-28 shrink-0 text-right text-[14px] font-semibold text-rose-600">
                        −{money(e.costPerMonth, true)}
                      </span>
                    )}
                  </li>
                ))}
            </ul>
          </Card>
        </section>
      )}
    </>
  );
}
