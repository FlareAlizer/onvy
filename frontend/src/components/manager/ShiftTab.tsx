// Кто сейчас на связи + лента последних реплик рации.
//
// Честная оговорка (см. отчёт агента): бэкенд пока не отдаёт настоящий REST
// для присутствия по точке (app/services/presence.py есть, наружу не выведен) —
// поэтому статус "в эфире" здесь считается по факту недавней реплики в этой
// вкладке, а не по серверному списку подключений. Как только появится
// GET /venues/{id}/presence, эту эвристику надо заменить на реальные данные.
//
// Вопросы к ассистенту (assistant_query) сюда тоже не попадают: наружу их
// сейчас никто не транслирует и не отдаёт историей — нужен либо WS-relay,
// либо GET /venues/{id}/assistant-queries.

import { useEffect, useState } from 'react';
import { Radio, Users, WifiOff } from 'lucide-react';
import { apiPublic } from '../../lib/api';
import { LoadingState, ErrorState } from '../StateView';
import { roleLabel, languageLabel } from '../roles';
import type { IncomingMessage } from '../../lib/api';

type EmployeeOption = { id: number; name: string; role: string; language: string };

export type FeedEntry = IncomingMessage & { id: string; at: number };

const ONLINE_WINDOW_MS = 5 * 60_000;

export default function ShiftTab({
  venueId,
  feed,
  wsStatus,
}: {
  venueId: number;
  feed: FeedEntry[];
  wsStatus: 'connecting' | 'online' | 'lost';
}) {
  const [status, setStatus] = useState<'loading' | 'error' | 'ready'>('loading');
  const [roster, setRoster] = useState<EmployeeOption[]>([]);

  const load = () => {
    setStatus('loading');
    apiPublic<EmployeeOption[]>(`/auth/venues/${venueId}/employees`)
      .then((list) => {
        setRoster(list);
        setStatus('ready');
      })
      .catch(() => setStatus('error'));
  };

  useEffect(load, [venueId]);

  const now = useNowTicker();
  const lastSeen = new Map<number, number>();
  for (const item of feed) {
    if (!lastSeen.has(item.from_id) || lastSeen.get(item.from_id)! < item.at) {
      lastSeen.set(item.from_id, item.at);
    }
  }

  if (status === 'loading') return <LoadingState label="Загружаю смену…" />;
  if (status === 'error')
    return <ErrorState message="Не удалось загрузить список сотрудников." onRetry={load} />;

  return (
    <div className="flex h-full flex-col gap-6 overflow-y-auto px-5 pt-4 pb-6">
      {wsStatus === 'lost' && (
        <div className="flex items-center gap-2 rounded-xl bg-amber-500/15 px-4 py-3 text-sm font-medium text-amber-200">
          <WifiOff size={18} /> Нет связи с рацией — лента не обновляется, переподключаюсь…
        </div>
      )}

      <section>
        <h3 className="mb-1 flex items-center gap-2 text-sm font-bold uppercase tracking-widest text-stone-500">
          <Users size={16} /> Сотрудники точки
        </h3>
        <p className="mb-3 text-xs text-stone-500">
          «В эфире» — говорил по рации последние 5 минут, а не то же самое, что реально на смене.
        </p>
        <ul className="space-y-2">
          {roster.length === 0 && (
            <li className="text-base text-stone-500">Список пуст — добавьте сотрудников точки.</li>
          )}
          {roster.map((e) => {
            const seenAt = lastSeen.get(e.id);
            const isOnAir = seenAt !== undefined && now - seenAt < ONLINE_WINDOW_MS;
            return (
              <li
                key={e.id}
                className="flex items-center justify-between rounded-2xl bg-stone-900 px-5 py-3.5"
              >
                <span className="min-w-0">
                  <span className="block truncate text-lg font-semibold text-stone-50">{e.name}</span>
                  <span className="block text-sm text-stone-400">
                    {roleLabel(e.role)} · {languageLabel(e.language)}
                  </span>
                </span>
                <span
                  className={`flex shrink-0 items-center gap-1.5 rounded-full px-3 py-1 text-xs font-bold uppercase tracking-wide ${
                    isOnAir ? 'bg-emerald-500/15 text-emerald-300' : 'bg-stone-800 text-stone-500'
                  }`}
                >
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${isOnAir ? 'bg-emerald-400 animate-pulse' : 'bg-stone-600'}`}
                  />
                  {isOnAir ? 'В эфире' : 'Не в эфире'}
                </span>
              </li>
            );
          })}
        </ul>
      </section>

      <section className="flex-1">
        <h3 className="mb-1 flex items-center gap-2 text-sm font-bold uppercase tracking-widest text-stone-500">
          <Radio size={16} /> Лента реплик
        </h3>
        <p className="mb-3 text-xs text-stone-500">
          Реплики рации с момента открытия кабинета. История вопросов к ассистенту пока не отдаётся бэкендом.
        </p>
        {feed.length === 0 ? (
          <p className="py-6 text-center text-base text-stone-500">
            Пока тихо — сообщения появятся, когда кто-то заговорит по рации.
          </p>
        ) : (
          <ul className="space-y-2.5">
            {feed.map((item) => (
              <li key={item.id} className="rounded-2xl bg-stone-900 px-5 py-3.5">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-stone-300">{item.from_name}</span>
                  <span className="text-xs text-stone-500">{formatTime(item.at)}</span>
                </div>
                <p className="mt-1 text-lg leading-snug text-stone-50">{item.text}</p>
                {item.translation_failed && (
                  <p className="mt-1.5 text-sm font-medium text-amber-300">Перевод не сработал</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

function useNowTicker(): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), 15000);
    return () => window.clearInterval(t);
  }, []);
  return now;
}

function formatTime(at: number): string {
  return new Date(at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
}
