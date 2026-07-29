// Рабочий экран управляющего с телефона. Главное — стоп-лист (spec S4), поэтому
// он первая вкладка и открывается по умолчанию. Нижняя навигация, а не боковая:
// на 360px это то, что достаёт большой палец, держащий телефон одной рукой.
//
// Как и WaiterView.tsx, экран самодостаточен: сам берёт сессию и сам решает,
// что делать при выходе — App.tsx ничего в него не прокидывает.

import { useEffect, useState } from 'react';
import {
  Ban,
  BarChart3,
  ChevronLeft,
  FileUp,
  LogOut,
  Mic,
  Radio,
  Users,
  WifiOff,
} from 'lucide-react';
import { clearSession, getSession, openCommsSocket, type IncomingMessage } from '../lib/api';
import StopListTab from '../components/manager/StopListTab';
import ShiftTab, { type FeedEntry } from '../components/manager/ShiftTab';
import MenuImportTab from '../components/manager/MenuImportTab';
import MetricsTab from '../components/manager/MetricsTab';
import TalkTab from '../components/manager/TalkTab';

type TabKey = 'stop' | 'talk' | 'shift' | 'menu' | 'metrics';

const TABS: { key: TabKey; label: string; icon: typeof Ban }[] = [
  { key: 'stop', label: 'Стоп-лист', icon: Ban },
  // Управляющий не только слышит смену, но и говорит с ней: по спеке §4 он
  // координирует зал, а без кнопки мог только слушать.
  { key: 'talk', label: 'Рация', icon: Mic },
  { key: 'shift', label: 'Смена', icon: Users },
  { key: 'menu', label: 'Меню', icon: FileUp },
  { key: 'metrics', label: 'Метрики', icon: BarChart3 },
];

type Props = {
  /** Вернуться в кабинет. Передаётся, когда экран открыт из консоли: он
   *  полноэкранный (h-dvh) и живёт ВНЕ прокручиваемой страницы кабинета —
   *  внутри неё вложенная высота вьюпорта ломала вёрстку на телефоне. */
  onExit?: () => void;
};

export default function ManagerView({ onExit }: Props = {}) {
  const session = getSession();
  const [tab, setTab] = useState<TabKey>('stop');
  const [feed, setFeed] = useState<FeedEntry[]>([]);
  const [wsStatus, setWsStatus] = useState<'connecting' | 'online' | 'lost'>('connecting');

  // Один канал рации на весь кабинет — управляющий "слышит всё" (spec §4),
  // и лента реплик во вкладке "Смена" должна жить, даже когда открыта другая вкладка.
  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;
    let ping: number | undefined;
    let retry: number | undefined;

    const connect = async () => {
      try {
        socket = await openCommsSocket();
      } catch {
        retry = window.setTimeout(connect, 3000);
        return;
      }
      if (cancelled) {
        socket.close();
        return;
      }
      socket.onopen = () => {
        setWsStatus('online');
        ping = window.setInterval(() => socket?.send('ping'), 20000);
      };
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data) as IncomingMessage;
        setFeed((cur) => [{ ...message, id: crypto.randomUUID(), at: Date.now() }, ...cur].slice(0, 50));
      };
      socket.onclose = () => {
        setWsStatus('lost');
        window.clearInterval(ping);
        if (!cancelled) retry = window.setTimeout(connect, 3000);
      };
    };

    void connect();
    return () => {
      cancelled = true;
      window.clearInterval(ping);
      window.clearTimeout(retry);
      socket?.close();
    };
  }, []);

  const logout = () => {
    clearSession();
    location.reload();
  };

  if (!session) return null; // App.tsx рендерит этот экран только при наличии сессии

  return (
    <div className="flex h-dvh w-full flex-col bg-stone-950 text-stone-50">
      <header className="flex shrink-0 items-center justify-between border-b border-stone-800 px-5 py-4">
        <div className="min-w-0">
          <p className="truncate text-lg font-semibold leading-tight">{session.name}</p>
          <p className="text-sm text-stone-400">Управляющий</p>
        </div>
        <div className="flex items-center gap-3">
          <ConnBadge status={wsStatus} />
          <button
            onClick={onExit ?? logout}
            aria-label={onExit ? 'В кабинет' : 'Выйти'}
            className="rounded-xl p-2.5 text-stone-400 transition-colors duration-150 ease-out active:text-stone-100"
          >
            {onExit ? <ChevronLeft size={22} /> : <LogOut size={22} />}
          </button>
        </div>
      </header>

      <main className="min-h-0 flex-1 overflow-hidden">
        {tab === 'stop' && <StopListTab onGoToMenu={() => setTab('menu')} />}
        {tab === 'talk' && <TalkTab />}
        {tab === 'shift' && <ShiftTab venueId={session.venueId} feed={feed} wsStatus={wsStatus} />}
        {tab === 'menu' && <MenuImportTab />}
        {tab === 'metrics' && <MetricsTab />}
      </main>

      <nav className="grid shrink-0 grid-cols-5 border-t border-stone-800 bg-stone-950 pb-[env(safe-area-inset-bottom)]">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex flex-col items-center gap-1 py-3 text-xs font-semibold transition-colors duration-150 ease-out ${
              tab === key ? 'text-emerald-400' : 'text-stone-500'
            }`}
          >
            <Icon size={22} />
            {label}
          </button>
        ))}
      </nav>
    </div>
  );
}

function ConnBadge({ status }: { status: 'connecting' | 'online' | 'lost' }) {
  return (
    <span
      className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium ${
        status === 'online'
          ? 'bg-emerald-500/15 text-emerald-300'
          : status === 'lost'
            ? 'bg-amber-500/15 text-amber-300'
            : 'bg-stone-800 text-stone-400'
      }`}
    >
      {status === 'online' ? <Radio size={16} /> : <WifiOff size={16} />}
      {status === 'online' ? 'На связи' : status === 'lost' ? 'Нет связи' : 'Подключаюсь…'}
    </span>
  );
}
