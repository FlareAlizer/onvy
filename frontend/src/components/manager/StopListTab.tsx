// Стоп-лист управляющего (spec S4): поставить позицию в стоп должно занимать
// секунды. Вся строка — цель нажатия, реакция мгновенная и оптимистичная,
// без модалок и подтверждений. Ошибка сети откатывает переключатель назад
// и показывает короткую полоску сверху — не всплывающее окно.

import { useCallback, useEffect, useRef, useState } from 'react';
import { Ban, FileUp, Search } from 'lucide-react';
import { api, getSession } from '../../lib/api';
import { LoadingState, ErrorState, EmptyState } from '../StateView';
import { Toggle } from '../Toggle';

type MenuItem = {
  id: number;
  name: string;
  category: string | null;
  price: string | number;
};

type StopEntry = { menu_item_id: number };

type LoadStatus = 'loading' | 'error' | 'ready';

const POLL_MS = 5000;
const NO_CATEGORY = 'Без категории';

export default function StopListTab({ onGoToMenu }: { onGoToMenu: () => void }) {
  const venueId = getSession()?.venueId;
  const [status, setStatus] = useState<LoadStatus>('loading');
  const [items, setItems] = useState<MenuItem[]>([]);
  const [stopped, setStopped] = useState<Set<number>>(new Set());
  const [query, setQuery] = useState('');
  const [banner, setBanner] = useState<string | null>(null);
  const bannerTimer = useRef<number | undefined>(undefined);

  const showBanner = (message: string) => {
    setBanner(message);
    window.clearTimeout(bannerTimer.current);
    bannerTimer.current = window.setTimeout(() => setBanner(null), 4000);
  };

  const loadAll = useCallback(() => {
    if (!venueId) return;
    setStatus('loading');
    Promise.all([
      api<MenuItem[]>(`/venues/${venueId}/menu`),
      api<StopEntry[]>(`/venues/${venueId}/stop-list`),
    ])
      .then(([menu, stops]) => {
        setItems(menu);
        setStopped(new Set(stops.map((s) => s.menu_item_id)));
        setStatus('ready');
      })
      .catch(() => setStatus('error'));
  }, [venueId]);

  useEffect(loadAll, [loadAll]);

  // Другой управляющий мог поменять стоп-лист со своего телефона — фоновый
  // опрос без мигания загрузкой (S4 требует, чтобы изменение было видно всем).
  useEffect(() => {
    if (!venueId) return;
    const t = window.setInterval(() => {
      api<StopEntry[]>(`/venues/${venueId}/stop-list`)
        .then((stops) => setStopped(new Set(stops.map((s) => s.menu_item_id))))
        .catch(() => {});
    }, POLL_MS);
    return () => window.clearInterval(t);
  }, [venueId]);

  const toggle = async (item: MenuItem) => {
    if (!venueId) return;
    const wasStopped = stopped.has(item.id);
    setStopped((cur) => {
      const next = new Set(cur);
      wasStopped ? next.delete(item.id) : next.add(item.id);
      return next;
    });
    try {
      if (wasStopped) {
        await api(`/venues/${venueId}/stop-list/${item.id}/unset`, { method: 'POST' });
      } else {
        await api(`/venues/${venueId}/stop-list/${item.id}/set`, {
          method: 'POST',
          body: JSON.stringify({}),
        });
      }
    } catch {
      setStopped((cur) => {
        const next = new Set(cur);
        wasStopped ? next.add(item.id) : next.delete(item.id);
        return next;
      });
      showBanner('Не получилось изменить стоп-лист. Проверьте связь и попробуйте снова.');
    }
  };

  if (status === 'loading') return <LoadingState label="Загружаю меню и стоп-лист…" />;
  if (status === 'error')
    return (
      <ErrorState
        message="Не удалось загрузить меню. Проверьте вайфай и попробуйте ещё раз."
        onRetry={loadAll}
      />
    );

  if (items.length === 0) {
    return (
      <EmptyState
        icon={<Ban size={26} />}
        title="Меню ещё не загружено"
        description="Стоп-лист работает поверх меню точки — сначала импортируйте позиции из CSV."
        action={
          <button
            onClick={onGoToMenu}
            className="mt-2 flex items-center gap-2 rounded-2xl bg-stone-50 px-6 py-3 text-base font-semibold text-stone-950 transition-transform duration-150 ease-out active:scale-[0.97]"
          >
            <FileUp size={20} /> Импортировать меню
          </button>
        }
      />
    );
  }

  const filtered = items.filter((i) => i.name.toLowerCase().includes(query.trim().toLowerCase()));
  const groups = groupByCategory(filtered);

  return (
    <div className="flex h-full flex-col px-5 pt-4">
      {banner && (
        <div className="mb-3 rounded-xl bg-amber-500/15 px-4 py-3 text-sm font-medium text-amber-200">
          {banner}
        </div>
      )}

      <div className="mb-4 flex items-center gap-2 rounded-2xl bg-stone-900 px-4 py-3">
        <Search size={20} className="shrink-0 text-stone-500" />
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Найти блюдо"
          className="w-full bg-transparent text-lg text-stone-50 placeholder-stone-500 outline-none"
        />
      </div>

      <p className="mb-3 text-sm font-medium text-stone-400">
        В стопе: {stopped.size} из {items.length}
      </p>

      <div className="flex-1 space-y-6 overflow-y-auto pb-4">
        {groups.map(([category, rows]) => (
          <section key={category}>
            <h3 className="mb-2 text-xs font-bold uppercase tracking-widest text-stone-500">
              {category}
            </h3>
            <ul className="space-y-2.5">
              {rows.map((item) => {
                const isStopped = stopped.has(item.id);
                return (
                  <li key={item.id}>
                    <button
                      onClick={() => toggle(item)}
                      className={`flex w-full items-center gap-4 rounded-2xl border px-5 py-4 text-left transition-transform duration-150 ease-out active:scale-[0.98] ${
                        isStopped
                          ? 'border-red-500/40 bg-red-500/10'
                          : 'border-transparent bg-stone-900'
                      }`}
                    >
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-xl font-semibold text-stone-50">
                          {item.name}
                        </span>
                        <span className="mt-0.5 flex items-center gap-2 text-sm">
                          <span className="text-stone-400">{formatPrice(item.price)}</span>
                          {isStopped && (
                            <span className="font-bold uppercase tracking-wide text-red-400">
                              Стоп
                            </span>
                          )}
                        </span>
                      </span>
                      <Toggle checked={isStopped} />
                    </button>
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
        {filtered.length === 0 && (
          <p className="pt-8 text-center text-base text-stone-500">Ничего не нашли по «{query}»</p>
        )}
      </div>
    </div>
  );
}

function formatPrice(price: string | number): string {
  const n = Number(price);
  return Number.isFinite(n) ? `${n.toLocaleString('ru-RU')} ₽` : '—';
}

function groupByCategory(items: MenuItem[]): [string, MenuItem[]][] {
  const map = new Map<string, MenuItem[]>();
  for (const item of items) {
    const key = item.category?.trim() || NO_CATEGORY;
    const list = map.get(key);
    if (list) list.push(item);
    else map.set(key, [item]);
  }
  return [...map.entries()].sort(([a], [b]) => {
    if (a === NO_CATEGORY) return 1;
    if (b === NO_CATEGORY) return -1;
    return a.localeCompare(b, 'ru');
  });
}
