import { useEffect, useMemo, useState } from 'react';
import {
  ArrowLeft,
  ArrowRight,
  Building2,
  Check,
  Copy,
  FileText,
  Headphones,
  Loader2,
  Plus,
  Trash2,
  Upload,
  UserRound,
  Users,
} from 'lucide-react';
import { Logo } from '../components/Logo';
import { LiveBars } from '../components/Waveform';
import { Chip, Field } from '../components/ui';
import { FOCUS_META, useStore, type CompanySignup, type PointDraft } from '../store';
import { INDUSTRY_ORDER, INDUSTRY_PROFILES, getProfile } from '../industryProfiles';
import { DEMO_SPACES } from '../demo';
import type { IndustryKey, KnowledgeSourceFile, ManagerFocus } from '../types';

type Mode = 'choose' | 'login' | 'company' | 'employee';

function BrandPanel() {
  const { profile } = useStore();
  const cues = profile.cues;
  const [i, setI] = useState(0);

  useEffect(() => {
    setI(0);
  }, [profile.key]);

  useEffect(() => {
    const t = setInterval(() => setI((v) => (v + 1) % cues.length), 5200);
    return () => clearInterval(t);
  }, [cues.length]);

  const cue = cues[i % cues.length];

  return (
    <aside className="relative hidden flex-col justify-between overflow-hidden bg-ink p-10 lg:flex">
      <div
        aria-hidden
        className="absolute inset-0 opacity-[0.16]"
        style={{
          backgroundImage: 'radial-gradient(circle at 20% 15%, var(--color-brand-500) 0%, transparent 45%)',
        }}
      />
      <div className="relative">
        <Logo size={34} invert />
      </div>

      <div className="relative">
        <p className="mb-3 inline-flex items-center gap-2 rounded-full bg-white/10 px-3 py-1.5 text-[11px] font-semibold tracking-[0.09em] text-brand-200 uppercase">
          <span className="relative flex h-1.5 w-1.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand-400 opacity-70" />
            <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-brand-300" />
          </span>
          В эфире
        </p>
        <h1 className="text-[34px] leading-[1.12] font-semibold tracking-tight text-white">
          Рабочее место
          <br />
          линейного персонала
          <br />
          <span className="text-brand-300">в офлайн-точке</span>
        </h1>
        <p className="mt-4 max-w-sm text-[15px] leading-relaxed text-slate-300">
          Бейдж слышит разговор с клиентом, платформа разбирает его на приёмы и ошибки. Руководитель
          видит цифры, сотрудник — что исправить в следующем диалоге.
        </p>

        <div className="mt-8 max-w-md rounded-xl border border-white/10 bg-white/[0.04] p-4">
          <div className="flex items-center gap-3">
            <LiveBars active bars={16} height={22} color="var(--color-brand-400)" />
            <span className="text-[11px] font-semibold tracking-[0.08em] text-slate-400 uppercase">
              Подсказка в гарнитуру · {profile.labels.industry}
            </span>
          </div>
          <p className="mt-3 text-[13px] text-slate-400">
            {profile.labels.client}: <span className="text-slate-200">«{cue.q}»</span>
          </p>
          <p className="mt-2 text-[14px] leading-relaxed font-medium text-white">{cue.a}</p>
        </div>
      </div>

      <div className="relative flex gap-8">
        {[
          ['−40 %', 'скорость ответа'],
          ['+23 п.п.', 'решено самостоятельно'],
          ['1,5 нед', 'адаптация новичка'],
        ].map(([v, l]) => (
          <div key={l}>
            <p className="figure text-xl font-semibold text-white">{v}</p>
            <p className="mt-0.5 text-[12px] text-slate-400">{l}</p>
          </div>
        ))}
      </div>
    </aside>
  );
}

export default function AuthView() {
  const [mode, setMode] = useState<Mode>('choose');

  return (
    <div className="grid min-h-screen lg:grid-cols-[minmax(0,1fr)_minmax(0,1.05fr)]">
      <BrandPanel />
      <main className="flex flex-col justify-center bg-white px-5 py-10 sm:px-10 lg:px-14">
        <div className="mx-auto w-full max-w-[460px]">
          <div className="mb-8 lg:hidden">
            <Logo />
          </div>
          {mode === 'choose' && <Choose onPick={setMode} />}
          {mode === 'login' && <LoginForm onBack={() => setMode('choose')} />}
          {mode === 'company' && <CompanyWizard onBack={() => setMode('choose')} />}
          {mode === 'employee' && <EmployeeForm onBack={() => setMode('choose')} />}
        </div>
      </main>
    </div>
  );
}

function DemoSpacePicker() {
  const { data, switchSpace } = useStore();
  return (
    <div className="mt-7 rounded-xl border border-slate-200 bg-slate-50 p-3.5">
      <p className="label mb-2.5">Демо-пространство</p>
      <div className="space-y-1.5">
        {DEMO_SPACES.map((s) => {
          const on = data.space === s.key;
          return (
            <button
              key={s.key}
              type="button"
              onClick={() => switchSpace(s.key)}
              className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition ${
                on ? 'border-brand-400 bg-white' : 'border-transparent hover:bg-white'
              }`}
            >
              <span className="min-w-0 flex-1">
                <span className="block text-[13px] font-semibold text-ink">{s.label}</span>
                <span className="block truncate text-[12px] text-slate-500">{s.hint}</span>
              </span>
              {on && <Check size={15} className="shrink-0 text-brand-600" />}
            </button>
          );
        })}
      </div>
      <p className="mt-2.5 text-[11px] text-slate-500">
        Переключение загружает готовые демо-данные другой отрасли и выходит из аккаунта.
      </p>
    </div>
  );
}

function Choose({ onPick }: { onPick: (m: Mode) => void }) {
  const { profile } = useStore();
  const paths = [
    {
      mode: 'company' as const,
      icon: <Building2 size={20} />,
      title: 'Подключить компанию',
      hint: 'Для руководителя: выбираем отрасль, заводим точки и базу знаний, получаем код.',
    },
    {
      mode: 'employee' as const,
      icon: <Headphones size={20} />,
      title: 'Присоединиться по коду',
      hint: `Для сотрудника: код даёт руководитель, бейдж привяжется к смене.`,
    },
  ];
  return (
    <>
      <h2 className="text-[28px] leading-tight font-semibold tracking-tight text-ink">
        Начнём работу
      </h2>
      <p className="mt-2 text-[15px] text-slate-500">
        Onvy настраивается под отрасль: {profile.labels.industry.toLowerCase()}, ритейл, DIY, HoReCa —
        одно ядро, разные термины и метрики.
      </p>

      <div className="mt-7 space-y-3">
        {paths.map((p) => (
          <button
            key={p.mode}
            type="button"
            onClick={() => onPick(p.mode)}
            className="group flex w-full items-start gap-4 rounded-xl border border-slate-200 bg-white p-4 text-left transition hover:border-brand-400 hover:bg-brand-50/40"
          >
            <span className="mt-0.5 flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-brand-50 text-brand-700 transition group-hover:bg-brand-600 group-hover:text-white">
              {p.icon}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block text-[15px] font-semibold text-ink">{p.title}</span>
              <span className="mt-0.5 block text-[13px] leading-relaxed text-slate-500">{p.hint}</span>
            </span>
            <ArrowRight
              size={18}
              className="mt-2.5 shrink-0 text-slate-300 transition group-hover:translate-x-0.5 group-hover:text-brand-600"
            />
          </button>
        ))}
      </div>

      <p className="mt-6 text-center text-[14px] text-slate-500">
        Уже есть аккаунт?{' '}
        <button
          type="button"
          onClick={() => onPick('login')}
          className="font-semibold text-brand-700 underline-offset-4 hover:underline"
        >
          Войти
        </button>
      </p>

      <DemoSpacePicker />
    </>
  );
}

function BackLink({ onBack }: { onBack: () => void }) {
  return (
    <button type="button" onClick={onBack} className="btn-quiet -ml-3 mb-5 text-[13px]">
      <ArrowLeft size={15} /> Назад
    </button>
  );
}

function LoginForm({ onBack }: { onBack: () => void }) {
  const { login, data, profile } = useStore();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const rop = data.accounts.find((a) => a.role === 'rop');
  const emp = data.accounts.find((a) => a.role === 'employee');

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const r = login(email, password);
    if (!r.ok) setError(r.error);
  };

  const fill = (which: 'rop' | 'emp') => {
    const acc = which === 'rop' ? rop : emp;
    if (!acc) return;
    setEmail(acc.email);
    setPassword(acc.password);
    setError('');
  };

  return (
    <>
      <BackLink onBack={onBack} />
      <h2 className="text-[28px] leading-tight font-semibold tracking-tight text-ink">
        Вход
      </h2>
      <p className="mt-2 text-[15px] text-slate-500">Роль подставится автоматически по вашему аккаунту.</p>

      <form onSubmit={submit} className="mt-7 space-y-4">
        <Field label="Рабочая почта">
          <input
            className="field"
            type="email"
            required
            autoComplete="email"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              setError('');
            }}
            placeholder="name@company.ru"
          />
        </Field>
        <Field label="Пароль" error={error}>
          <input
            className="field"
            type="password"
            required
            autoComplete="current-password"
            value={password}
            onChange={(e) => {
              setPassword(e.target.value);
              setError('');
            }}
            placeholder="••••••••"
          />
        </Field>
        <button type="submit" className="console-btn-primary w-full">
          Войти
        </button>
      </form>

      {(rop || emp) && (
        <div className="mt-6 rounded-lg border border-slate-200 bg-slate-50 p-3.5">
          <p className="label mb-2">
            Демо-доступы · {data.company?.name} · {profile.labels.industry}
          </p>
          <div className="flex flex-wrap gap-2">
            {rop && (
              <button type="button" onClick={() => fill('rop')} className="btn-ghost px-3 py-1.5 text-[12px]">
                <Building2 size={14} /> Войти как РОП
              </button>
            )}
            {emp && (
              <button type="button" onClick={() => fill('emp')} className="btn-ghost px-3 py-1.5 text-[12px]">
                <UserRound size={14} /> Войти как сотрудник
              </button>
            )}
          </div>
        </div>
      )}
    </>
  );
}

const STEPS = ['Компания', 'Точки', 'База знаний', 'Аккаунт', 'Сотрудники'];

const emptyPoint = (): PointDraft => ({ name: '', city: '', address: '', zones: '', manager: '', staffCount: '' });

/** Типовые цели пилота под приоритет руководителя. */
const PILOT_GOALS: Record<ManagerFocus, string[]> = {
  culture: [
    'Сократить срок выхода новичка на самостоятельную работу',
    'Поднять единообразие стандартов между точками',
    'Распространить удачные практики сильных сотрудников',
    'Сделать обучение адресным — по реальным пробелам',
  ],
  operations: [
    'Снизить обращения за помощью к коллегам и смежным службам',
    'Ускорить ответ клиенту в зале',
    'Сократить количество ошибок в работе',
    'Обеспечить покрытие смены бейджами',
  ],
  sales: [
    'Поднять выполнение рабочего скрипта',
    'Увеличить долю дополнительных продаж',
    'Поднять результативность консультаций',
    'Выровнять средний чек между сотрудниками',
  ],
};

function CompanyWizard({ onBack }: { onBack: () => void }) {
  const { registerCompany, login } = useStore();
  const [step, setStep] = useState(0);
  const [error, setError] = useState('');
  const [joinCode, setJoinCode] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [form, setForm] = useState<CompanySignup>({
    companyName: '',
    industry: 'universal',
    staffSize: '10–50',
    pointsPlanned: '1–3',
    city: '',
    points: [emptyPoint()],
    knowledgeFiles: [],
    focus: 'culture',
    pilotGoals: [],
    ropName: '',
    ropEmail: '',
    ropPassword: '',
  });

  const profile = useMemo(() => getProfile(form.industry), [form.industry]);
  const L = profile.labels;

  const set = <K extends keyof CompanySignup>(k: K, v: CompanySignup[K]) =>
    setForm((f) => ({ ...f, [k]: v }));

  const setPoint = (i: number, k: keyof PointDraft, v: string) =>
    setForm((f) => ({ ...f, points: f.points.map((p, pi) => (pi === i ? { ...p, [k]: v } : p)) }));

  const canNext =
    step === 0
      ? form.companyName.trim().length > 1 && form.city.trim().length > 1
      : step === 1
        ? form.points.some((p) => p.name.trim())
        : step === 2
          ? true
          : step === 3
            ? form.ropName.trim().length > 1 && form.ropEmail.includes('@') && form.ropPassword.length >= 6
            : true;

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (step < 3) {
      setStep(step + 1);
      return;
    }
    const r = registerCompany(form);
    if (!r.ok) {
      setError(r.error);
      return;
    }
    setJoinCode(r.joinCode);
    setStep(4);
  };

  // Шаг 5 — код компании и приглашение сотрудников.
  if (step === 4 && joinCode) {
    return (
      <>
        <div className="mb-5 flex h-11 w-11 items-center justify-center rounded-lg bg-emerald-50 text-emerald-600">
          <Check size={22} strokeWidth={2.5} />
        </div>
        <h2 className="text-[26px] leading-tight font-semibold tracking-tight text-ink">
          Компания подключена
        </h2>
        <p className="mt-2 text-[15px] text-slate-500">
          Осталось подключить {L.employeePlural.toLowerCase()}. По этому коду они зарегистрируются и
          привяжут бейджи к своей точке.
        </p>

        <div className="mt-6 rounded-xl border border-slate-200 bg-slate-50 p-4">
          <p className="label mb-2">Код компании</p>
          <div className="flex items-center gap-3">
            <code className="num flex-1 rounded-lg border border-slate-200 bg-white px-3.5 py-2.5 text-[15px] font-semibold text-ink">
              {joinCode}
            </code>
            <button
              type="button"
              className="btn-ghost shrink-0"
              onClick={() => {
                navigator.clipboard?.writeText(joinCode);
                setCopied(true);
                setTimeout(() => setCopied(false), 1800);
              }}
            >
              {copied ? <Check size={15} /> : <Copy size={15} />}
              {copied ? 'Скопировано' : 'Копировать'}
            </button>
          </div>
        </div>

        <ol className="mt-5 space-y-2.5">
          {[
            `Отправьте код ${L.employeePlural.toLowerCase()}`,
            'Сотрудник выбирает «Присоединиться по коду» на этом же экране',
            'Указывает точку и должность, затем подключает бейдж',
          ].map((s, i) => (
            <li key={s} className="flex gap-3 text-[13px] leading-relaxed text-slate-600">
              <span className="num mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-slate-100 text-[11px] font-semibold text-slate-500">
                {i + 1}
              </span>
              {s}
            </li>
          ))}
        </ol>

        <div className="mt-5 rounded-lg border border-slate-200 p-3.5">
          <p className="label mb-1.5">Приглашённые</p>
          <p className="flex items-center gap-2 text-[13px] text-slate-500">
            <Users size={15} className="text-slate-500" />
            Пока никто не присоединился
          </p>
        </div>

        <button
          type="button"
          className="console-btn-primary mt-5 w-full"
          onClick={() => login(form.ropEmail, form.ropPassword)}
        >
          Перейти в кабинет <ArrowRight size={16} />
        </button>
        <p className="mt-3 text-center text-[13px] text-slate-500">
          Код всегда доступен в разделе «Торговые точки».
        </p>
      </>
    );
  }

  return (
    <>
      <BackLink onBack={step === 0 ? onBack : () => setStep(step - 1)} />

      <div className="mb-6 flex items-center gap-1.5">
        {STEPS.map((s, i) => (
          <div key={s} className="min-w-0 flex-1">
            <div className={`h-1 rounded-full transition ${i <= step ? 'bg-brand-600' : 'bg-slate-200'}`} />
            <p
              className={`mt-1.5 truncate text-[10.5px] font-semibold ${i <= step ? 'text-brand-700' : 'text-slate-500'}`}
            >
              {s}
            </p>
          </div>
        ))}
      </div>

      <h2 className="text-[26px] leading-tight font-semibold tracking-tight text-ink">
        {step === 0 && 'Данные компании'}
        {step === 1 && (form.points.length > 1 ? 'Торговые точки' : 'Торговая точка')}
        {step === 2 && 'База знаний'}
        {step === 3 && 'Аккаунт руководителя'}
      </h2>
      <p className="mt-2 text-[15px] text-slate-500">
        {step === 0 && 'Сфера определит термины, метрики и структуру базы знаний.'}
        {step === 1 && `Добавьте хотя бы одну точку — позже их можно завести сколько угодно.`}
        {step === 2 && `Загрузите источники, из которых Onvy будет отвечать ${L.employeePlural.toLowerCase()}.`}
        {step === 3 && 'Этот аккаунт получит доступ к дашборду, KPI и генератору тестов.'}
      </p>

      <form onSubmit={submit} className="mt-6 space-y-4">
        {step === 0 && (
          <>
            <Field label="Название компании">
              <input
                className="field"
                required
                value={form.companyName}
                onChange={(e) => set('companyName', e.target.value)}
                placeholder="Название сети"
              />
            </Field>
            <Field label="Сфера" hint={profile.labels.industryHint}>
              <select
                className="field"
                value={form.industry}
                onChange={(e) => set('industry', e.target.value as IndustryKey)}
              >
                {INDUSTRY_ORDER.map((k) => (
                  <option key={k} value={k}>
                    {INDUSTRY_PROFILES[k].labels.industry}
                  </option>
                ))}
              </select>
            </Field>
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Размер команды">
                <select className="field" value={form.staffSize} onChange={(e) => set('staffSize', e.target.value)}>
                  {['до 10', '10–50', '50–200', '200–500', '500+'].map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </Field>
              <Field label="Количество точек">
                <select
                  className="field"
                  value={form.pointsPlanned}
                  onChange={(e) => set('pointsPlanned', e.target.value)}
                >
                  {['1', '1–3', '4–10', '11–30', '30+'].map((s) => (
                    <option key={s}>{s}</option>
                  ))}
                </select>
              </Field>
            </div>
            <Field label="Город">
              <input
                className="field"
                required
                value={form.city}
                onChange={(e) => set('city', e.target.value)}
                placeholder="Москва"
              />
            </Field>

            <Field
              label="Приоритет руководителя"
              hint="Роли остаются те же — меняется порядок разделов и что показывается первым."
            >
              <select
                className="field"
                value={form.focus}
                onChange={(e) => set('focus', e.target.value as ManagerFocus)}
              >
                {(Object.keys(FOCUS_META) as ManagerFocus[]).map((k) => (
                  <option key={k} value={k}>
                    {FOCUS_META[k].label}
                  </option>
                ))}
              </select>
            </Field>

            <div className="rounded-lg border border-slate-200 p-3.5">
              <p className="label mb-2.5">Что проверяем в пилоте</p>
              <div className="space-y-1.5">
                {PILOT_GOALS[form.focus].map((g) => {
                  const on = form.pilotGoals.includes(g);
                  return (
                    <label
                      key={g}
                      className="flex cursor-pointer items-start gap-2.5 text-[13px] leading-relaxed text-slate-600"
                    >
                      <input
                        type="checkbox"
                        checked={on}
                        onChange={() =>
                          set(
                            'pilotGoals',
                            on ? form.pilotGoals.filter((x) => x !== g) : [...form.pilotGoals, g],
                          )
                        }
                        className="mt-0.5 h-4 w-4 shrink-0 rounded border-slate-300 text-brand-600 focus:ring-brand-500"
                      />
                      {g}
                    </label>
                  );
                })}
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 bg-slate-50 p-3.5">
              <p className="label mb-2">Что изменится в интерфейсе</p>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-[12.5px]">
                {[
                  ['Клиент', L.client],
                  ['Сотрудник', L.employee],
                  ['Локация', L.location],
                  ['Взаимодействие', L.interaction],
                  ['Результат', L.outcome],
                  ['Каталог', L.catalog],
                ].map(([k, v]) => (
                  <div key={k} className="flex min-w-0 justify-between gap-2">
                    <dt className="truncate text-slate-500">{k}</dt>
                    <dd className="truncate font-semibold text-ink">{v}</dd>
                  </div>
                ))}
              </dl>
            </div>
          </>
        )}

        {step === 1 && (
          <div className="space-y-3">
            {form.points.map((p, i) => (
              <div key={i} className="rounded-xl border border-slate-200 p-4">
                <div className="mb-3 flex items-center justify-between">
                  <p className="label">
                    {L.location} {i + 1}
                  </p>
                  {form.points.length > 1 && (
                    <button
                      type="button"
                      className="btn-quiet rounded-md p-1.5 text-slate-500 hover:text-rose-600"
                      onClick={() => set('points', form.points.filter((_, pi) => pi !== i))}
                    >
                      <Trash2 size={15} />
                      <span className="sr-only">Удалить</span>
                    </button>
                  )}
                </div>
                <div className="space-y-3">
                  <input
                    className="field"
                    placeholder="Название"
                    value={p.name}
                    onChange={(e) => setPoint(i, 'name', e.target.value)}
                  />
                  <input
                    className="field"
                    placeholder="Адрес"
                    value={p.address}
                    onChange={(e) => setPoint(i, 'address', e.target.value)}
                  />
                  <div className="grid gap-3 sm:grid-cols-2">
                    <input
                      className="field"
                      placeholder="Руководитель точки"
                      value={p.manager}
                      onChange={(e) => setPoint(i, 'manager', e.target.value)}
                    />
                    <input
                      className="field"
                      placeholder="Сотрудников"
                      inputMode="numeric"
                      value={p.staffCount}
                      onChange={(e) => setPoint(i, 'staffCount', e.target.value)}
                    />
                  </div>
                  <div>
                    <input
                      className="field"
                      placeholder={L.zonesPlaceholder}
                      value={p.zones}
                      onChange={(e) => setPoint(i, 'zones', e.target.value)}
                    />
                    <span className="mt-1.5 block text-xs text-slate-500">
                      {L.zones} через запятую
                    </span>
                  </div>
                </div>
              </div>
            ))}
            <button
              type="button"
              className="btn-ghost w-full border-dashed"
              onClick={() => set('points', [...form.points, emptyPoint()])}
            >
              <Plus size={16} /> Добавить {L.location.toLowerCase()}
            </button>
          </div>
        )}

        {step === 2 && (
          <KnowledgeStep
            profile={profile}
            files={form.knowledgeFiles}
            onChange={(files) => set('knowledgeFiles', files)}
          />
        )}

        {step === 3 && (
          <>
            <Field label="Имя и фамилия">
              <input
                className="field"
                required
                value={form.ropName}
                onChange={(e) => set('ropName', e.target.value)}
                placeholder="Имя Фамилия"
              />
            </Field>
            <Field label="Рабочая почта">
              <input
                className="field"
                type="email"
                required
                autoComplete="email"
                value={form.ropEmail}
                onChange={(e) => {
                  set('ropEmail', e.target.value);
                  setError('');
                }}
                placeholder="rop@company.ru"
              />
            </Field>
            <Field label="Пароль" hint="Не короче 6 символов" error={error}>
              <input
                className="field"
                type="password"
                required
                minLength={6}
                autoComplete="new-password"
                value={form.ropPassword}
                onChange={(e) => {
                  set('ropPassword', e.target.value);
                  setError('');
                }}
                placeholder="••••••••"
              />
            </Field>
          </>
        )}

        <button type="submit" className="console-btn-primary w-full" disabled={!canNext}>
          {step < 3 ? 'Дальше' : 'Создать компанию'}
          {step < 3 && <ArrowRight size={16} />}
        </button>
      </form>
    </>
  );
}

/** Шаг 3: источники базы знаний. Загрузка симулируется на фронтенде. */
function KnowledgeStep({
  profile,
  files,
  onChange,
}: {
  profile: ReturnType<typeof getProfile>;
  files: KnowledgeSourceFile[];
  onChange: (f: KnowledgeSourceFile[]) => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);

  const upload = (kind: string, label: string, fileName: string, sizeKb: number) => {
    setBusy(kind);
    // Симуляция разбора файла — реального парсинга на фронтенде нет.
    setTimeout(() => {
      const categories = profile.categories.slice(0, 3);
      onChange([
        ...files.filter((f) => f.kind !== kind),
        {
          id: `kf${Math.random().toString(36).slice(2, 8)}`,
          name: fileName,
          sizeKb,
          uploadedAt: new Date().toISOString().slice(0, 10),
          kind,
          categories,
          records: 40 + Math.round(sizeKb * 1.7),
        },
      ]);
      setBusy(null);
      void label;
    }, 1400);
  };

  return (
    <div className="space-y-3">
      <div className="rounded-lg border border-slate-200 bg-slate-50 px-3.5 py-2.5">
        <p className="text-[12.5px] leading-relaxed text-slate-600">
          Демо-режим: файл не отправляется на сервер и не разбирается по-настоящему — показывается
          симуляция обработки. Шаг можно пропустить.
        </p>
      </div>

      {profile.knowledgeSources.map((src) => {
        const done = files.find((f) => f.kind === src.key);
        const loading = busy === src.key;
        return (
          <div
            key={src.key}
            className={`rounded-xl border p-4 transition ${done ? 'border-emerald-200 bg-emerald-50/40' : 'border-slate-200'}`}
          >
            <div className="flex items-start gap-3">
              <span
                className={`mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg ${
                  done ? 'bg-emerald-500 text-white' : 'bg-slate-100 text-slate-500'
                }`}
              >
                {done ? <Check size={16} strokeWidth={3} /> : loading ? <Loader2 size={16} className="animate-spin" /> : <FileText size={16} />}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[14px] font-semibold text-ink">{src.label}</p>
                <p className="mt-0.5 text-[12.5px] leading-relaxed text-slate-500">{src.hint}</p>

                {done && (
                  <div className="mt-2.5 rounded-md border border-emerald-200 bg-white p-2.5">
                    <p className="num truncate text-[12px] font-semibold text-ink">{done.name}</p>
                    <p className="num mt-0.5 text-[11px] text-slate-500">
                      {done.sizeKb} КБ · найдено записей: {done.records}
                    </p>
                    <div className="mt-1.5 flex flex-wrap gap-1">
                      {done.categories.map((c) => (
                        <Chip key={c} tone="good">
                          {c}
                        </Chip>
                      ))}
                    </div>
                  </div>
                )}

                {!done && !loading && (
                  <label className="mt-2.5 inline-flex cursor-pointer items-center gap-2 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-[12px] font-semibold text-slate-700 transition hover:border-brand-400 hover:text-brand-700">
                    <Upload size={13} /> Загрузить файл
                    <input
                      type="file"
                      className="sr-only"
                      accept=".pdf,.doc,.docx,.xls,.xlsx,.txt,.csv"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) upload(src.key, src.label, f.name, Math.max(8, Math.round(f.size / 1024)));
                        e.target.value = '';
                      }}
                    />
                  </label>
                )}
                {loading && <p className="mt-2.5 text-[12px] text-brand-700">Разбираем файл…</p>}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function EmployeeForm({ onBack }: { onBack: () => void }) {
  const { registerEmployee, findCompanyByCode, data } = useStore();
  const [code, setCode] = useState('');
  const [checked, setChecked] = useState<ReturnType<typeof findCompanyByCode>>(null);
  const [error, setError] = useState('');
  const [form, setForm] = useState({ name: '', email: '', password: '', position: '', pointId: '' });

  const profile = useMemo(
    () => getProfile(checked?.company.industry ?? data.company?.industry),
    [checked, data.company?.industry],
  );
  const L = profile.labels;

  const check = () => {
    const found = findCompanyByCode(code);
    if (!found) {
      setError('Код компании не найден. Проверьте у руководителя.');
      setChecked(null);
      return;
    }
    setError('');
    setChecked(found);
    const p = getProfile(found.company.industry);
    setForm((f) => ({
      ...f,
      pointId: found.points[0]?.id ?? '',
      position: f.position || p.labels.employeeRoles[1] || p.labels.employee,
    }));
  };

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const r = registerEmployee({ ...form, joinCode: code });
    if (!r.ok) setError(r.error);
  };

  return (
    <>
      <BackLink onBack={onBack} />
      <h2 className="text-[28px] leading-tight font-semibold tracking-tight text-ink">
        Регистрация сотрудника
      </h2>
      <p className="mt-2 text-[15px] text-slate-500">
        Введите код компании — он определит вашу сеть и список точек.
      </p>

      {!checked ? (
        <div className="mt-7 space-y-4">
          <Field label="Код компании" error={error} hint={`Например, ${data.company?.joinCode ?? 'ONVY-2026'}`}>
            <input
              className="field num uppercase"
              value={code}
              onChange={(e) => {
                setCode(e.target.value);
                setError('');
              }}
              onKeyDown={(e) => e.key === 'Enter' && check()}
              placeholder={data.company?.joinCode ?? 'ONVY-2026'}
            />
          </Field>
          <button type="button" className="console-btn-primary w-full" onClick={check} disabled={code.trim().length < 3}>
            Проверить код <ArrowRight size={16} />
          </button>
        </div>
      ) : (
        <form onSubmit={submit} className="mt-7 space-y-4">
          <div className="flex items-center gap-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3.5 py-3">
            <Check size={17} className="shrink-0 text-emerald-600" />
            <p className="text-[13px] text-emerald-900">
              Компания найдена: <span className="font-semibold">{checked.company.name}</span> ·{' '}
              {L.industry}
            </p>
          </div>
          <Field label="Имя и фамилия">
            <input
              className="field"
              required
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="Имя Фамилия"
            />
          </Field>
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Должность">
              <select
                className="field"
                value={form.position}
                onChange={(e) => setForm({ ...form, position: e.target.value })}
              >
                {L.employeeRoles.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </Field>
            <Field label={L.location}>
              <select
                className="field"
                value={form.pointId}
                onChange={(e) => setForm({ ...form, pointId: e.target.value })}
              >
                {checked.points.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.name}
                  </option>
                ))}
              </select>
            </Field>
          </div>
          <Field label="Рабочая почта">
            <input
              className="field"
              type="email"
              required
              autoComplete="email"
              value={form.email}
              onChange={(e) => {
                setForm({ ...form, email: e.target.value });
                setError('');
              }}
              placeholder="name@company.ru"
            />
          </Field>
          <Field label="Пароль" hint="Не короче 6 символов" error={error}>
            <input
              className="field"
              type="password"
              required
              minLength={6}
              autoComplete="new-password"
              value={form.password}
              onChange={(e) => {
                setForm({ ...form, password: e.target.value });
                setError('');
              }}
              placeholder="••••••••"
            />
          </Field>
          <button type="submit" className="console-btn-primary w-full">
            Создать аккаунт
          </button>
        </form>
      )}
    </>
  );
}



