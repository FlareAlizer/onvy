export type Role = 'rop' | 'employee';

/** Отрасль компании. Определяет термины, метрики, базу знаний и сценарии. */
export type IndustryKey =
  | 'universal'
  | 'electronics'
  | 'diy'
  | 'furniture'
  | 'sport'
  | 'fashion'
  | 'horeca'
  | 'other';

export interface Company {
  id: string;
  name: string;
  industry: IndustryKey;
  staffSize: string;
  pointsPlanned: string;
  city: string;
  /** Код, по которому сотрудники присоединяются к компании. */
  joinCode: string;
  createdAt: string;
}

export interface SalesPoint {
  id: string;
  name: string;
  city: string;
  address: string;
  /** Отделы, зоны обслуживания — название поля берётся из профиля отрасли. */
  zones: string[];
  manager: string;
  staffCount: number;
  badgesOnline: number;
  /** План выручки на месяц, ₽ */
  plan: number;
  revenue: number;
  avgCheck: number;
  /** Количество взаимодействий с клиентами за месяц. */
  interactions: number;
  /** Доля взаимодействий с результатом, % */
  conversion: number;
  scriptCompliance: number;
  training: number;
  helpRequests: number;
  /** Отраслевые показатели: ключ метрики из профиля → значение. */
  industry: Record<string, number>;
}

/**
 * Приоритет руководителя. Роли по-прежнему две — меняется только то,
 * что выносится на первый экран и в каком порядке.
 */
export type ManagerFocus = 'culture' | 'operations' | 'sales';

export interface Account {
  id: string;
  role: Role;
  name: string;
  email: string;
  password: string;
  companyId: string;
  pointId?: string;
  position?: string;
  employeeId?: string;
  /** Только для руководителя. */
  focus?: ManagerFocus;
}

/** Удачная практика сотрудника, которую можно тиражировать. */
export interface BestPractice {
  id: string;
  employeeId: string;
  pointId: string;
  title: string;
  quote: string;
  effect: string;
  category: string;
  /** Диалог, из которого взята практика. */
  dialogId?: string;
  /** Практика уже превращена в учебный материал. */
  inTraining: boolean;
}

/** Связка «пробел → обучение → изменение поведения». */
export interface TrainingOutcome {
  testId: string;
  /** Почему тест назначен. */
  reason: string;
  /** Источник: диалог, частый вопрос, материал базы. */
  origin: string;
  /** Отслеживаемая метрика. */
  metric: string;
  metricLabel: string;
  before: number;
  after: number;
  unit: 'pct' | 'count' | 'sec';
  better: 'up' | 'down';
  /** Ошибка повторилась после обучения. */
  repeated: boolean;
}

/** Базовые показатели, одинаковые во всех отраслях. */
export interface EmployeeStats {
  revenue: number;
  /** Продажи или чеки — название берётся из профиля. */
  deals: number;
  /** Взаимодействия: консультации или обслуживания. */
  dialogs: number;
  avgCheck: number;
  conversion: number;
  scriptCompliance: number;
  responseSec: number;
  /** Доля вопросов, закрытых без помощи коллег, % */
  autonomy: number;
  /** Обращений за помощью за месяц. */
  helpRequests: number;
}

export interface SoldItem {
  name: string;
  qty: number;
  revenue: number;
}

export interface RequestTopic {
  label: string;
  count: number;
  conversion: number;
}

export type KpiPeriod = 'day' | 'week' | 'month';

export interface Kpi {
  id: string;
  employeeId: string;
  /** Ключ метрики из профиля отрасли. */
  metric: string;
  target: number;
  current: number;
  period: KpiPeriod;
  setBy: string;
  note?: string;
}

export interface Employee {
  id: string;
  name: string;
  position: string;
  pointId: string;
  hiredAt: string;
  onboarding: number;
  level: number;
  xp: number;
  badgeOnline: boolean;
  badgeBattery: number;
  /** Качество микрофона бейджа, % */
  micQuality: number;
  stats: EmployeeStats;
  /** Отраслевые показатели: ключ метрики из профиля → значение. */
  industry: Record<string, number>;
  /** Выручка по дням за последние 14 дней. */
  daily: number[];
  topItems: SoldItem[];
  topRequests: RequestTopic[];
  strengths: string[];
  growthAreas: string[];
  trainingDone: number;
  trainingTotal: number;
}

export type MomentType = 'win' | 'miss' | 'help';

export interface DialogMoment {
  id: string;
  /** Позиция на дорожке разговора, 0–100 % */
  at: number;
  type: MomentType;
  title: string;
  note: string;
}

export type Speaker = 'client' | 'employee' | 'ai' | 'colleague';

export interface TranscriptLine {
  id: string;
  at: number;
  speaker: Speaker;
  text: string;
  momentId?: string;
  /** Onvy не подтвердил информацию и отказался отвечать. */
  unverified?: boolean;
}

export type DialogOutcome = 'success' | 'lost' | 'consult';

export interface DialogItem {
  name: string;
  qty: number;
  price: number;
}

export interface Dialog {
  id: string;
  employeeId: string;
  pointId: string;
  startedAt: string;
  durationSec: number;
  outcome: DialogOutcome;
  revenue: number;
  scriptScore: number;
  /** Средняя скорость ответа в этом диалоге, сек. */
  responseSec: number;
  /** Категория вопроса — из категорий профиля отрасли. */
  category: string;
  topic: string;
  /** Товары или позиции заказа. */
  items: DialogItem[];
  /** Обращений к коллегам, складу, кухне. */
  helpRequests: number;
  /** В диалоге сработала подсказка Onvy. */
  hasCue: boolean;
  wave: number[];
  moments: DialogMoment[];
  transcript: TranscriptLine[];
  summary: string;
  recommendations: string[];
  /** Диалог записан демо-симуляцией из кабинета сотрудника. */
  simulated?: boolean;
}

export interface TestQuestion {
  id: string;
  question: string;
  options: string[];
  correct: number;
  explain: string;
  /** Откуда взят вопрос: раздел базы знаний или тип ошибки. */
  source: string;
}

export type TestSource = 'errors' | 'questions' | 'knowledge' | 'file' | 'prompt';

export interface Test {
  id: string;
  title: string;
  description: string;
  source: TestSource;
  sourceDetail: string;
  createdAt: string;
  createdBy: string;
  deadline: string;
  /** Проходной балл, % */
  passScore: number;
  questions: TestQuestion[];
  assignedTo: string[];
  /** Результаты: employeeId → процент правильных */
  results: Record<string, number>;
}

export type KnowledgeStatus = 'published' | 'draft' | 'outdated';

export interface FaqItem {
  id: string;
  question: string;
  /** Категория из базы знаний профиля. */
  category: string;
  count: number;
  /** Изменение частоты за неделю, % */
  trend: number;
  conversion: number;
  avgResponseSec: number;
  bestAnswer: string;
  weakSpot: string;
  source: string;
  updatedAt: string;
  status: KnowledgeStatus;
  /** Ответ подтверждён ответственным сотрудником. */
  verified: boolean;
}

export interface ScriptError {
  id: string;
  label: string;
  count: number;
  costPerMonth: number;
  employees: string[];
}

/** Показатель отчёта по пилоту: до и во время. */
export interface PilotMetric {
  key: string;
  label: string;
  before: number;
  during: number;
  unit: 'pct' | 'count' | 'sec' | 'money';
  /** Направление, в котором показатель считается улучшением. */
  better: 'up' | 'down';
  /** Данные из учётной системы, а не прямое измерение Onvy. */
  external?: boolean;
}

export interface PilotInfo {
  startedAt: string;
  weeks: number;
  scope: string;
  /** Приоритеты пилота — что именно проверяем. */
  goals: string[];
  metrics: PilotMetric[];
}

/** Показатели адаптации новых сотрудников. */
export interface AdaptationInfo {
  /** Среднее время до самостоятельной смены, дней. */
  daysToSolo: number;
  daysToSoloBefore: number;
  requiredModules: number;
  /** Процент завершения онбординга по компании. */
  completion: number;
  /** Средний результат первой проверки знаний, %. */
  firstCheckScore: number;
  /** Повторные ошибки после обучения, шт. */
  repeatedErrors: number;
  /** Обращений новичка к опытным коллегам за смену. */
  noviceHelpPerShift: number;
  /** Соблюдение стандартов в первые две недели, %. */
  earlyCompliance: number;
}

/** Загруженный в базу знаний источник — симуляция обработки файла. */
export interface KnowledgeSourceFile {
  id: string;
  name: string;
  sizeKb: number;
  uploadedAt: string;
  /** Ключ источника из профиля отрасли. */
  kind: string;
  categories: string[];
  records: number;
}

export interface AppData {
  /** Ключ демо-пространства, из которого собраны данные. */
  space: string;
  company: Company | null;
  points: SalesPoint[];
  accounts: Account[];
  employees: Employee[];
  kpis: Kpi[];
  dialogs: Dialog[];
  tests: Test[];
  faq: FaqItem[];
  scriptErrors: ScriptError[];
  knowledgeFiles: KnowledgeSourceFile[];
  pilot: PilotInfo | null;
  bestPractices: BestPractice[];
  trainingOutcomes: TrainingOutcome[];
  adaptation: AdaptationInfo | null;
}
