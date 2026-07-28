// Вход в зале, не в офисе: сотрудник тыкает себя в списке точки и вводит
// четырёхзначный PIN на клавиатуре на весь низ экрана. Никакого мелкого поля
// ввода и никакой экранной клавиатуры телефона — см. specs/pilot-chaihana.md §6.
//
// Экран сам управляет своей сессией (как WaiterView.tsx управляет своей):
// после успешного входа сохраняет сессию и перечитывает страницу — App.tsx
// не нуждается в колбэке, просто перечитывает getSession() при следующем рендере.

import { useEffect, useRef, useState } from 'react';
import { ChevronLeft, RotateCcw, Users } from 'lucide-react';
import { apiPublic, saveSession, type Session } from '../lib/api';
import { PinPad } from '../components/PinPad';
import { LoadingState, ErrorState, EmptyState } from '../components/StateView';
import { roleLabel, languageLabel } from '../components/roles';

const VENUE_ID = Number(import.meta.env.VITE_VENUE_ID ?? 1);
const PIN_LENGTH = 4;

type EmployeeOption = {
  id: number;
  name: string;
  role: string;
  language: string;
};

type ListStatus = 'loading' | 'error' | 'empty' | 'ready';

export default function LoginView() {
  const [status, setStatus] = useState<ListStatus>('loading');
  const [employees, setEmployees] = useState<EmployeeOption[]>([]);
  const [selected, setSelected] = useState<EmployeeOption | null>(null);

  const loadEmployees = () => {
    setStatus('loading');
    apiPublic<EmployeeOption[]>(`/auth/venues/${VENUE_ID}/employees`)
      .then((list) => {
        setEmployees(list);
        setStatus(list.length ? 'ready' : 'empty');
      })
      .catch(() => setStatus('error'));
  };

  useEffect(loadEmployees, []);

  if (status === 'loading') {
    return (
      <Shell>
        <LoadingState label="Загружаю список сотрудников…" />
      </Shell>
    );
  }

  if (status === 'error') {
    return (
      <Shell>
        <ErrorState
          message="Не удалось загрузить список сотрудников. Проверьте вайфай и попробуйте ещё раз."
          onRetry={loadEmployees}
        />
      </Shell>
    );
  }

  if (status === 'empty') {
    return (
      <Shell>
        <EmptyState
          icon={<Users size={26} />}
          title="Сотрудников пока нет"
          description="Управляющий ещё не добавил сотрудников этой точки. Обратитесь к нему, чтобы попасть в список."
        />
      </Shell>
    );
  }

  return (
    <Shell>
      {selected ? (
        <PinStep employee={selected} onBack={() => setSelected(null)} />
      ) : (
        <PickStep employees={employees} onPick={setSelected} />
      )}
    </Shell>
  );
}

function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex h-dvh w-full flex-col bg-stone-950 text-stone-50">
      <header className="px-6 pt-8 pb-2">
        <span className="text-sm font-semibold uppercase tracking-widest text-stone-500">Onvy</span>
      </header>
      <div className="flex flex-1 flex-col px-6 pb-8">{children}</div>
    </div>
  );
}

/* ---------- Шаг 1: выбери себя ---------- */

function PickStep({
  employees,
  onPick,
}: {
  employees: EmployeeOption[];
  onPick: (e: EmployeeOption) => void;
}) {
  return (
    <div className="flex flex-1 flex-col">
      <h1 className="mb-1 text-2xl font-bold tracking-tight">Кто вы?</h1>
      <p className="mb-6 text-base text-stone-400">Выберите себя в списке смены</p>
      <ul className="flex-1 space-y-3 overflow-y-auto">
        {employees.map((e) => (
          <li key={e.id}>
            <button
              onClick={() => onPick(e)}
              className="flex w-full items-center gap-4 rounded-2xl bg-stone-900 px-5 py-4 text-left transition-transform duration-150 ease-out active:scale-[0.98] active:bg-stone-800"
            >
              <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-full bg-stone-800 text-lg font-bold text-stone-200">
                {initials(e.name)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-xl font-semibold text-stone-50">{e.name}</span>
                <span className="block text-sm text-stone-400">
                  {roleLabel(e.role)} · {languageLabel(e.language)}
                </span>
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function initials(name: string): string {
  const parts = name.trim().split(/\s+/);
  return (parts[0]?.[0] ?? '') + (parts[1]?.[0] ?? '');
}

/* ---------- Шаг 2: PIN ---------- */

type LoginOutcome =
  | { ok: true; tokens: { access_token: string; refresh_token: string } }
  | { ok: false; kind: 'invalid' | 'locked' | 'network'; message: string; retryAfterSeconds?: number };

async function submitLogin(employeeId: number, pin: string): Promise<LoginOutcome> {
  let resp: Response;
  try {
    resp = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ employee_id: employeeId, pin }),
    });
  } catch {
    return {
      ok: false,
      kind: 'network',
      message: 'Нет связи с сервером. Проверьте вайфай и попробуйте снова.',
    };
  }

  if (resp.status === 429) {
    const retryAfterSeconds = Number(resp.headers.get('Retry-After')) || 30;
    return {
      ok: false,
      kind: 'locked',
      message: 'Слишком много неверных попыток подряд',
      retryAfterSeconds,
    };
  }

  if (!resp.ok) {
    return { ok: false, kind: 'invalid', message: 'Не тот PIN, попробуйте ещё раз' };
  }

  return { ok: true, tokens: await resp.json() };
}

function formatWait(seconds: number): string {
  if (seconds < 60) return `${seconds} сек.`;
  return `${Math.ceil(seconds / 60)} мин.`;
}

function PinStep({ employee, onBack }: { employee: EmployeeOption; onBack: () => void }) {
  const [pin, setPin] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [shake, setShake] = useState(false);
  const [lockSeconds, setLockSeconds] = useState(0);
  const attemptRef = useRef(0);

  // Обратный отсчёт блокировки — секундами, а не абстрактным "попробуйте позже".
  useEffect(() => {
    if (lockSeconds <= 0) return;
    const t = window.setInterval(() => {
      setLockSeconds((s) => {
        if (s <= 1) {
          setError(null);
          return 0;
        }
        return s - 1;
      });
    }, 1000);
    return () => window.clearInterval(t);
  }, [lockSeconds]);

  useEffect(() => {
    if (pin.length !== PIN_LENGTH || submitting || lockSeconds > 0) return;
    const attempt = ++attemptRef.current;
    setSubmitting(true);
    submitLogin(employee.id, pin).then((result) => {
      if (attemptRef.current !== attempt) return; // сгорела гонка с новым набором PIN
      setSubmitting(false);
      if (result.ok) {
        const session: Session = {
          accessToken: result.tokens.access_token,
          refreshToken: result.tokens.refresh_token,
          employeeId: employee.id,
          venueId: VENUE_ID,
          role: employee.role,
          name: employee.name,
          language: employee.language,
        };
        saveSession(session);
        location.reload();
        return;
      }

      setPin('');
      setError(result.message);
      if (result.kind === 'locked') {
        setLockSeconds(result.retryAfterSeconds ?? 30);
      } else {
        setShake(true);
        window.setTimeout(() => setShake(false), 300);
      }
    });
  }, [pin, submitting, lockSeconds, employee]);

  return (
    <div className="flex flex-1 flex-col">
      <button
        onClick={onBack}
        className="mb-6 flex items-center gap-1.5 self-start text-base font-medium text-stone-400 active:text-stone-200"
      >
        <ChevronLeft size={20} /> Это не я
      </button>

      <div className="mb-8 text-center">
        <span className="mx-auto mb-3 flex h-14 w-14 items-center justify-center rounded-full bg-stone-800 text-xl font-bold text-stone-200">
          {initials(employee.name)}
        </span>
        <h1 className="text-2xl font-bold tracking-tight">{employee.name}</h1>
        <p className="text-base text-stone-400">Введите свой PIN</p>
      </div>

      <div className={`mx-auto w-full max-w-xs flex-1 ${shake ? 'animate-shake-x' : ''}`}>
        <PinPad length={PIN_LENGTH} value={pin} onChange={setPin} disabled={submitting || lockSeconds > 0} />

        <div className="mt-5 min-h-[3.5rem] text-center">
          {lockSeconds > 0 ? (
            <p className="flex items-center justify-center gap-2 text-base font-medium text-amber-300">
              <RotateCcw size={18} />
              Подождите {formatWait(lockSeconds)} и попробуйте снова
            </p>
          ) : submitting ? (
            <p className="text-base text-stone-400">Проверяю…</p>
          ) : error ? (
            <p className="text-base font-medium text-red-400">{error}</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
