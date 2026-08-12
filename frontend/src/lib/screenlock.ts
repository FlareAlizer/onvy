// Не дать телефону погасить экран, пока открыт экран рации.
//
// Почему это вообще нужно. Микрофон в браузере живёт, пока жива вкладка: как
// только телефон гасит экран, система усыпляет вкладку, AudioContext уходит в
// suspended, и Онви перестаёт слышать. Снаружи это выглядит как «работал и
// перестал» — без единого сообщения, потому что усыплённая вкладка не может
// даже сказать об этом.
//
// Что можно и чего нельзя. Держать экран включённым — можно, это Screen Wake
// Lock, он есть в Chrome на Android и в Safari с 16.4. Слушать микрофон при
// ПОГАШЕННОМ экране — веб-приложению нельзя: на iPhone захват звука
// прекращается при блокировке, на Android поведение зависит от прошивки и
// экономии энергии. Обещать это через браузер невозможно; для настоящей работы
// «в кармане с погашенным экраном» нужен обёрточный клиент, и это отдельное
// решение — см. docs/plan-pilot.md.
//
// Плата за удержание — заряд. Телефон на смене должен стоять на зарядке или
// висеть на повербанке, иначе он сядет быстрее, чем кончится смена.

type Блокировка = { release: () => Promise<void>; released: boolean } | null;

export class ScreenAwake {
  private lock: Блокировка = null;
  private активна = false;

  /** Поддерживается ли удержание экрана в этом браузере. */
  static доступно(): boolean {
    return typeof navigator !== 'undefined' && 'wakeLock' in navigator;
  }

  async start(): Promise<void> {
    this.активна = true;
    await this.запросить();
    // Система снимает удержание, когда вкладка уходит в фон, и НЕ возвращает
    // его сама при возврате. Без этого экран гаснет после первого же переключения
    // на другое приложение, и дальше рация тихо не слышит.
    document.addEventListener('visibilitychange', this.приВозврате);
  }

  async stop(): Promise<void> {
    this.активна = false;
    document.removeEventListener('visibilitychange', this.приВозврате);
    await this.освободить();
  }

  private приВозврате = () => {
    if (this.активна && document.visibilityState === 'visible') void this.запросить();
  };

  private async запросить(): Promise<void> {
    if (!ScreenAwake.доступно() || this.lock) return;
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      this.lock = await (navigator as any).wakeLock.request('screen');
    } catch {
      // Отказ — не повод ломать смену: экран просто погаснет как обычно.
      this.lock = null;
    }
  }

  private async освободить(): Promise<void> {
    const lock = this.lock;
    this.lock = null;
    try {
      if (lock && !lock.released) await lock.release();
    } catch {
      /* уже отпущен системой */
    }
  }
}
