// Экран официанта. Всё подчинено одному: сказать и услышать, не глядя.
//
// Держать нажатой — говорить, отпустить — отправить. Так же, как рация, которой
// этот продукт заменяет. Кнопка занимает нижнюю половину экрана, потому что туда
// достаёт большой палец руки, в которой телефон, а вторая рука занята подносом.
//
// Кнопка на проводной гарнитуре шлёт медиа-клавиши, а не события страницы.
// Ловим их через mediaSession: официант жмёт кнопку на проводе, телефон остаётся
// в кармане. Это основной способ работы на пилоте, экран — запасной.

import { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, Loader2, Mic, Radio, WifiOff } from 'lucide-react';
import {
  clearSession,
  getSession,
  openCommsSocket,
  playAudio,
  sendVoice,
  type IncomingMessage,
  type VoiceResult,
} from '../lib/api';
import { startRecording, stopRecording } from '../lib/recorder';

type Phase = 'idle' | 'recording' | 'sending';

type FeedItem = {
  id: string;
  kind: 'answer' | 'incoming' | 'sent';
  title: string;
  text: string;
  warning?: string;
};

const DEGRADED_TEXT: Record<string, string> = {
  asr: 'Не расслышал',
  answer: 'Ассистент недоступен, связь работает',
  tts: 'Голос не пришёл — читайте текст',
};

export default function WaiterView() {
  const session = getSession();
  const [phase, setPhase] = useState<Phase>('idle');
  const [online, setOnline] = useState(false);
  const [feed, setFeed] = useState<FeedItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const phaseRef = useRef<Phase>('idle');

  phaseRef.current = phase;

  const push = useCallback((item: Omit<FeedItem, 'id'>) => {
    setFeed((current) => [{ ...item, id: crypto.randomUUID() }, ...current].slice(0, 12));
  }, []);

  // --- Канал рации -------------------------------------------------------
  useEffect(() => {
    let cancelled = false;
    let socket: WebSocket | null = null;
    let ping: number | undefined;
    let retry: number | undefined;

    const connect = async () => {
      try {
        socket = await openCommsSocket();
      } catch {
        // Вайфай чайханы моргает — пробуем снова, молча.
        retry = window.setTimeout(connect, 3000);
        return;
      }
      if (cancelled) {
        socket.close();
        return;
      }
      socketRef.current = socket;

      socket.onopen = () => {
        setOnline(true);
        // Подтверждаем, что на смене, чаще, чем истекает отметка присутствия.
        ping = window.setInterval(() => socket?.send('ping'), 20000);
      };
      socket.onmessage = (event) => {
        const message = JSON.parse(event.data) as IncomingMessage;
        push({
          kind: 'incoming',
          title: message.from_name,
          text: message.text,
          warning: message.translation_failed ? 'Перевод не сработал' : undefined,
        });
        if (message.audio_base64) void playAudio(message.audio_base64, message.mime_type);
      };
      socket.onclose = () => {
        setOnline(false);
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
  }, [push]);

  // --- Кнопка ------------------------------------------------------------
  const begin = useCallback(async () => {
    if (phaseRef.current !== 'idle') return;
    setError(null);
    try {
      await startRecording();
      setPhase('recording');
      navigator.vibrate?.(15);
    } catch {
      setError('Нет доступа к микрофону. Разрешите его в настройках браузера.');
    }
  }, []);

  const finish = useCallback(async () => {
    if (phaseRef.current !== 'recording') return;
    setPhase('sending');
    navigator.vibrate?.(10);
    try {
      const blob = await stopRecording();
      const result: VoiceResult = await sendVoice(blob);
      handleResult(result);
    } catch {
      setError('Не отправилось. Проверьте связь и повторите.');
    } finally {
      setPhase('idle');
    }
  }, []);

  const handleResult = (result: VoiceResult) => {
    if (result.intent === 'ignored') return;

    if (result.intent === 'send_group' || result.intent === 'send_person') {
      push({
        kind: 'sent',
        title: result.group ? `Передал: ${result.group}` : `Передал: ${result.person_name ?? ''}`,
        text: result.query_text,
        warning: result.delivered_to.length === 0 ? 'Никого нет на связи' : undefined,
      });
    } else {
      push({
        kind: 'answer',
        title: result.query_text || 'Ассистент',
        text: result.answer_text,
        warning: result.degraded ? DEGRADED_TEXT[result.degraded] : undefined,
      });
    }
    if (result.audio_base64) void playAudio(result.audio_base64, result.mime_type);
  };

  // Кнопка на проводной гарнитуре приходит как медиа-клавиша. Переключаем
  // запись по ней: нажал — говорит, нажал ещё раз — отправилось.
  useEffect(() => {
    if (!('mediaSession' in navigator)) return;
    const toggle = () => {
      if (phaseRef.current === 'recording') void finish();
      else void begin();
    };
    try {
      navigator.mediaSession.setActionHandler('play', toggle);
      navigator.mediaSession.setActionHandler('pause', toggle);
    } catch {
      // Браузер не отдаёт медиа-клавиши — работаем экранной кнопкой.
    }
    return () => {
      try {
        navigator.mediaSession.setActionHandler('play', null);
        navigator.mediaSession.setActionHandler('pause', null);
      } catch {
        /* уже снято */
      }
    };
  }, [begin, finish]);

  const label =
    phase === 'recording' ? 'Говорите' : phase === 'sending' ? 'Отправляю' : 'Держите и говорите';

  return (
    <div className="flex h-dvh flex-col bg-stone-950 text-stone-50">
      <header className="flex items-center justify-between px-5 py-4">
        <div>
          <p className="text-lg font-semibold leading-tight">{session?.name}</p>
          <p className="text-sm text-stone-400">{roleLabel(session?.role)}</p>
        </div>
        <div className="flex items-center gap-3">
          <span
            className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium ${
              online ? 'bg-emerald-500/15 text-emerald-300' : 'bg-amber-500/15 text-amber-300'
            }`}
          >
            {online ? <Radio size={16} /> : <WifiOff size={16} />}
            {online ? 'На смене' : 'Нет связи'}
          </span>
          <button
            onClick={() => {
              clearSession();
              location.reload();
            }}
            className="rounded-lg px-3 py-1.5 text-sm text-stone-400"
          >
            Выйти
          </button>
        </div>
      </header>

      {error && (
        <div className="mx-5 mb-3 flex items-start gap-2 rounded-xl bg-red-500/15 px-4 py-3 text-sm text-red-200">
          <AlertTriangle size={18} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <main className="min-h-0 flex-1 overflow-y-auto px-5 pb-4">
        {feed.length === 0 ? (
          <p className="pt-8 text-center text-base leading-relaxed text-stone-500">
            Спросите про блюдо или передайте на кухню.
            <br />
            «Онви, что в составе лагмана»
          </p>
        ) : (
          <ul className="space-y-3">
            {feed.map((item) => (
              <li
                key={item.id}
                className={`rounded-2xl px-4 py-3 ${
                  item.kind === 'incoming'
                    ? 'bg-sky-500/12 border border-sky-500/25'
                    : 'bg-stone-900'
                }`}
              >
                <p className="text-sm font-medium text-stone-400">{item.title}</p>
                <p className="mt-1 text-xl leading-snug">{item.text}</p>
                {item.warning && (
                  <p className="mt-2 text-sm text-amber-300">{item.warning}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </main>

      {/* Кнопка внизу: туда достаёт большой палец руки, держащей телефон. */}
      <div className="px-5 pb-8 pt-2">
        <button
          onPointerDown={(event) => {
            event.currentTarget.setPointerCapture(event.pointerId);
            void begin();
          }}
          onPointerUp={() => void finish()}
          onPointerCancel={() => void finish()}
          disabled={phase === 'sending'}
          style={{ touchAction: 'none' }}
          className={`flex h-44 w-full select-none flex-col items-center justify-center gap-3 rounded-3xl text-2xl font-semibold transition-transform duration-150 ease-out active:scale-[0.98] ${
            phase === 'recording'
              ? 'bg-red-500 text-white'
              : phase === 'sending'
                ? 'bg-stone-700 text-stone-300'
                : 'bg-emerald-500 text-stone-950'
          }`}
        >
          {phase === 'sending' ? (
            <Loader2 size={44} className="animate-spin" />
          ) : (
            <Mic size={44} />
          )}
          {label}
        </button>
      </div>
    </div>
  );
}

function roleLabel(role?: string): string {
  const labels: Record<string, string> = {
    waiter: 'Официант',
    kitchen: 'Кухня',
    bar: 'Бар',
    host: 'Хостес',
    manager: 'Управляющий',
  };
  return role ? (labels[role] ?? role) : '';
}
