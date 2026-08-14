// Кто сейчас на связи + лента последних реплик рации.
//
// «В эфире» — по данным сервера, а не по догадке.
//
// Раньше здесь стояла эвристика: в эфире тот, кто говорил по рации последние
// пять минут. Молчащий человек с включённым телефоном при этом числился вне
// сети — то есть управляющий видел пустую смену там, где все на месте, и не
// понимал, почему реплики никому не доходят. Теперь спрашиваем
// GET /venues/{id}/presence, как и задумывалось в этом комментарии.
//
// Вопросы к ассистенту (assistant_query) сюда тоже не попадают: наружу их
// сейчас никто не транслирует и не отдаёт историей — нужен либо WS-relay,
// либо GET /venues/{id}/assistant-queries.

import { useEffect, useState } from 'react';
import { Radio, Users, WifiOff } from 'lucide-react';
import { apiPublic, fetchPresence } from '../../lib/api';
import { LoadingState, ErrorState } from '../StateView';
import { roleLabel, languageLabel } from '../roles';
import type { ConnStatus, FeedEntry } from '../../lib/comms';

type EmployeeOption = { id: number; name: string; role: string; language: string };

// Как часто переспрашиваем, кто на связи. Отметка присутствия на сервере живёт
// 45 секунд, поэтому десяти секунд хватает, чтобы уход со смены был заметен
// почти сразу и при этом не долбить сервер на каждой отрисовке.
const PRESENCE_POLL_MS = 10_000;

export default function ShiftTab({
  venueId,
  feed,
  wsStatus,
}: {
  venueId: number;
  feed: FeedEntry[];
  wsStatus: ConnStatus;
}) {
  const [status, setStatus] = useState<'loading' | 'error' | 'ready'>('loading');
  const [roster, setRoster] = useState<EmployeeOption[]>([]);
  const [вЭфире, setВЭфире] = useState<Set<number>>(new Set());

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

  // Присутствие переспрашиваем по таймеру: сокет знает только про себя, а
  // остальная смена подключается и отваливается независимо от этого экрана.
  useEffect(() => {
    let отменено = false;
    const обновить = () => {
      fetchPresence(venueId)
        .then((p) => {
          if (!отменено) setВЭфире(new Set(p.online_employee_ids));
        })
        .catch(() => {
          // Сеть моргнула — оставляем прошлый список, он честнее пустого.
        });
    };
    обновить();
    const таймер = window.setInterval(обновить, PRESENCE_POLL_MS);
    return () => {
      отменено = true;
      window.clearInterval(таймер);
    };
  }, [venueId]);

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
          «В эфире» — приложение открыто и телефон на связи прямо сейчас.
        </p>
        <ul className="space-y-2">
          {roster.length === 0 && (
            <li className="text-base text-stone-500">Список пуст — добавьте сотрудников точки.</li>
          )}
          {roster.map((e) => {
            const isOnAir = вЭфире.has(e.id);
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

function formatTime(at: number): string {
  return new Date(at).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' });
}
