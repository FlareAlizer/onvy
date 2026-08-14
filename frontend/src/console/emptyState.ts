// Чистое состояние кабинета: ни одной выдуманной цифры.
//
// Раньше здесь стояли три готовых демо-пространства на 3200 строк — витрина
// консоли до переноса в платформу. Внутри продукта они опасны: управляющий
// принимает демо-выручку за свою. Пустой экран честнее придуманного числа,
// а на пилоте нам нужно видеть, какие разделы наполнены настоящими данными,
// а какие пока пусты.
//
// Настоящие данные приходят из API платформы (app/api/*). Экраны, которые к нему
// ещё не подключены, показывают пустое состояние — это и есть чистая картина.

import type { TestOut } from '../lib/api';
import type { Account, AppData, Employee, Role, Test, TestSource } from './types';

export const PERIOD_LABEL: Record<string, string> = {
  day: 'на день',
  week: 'на неделю',
  month: 'на месяц',
};

/** Пространство без данных — состояние по умолчанию. */
export function emptyData(): AppData {
  return {
    space: 'onvy',
    company: null,
    points: [],
    accounts: [],
    employees: [],
    kpis: [],
    dialogs: [],
    tests: [],
    faq: [],
    scriptErrors: [],
    knowledgeFiles: [],
    pilot: null,
    bestPractices: [],
    trainingOutcomes: [],
    adaptation: null,
  };
}

const ROLE_POSITION: Record<Role, string> = {
  rop: 'Управляющий',
  employee: 'Сотрудник',
};

/** Роль из базы платформы — в должность на экране. */
const ДОЛЖНОСТЬ_ПО_РОЛИ: Record<string, string> = {
  manager: 'Управляющий',
  waiter: 'Официант',
  kitchen: 'Кухня',
  bar: 'Бар',
  host: 'Хостес',
};

/**
 * Сотрудник смены из настоящей базы — в карточку кабинета.
 *
 * Показатели остаются нулями: их считает бэкенд, и до подключения
 * соответствующих экранов брать их неоткуда. Ноль здесь — не «работал плохо»,
 * а «мы этого пока не показываем»; экраны, которые эти поля рисуют, обязаны
 * говорить, что источника нет (см. подписи «нет источника» в Staff.tsx).
 */
export function employeeFromStaff(член: {
  id: number;
  name: string;
  nickname: string | null;
  role: string;
  hired_at: string;
}): Employee {
  const базовый = meFromSession(член.id, член.name, 'employee');
  return {
    ...базовый,
    position: ДОЛЖНОСТЬ_ПО_РОЛИ[член.role] ?? член.role,
    hiredAt: член.hired_at,
  };
}

/**
 * Карточка вошедшего, собранная из настоящей сессии платформы.
 *
 * Раньше вошедшего привязывали к первому подходящему демо-сотруднику — иначе
 * `me` был null и экраны оставались белыми. Вместе с ним приезжали и чужие
 * цифры. Теперь карточка настоящая, а всё, что мы про человека пока не знаем,
 * честно равно нулю: эти показатели считает бэкенд, и они появятся, когда
 * соответствующий экран к нему подключат.
 */
export function meFromSession(employeeId: number, name: string, role: Role): Employee {
  return {
    id: String(employeeId),
    name,
    position: ROLE_POSITION[role],
    pointId: '',
    hiredAt: '',
    onboarding: 0,
    level: 0,
    xp: 0,
    badgeOnline: false,
    badgeBattery: 0,
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
    daily: [],
    topItems: [],
    topRequests: [],
    strengths: [],
    growthAreas: [],
    trainingDone: 0,
    trainingTotal: 0,
  };
}

/** Аккаунт консоли для вошедшего в платформу. */
export function accountFromSession(
  employeeId: number,
  name: string,
  role: Role,
  email = '',
): Account {
  return {
    id: `platform-${employeeId}`,
    role,
    name,
    email,
    password: '',
    companyId: '',
    position: ROLE_POSITION[role],
    employeeId: String(employeeId),
  };
}


/**
 * Тест из базы — в форму, которую понимают экраны кабинета.
 *
 * Формы разные исторически: кабинет писался под своё локальное хранилище, а
 * бэкенд — под API платформы. Переводим здесь, в одном месте, вместо того чтобы
 * переписывать семь экранов: так база остаётся единственным источником, а вид
 * данных на экранах не меняется.
 */
export function testFromApi(тест: TestOut): Test {
  return {
    id: String(тест.id),
    title: тест.title,
    description: тест.description,
    source: тест.source as TestSource,
    sourceDetail: тест.source_detail,
    createdAt: тест.created_at.slice(0, 10),
    createdBy: '',
    deadline: тест.deadline ?? '',
    passScore: тест.pass_score,
    questions: тест.questions.map((в) => ({
      id: String(в.id),
      question: в.question,
      options: в.options,
      correct: в.correct_index,
      explain: в.explain ?? '',
      source: в.source ?? '',
    })),
    assignedTo: тест.assigned_employee_ids.map(String),
    results: Object.fromEntries(
      тест.results.map((р) => [String(р.employee_id), р.score_percent]),
    ),
  };
}
