// Рация управляющего: сказать смене голосом, не выходя из кабинета.
//
// Отличие от экрана официанта: тому нужна одна кнопка на пол-экрана и ничего
// больше, а управляющему важно выбрать адресата — объявление всем, только кухне
// или только бару. Поэтому выбор группы сверху, кнопка снизу.
//
// Каждый слышит реплику на своём языке: перевод делает сервер по языку
// получателя, здесь ничего выбирать не нужно.

import { useCallback, useRef, useState } from 'react';
import { AlertTriangle, Lock, Loader2, Mic, Send } from 'lucide-react';
import { playAudio, sendVoice, api, getSession, type VoiceResult } from '../../lib/api';
import { startRecording, stopRecording } from '../../lib/recorder';
import PersonPicker from '../PersonPicker';

type Группа = 'все' | 'кухня' | 'бар' | 'зал';

const ГРУППЫ: { key: Группа; label: string }[] = [
  { key: 'все', label: 'Всем' },
  { key: 'кухня', label: 'Кухне' },
  { key: 'бар', label: 'Бару' },
  { key: 'зал', label: 'Залу' },
];

// Адресат текстовой реплики: либо группа смены, либо конкретный человек.
// Голосовую реплику всё равно маршрутизирует сервер по смыслу фразы — этот
// выбор относится только к отправке текстом и к тому, что видно на экране.
type Адресат = { kind: 'group'; group: Группа } | { kind: 'person'; id: number; name: string };

function адресатLabel(адресат: Адресат): string {
  if (адресат.kind === 'person') return адресат.name;
  return ГРУППЫ.find((g) => g.key === адресат.group)?.label ?? адресат.group;
}

type Phase = 'idle' | 'recording' | 'sending';

type Сказанное = {
  id: string;
  text: string;
  адресат: string;
  услышали: number;
  warning?: string;
};

export default function TalkTab() {
  const session = getSession();
  const [адресат, setАдресат] = useState<Адресат>({ kind: 'group', group: 'все' });
  const [phase, setPhase] = useState<Phase>('idle');
  const [текст, setТекст] = useState('');
  const [история, setИстория] = useState<Сказанное[]>([]);
  const [error, setError] = useState<string | null>(null);
  const phaseRef = useRef<Phase>('idle');
  phaseRef.current = phase;

  const запомнить = useCallback((item: Omit<Сказанное, 'id'>) => {
    setИстория((current) => [{ ...item, id: crypto.randomUUID() }, ...current].slice(0, 10));
  }, []);

  const начать = useCallback(async () => {
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

  const закончить = useCallback(async () => {
    if (phaseRef.current !== 'recording') return;
    setPhase('sending');
    try {
      const blob = await stopRecording();
      const result: VoiceResult = await sendVoice(blob, false, {
        // Передаём выбранного на экране адресата: сервер применит его только
        // если в самой фразе обращения не было.
        ...(адресат.kind === 'person'
          ? { employeeId: адресат.id }
          : { group: адресат.group }),
      });
      // Голосом управляющий может и спросить ассистента, и передать смене —
      // сервер разбирает это сам по фразе, как и у официанта.
      запомнить({
        text: result.query_text || result.answer_text,
        адресат:
          result.group ?? result.person_name ?? (result.intent === 'ask' ? 'Ассистент' : '—'),
        услышали: result.delivered_to.length,
        warning:
          result.intent !== 'ask' && result.delivered_to.length === 0
            ? 'Никого нет на связи'
            : undefined,
      });
      if (result.audio_base64) void playAudio(result.audio_base64, result.mime_type);
    } catch {
      setError('Не отправилось. Проверьте связь.');
    } finally {
      setPhase('idle');
    }
  }, [запомнить]);

  const отправитьТекстом = async () => {
    const сообщение = текст.trim();
    if (!сообщение) return;
    setError(null);
    setPhase('sending');
    try {
      const тело =
        адресат.kind === 'person'
          ? { text: сообщение, recipient_id: адресат.id }
          : { text: сообщение, group: адресат.group };
      const результат = await api<{ delivered_to: number[] }>('/comms/text', {
        method: 'POST',
        body: JSON.stringify(тело),
      });
      запомнить({
        text: сообщение,
        адресат: адресатLabel(адресат),
        услышали: результат.delivered_to.length,
        warning:
          результат.delivered_to.length === 0
            ? адресат.kind === 'person'
              ? 'Не на связи'
              : 'Никого нет на связи'
            : undefined,
      });
      setТекст('');
    } catch {
      setError('Не отправилось. Проверьте связь.');
    } finally {
      setPhase('idle');
    }
  };

  return (
    <div className="flex h-full flex-col text-stone-50">
      <div className="shrink-0 px-5 pt-4">
        <p className="text-sm font-medium text-stone-400">Кому передать</p>
        <div className="mt-2 grid grid-cols-4 gap-2">
          {ГРУППЫ.map(({ key, label }) => (
            <button
              key={key}
              onClick={() => setАдресат({ kind: 'group', group: key })}
              style={{ minHeight: 44 }}
              className={`rounded-xl text-sm font-semibold transition-colors duration-150 ease-out ${
                адресат.kind === 'group' && адресат.group === key
                  ? 'bg-emerald-500 text-stone-950'
                  : 'bg-stone-900 text-stone-300'
              }`}
            >
              {label}
            </button>
          ))}
        </div>

        {/* Или конкретный человек — один на один, остальная смена не слышит. */}
        <p className="mt-3 text-sm font-medium text-stone-400">Или лично</p>
        <div className="mt-1">
          <PersonPicker
            venueId={session?.venueId ?? 0}
            excludeId={session?.employeeId ?? 0}
            selectedId={адресат.kind === 'person' ? адресат.id : null}
            onSelect={(person) =>
              setАдресат(
                person ? { kind: 'person', id: person.id, name: person.name } : { kind: 'group', group: 'все' },
              )
            }
          />
        </div>
        {адресат.kind === 'person' && (
          <p className="mt-1 flex items-center gap-1.5 text-sm text-emerald-300">
            <Lock size={14} />
            Личное — услышит только {адресат.name}, смена не услышит
          </p>
        )}

        {/* Текстом — когда в зале шумно или говорить неловко. Получатель всё
            равно слышит голосом: он в наушнике и в телефон не смотрит. */}
        <div className="mt-3 flex gap-2">
          <input
            value={текст}
            onChange={(e) => setТекст(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && void отправитьТекстом()}
            placeholder="Или напишите текстом"
            className="min-w-0 flex-1 rounded-xl bg-stone-900 px-4 py-3 text-base outline-none ring-1 ring-stone-800 focus:ring-2 focus:ring-emerald-500"
          />
          <button
            onClick={() => void отправитьТекстом()}
            disabled={!текст.trim() || phase === 'sending'}
            className="shrink-0 rounded-xl bg-stone-800 px-4 text-stone-200 disabled:text-stone-600"
          >
            <Send size={20} />
          </button>
        </div>
      </div>

      {error && (
        <div className="mx-5 mt-3 flex items-start gap-2 rounded-xl bg-red-500/15 px-4 py-3 text-sm text-red-200">
          <AlertTriangle size={18} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-3">
        {история.length === 0 ? (
          <p className="pt-6 text-center text-base leading-relaxed text-stone-500">
            Держите кнопку и говорите.
            <br />
            Каждый услышит на своём языке.
          </p>
        ) : (
          <ul className="space-y-2">
            {история.map((item) => (
              <li key={item.id} className="rounded-2xl bg-stone-900 px-4 py-3">
                <p className="text-sm text-stone-400">
                  {item.адресат}
                  {item.услышали > 0 && ` · слышали ${item.услышали}`}
                </p>
                <p className="mt-1 text-lg leading-snug">{item.text}</p>
                {item.warning && (
                  <p className="mt-1.5 text-sm text-amber-300">{item.warning}</p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="shrink-0 px-5 pb-6 pt-2">
        <button
          onPointerDown={(event) => {
            event.currentTarget.setPointerCapture(event.pointerId);
            void начать();
          }}
          onPointerUp={() => void закончить()}
          onPointerCancel={() => void закончить()}
          disabled={phase === 'sending'}
          style={{ touchAction: 'none' }}
          className={`flex h-32 w-full select-none flex-col items-center justify-center gap-2 rounded-3xl text-xl font-semibold transition-transform duration-150 ease-out active:scale-[0.98] ${
            phase === 'recording'
              ? 'bg-red-500 text-white'
              : phase === 'sending'
                ? 'bg-stone-700 text-stone-300'
                : 'bg-emerald-500 text-stone-950'
          }`}
        >
          {phase === 'sending' ? (
            <Loader2 size={36} className="animate-spin" />
          ) : (
            <Mic size={36} />
          )}
          {phase === 'recording' ? 'Говорите' : phase === 'sending' ? 'Отправляю' : 'Держите и говорите'}
        </button>
      </div>
    </div>
  );
}
