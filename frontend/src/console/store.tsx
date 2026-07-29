import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { DEFAULT_SPACE, emptyData, makeDemoDialog, makeSpace } from './demo';
import { getProfile, type IndustryProfile } from './industryProfiles';
import type {
  Account,
  AppData,
  Company,
  Employee,
  IndustryKey,
  KnowledgeSourceFile,
  Kpi,
  ManagerFocus,
  SalesPoint,
  Test,
} from './types';

const DATA_KEY = 'onvy.data.v2';
const SESSION_KEY = 'onvy.session.v2';

function load<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function save(key: string, value: unknown) {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    /* приватный режим — работаем без сохранения */
  }
}

const uid = (p: string) => `${p}${Math.random().toString(36).slice(2, 9)}`;

/**
 * Приоритеты руководителя. Ролей по-прежнему две — фокус влияет только на то,
 * какие разделы выходят вперёд и что показывается первым на дашборде.
 */
export const FOCUS_META: Record<
  ManagerFocus,
  { label: string; title: string; hint: string; nav: string[]; primary: 'people' | 'ops' | 'sales' }
> = {
  culture: {
    label: 'Корпоративная культура и обучение',
    title: 'Директор по корпоративной культуре',
    hint: 'Адаптация, стандарты, развитие команды и лучшие практики',
    nav: ['overview', 'team', 'analytics', 'staff', 'tests', 'knowledge', 'points', 'pilot'],
    primary: 'people',
  },
  operations: {
    label: 'Операционное управление',
    title: 'Операционный директор',
    hint: 'Работа точек, скорость, ошибки и покрытие бейджами',
    nav: ['overview', 'analytics', 'points', 'staff', 'team', 'tests', 'knowledge', 'pilot'],
    primary: 'ops',
  },
  sales: {
    label: 'Продажи и KPI',
    title: 'Руководитель отдела продаж',
    hint: 'Результативность, средний чек, скрипты и цели',
    nav: ['overview', 'analytics', 'staff', 'points', 'tests', 'team', 'knowledge', 'pilot'],
    primary: 'sales',
  },
};

const FOCUS_TITLE: Record<ManagerFocus, string> = {
  culture: FOCUS_META.culture.title,
  operations: FOCUS_META.operations.title,
  sales: FOCUS_META.sales.title,
};

export interface PointDraft {
  name: string;
  city: string;
  address: string;
  zones: string;
  manager: string;
  staffCount: string;
}

export interface CompanySignup {
  companyName: string;
  industry: IndustryKey;
  staffSize: string;
  pointsPlanned: string;
  city: string;
  points: PointDraft[];
  knowledgeFiles: KnowledgeSourceFile[];
  /** Приоритет руководителя — меняет порядок блоков в его кабинете. */
  focus: ManagerFocus;
  pilotGoals: string[];
  ropName: string;
  ropEmail: string;
  ropPassword: string;
}

export interface EmployeeSignup {
  joinCode: string;
  name: string;
  email: string;
  password: string;
  position: string;
  pointId: string;
}

type Result = { ok: true } | { ok: false; error: string };
type CompanyResult = { ok: true; joinCode: string } | { ok: false; error: string };

interface StoreValue {
  data: AppData;
  /** Отраслевой профиль текущей компании — источник всех названий и метрик. */
  profile: IndustryProfile;
  session: Account | null;
  me: Employee | null;
  login: (email: string, password: string) => Result;
  logout: () => void;
  /** Сессию не открывает: РОП сначала должен увидеть код для сотрудников. */
  registerCompany: (input: CompanySignup) => CompanyResult;
  registerEmployee: (input: EmployeeSignup) => Result;
  findCompanyByCode: (code: string) => { company: Company; points: SalesPoint[] } | null;
  setKpi: (kpi: Omit<Kpi, 'id'>) => void;
  removeKpi: (id: string) => void;
  addTest: (test: Omit<Test, 'id' | 'createdAt' | 'results'>) => Test;
  assignTest: (testId: string, employeeIds: string[]) => void;
  recordTestResult: (testId: string, employeeId: string, score: number) => void;
  /** Записывает демо-диалог сотрудника — он сразу виден РОПу в аналитике. */
  runDemoDialog: () => string | null;
  /** Приоритет текущего руководителя. */
  focus: ManagerFocus;
  setFocus: (f: ManagerFocus) => void;
  /** Превратить удачную практику в учебный материал. */
  promotePractice: (id: string) => void;
  /** Переключение готового демо-пространства. */
  switchSpace: (key: string) => void;
  resetDemo: () => void;
}

const StoreContext = createContext<StoreValue | null>(null);

/**
 * Пригодны ли сохранённые данные к показу.
 *
 * Внутри платформы консоль открывается сразу, минуя её собственную регистрацию,
 * поэтому пустое пространство здесь означает не «пользователь только начал»,
 * а мусор в localStorage от прежних заходов — и все разделы выглядят пустыми,
 * хотя ничего не сломано. В таком случае честнее показать демо-данные.
 */
function usable(data: AppData | null): data is AppData {
  return Boolean(data && Array.isArray(data.employees) && data.employees.length > 0);
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [data, setData] = useState<AppData>(() => {
    const saved = load<AppData | null>(DATA_KEY, null);
    return usable(saved) ? saved : makeSpace(DEFAULT_SPACE);
  });
  const [session, setSession] = useState<Account | null>(() => load<Account | null>(SESSION_KEY, null));

  useEffect(() => save(DATA_KEY, data), [data]);
  useEffect(() => save(SESSION_KEY, session), [session]);

  const profile = useMemo(() => getProfile(data.company?.industry), [data.company?.industry]);

  const login = useCallback<StoreValue['login']>(
    (email, password) => {
      const account = data.accounts.find(
        (a) => a.email.trim().toLowerCase() === email.trim().toLowerCase(),
      );
      if (!account) return { ok: false, error: 'Аккаунта с такой почтой нет' };
      if (account.password !== password) return { ok: false, error: 'Неверный пароль' };
      setSession(account);
      return { ok: true };
    },
    [data.accounts],
  );

  const logout = useCallback(() => setSession(null), []);

  const findCompanyByCode = useCallback<StoreValue['findCompanyByCode']>(
    (code) => {
      const c = data.company;
      if (!c || c.joinCode.trim().toLowerCase() !== code.trim().toLowerCase()) return null;
      return { company: c, points: data.points };
    },
    [data.company, data.points],
  );

  const registerCompany = useCallback<StoreValue['registerCompany']>(
    (input) => {
      const email = input.ropEmail.trim().toLowerCase();
      if (data.accounts.some((a) => a.email.toLowerCase() === email)) {
        return { ok: false, error: 'Такая почта уже зарегистрирована' };
      }
      const companyId = uid('c');
      const slug =
        input.companyName
          .toUpperCase()
          .replace(/[^A-ZА-ЯЁ0-9]/gi, '')
          .slice(0, 9) || 'ONVY';
      const company: Company = {
        id: companyId,
        name: input.companyName,
        industry: input.industry,
        staffSize: input.staffSize,
        pointsPlanned: input.pointsPlanned,
        city: input.city,
        joinCode: `${slug}-${new Date().getFullYear()}`,
        createdAt: new Date().toISOString().slice(0, 10),
      };
      const points: SalesPoint[] = input.points
        .filter((p) => p.name.trim())
        .map((p) => ({
          id: uid('p'),
          name: p.name,
          city: p.city || input.city,
          address: p.address,
          zones: p.zones
            .split(',')
            .map((z) => z.trim())
            .filter(Boolean),
          manager: p.manager,
          staffCount: 0,
          badgesOnline: 0,
          plan: 0,
          revenue: 0,
          avgCheck: 0,
          interactions: 0,
          conversion: 0,
          scriptCompliance: 0,
          training: 0,
          helpRequests: 0,
          industry: {},
        }));
      const rop: Account = {
        id: uid('a'),
        role: 'rop',
        name: input.ropName,
        email,
        password: input.ropPassword,
        companyId,
        position: FOCUS_TITLE[input.focus],
        focus: input.focus,
      };
      setData({
        ...emptyData(`custom:${input.industry}`),
        company,
        points,
        accounts: [rop],
        knowledgeFiles: input.knowledgeFiles,
        pilot: {
          startedAt: new Date().toISOString().slice(0, 10),
          weeks: 6,
          scope: `${points.length} · подключение сотрудников`,
          goals: input.pilotGoals,
          metrics: [],
        },
      });
      return { ok: true, joinCode: company.joinCode };
    },
    [data.accounts],
  );

  const registerEmployee = useCallback<StoreValue['registerEmployee']>(
    (input) => {
      const company = data.company;
      if (!company || company.joinCode.trim().toLowerCase() !== input.joinCode.trim().toLowerCase()) {
        return { ok: false, error: 'Код компании не найден' };
      }
      const email = input.email.trim().toLowerCase();
      if (data.accounts.some((a) => a.email.toLowerCase() === email)) {
        return { ok: false, error: 'Такая почта уже зарегистрирована' };
      }
      const employeeId = uid('e');
      const employee: Employee = {
        id: employeeId,
        name: input.name,
        position: input.position,
        pointId: input.pointId,
        hiredAt: new Date().toISOString().slice(0, 10),
        onboarding: 0,
        level: 1,
        xp: 0,
        badgeOnline: false,
        badgeBattery: 100,
        micQuality: 0,
        stats: {
          revenue: 0,
          deals: 0,
          dialogs: 0,
          avgCheck: 0,
          conversion: 0,
          scriptCompliance: 0,
          responseSec: 0,
          autonomy: 0,
          helpRequests: 0,
        },
        industry: {},
        daily: Array(14).fill(0),
        topItems: [],
        topRequests: [],
        strengths: [],
        growthAreas: [],
        trainingDone: 0,
        trainingTotal: data.tests.length,
      };
      const account: Account = {
        id: uid('a'),
        role: 'employee',
        name: input.name,
        email,
        password: input.password,
        companyId: company.id,
        pointId: input.pointId,
        position: input.position,
        employeeId,
      };
      setData((d) => ({
        ...d,
        employees: [...d.employees, employee],
        accounts: [...d.accounts, account],
        points: d.points.map((p) =>
          p.id === input.pointId ? { ...p, staffCount: p.staffCount + 1 } : p,
        ),
      }));
      setSession(account);
      return { ok: true };
    },
    [data.company, data.accounts, data.tests.length],
  );

  const setKpi = useCallback<StoreValue['setKpi']>((kpi) => {
    setData((d) => {
      const existing = d.kpis.find(
        (k) => k.employeeId === kpi.employeeId && k.metric === kpi.metric && k.period === kpi.period,
      );
      if (existing) {
        return {
          ...d,
          kpis: d.kpis.map((k) => (k.id === existing.id ? { ...existing, ...kpi } : k)),
        };
      }
      return { ...d, kpis: [...d.kpis, { ...kpi, id: uid('k') }] };
    });
  }, []);

  const removeKpi = useCallback<StoreValue['removeKpi']>((id) => {
    setData((d) => ({ ...d, kpis: d.kpis.filter((k) => k.id !== id) }));
  }, []);

  const addTest = useCallback<StoreValue['addTest']>((test) => {
    const created: Test = {
      ...test,
      id: uid('ts'),
      createdAt: new Date().toISOString().slice(0, 10),
      results: {},
    };
    setData((d) => ({ ...d, tests: [created, ...d.tests] }));
    return created;
  }, []);

  const assignTest = useCallback<StoreValue['assignTest']>((testId, employeeIds) => {
    setData((d) => ({
      ...d,
      tests: d.tests.map((t) => (t.id === testId ? { ...t, assignedTo: employeeIds } : t)),
    }));
  }, []);

  const recordTestResult = useCallback<StoreValue['recordTestResult']>((testId, employeeId, score) => {
    setData((d) => {
      const tests = d.tests.map((t) =>
        t.id === testId ? { ...t, results: { ...t.results, [employeeId]: score } } : t,
      );
      const mine = tests.filter((t) => t.assignedTo.includes(employeeId));
      const passed = mine.filter((t) => (t.results[employeeId] ?? 0) >= t.passScore).length;
      const employees = d.employees.map((e) =>
        e.id === employeeId
          ? {
              ...e,
              trainingDone: passed,
              trainingTotal: mine.length,
              xp: e.xp + Math.round(score * 2),
              onboarding: Math.min(
                100,
                Math.max(e.onboarding, Math.round((passed / Math.max(1, mine.length)) * 100)),
              ),
            }
          : e,
      );
      return { ...d, tests, employees };
    });
  }, []);

  const runDemoDialog = useCallback<StoreValue['runDemoDialog']>(() => {
    if (!session?.employeeId) return null;
    const employee = data.employees.find((e) => e.id === session.employeeId);
    if (!employee) return null;
    const seq = data.dialogs.filter((d) => d.simulated).length + 1;
    const dialog = makeDemoDialog(data.company?.industry ?? 'universal', employee, seq);
    setData((d) => ({
      ...d,
      dialogs: [dialog, ...d.dialogs],
      // Записанный диалог сразу попадает в счётчики сотрудника и точки.
      employees: d.employees.map((e) =>
        e.id === employee.id
          ? {
              ...e,
              stats: {
                ...e.stats,
                dialogs: e.stats.dialogs + 1,
                deals: e.stats.deals + 1,
                revenue: e.stats.revenue + dialog.revenue,
              },
            }
          : e,
      ),
      points: d.points.map((p) =>
        p.id === employee.pointId ? { ...p, interactions: p.interactions + 1 } : p,
      ),
    }));
    return dialog.id;
  }, [session, data.employees, data.dialogs, data.company?.industry]);

  const setFocus = useCallback<StoreValue['setFocus']>((f) => {
    setSession((s) => (s && s.role === 'rop' ? { ...s, focus: f } : s));
    setData((d) => ({
      ...d,
      accounts: d.accounts.map((a) =>
        a.role === 'rop' ? { ...a, focus: f, position: FOCUS_TITLE[f] } : a,
      ),
    }));
  }, []);

  const promotePractice = useCallback<StoreValue['promotePractice']>((id) => {
    setData((d) => ({
      ...d,
      bestPractices: d.bestPractices.map((p) => (p.id === id ? { ...p, inTraining: true } : p)),
    }));
  }, []);

  const switchSpace = useCallback<StoreValue['switchSpace']>((key) => {
    setData(makeSpace(key));
    setSession(null);
  }, []);

  const resetDemo = useCallback(() => {
    setData((d) => makeSpace(d.space.startsWith('custom') ? DEFAULT_SPACE : d.space));
    setSession(null);
  }, []);

  const me = useMemo(() => {
    if (!session?.employeeId) return null;
    return data.employees.find((e) => e.id === session.employeeId) ?? null;
  }, [session, data.employees]);

  const focus = session?.focus ?? data.accounts.find((a) => a.role === 'rop')?.focus ?? 'sales';

  const value = useMemo<StoreValue>(
    () => ({
      data,
      profile,
      session,
      me,
      focus,
      setFocus,
      promotePractice,
      login,
      logout,
      registerCompany,
      registerEmployee,
      findCompanyByCode,
      setKpi,
      removeKpi,
      addTest,
      assignTest,
      recordTestResult,
      runDemoDialog,
      switchSpace,
      resetDemo,
    }),
    [
      data,
      profile,
      session,
      me,
      focus,
      setFocus,
      promotePractice,
      login,
      logout,
      registerCompany,
      registerEmployee,
      findCompanyByCode,
      setKpi,
      removeKpi,
      addTest,
      assignTest,
      recordTestResult,
      runDemoDialog,
      switchSpace,
      resetDemo,
    ],
  );

  return <StoreContext.Provider value={value}>{children}</StoreContext.Provider>;
}

export function useStore() {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error('useStore должен вызываться внутри StoreProvider');
  return ctx;
}

/** Короткий доступ к названиям текущей отрасли. */
export function useLabels() {
  return useStore().profile.labels;
}
