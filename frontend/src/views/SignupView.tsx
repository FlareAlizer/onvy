// Регистрация заведения. Одна форма, а не мастер: чем меньше шагов между
// «хочу попробовать» и работающим кабинетом, тем больше людей доходит.
//
// Регистрируется только управляющий и сразу со своим заведением — он его
// владелец. Сотрудников он добавляет сам изнутри: самостоятельная регистрация
// в чужую чайхану открыла бы вход любому, кто знает её название.

import { useState, type FormEvent } from 'react';
import { AlertTriangle, ArrowLeft, Loader2, Store } from 'lucide-react';
import { ApiError, signupVenue } from '../lib/api';

type Props = {
  onBackToLogin: () => void;
};

export default function SignupView({ onBackToLogin }: Props) {
  const [venueName, setVenueName] = useState('');
  const [managerName, setManagerName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (submitting) return;
    setError(null);
    setSubmitting(true);
    try {
      await signupVenue({
        venue_name: venueName,
        manager_name: managerName,
        email,
        password,
      });
      location.reload();
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // Здесь, в отличие от формы входа, причину назвать нужно: человек
        // регистрируется и должен понять, что делать дальше.
        setError(err.message);
      } else if (err instanceof ApiError && err.status === 429) {
        setError('Слишком много попыток регистрации. Попробуйте позже.');
      } else {
        setError('Не получилось зарегистрироваться. Проверьте связь.');
      }
    } finally {
      setSubmitting(false);
    }
  };

  const disabled =
    submitting ||
    venueName.trim().length < 2 ||
    managerName.trim().length < 2 ||
    !email.trim() ||
    password.length < 8;

  const поле =
    'mt-1.5 w-full rounded-2xl bg-stone-900 px-4 py-4 text-lg outline-none ring-1 ring-stone-800 focus:ring-2 focus:ring-emerald-500';

  return (
    <div className="flex min-h-dvh items-center justify-center bg-stone-950 px-5 py-10 text-stone-50">
      <div className="w-full max-w-sm">
        <button
          onClick={onBackToLogin}
          className="mb-6 flex items-center gap-1.5 text-sm text-stone-400"
        >
          <ArrowLeft size={18} />
          Уже есть доступ
        </button>

        <p className="text-sm font-medium uppercase tracking-[0.2em] text-stone-500">Onvy</p>
        <h1 className="mt-2 text-3xl font-semibold">Подключить заведение</h1>
        <p className="mt-1 text-base text-stone-400">
          Сотрудников добавите сами — после регистрации
        </p>

        <form onSubmit={submit} className="mt-8 space-y-4">
          <label className="block">
            <span className="text-sm font-medium text-stone-400">Название заведения</span>
            <input
              value={venueName}
              onChange={(e) => setVenueName(e.target.value)}
              disabled={submitting}
              className={поле}
              placeholder="Чайхана Шарк"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-stone-400">Ваше имя</span>
            <input
              value={managerName}
              onChange={(e) => setManagerName(e.target.value)}
              disabled={submitting}
              autoComplete="name"
              className={поле}
              placeholder="Гульнара Садыкова"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-stone-400">Почта</span>
            <input
              type="email"
              inputMode="email"
              autoComplete="username"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              disabled={submitting}
              className={поле}
              placeholder="rop@chayhana.ru"
            />
          </label>

          <label className="block">
            <span className="text-sm font-medium text-stone-400">Пароль</span>
            <input
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              disabled={submitting}
              className={поле}
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
            {submitting ? <Loader2 size={22} className="animate-spin" /> : <Store size={22} />}
            Создать кабинет
          </button>
        </form>
      </div>
    </div>
  );
}
