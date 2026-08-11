import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { fetchStaff, getSession, logoutSession, type KpiMetric } from '../lib/api';
import { accountFromSession, emptyData, employeeFromStaff, meFromSession } from './emptyState';
import { getProfile, type IndustryProfile, type MetricDef } from './industryProfiles';
import type { Account, AppData, Employee, ManagerFocus, Role, Test } from './types';

// Версия ключа поднята намеренно: у всех, кто открывал кабинет раньше, в браузере
// лежит демо-пространство с выдуманными цифрами. Со старым ключом оно бы
// подгрузилось снова и «чистая картина» не наступила бы ни у кого, кроме тех,
// кто вручную чистит localStorage.
const DATA_KEY = 'onvy.data.v3';
const SESSION_KEY = 'onvy.session.v3';

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

/**
 * Метрики, по которым управляющий реально может ставить KPI — дословно
 * app/db/models/enums.py KPI_METRICS. Выручка, средний чек и конверсия сюда
 * не входят: без кассовой интеграции их не из чего посчитать, а "цель" без
 * источника — это враньё управляющему, а не показатель.
 */
export const KPI_METRIC_META: Record<KpiMetric, MetricDef> = {
  dialogs: {
    key: 'dialogs',
    label: 'Диалоги',
    unit: 'count',
    hint: 'Сколько обращений клиентов сотрудник обработал за период',
  },
  response_sec: {
    key: 'response_sec',
    label: 'Скорость ответа',
    unit: 'sec',
    lowerIsBetter: true,
    hint: 'Среднее время до ответа клиенту — цель не превышать значение',
  },
  autonomy: {
    key: 'autonomy',
    label: 'Самостоятельность',
    unit: 'pct',
    hint: 'Доля обращений, закрытых без обращения за помощью к коллегам',
  },
  help_requests: {
    key: 'help_requests',
    label: 'Обращения за помощью',
    unit: 'count',
    lowerIsBetter: true,
    hint: 'Сколько раз за период потребовалась помощь коллег — цель не превышать значение',
  },
};

export const KPI_METRIC_ORDER: KpiMetric[] = ['dialogs', 'response_sec', 'autonomy', 'help_requests'];

interface StoreValue {
  data: AppData;
  /** Отраслевой профиль текущей компании — источник всех названий и метрик. */
  profile: IndustryProfile;
  session: Account | null;
  me: Employee | null;
  /** Название заведения из настоящей сессии — подпись рабочего пространства. */
  venueName: string;
  /** Смена уже приехала с сервера. Пока false, пустой список ещё ничего не
   *  значит: экраны не должны звать заводить людей, которые, может быть, есть. */
  staffLoaded: boolean;
  logout: () => void;
  addTest: (test: Omit<Test, 'id' | 'createdAt' | 'results'>) => Test;
  assignTest: (testId: string, employeeIds: string[]) => void;
  recordTestResult: (testId: string, employeeId: string, score: number) => void;
  /** Приоритет текущего руководителя. */
  focus: ManagerFocus;
  setFocus: (f: ManagerFocus) => void;
  /** Превратить удачную практику в учебный материал. */
  promotePractice: (id: string) => void;
}

const StoreContext = createContext<StoreValue | null>(null);

/**
 * Настоящая сессия платформы (см. frontend/src/lib/api.ts) в объёме, который
 * нужен кабинету, чтобы показать вошедшего.
 */
export interface PlatformIdentity {
  employeeId: number;
  role: Role;
  name: string;
  /** Название заведения — подпись рабочего пространства в боковой панели. */
  venueName: string;
}

export function StoreProvider({
  children,
  identity = null,
}: {
  children: ReactNode;
  /** Настоящий вошедший платформы. Без него кабинет показывать некому. */
  identity?: PlatformIdentity | null;
}) {
  // Данные кабинета. Начальное состояние — пустое: всё, что здесь появится,
  // должно приехать из API платформы, а не из выдуманного набора.
  const [data, setData] = useState<AppData>(() => load<AppData>(DATA_KEY, emptyData()));

  useEffect(() => save(DATA_KEY, data), [data]);

  // Кто вошёл — берётся из настоящей сессии платформы, целиком. Своего входа у
  // консоли больше нет: внутри продукта человек уже авторизован, и вторая форма
  // логина была бы лишним экраном с чужими аккаунтами.
  const session = useMemo<Account | null>(
    () =>
      identity
        ? accountFromSession(identity.employeeId, identity.name, identity.role)
        : null,
    [identity],
  );

  const profile = useMemo(() => getProfile(data.company?.industry), [data.company?.industry]);

  /**
   * Смена — из базы платформы, один раз при открытии кабинета.
   *
   * До этого `data.employees` не наполнялся ничем: список брался из пустого
   * локального хранилища и был пуст ВСЕГДА, даже у заведения с семью людьми.
   * Наружу это выглядело так, будто новое заведение и работающее ничем не
   * отличаются, а поставить цель подчинённому было физически некому.
   *
   * Отказ не роняет кабинет: остальные разделы (меню, стоп-лист, рация) от
   * этого списка не зависят и должны открыться даже когда сеть моргнула.
   */
  const [штатЗагружен, setШтатЗагружен] = useState(false);
  useEffect(() => {
    const venueId = getSession()?.venueId;
    if (!identity || !venueId) return;
    let отменено = false;
    fetchStaff(venueId)
      .then((смена) => {
        if (отменено) return;
        setData((d) => ({ ...d, employees: смена.map(employeeFromStaff) }));
        setШтатЗагружен(true);
      })
      .catch(() => {
        if (!отменено) setШтатЗагружен(true);
      });
    return () => {
      отменено = true;
    };
  }, [identity?.employeeId]);

  // Выход из кабинета — это выход из платформы: гасим токен на сервере и
  // возвращаемся на экран входа.
  const logout = useCallback(() => void logoutSession(), []);


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

  // Приоритет руководителя меняет только порядок разделов, данных не касается.
  const [focus, setFocusState] = useState<ManagerFocus>('sales');
  const setFocus = useCallback<StoreValue['setFocus']>((f) => setFocusState(f), []);

  const promotePractice = useCallback<StoreValue['promotePractice']>((id) => {
    setData((d) => ({
      ...d,
      bestPractices: d.bestPractices.map((p) => (p.id === id ? { ...p, inTraining: true } : p)),
    }));
  }, []);

  /**
   * Карточка вошедшего. Собирается из настоящей сессии, а не ищется среди
   * сотрудников кабинета: их список приходит из API платформы и на части экранов
   * пока пуст. Раньше вошедшего подменяли демо-сотрудником — только чтобы `me`
   * нашёлся и экраны не были белыми, — и вместе с ним приезжали чужие цифры.
   */
  const me = useMemo<Employee | null>(() => {
    if (!identity) return null;
    const реальный = data.employees.find((e) => e.id === String(identity.employeeId));
    return реальный ?? meFromSession(identity.employeeId, identity.name, identity.role);
  }, [identity, data.employees]);

  const value = useMemo<StoreValue>(
    () => ({
      data,
      profile,
      session,
      me,
      venueName: identity?.venueName ?? '',
      staffLoaded: штатЗагружен,
      focus,
      setFocus,
      promotePractice,
      logout,
      addTest,
      assignTest,
      recordTestResult,
    }),
    [
      data,
      profile,
      session,
      me,
      identity?.venueName,
      штатЗагружен,
      focus,
      setFocus,
      promotePractice,
      logout,
      addTest,
      assignTest,
      recordTestResult,
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
