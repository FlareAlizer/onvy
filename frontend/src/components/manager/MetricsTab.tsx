// Метрики пилота (spec S6): Δ среднего чека, Δ скорости обслуживания, латентность
// стека, выгрузка CSV для инвестраунда.
//
// Честная оговорка (см. отчёт агента): на момент написания этого экрана
// бэкенд ещё не отдаёт ни одного из этих чисел — day-план спеки (§3) относит
// замер латентности и телеметрию пилота на 30 июля. Экран написан против
// разумного контракта:
//   GET /api/venues/{id}/metrics/summary  -> MetricsSummary (ниже)
//   GET /api/venues/{id}/metrics/export.csv -> файл
// и явно отличает "эндпоинт ещё не готов" (404) от настоящей ошибки сети —
// как только бэкенд реализует эти два роута, вкладка заработает без правок.

import { useEffect, useState } from 'react';
import { BarChart3, Download, HelpCircle } from 'lucide-react';
import { ApiError, api, getSession } from '../../lib/api';
import { LoadingState, ErrorState } from '../StateView';

type MetricsSummary = {
  since: string;
  avg_check_delta_percent: number | null;
  service_speed_delta_percent: number | null;
  assistant_queries_total: number;
  assistant_hit_rate: number;
  translation_failures: number;
  stage_latency_ms: { asr: number; search: number; answer: number; tts: number; total: number };
};

type Status = 'loading' | 'ready' | 'not-ready' | 'error';

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
      .catch((e) => setStatus(e instanceof ApiError && e.status === 404 ? 'not-ready' : 'error'));
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

  if (status === 'not-ready') {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 px-8 text-center">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-stone-800 text-stone-400">
          <HelpCircle size={26} />
        </div>
        <h3 className="text-lg font-semibold text-stone-100">Метрики пока не готовы</h3>
        <p className="max-w-xs text-sm leading-relaxed text-stone-400">
          Замер латентности и телеметрия пилота появятся ближе к 30 июля. Экран уже готов
          показать цифры, как только бэкенд отдаст `GET /venues/{'{id}'}/metrics/summary`.
        </p>
      </div>
    );
  }

  if (!data) return null;

  return (
    <div className="flex h-full flex-col gap-5 overflow-y-auto px-5 pt-4 pb-6">
      <div className="flex items-center justify-between">
        <h2 className="flex items-center gap-2 text-xl font-bold tracking-tight text-stone-50">
          <BarChart3 size={22} /> Метрики пилота
        </h2>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Stat label="Δ средний чек" value={formatDelta(data.avg_check_delta_percent)} />
        <Stat label="Δ скорость обслуживания" value={formatDelta(data.service_speed_delta_percent)} />
        <Stat label="Вопросов ассистенту" value={String(data.assistant_queries_total)} />
        <Stat label="Ответ найден" value={`${Math.round(data.assistant_hit_rate * 100)}%`} />
      </div>

      <div className="rounded-2xl bg-stone-900 p-5">
        <h3 className="mb-3 text-sm font-bold uppercase tracking-widest text-stone-500">
          Латентность стека, p95
        </h3>
        <div className="space-y-2">
          <LatencyRow label="Запись + ASR" ms={data.stage_latency_ms.asr} budgetMs={1100} />
          <LatencyRow label="Поиск / ответ" ms={data.stage_latency_ms.search + data.stage_latency_ms.answer} budgetMs={800} />
          <LatencyRow label="Озвучка" ms={data.stage_latency_ms.tts} budgetMs={600} />
          <LatencyRow label="Итого" ms={data.stage_latency_ms.total} budgetMs={2500} strong />
        </div>
      </div>

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

function formatDelta(value: number | null): string {
  if (value === null) return '—';
  const sign = value > 0 ? '+' : '';
  return `${sign}${value.toFixed(1)}%`;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl bg-stone-900 p-4">
      <p className="text-2xl font-bold text-stone-50">{value}</p>
      <p className="mt-1 text-xs font-medium text-stone-500">{label}</p>
    </div>
  );
}

function LatencyRow({ label, ms, budgetMs, strong }: { label: string; ms: number; budgetMs: number; strong?: boolean }) {
  const overBudget = ms > budgetMs;
  return (
    <div className="flex items-center justify-between">
      <span className={`text-sm ${strong ? 'font-semibold text-stone-200' : 'text-stone-400'}`}>{label}</span>
      <span className={`font-mono text-sm font-bold ${overBudget ? 'text-amber-300' : 'text-emerald-300'}`}>
        {ms} мс
      </span>
    </div>
  );
}
