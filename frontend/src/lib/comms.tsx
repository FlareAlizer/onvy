// Канал рации живёт на уровне приложения, а не внутри экрана.
//
// Раньше сокет открывали два компонента — WaiterView и ManagerView — каждый в
// своём useEffect. Оба монтируются условно: кабинет показывает экран рации
// только на первой вкладке (`if (tab === 'live') return <ManagerView/>`), а на
// остальных возвращает обычную страницу. Значит переход в «Метрики» размонтировал
// компонент, cleanup закрывал сокет, сервер снимал отметку присутствия — и
// управляющий выпадал со смены, ничего не сделав. В логах это видно как
// «на связи» → через 8–15 секунд «ушёл со связи».
//
// Это противоречит спеке §4: управляющий слышит смену всегда, а не только пока
// смотрит в одну вкладку. Поэтому соединение поднято выше всей навигации —
// провайдер висит над кабинетом и переживает любую смену вкладок и разделов.
//
// Здесь же и звук. Экран официанта проигрывал входящие, кабинет управляющего —
// нет: он видел текст, но не слышал смену. Теперь входящие озвучиваются в одном
// месте для всех ролей — «слышит смену» из спеки означает именно слышит.

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { openCommsSocket, playAudio, type IncomingMessage } from './api';

/** Состояние канала: показывается значком в шапке обоих экранов. */
export type ConnStatus = 'connecting' | 'online' | 'lost';

/** Входящая реплика с отметкой времени получения — для ленты смены. */
export type FeedEntry = IncomingMessage & { id: string; at: number };

// Клиент подтверждает присутствие чаще, чем истекает отметка на сервере
// (ONLINE_TTL_SECONDS = 45 в app/services/presence.py).
const PING_MS = 20_000;
// Вайфай в чайхане моргает — переподключаемся молча и бесконечно.
const RETRY_MS = 3_000;
// Лента нужна для вкладки «Смена»; глубже полусотни реплик никто не смотрит.
const FEED_LIMIT = 50;

interface CommsValue {
  status: ConnStatus;
  /** Входящие реплики, новые сверху. Копится, пока открыт кабинет. */
  feed: FeedEntry[];
}

const CommsContext = createContext<CommsValue>({ status: 'connecting', feed: [] });

/**
 * Держит единственный сокет рации на всё приложение.
 *
 * Монтируется в App.tsx выше кабинета — только там, где сессия уже есть.
 */
export function CommsProvider({ children }: { children: ReactNode }) {
  const [status, setStatus] = useState<ConnStatus>('connecting');
  const [feed, setFeed] = useState<FeedEntry[]>([]);

  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;
    let ping: number | undefined;
    let retry: number | undefined;

    const connect = async () => {
      try {
        socket = await openCommsSocket();
      } catch {
        // Тикет не выдали (сеть моргнула, токен обновляется) — пробуем снова.
        retry = window.setTimeout(connect, RETRY_MS);
        return;
      }
      if (cancelled) {
        socket.close();
        return;
      }
      // Локальная ссылка: к моменту события `socket` уже может указывать на
      // следующее соединение после переподключения.
      const current = socket;

      current.onopen = () => setStatus('online');
      // Пинг ставим здесь, а не в onopen: в StrictMode эффект прогоняется
      // дважды, и таймер, созданный в обработчике, пережил бы свой сокет.
      ping = window.setInterval(() => {
        if (current.readyState === WebSocket.OPEN) current.send('ping');
      }, PING_MS);

      current.onmessage = (event) => {
        const message = JSON.parse(event.data) as IncomingMessage;
        setFeed((cur) =>
          [{ ...message, id: crypto.randomUUID(), at: Date.now() }, ...cur].slice(0, FEED_LIMIT),
        );
        if (message.audio_base64) void playAudio(message.audio_base64, message.mime_type);
      };

      current.onclose = () => {
        setStatus('lost');
        window.clearInterval(ping);
        if (!cancelled) retry = window.setTimeout(connect, RETRY_MS);
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

  const value = useMemo<CommsValue>(() => ({ status, feed }), [status, feed]);
  return <CommsContext.Provider value={value}>{children}</CommsContext.Provider>;
}

/** Состояние канала и лента входящих. Работает на любом экране кабинета. */
export function useComms(): CommsValue {
  return useContext(CommsContext);
}
