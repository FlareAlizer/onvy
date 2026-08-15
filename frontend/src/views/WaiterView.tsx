// Экран официанта. Всё подчинено одному: сказать и услышать, не глядя.
//
// Держать нажатой — говорить, отпустить — отправить. Так же, как рация, которой
// этот продукт заменяет. Кнопка занимает нижнюю половину экрана, потому что туда
// достаёт большой палец руки, в которой телефон, а вторая рука занята подносом.
//
// Кнопка на проводной гарнитуре шлёт медиа-клавиши, а не события страницы.
// Ловим их через mediaSession: официант жмёт кнопку на проводе, телефон остаётся
// в кармане. Это основной способ работы на пилоте, экран — запасной.

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  AlertTriangle,
  ChevronDown,
  Ear,
  EarOff,
  Loader2,
  Lock,
  Mic,
  Radio,
  Send,
  Sparkles,
  Users,
  WifiOff,
} from 'lucide-react';
import {
  api,
  ApiError,
  getSession,
  logoutSession,
  playAudio,
  sendVoice,
  type VoiceResult,
} from '../lib/api';
import { проверитьВыход } from '../lib/audioOut';
import { useComms } from '../lib/comms';
import { startRecording, stopRecording, WakeListener } from '../lib/recorder';
import { ScreenAwake } from '../lib/screenlock';
import PersonPicker from '../components/PersonPicker';

// Кому уходит нажатие кнопки. Выбор пальцем нужен для случая, когда называть
// адресата вслух неудобно, но он не отменяет разбор речи: сказанное вслух
// («Азиз, подойди» / «кухня, два лагмана» / «Онви, что в лагмане») всегда сильнее.
//
// По умолчанию выбран ассистент — это самое частое действие в смене, вопрос по
// меню. Раньше по умолчанию стояло «всем», и любой вопрос уходил в рацию:
// до ассистента нельзя было добраться вообще.
type Группа = 'все' | 'кухня' | 'бар' | 'зал';

const ГРУППЫ: { key: Группа; label: string }[] = [
  { key: 'все', label: 'Всем' },
  { key: 'кухня', label: 'Кухне' },
  { key: 'бар', label: 'Бару' },
  { key: 'зал', label: 'Залу' },
];

type Адресат =
  | { kind: 'assistant' }
  | { kind: 'group'; group: Группа }
  | { kind: 'person'; id: number; name: string };

const АССИСТЕНТ: Адресат = { kind: 'assistant' };

function адресатLabel(адресат: Адресат): string {
  if (адресат.kind === 'assistant') return 'Ассистенту';
  if (адресат.kind === 'person') return адресат.name;
  return ГРУППЫ.find((g) => g.key === адресат.group)?.label ?? адресат.group;
}

type Phase = 'idle' | 'recording' | 'sending';

type FeedItem = {
  id: string;
  kind: 'answer' | 'incoming' | 'sent';
  title: string;
  text: string;
  warning?: string;
  /** Когда появилось — по нему свои реплики и входящие сливаются в одну ленту. */
  at: number;
};

// Метка сборки. Меняется руками при каждом выкате, который надо подтвердить на
// смене: по ней сразу видно, обновил телефон страницу или показывает вчерашнее.
const СБОРКА = '15.08-5';

const DEGRADED_TEXT: Record<string, string> = {
  asr: 'Не расслышал',
  answer: 'Ассистент недоступен, связь работает',
  tts: 'Голос не пришёл — читайте текст',
};

type Props = {
  /** Вернуться в кабинет — когда экран открыт из консоли сотрудника. */
  onExit?: () => void;
};

export default function WaiterView({ onExit }: Props = {}) {
  const session = getSession();
  const [phase, setPhase] = useState<Phase>('idle');
  // Канал рации держит App.tsx: он обязан пережить уход в другой раздел кабинета,
  // иначе официант молча выпадает со смены — см. lib/comms.tsx.
  const { status, feed: входящие } = useComms();
  const online = status === 'online';
  // Свои реплики — ответы ассистента и отправленное. Входящие сюда не кладём:
  // они приходят из провайдера и живут дольше этого экрана.
  const [собственные, setСобственные] = useState<FeedItem[]>([]);
  const [error, setError] = useState<string | null>(null);
  const phaseRef = useRef<Phase>('idle');

  // Микрофон открыт всю смену — переключателя нет.
  //
  // Официант стоит перед гостем с подносом. Любое действие в телефоне видно
  // гостю и выглядит несолидно, поэтому включать слушателя руками он не должен:
  // экран рации открыт — Онви слышит. Что при этом происходит с чужими
  // разговорами, решено на сервере: фраза без обращения выбрасывается целиком
  // и никуда не сохраняется (app/services/assistant_flow.py).
  const [wakeState, setWakeState] = useState<'idle' | 'speech' | 'sending'>('idle');
  const [микрофонНеДоступен, setМикрофонНеДоступен] = useState(false);
  const wakeListenerRef = useRef<WakeListener | null>(null);

  // Проверка звука в ухе. Нужна потому, что «ассистент не ответил» и «ответил,
  // но звук ушёл мимо гарнитуры» на смене выглядят одинаково — тишиной, — а по
  // логам сервера неразличимы вовсе: синтез отрабатывает в обоих случаях.
  const [звукИтог, setЗвукИтог] = useState<string | null>(null);
  const [звукИдёт, setЗвукИдёт] = useState(false);

  // Что произошло с последним ответом на самом телефоне.
  //
  // В базе видно только серверную половину, и она каждый раз в порядке: текст
  // распознан, ответ составлен, звук синтезирован. Вторая половина — доехал ли
  // звук до уха — целиком на устройстве, и оттуда до сих пор не было ни одного
  // факта. Поэтому строка показывается прямо на экране: официант читает её
  // вслух, и мы перестаём гадать.
  const [следЗвука, setСледЗвука] = useState<string[]>([]);

  const записатьСлед = useCallback((строка: string) => {
    const время = new Date().toLocaleTimeString('ru-RU', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
    setСледЗвука((было) => [`${время} ${строка}`, ...было].slice(0, 4));
  }, []);

  const проверитьЗвук = useCallback(async () => {
    setЗвукИдёт(true);
    setЗвукИтог(null);
    try {
      const итог = wakeListenerRef.current
        ? await wakeListenerRef.current.проверитьВыход()
        : await проверитьВыход();
      if (!итог.ok) {
        setЗвукИтог('Сигнал не проиграть. Коснитесь экрана и нажмите ещё раз.');
      } else if (итог.sampleRate > 0 && итог.sampleRate <= 16000) {
        // Телефон перевёл беспроводную гарнитуру в режим телефонного разговора:
        // микрофон в ней работает, а музыкальный канал на это время выключен.
        setЗвукИтог(
          `Гарнитура в режиме разговора (${итог.sampleRate} Гц) — ответы в неё не пойдут. ` +
            'Возьмите проводную или отключите Bluetooth.',
        );
      } else {
        setЗвукИтог(`Звук идёт (${итог.sampleRate} Гц). Не услышали — проверьте громкость.`);
      }
    } finally {
      setЗвукИдёт(false);
    }
  }, []);

  // Выбор адресата пальцем и отправка текстом — запасной путь для того же
  // случая, когда голосом неудобно (шум, не хочет говорить при госте).
  const [панельОткрыта, setПанельОткрыта] = useState(false);
  const [адресат, setАдресат] = useState<Адресат>(АССИСТЕНТ);
  const [текст, setТекст] = useState('');
  const [отправка, setОтправка] = useState(false);

  phaseRef.current = phase;

  // Адресат читается через ref теми же стабильными колбэками, что и кнопка:
  // объявлен здесь, а не рядом с кнопкой, потому что нужен ещё и постоянному
  // прослушиванию, которое собирается раньше кнопки ниже по файлу.
  const адресатRef = useRef<Адресат>(адресат);
  адресатRef.current = адресат;

  const push = useCallback((item: Omit<FeedItem, 'id' | 'at'>) => {
    setСобственные((current) =>
      [{ ...item, id: crypto.randomUUID(), at: Date.now() }, ...current].slice(0, 12),
    );
  }, []);

  // Кладёт результат в ленту. Отдельно от воспроизведения звука: у кнопки и у
  // постоянного прослушивания разные способы проиграть ответ (см. finish и
  // onWakeUtterance ниже), а лента одна на оба пути.
  const applyResult = useCallback(
    (result: VoiceResult) => {
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
    },
    [push],
  );

  // Путь кнопки и текстового ввода.
  //
  // Играем тем же AudioContext, что и постоянное прослушивание, а не отдельным
  // Audio-элементом. Элемент здесь молчал: `play()` вызывается уже после ответа
  // сервера, когда разрешение на автоплей от нажатия истекло, и уходит мимо
  // гарнитуры, пока та переключена в режим связи захватом микрофона. На живом
  // официанте это выглядело так: ответ на экране есть, в ухе тишина.
  const handleResult = useCallback(
    async (result: VoiceResult) => {
      applyResult(result);
      // Отброшенная фраза — это фон зала, а не ответ нам. Микрофон открыт всю
      // смену и шлёт на сервер всё подряд, поэтому таких ответов приходят
      // десятки: раньше каждый из них перетирал строку диагностики, и вместо
      // следа настоящего вопроса там оказывался последний посторонний разговор.
      if (result.intent === 'ignored') return;

      const слушатель = wakeListenerRef.current;
      const кб = result.audio_base64 ? Math.round((result.audio_base64.length * 3) / 4096) : 0;
      if (!result.audio_base64) {
        записатьСлед(`звука в ответе нет (${result.degraded ?? 'причина не указана'})`);
        return;
      }
      const сыграло = слушатель
        ? await слушатель.playMp3(result.audio_base64)
        : await playAudio(result.audio_base64, result.mime_type);
      const с = слушатель?.состояние();
      записатьСлед(
        `звук ${кб} КБ · играл: ${сыграло ? 'да' : 'НЕТ'}` +
          (с ? ` · ${с.sampleRate} Гц · ${с.state} · микрофон ${с.трекЖив ? 'жив' : 'МЁРТВ'}` : ' · общий выход'),
      );
      // Тишину нельзя оставлять без объяснения: официант читает её как «не
      // ответил» и переспрашивает, вместо того чтобы коснуться экрана.
      if (!сыграло) setError('Звук выключен — коснитесь экрана и спросите ещё раз.');
    },
    [applyResult, записатьСлед],
  );

  // Одна лента на экране: свои реплики и входящие из рации, новые сверху.
  const feed = useMemo<FeedItem[]>(
    () =>
      [
        ...собственные,
        ...входящие.map((m) => ({
          id: m.id,
          kind: 'incoming' as const,
          title: m.from_name,
          text: m.text,
          warning: m.translation_failed ? 'Перевод не сработал' : undefined,
          at: m.at,
        })),
      ]
        .sort((a, b) => b.at - a.at)
        .slice(0, 12),
    [собственные, входящие],
  );

  const отправитьТекстом = async () => {
    const сообщение = текст.trim();
    if (!сообщение) return;
    setError(null);
    setОтправка(true);
    try {
      // Вопрос ассистенту текстом — тот же ответ по меню, без микрофона:
      // в шумном зале и при госте говорить вслух неудобно.
      if (адресат.kind === 'assistant') {
        const ответ = await api<VoiceResult>('/assistant/ask', {
          method: 'POST',
          body: JSON.stringify({ text: сообщение }),
        });
        setТекст('');
        await handleResult(ответ);
        return;
      }
      const тело =
        адресат.kind === 'person'
          ? { text: сообщение, recipient_id: адресат.id }
          : { text: сообщение, group: адресат.group };
      const результат = await api<{ delivered_to: number[] }>('/comms/text', {
        method: 'POST',
        body: JSON.stringify(тело),
      });
      push({
        kind: 'sent',
        title: адресат.kind === 'person' ? `Лично: ${адресат.name}` : `Передал: ${адресатLabel(адресат)}`,
        text: сообщение,
        warning: результат.delivered_to.length === 0 ? 'Никого нет на связи' : undefined,
      });
      setТекст('');
    } catch {
      setError('Не отправилось. Проверьте связь.');
    } finally {
      setОтправка(false);
    }
  };

  // --- Постоянное прослушивание («Онви слушает») -------------------------
  //
  // Отправляем с always_on=true: без слова «Онви» в начале фразы сервер
  // вернёт intent «ignored» и ничего не сделает (require_wake_word в
  // app/domain/intents.py) — так фоновые разговоры зала не улетают ассистенту.
  const onWakeUtterance = useCallback(
    async (blob: Blob) => {
      const кому = адресатRef.current;
      try {
        const result: VoiceResult = await sendVoice(
          blob,
          true,
          кому.kind === 'assistant'
            ? undefined
            : кому.kind === 'person'
              ? { employeeId: кому.id }
              : { group: кому.group },
        );
        // Тот же путь, что у кнопки и текста: играем через AudioContext самого
        // слушателя (пока идёт playMp3, микрофон помечен занятым и не подхватит
        // голос ассистента из динамика) и оставляем след для диагностики.
        await handleResult(result);
      } catch (сбой) {
        // 429 — это не «связь плохая», а «зал шумит и мы выбрали бюджет минуты».
        // Раньше оба случая выглядели одинаково, и официант чинил вайфай вместо
        // того, чтобы выключить прослушивание или просто подождать.
        setError(
          сбой instanceof ApiError && сбой.status === 429
            ? 'Онви слушает слишком много шума — подождите минуту или выключите режим.'
            : сбой instanceof DOMException && сбой.name === 'AbortError'
              ? 'Сервер не ответил за двадцать секунд — проверьте вайфай и повторите.'
              : 'Онви не расслышал — проверьте связь.',
        );
      }
    },
    [handleResult],
  );

  // Занимаем место ДО await: getUserMedia и AudioContext на телефоне
  // раскачиваются сотни миллисекунд, и всё это время ref пустой. Из-за этого
  // «уже слушает» не срабатывало, и микрофон открывался дважды или оставался
  // открытым после ухода с экрана — индикатор записи горел до конца смены.
  // Ключ старта заодно отвечает на вопрос «этот запуск ещё нужен?»: если пока
  // мы ждали, режим выключили или ушли с экрана, ключ сменится, и свежий
  // слушатель гасится сразу, а не остаётся висеть.
  const wakeStartKeyRef = useRef(0);

  const startWakeListener = useCallback(async () => {
    if (wakeListenerRef.current || wakeStartKeyRef.current !== 0) return; // уже слушает или стартует
    const ключ = Date.now();
    wakeStartKeyRef.current = ключ;
    setError(null);
    try {
      const listener = new WakeListener(onWakeUtterance, setWakeState);
      await listener.start();
      if (wakeStartKeyRef.current !== ключ) {
        // Пока поднимались, режим успели выключить — этот микрофон уже не нужен.
        await listener.stop();
        return;
      }
      wakeListenerRef.current = listener;
    } catch {
      if (wakeStartKeyRef.current === ключ) {
        wakeStartKeyRef.current = 0;
        setМикрофонНеДоступен(true);
      }
    }
  }, [onWakeUtterance]);

  const stopWakeListener = useCallback(async () => {
    // Сбрасываем ключ первым: этим мы отменяем и тот запуск, который сейчас
    // висит на await и ещё не успел записаться в ref.
    wakeStartKeyRef.current = 0;
    const listener = wakeListenerRef.current;
    wakeListenerRef.current = null;
    setWakeState('idle');
    if (listener) await listener.stop();
  }, []);

  // Микрофон поднимается сам при открытии экрана: официанту не за чем следить.
  useEffect(() => {
    void startWakeListener();
  }, [startWakeListener]);

  // Экран не должен гаснуть, пока идёт смена.
  //
  // Телефон, погасив экран, усыпляет вкладку — звуковой контекст уходит в сон,
  // и Онви перестаёт слышать. Без единого сообщения: усыплённая вкладка не может
  // о себе сказать. Официант в это время говорит в мёртвый микрофон.
  useEffect(() => {
    const бодрость = new ScreenAwake();
    void бодрость.start();
    return () => void бодрость.stop();
  }, []);

  // Телефон всё равно могли заблокировать кнопкой или переключиться на другое
  // приложение. При возврате будим микрофон, а если дорожку забрала система —
  // поднимаем слушателя заново. Молча мёртвым он остаться не должен.
  useEffect(() => {
    const приВозврате = async () => {
      if (document.visibilityState !== 'visible') return;
      const слушатель = wakeListenerRef.current;
      if (!слушатель) {
        void startWakeListener();
        return;
      }
      if (!(await слушатель.оживить())) {
        await stopWakeListener();
        void startWakeListener();
      }
    };
    document.addEventListener('visibilitychange', приВозврате);
    return () => document.removeEventListener('visibilitychange', приВозврате);
  }, [startWakeListener, stopWakeListener]);

  // Сторож микрофона.
  //
  // Онви «отвечал немного и умирал»: слушатель молча переставал слышать, а
  // экран продолжал звать говорить. Умереть он может двумя способами, и оба не
  // сообщают о себе никак. Первый — застрявшая занятость: повисший запрос или
  // недоигравший ответ не снимают флаг, и каждая следующая фраза выбрасывается.
  // Второй — систему забрала звуковую дорожку (звонок, другое приложение,
  // переключение гарнитуры), и микрофон мёртв при живой вкладке.
  //
  // Проверка по visibilitychange это не ловит: официант с экрана не уходит.
  // Поэтому смотрим сами, раз в несколько секунд, всю смену.
  useEffect(() => {
    const сторож = window.setInterval(() => {
      void (async () => {
        const слушатель = wakeListenerRef.current;
        if (!слушатель) {
          void startWakeListener();
          return;
        }
        if (слушатель.разбудитьЕслиЗастрял()) {
          setError('Связь подвисла — Онви снова слушает. Повторите вопрос.');
          return;
        }
        if (!слушатель.жив() && !(await слушатель.оживить())) {
          await stopWakeListener();
          void startWakeListener();
        }
      })();
    }, 5000);
    return () => window.clearInterval(сторож);
  }, [startWakeListener, stopWakeListener]);

  // Закрыть микрофон постоянного прослушивания при уходе с экрана — иначе
  // индикатор записи в браузере горит и после того, как официант открыл кабинет.
  useEffect(() => {
    return () => {
      void stopWakeListener();
    };
  }, [stopWakeListener]);

  // --- Кнопка ------------------------------------------------------------
  const begin = useCallback(async () => {
    if (phaseRef.current !== 'idle') return;
    setError(null);
    // Постоянное прослушивание и кнопка не должны держать микрофон
    // одновременно: иначе это два открытых устройства сразу, а RMS-детектор
    // словил бы ту же фразу, что произносится в кнопку, и попытался бы
    // отправить её ещё раз после отпускания.
    //
    // Гасим безусловно, без «если уже слушает»: слушатель может быть ещё на
    // полпути — finish() запускает его сразу после отпускания кнопки, а
    // getUserMedia на телефоне поднимается сотни миллисекунд. Пока он в пути,
    // ref пустой, и проверка по ref пропускала бы его вперёд: официант жмёт
    // кнопку второй раз подряд (обычное дело на проводной гарнитуре) — и
    // микрофон открывается дважды. stopWakeListener сбрасывает ключ старта,
    // поэтому отменяется и тот запуск, который ещё не дошёл до ref.
    await stopWakeListener();
    try {
      await startRecording();
      setPhase('recording');
      navigator.vibrate?.(15);
    } catch {
      setError('Нет доступа к микрофону. Разрешите его в настройках браузера.');
      void startWakeListener();
    }
  }, [stopWakeListener, startWakeListener]);

  const finish = useCallback(async () => {
    if (phaseRef.current !== 'recording') return;
    setPhase('sending');
    navigator.vibrate?.(10);
    const кому = адресатRef.current;
    try {
      const blob = await stopRecording();
      // Ассистент выбран — получателя не навязываем, и сервер сам решает по фразе:
      // вопрос по меню он ответит сам, названного вслух коллегу найдёт и передаст.
      const result: VoiceResult = await sendVoice(
        blob,
        false,
        кому.kind === 'assistant'
          ? undefined
          : кому.kind === 'person'
            ? { employeeId: кому.id }
            : { group: кому.group },
      );
      // Кнопку отпускаем сразу, а ответ дослушиваем: пока он играет, микрофон
      // постоянного прослушивания поднимать нельзя — иначе Онви услышит свой
      // собственный ответ из динамика и ответит на него.
      setPhase('idle');
      await handleResult(result);
    } catch {
      setError('Не отправилось. Проверьте связь и повторите.');
    } finally {
      setPhase('idle');
      // Отпустили кнопку — если постоянное прослушивание было включено,
      // возвращаем его: begin() выключал микрофон только на время записи.
      void startWakeListener();
    }
  }, [handleResult, startWakeListener]);

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
            onClick={onExit ?? (() => void logoutSession())}
            className="rounded-lg px-3 py-1.5 text-sm text-stone-400"
          >
            {onExit ? 'В кабинет' : 'Выйти'}
          </button>
        </div>
      </header>

      {/* Кому уходит реплика — видно всегда, меняется одним касанием.
          Разворачивает список групп и коллег для точного адресата. */}
      <button
        onClick={() => setПанельОткрыта((v) => !v)}
        style={{ minHeight: 44 }}
        className="mx-5 mb-2 flex items-center justify-between gap-2 rounded-xl bg-stone-900 px-4 text-sm font-semibold text-stone-200"
      >
        <span className="flex items-center gap-2">
          {адресат.kind === 'assistant' ? (
            <Sparkles size={16} className="text-sky-400" />
          ) : адресат.kind === 'person' ? (
            <Lock size={16} className="text-emerald-400" />
          ) : (
            <Users size={16} className="text-stone-400" />
          )}
          Кому: {адресатLabel(адресат)}
        </span>
        <ChevronDown
          size={18}
          className={`transition-transform duration-150 ${панельОткрыта ? 'rotate-180' : ''}`}
        />
      </button>

      {/* Индикатор, а не кнопка: микрофон работает всю смену сам.
          Официант держит поднос и стоит перед гостем — ему не за чем следить и
          нечего включать. Строка нужна только чтобы он видел, что его слышат. */}
      <div
        className={`mx-5 mb-2 flex items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium ${
          микрофонНеДоступен ? 'bg-amber-500/15 text-amber-200' : 'bg-stone-900 text-stone-400'
        }`}
      >
        {микрофонНеДоступен ? <EarOff size={16} /> : (
          <Ear size={16} className={wakeState === 'speech' ? 'animate-pulse text-sky-300' : ''} />
        )}
        <span className="min-w-0 flex-1 truncate">
          {микрофонНеДоступен
            ? 'Нет доступа к микрофону — разрешите его в настройках браузера'
            : wakeState === 'speech'
              ? 'Слышу вас'
              : wakeState === 'sending'
                ? 'Секунду…'
                : 'Скажите «Онви» — или держите кнопку'}
        </span>
        <button
          type="button"
          onClick={() => void проверитьЗвук()}
          disabled={звукИдёт}
          style={{ minHeight: 32 }}
          className="shrink-0 rounded-lg bg-stone-800 px-3 text-xs font-semibold text-stone-300 disabled:text-stone-600"
        >
          {звукИдёт ? '…' : 'Звук'}
        </button>
      </div>

      {звукИтог && (
        <p className="mx-5 mb-2 rounded-xl bg-stone-900 px-4 py-2.5 text-xs leading-relaxed text-stone-300">
          {звукИтог}
        </p>
      )}

      {/* След последних ответов. Некрасиво и намеренно на виду: пока причина
          тишины не найдена, эти строки — единственный источник фактов с самого
          телефона. Держим четыре, а не одну: фоновая фраза больше их не
          перетирает, но и настоящих вопросов подряд бывает несколько.
          Убрать сразу, как только перестанет быть нужно. */}
      <div className="mx-5 mb-2 font-mono text-[11px] leading-relaxed text-stone-500">
        <p className="text-stone-600">сборка {СБОРКА}</p>
        {следЗвука.length === 0 ? (
          <p>ответов ещё не было</p>
        ) : (
          следЗвука.map((строка) => <p key={строка}>{строка}</p>)
        )}
      </div>

      {панельОткрыта && (
        <div className="mx-5 mb-2 rounded-2xl bg-stone-900/60 px-4 py-3">
          <button
            onClick={() => setАдресат(АССИСТЕНТ)}
            style={{ minHeight: 44 }}
            className={`flex w-full items-center gap-2 rounded-xl px-3 text-sm font-semibold transition-colors duration-150 ease-out ${
              адресат.kind === 'assistant'
                ? 'bg-sky-500 text-stone-950'
                : 'bg-stone-800 text-stone-300'
            }`}
          >
            <Sparkles size={16} />
            Ассистенту — состав, цены, аллергены
          </button>

          <p className="mt-3 text-xs font-medium text-stone-500">Или в рацию, отделу</p>
          <div className="mt-1 grid grid-cols-4 gap-2">
            {ГРУППЫ.map(({ key, label }) => (
              <button
                key={key}
                onClick={() => setАдресат({ kind: 'group', group: key })}
                style={{ minHeight: 44 }}
                className={`rounded-xl text-sm font-semibold transition-colors duration-150 ease-out ${
                  адресат.kind === 'group' && адресат.group === key
                    ? 'bg-emerald-500 text-stone-950'
                    : 'bg-stone-800 text-stone-300'
                }`}
              >
                {label}
              </button>
            ))}
          </div>

          <p className="mt-3 text-xs font-medium text-stone-500">Или лично</p>
          <div className="mt-1">
            <PersonPicker
              venueId={session?.venueId ?? 0}
              excludeId={session?.employeeId ?? 0}
              selectedId={адресат.kind === 'person' ? адресат.id : null}
              onSelect={(person) =>
                setАдресат(person ? { kind: 'person', id: person.id, name: person.name } : АССИСТЕНТ)
              }
            />
          </div>
          {адресат.kind === 'person' && (
            <p className="mt-1 flex items-center gap-1.5 text-xs text-emerald-300">
              <Lock size={12} />
              Лично — услышит только {адресат.name}, зал не услышит
            </p>
          )}

          {/* Главное правило продукта, и его надо знать наизусть: выбор здесь —
              только для случая, когда называть адресата вслух неудобно.
              Сказанное голосом всегда сильнее выбранного пальцем. */}
          <p className="mt-3 border-t border-stone-800 pt-3 text-xs leading-relaxed text-stone-500">
            Проще позвать голосом — микрофон слышит всю смену.{' '}
            <span className="text-stone-400">«Азиз, подойди»</span> уйдёт Азизу,{' '}
            <span className="text-stone-400">«Кухня, два лагмана»</span> — кухне,{' '}
            <span className="text-stone-400">«Онви, что в лагмане»</span> — ассистенту.
            Кого выбрали здесь — применится, когда держите кнопку или пишете текстом.
          </p>

          <div className="mt-3 flex gap-2">
            <input
              value={текст}
              onChange={(e) => setТекст(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && void отправитьТекстом()}
              placeholder={
                адресат.kind === 'assistant' ? 'Вопрос по меню' : 'Написать текстом'
              }
              className="min-w-0 flex-1 rounded-xl bg-stone-800 px-4 py-3 text-base outline-none ring-1 ring-stone-700 focus:ring-2 focus:ring-emerald-500"
            />
            <button
              onClick={() => void отправитьТекстом()}
              disabled={!текст.trim() || отправка}
              style={{ minHeight: 44, minWidth: 44 }}
              className="shrink-0 rounded-xl bg-stone-700 px-4 text-stone-200 disabled:text-stone-600"
            >
              <Send size={20} />
            </button>
          </div>
        </div>
      )}

      {/* Всегда на виду: официант не читает документацию, а кнопку внизу
          понимает и голосом, если просто назвать имя или группу. */}
      <p className="px-5 pb-2 text-xs leading-relaxed text-stone-500">
        Голосом можно сказать: «Азиз, подойди» или «кухня, два лагмана»
      </p>

      {error && (
        <div className="mx-5 mb-3 flex items-start gap-2 rounded-xl bg-red-500/15 px-4 py-3 text-sm text-red-200">
          <AlertTriangle size={18} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <main className="min-h-0 flex-1 overflow-y-auto px-5 pb-4">
        {feed.length === 0 ? (
          <p className="pt-8 text-center text-base leading-relaxed text-stone-500">
            Спросите про блюдо, позовите коллегу или передайте на кухню.
            <br />
            «Онви, что в составе лагмана» · «Азиз, подойди»
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
