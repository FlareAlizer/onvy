/**
 * Единственный выход звука приложения.
 *
 * Раньше ответы ассистента и входящие реплики рации играл свежий
 * `new Audio(data:…).play()`. На телефоне это молча не работает по двум причинам
 * сразу, и обе не видны разработчику на десктопе:
 *
 * 1. Автоплей. Разрешение на звук даётся жестом пользователя и живёт считаные
 *    секунды. Ответ ассистента приходит ПОСЛЕ `await` — распознавание, поиск по
 *    меню и синтез занимают секунду и больше, — и к моменту `play()` разрешение
 *    уже истекло. Промис отклоняется, `.catch()` его глушил, официант видел
 *    текст и не слышал ничего.
 * 2. Маршрут. Пока микрофон захвачен через getUserMedia, гарнитура переключена
 *    в режим связи. Новый медиаэлемент уходит в мультимедийный выход — то есть
 *    мимо наушника официанта.
 *
 * AudioContext лишён обоих недостатков: его достаточно разбудить один раз любым
 * касанием экрана, дальше он играет без жеста и в тот же маршрут, куда идёт
 * захват микрофона. Поэтому голосовой путь («Онви, что в лагмане») звучал, а
 * кнопка и текстовый ввод — нет.
 *
 * Контекст будим на первом же касании и держим до конца смены.
 */

let ctx: AudioContext | null = null;
let разбужен = false;

function контекст(): AudioContext | null {
  if (ctx) return ctx;
  const Ctor = window.AudioContext ?? (window as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  if (!Ctor) return null;
  try {
    ctx = new Ctor();
    return ctx;
  } catch {
    return null;
  }
}

/**
 * Разбудить выход звука. Вызывается из обработчика жеста — только там браузер
 * разрешает `resume()`. Беззвучный буфер нужен старым Safari: одного resume ему
 * мало, контекст считается «немым», пока через него что-нибудь не проиграли.
 */
function разбудить(): void {
  const c = контекст();
  if (!c) return;
  void c.resume().catch(() => {});
  if (!разбужен) {
    try {
      const тишина = c.createBufferSource();
      тишина.buffer = c.createBuffer(1, 1, 22050);
      тишина.connect(c.destination);
      тишина.start(0);
      разбужен = true;
    } catch {
      /* не вышло — попробуем на следующем касании */
    }
  }
}

// Слушаем в фазе перехвата и не снимаем: экран официанта живёт всю смену, а
// контекст засыпает при сворачивании приложения — тогда следующее касание
// разбудит его снова.
if (typeof window !== 'undefined') {
  for (const событие of ['pointerdown', 'touchend', 'keydown'] as const) {
    window.addEventListener(событие, разбудить, { capture: true, passive: true });
  }
}

/** Что мы знаем про выход звука — для проверки на самом телефоне. */
export type ВыходЗвука = {
  ok: boolean;
  /** Частота дискретизации контекста. 8000/16000 — телефон переключил гарнитуру
   *  в режим телефонного разговора, и обычное воспроизведение в неё не идёт. */
  sampleRate: number;
  state: string;
};

/**
 * Короткий сигнал в тот же выход, куда играет ответ ассистента.
 *
 * Нужен, чтобы на смене отличать «ассистент не ответил» от «ответил, но звук
 * ушёл не в то ухо». По логам это неразличимо: сервер в обоих случаях
 * отработал одинаково, а разница целиком на устройстве.
 */
export async function сигналВВыход(c: AudioContext): Promise<boolean> {
  try {
    if (c.state === 'suspended') await c.resume();
    await new Promise<void>((resolve) => {
      const тон = c.createOscillator();
      const громкость = c.createGain();
      тон.frequency.value = 660;
      // Плавный вход и выход: щелчок в ухе на смене пугает сильнее сигнала.
      громкость.gain.setValueAtTime(0.0001, c.currentTime);
      громкость.gain.exponentialRampToValueAtTime(0.2, c.currentTime + 0.05);
      громкость.gain.exponentialRampToValueAtTime(0.0001, c.currentTime + 0.45);
      тон.connect(громкость);
      громкость.connect(c.destination);
      тон.onended = () => resolve();
      тон.start();
      тон.stop(c.currentTime + 0.5);
    });
    return true;
  } catch {
    return false;
  }
}

/** Проверить общий выход (когда микрофон не открыт — например, у управляющего). */
export async function проверитьВыход(): Promise<ВыходЗвука> {
  const c = контекст();
  if (!c) return { ok: false, sampleRate: 0, state: 'нет' };
  const ok = await сигналВВыход(c);
  return { ok, sampleRate: c.sampleRate, state: c.state };
}

function base64ВБайты(b64: string): Uint8Array {
  const строка = atob(b64);
  const байты = new Uint8Array(строка.length);
  for (let i = 0; i < строка.length; i += 1) байты[i] = строка.charCodeAt(i);
  return байты;
}

/** Запасной путь для окружений без AudioContext. */
function черезЭлемент(base64: string, mime: string): Promise<boolean> {
  return new Audio(`data:${mime};base64,${base64}`)
    .play()
    .then(() => true)
    .catch(() => false);
}

/**
 * Проиграть ответ целиком. Промис завершается, когда звук ДОСЛУШАН, а не когда
 * начал играть: постоянное прослушивание держит микрофон «занятым», пока ждёт
 * этот промис, иначе Онви услышит сам себя и ответит на свой же ответ.
 *
 * Возвращает false, если проиграть не удалось, — вызывающий обязан сказать об
 * этом человеку, а не промолчать: тишина неотличима от «ассистент не ответил».
 */
export async function playBase64(base64: string, mime = 'audio/mpeg'): Promise<boolean> {
  const c = контекст();
  if (!c) return черезЭлемент(base64, mime);
  try {
    if (c.state === 'suspended') await c.resume();
    const буфер = await c.decodeAudioData(base64ВБайты(base64).buffer as ArrayBuffer);
    await new Promise<void>((resolve) => {
      const источник = c.createBufferSource();
      источник.buffer = буфер;
      источник.connect(c.destination);
      источник.onended = () => resolve();
      источник.start();
    });
    return true;
  } catch {
    return черезЭлемент(base64, mime);
  }
}
