// Вход по почте и паролю — основной способ. Быстрый вход по PIN остаётся
// второй кнопкой: официант в зале держит поднос одной рукой, и вводить там
// длинный пароль неудобно, а PIN — четыре цифры не глядя.

import { useState, type FormEvent } from 'react';
import { AlertTriangle, Loader2, LogIn, Smartphone } from 'lucide-react';
import { ApiError, loginWithEmail } from '../lib/api';

type Props = {
  /** Переключиться на быстрый вход по PIN. */
  onUsePin: () => void;
  /** Открыть регистрацию заведения. */
  onSignup: () => void;
};

export default function EmailLoginView({ onUsePin, onSignup }: Props) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [waitSeconds, setWaitSeconds] = useState(0);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      await loginWithEmail(email, password);
      // Сессия сохранена — перечитываем страницу, дальше App покажет кабинет.
      location.reload();
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setWaitSeconds(60);
        setError('Слишком много попыток. Подождите минуту.');
      } else if (err instanceof ApiError && err.status === 401) {
        // Намеренно не уточняем, что именно не так: подсказка «такой почты нет»
        // превратила бы форму входа в способ узнать, кто здесь работает.
        setError('Не подходит почта или пароль.');
      } else {
        setError('Не получилось войти. Проверьте связь и попробуйте ещё раз.');
      }
      setPassword('');
    } finally {
      setSubmitting(false);
    }
  };

  const disabled = submitting || waitSeconds > 0 || !email.trim() || password.length < 8;

  return (
    <div className="flex min-h-dvh items-center justify-center bg-stone-950 px-5 py-10 text-stone-50">
      <div className="w-full max-w-sm">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-stone-500">Onvy</p>
        <h1 className="mt-2 text-3xl font-semibold">Вход</h1>
        <p className="mt-1 text-base text-stone-400">Почта и пароль, которые выдал управляющий</p>

        <form onSubmit={submit} className="mt-8 space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-stone-400">Почта</span>
            <input
              type="email"
              inputMode="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={submitting}
              className="mt-1.5 w-full rounded-2xl bg-stone-900 px-4 py-4 text-lg outline-none ring-1 ring-stone-800 focus:ring-2 focus:ring-emerald-500"
              placeholder="rop@chayhana.ru"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-stone-400">Пароль</span>
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={submitting}
              className="mt-1.5 w-full rounded-2xl bg-stone-900 px-4 py-4 text-lg outline-none ring-1 ring-stone-800 focus:ring-2 focus:ring-emerald-500"
              placeholder="не короче 8 символов"
            />
          </label>

          {error && (
            <div className="flex items-start gap-2 rounded-xl bg-red-500/15 px-4 py-3 text-sm text-red-200">
              <AlertTriangle size={18} className="mt-0.5 shrink-0" />
              <span>{error}</span>
            </div>
          )}

          <button
            type="submit"
            disabled={disabled}
            className="flex w-full items-center justify-center gap-2 rounded-2xl bg-emerald-500 py-4 text-lg font-semibold text-stone-950 transition-transform duration-150 ease-out active:scale-[0.98] disabled:bg-stone-700 disabled:text-stone-400"
          >
            {submitting ? <Loader2 size={22} className="animate-spin" /> : <LogIn size={22} />}
            Войти
          </button>
        </form>

        <button
          onClick={onUsePin}
          className="mt-6 flex w-full items-center justify-center gap-2 rounded-2xl border border-stone-800 py-4 text-base font-medium text-stone-300"
        >
          <Smartphone size={20} />
          Быстрый вход по PIN
        </button>

        {/* Регистрация внизу и без нажима: заведение подключают один раз,
            а входят каждую смену — вход и должен быть главным на экране. */}
        <p className="mt-8 text-center text-sm text-stone-500">
          Нет доступа?{' '}
          <button onClick={onSignup} className="font-medium text-emerald-400 underline">
            Подключить заведение
          </button>
        </p>
      </div>
    </div>
  );
}
