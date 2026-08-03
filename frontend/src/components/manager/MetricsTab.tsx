// Метрики пилота (spec S6): сколько спрашивали ассистента, как часто он находил
// ответ, сколько времени это занимало, сколько реплик прошло по рации.
//
// Экран когда-то был написан против придуманного контракта — с Δ среднего чека и
// поэтапной латентностью, — которого бэкенд так и не реализовал. Поля приходили
// undefined, и `.toFixed` ронял всё приложение в белый экран: падала не вкладка,
// а весь кабинет. Теперь типы повторяют app/schemas/insights.py: MetricsSummary.
//
// Среднего чека здесь нет и не будет до интеграции с учётной системой — её в
// пилот не берём, а выдумывать цифру нельзя.

import { useEffect, useState } from 'react';
import { BarChart3, Download } from 'lucide-react';
import { api, getSession } from '../../lib/api';
import { LoadingState, ErrorState } from '../StateView';

/** Ровно то, что отдаёт GET /venues/{id}/metrics/summary. */
type MetricsSummary = {
  days: number;
  assistant_queries: number;
  assistant_answered: number;
  assistant_missed: number;
  /** Пусто, когда данных за период ещё нет — это честнее нуля. */
  median_ms: number | null;
  p95_ms: number | null;
  utterances: number;
  translated: number;
  translation_failures: number;
};

type Status = 'loading' | 'ready' | 'error';

export default function MetricsTab() {
  const venueId = getSession()?.venueId;
  const [status, setStatus] = useState<Status>('loading');
  const [data, setData] = useState<MetricsSummary | null>(null);
  const [downloadError, setDownloadError] = useState('');

  const load = () => {
    if (!venueId) return;
    setStatus('loading');
    api<MetricsSummary>(`/venues/${venueId}/metrics/summary`)
      .then((d) => {
        setData(d);
        setStatus('ready');
      })
      .catch(() => setStatus('error'));
  };

  useEffect(load, [venueId]);

  const downloadCsv = async () => {
    if (!venueId) return;
    setDownloadError('');
    try {
      const session = getSession();
      const resp = await fetch(`/api/venues/${venueId}/metrics/export.csv`, {
        headers: session ? { Authorization: `Bearer ${session.accessToken}` } : undefined,
      });
      if (!resp.ok) throw new Error();
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `onvy-metrics-venue-${venueId}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      setDownloadError('Выгрузка CSV пока недоступна на сервере.');
    }
  };

  if (status === 'loading') return <LoadingState label="Загружаю метрики…" />;
  if (status === 'error')
    return <ErrorState message="Не удалось загрузить метрики. Проверьте вайфай." onRetry={load} />;

  if (!data) return null;

  const пустаяСводка = data.assistant_queries === 0 && data.utterances === 0;
  const доляОтветов =
    data.assistant_queries > 0
      ? Math.round((data.assistant_answered / data.assistant_queries) * 100)
      : null;

  return (
    <div className="flex h-full flex-col gap-5 overflow-y-auto px-5 pt-4 pb-6">
      <div>
        <h2 className="flex items-center gap-2 text-xl font-bold tracking-tight text-stone-50">
          <BarChart3 size={22} /> Метрики пилота
        </h2>
        <p className="mt-1 text-sm text-stone-500">За последние {data.days} дн.</p>
      </div>

      {пустаяСводка ? (
        <div className="rounded-2xl bg-stone-900 p-5">
          <p className="text-base font-semibold text-stone-200">Данных за период нет</p>
          <p className="mt-1.5 text-sm leading-relaxed text-stone-400">
            Цифры появятся после первых смен: считаются вопросы к ассистенту, реплики по рации
            и время ответа. Придуманных значений здесь не будет.
          </p>
        </div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3">
            <Stat label="Вопросов ассистенту" value={String(data.assistant_queries)} />
            <Stat
              label="Ответ нашёлся"
              value={доляОтветов === null ? '—' : `${доляОтветов}%`}
            />
            <Stat label="Реплик по рации" value={String(data.utterances)} />
            <Stat label="С переводом" value={String(data.translated)} />
          </div>

          <div className="rounded-2xl bg-stone-900 p-5">
            <h3 className="mb-3 text-sm font-bold uppercase tracking-widest text-stone-500">
              Время ответа
            </h3>
            <div className="space-y-2">
              <LatencyRow label="Медиана" ms={data.median_ms} budgetMs={2500} />
              <LatencyRow label="95-й процентиль" ms={data.p95_ms} budgetMs={2500} strong />
            </div>
            <p className="mt-3 text-xs leading-relaxed text-stone-500">
              Бюджет по спеке — 2.5 секунды. Среднее не показываем: один зависший запрос
              перекашивает его целиком.
            </p>
          </div>

          {data.assistant_missed > 0 && (
            <div className="rounded-2xl bg-stone-900 p-5">
              <p className="text-base font-semibold text-stone-200">
                Не нашлось ответа: {data.assistant_missed}
              </p>
              <p className="mt-1.5 text-sm leading-relaxed text-stone-400">
                Это не сбой, а подсказка: столько раз спросили то, чего нет в меню или что
                записано другими словами.
              </p>
            </div>
          )}

          {data.translation_failures > 0 && (
            <p className="text-sm text-amber-300">
              Перевод не сработал {data.translation_failures} раз — реплики доставлены на языке
              отправителя.
            </p>
          )}
        </>
      )}

      <button
        onClick={downloadCsv}
        className="flex items-center justify-center gap-2 rounded-2xl bg-stone-50 px-6 py-3.5 text-base font-semibold text-stone-950 transition-transform duration-150 ease-out active:scale-[0.97]"
      >
        <Download size={20} /> Выгрузить CSV
      </button>
      {downloadError && <p className="text-sm text-amber-300">{downloadError}</p>}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-stone-900 p-4">
      <p className="text-2xl font-bold text-stone-50">{value}</p>
      <p className="mt-1 text-xs font-medium text-stone-500">{label}</p>
    </div>
  );
}

function LatencyRow({
  label,
  ms,
  budgetMs,
  strong,
}: {
  label: string;
  /** Пусто, когда замеров за период не было. */
  ms: number | null;
  budgetMs: number;
  strong?: boolean;
}) {
  const overBudget = ms !== null && ms > budgetMs;
  return (
    <div className="flex items-center justify-between">
      <span className={`text-sm ${strong ? 'font-semibold text-stone-200' : 'text-stone-400'}`}>{label}</span>
      <span
        className={`font-mono text-sm font-bold ${
          ms === null ? 'text-stone-500' : overBudget ? 'text-amber-300' : 'text-emerald-300'
        }`}
      >
        {ms === null ? '—' : `${ms} мс`}
      </span>
    </div>
  );
}
