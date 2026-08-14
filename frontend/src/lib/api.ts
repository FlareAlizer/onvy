// Клиент API Onvy: JWT-сессия, автоматическое обновление токена, вебсокет по тикету.
//
// Токен живёт полчаса, смена — двенадцать. Значит обновление должно быть
// незаметным: официант не может оказаться разлогиненным посреди зала.
// Поэтому любой 401 один раз пробует refresh и повторяет запрос.

export type Session = {
  accessToken: string;
  refreshToken: string;
  employeeId: number;
  venueId: number;
  /** Название заведения — им подписан кабинет. Может отсутствовать у сессий,
   *  сохранённых до появления поля: тогда подпись просто пустая. */
  venueName?: string;
  role: string;
  name: string;
  language: string;
};

const KEY = 'onvy_session';

export function saveSession(session: Session): void {
  localStorage.setItem(KEY, JSON.stringify(session));
}

export function getSession(): Session | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Session;
    // Проверяем только токен. Раньше здесь стояло && parsed.employeeId —
    // и сессия с id=0 считалась невалидной, потому что ноль в JS ложный.
    // Из-за этого свежий вход рушился: запрос уходил без авторизации.
    return parsed?.accessToken ? parsed : null;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  localStorage.removeItem(KEY);
  // Кэш кабинета — тоже часть сессии. Он хранит смену прошлого заведения, и без
  // этой строки следующий вошедший видел в списке чужих людей, пока не приедет
  // его собственная смена. На общем телефоне это выглядит так, будто продукт
  // показывает чужие данные, — и по сути так и есть.
  localStorage.removeItem(CONSOLE_DATA_KEY);
}

/** Ключ кэша кабинета — он же в console/store.tsx. Держим здесь, чтобы выход
 *  чистил его вместе с сессией и это не забылось при следующей правке. */
export const CONSOLE_DATA_KEY = 'onvy.data.v3';

// --- Заведение этого телефона -------------------------------------------------
//
// Вход по PIN — это экран для смены в зале, и он показывает список сотрудников
// ДО всякой авторизации. Значит сервер должен знать, чьих сотрудников показать,
// а спросить не у кого: человек ещё не вошёл.
//
// Раньше номер заведения был зашит в сборку константой, и экран у всех показывал
// одну и ту же чужую смену: сотрудники нового заведения в списке не появлялись
// вовсе, а имена чужих — появлялись всем.
//
// Решение под реальную чайхану: телефон принадлежит заведению и никуда из него
// не уходит. Управляющий один раз входит на нём по почте — телефон запоминает
// заведение и дальше отдаёт его смене. Отдельный «код заведения» вводить не
// нужно, но если телефон настраивают без управляющего, номер можно ввести руками.
//
// PIN при этом может совпадать у людей из разных заведений, и это нормально:
// вход проверяет пару «конкретный сотрудник + его PIN», а не PIN сам по себе.
const DEVICE_VENUE_KEY = 'onvy_device_venue';

export function getDeviceVenue(): number | null {
  const raw = localStorage.getItem(DEVICE_VENUE_KEY);
  const id = Number(raw);
  return raw && Number.isFinite(id) && id > 0 ? id : null;
}

export function setDeviceVenue(venueId: number): void {
  localStorage.setItem(DEVICE_VENUE_KEY, String(venueId));
}

/**
 * Выйти из аккаунта: погасить токен на сервере, стереть сессию и вернуться на
 * экран входа.
 *
 * Единственный правильный способ выйти — все кнопки «Выйти» ведут сюда. Раньше
 * каждая делала своё: экран рации стирал localStorage, а кнопка в кабинете
 * чистила только внутреннее состояние консоли, после чего сессия собиралась
 * заново из платформенной — и выйти из кабинета было нельзя вообще.
 *
 * Сервер зовём первым, но его отказ выходу не мешает: телефон в зале теряет
 * вайфай, и человек, нажавший «Выйти», должен выйти в любом случае. Сессия
 * стирается всегда — этим же и заканчивается смена на общем телефоне.
 */
export async function logoutSession(): Promise<void> {
  const session = getSession();
  try {
    if (session) {
      await fetch('/api/auth/logout', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: session.refreshToken }),
      });
    }
  } catch {
    // Сети нет. Токен доживёт свой срок сам, но из этого браузера он исчезнет.
  } finally {
    clearSession();
    // Полная перезагрузка, а не переход по маршруту: она заодно рвёт вебсокет
    // рации и сбрасывает состояние всех экранов, включая демо-хранилище
    // консоли. Иначе следующий вошедший на этом телефоне увидел бы хвосты
    // предыдущей смены.
    location.replace('/');
  }
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function readError(resp: Response): Promise<string> {
  try {
    const body = await resp.json();
    return typeof body?.detail === 'string' ? body.detail : resp.statusText;
  } catch {
    return resp.statusText || String(resp.status);
  }
}

// Одно обновление на всё приложение одновременно. Без этого два запроса,
// одновременно получившие 401, дёрнули бы обновление вдвоём: второй пришёл бы
// с уже использованным токеном, и сервер имел бы полное право счесть это
// кражей и выкинуть официанта из смены. Держим одно обещание на всех.
let refreshInFlight: Promise<boolean> | null = null;

/** Обновить пару токенов. Возвращает false, если сессия окончательно мертва. */
function refreshSession(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;

  refreshInFlight = (async () => {
    const session = getSession();
    if (!session) return false;
    try {
      const resp = await fetch('/api/auth/refresh', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: session.refreshToken }),
      });
      if (!resp.ok) {
        clearSession();
        return false;
      }
      const tokens = await resp.json();
      saveSession({
        ...session,
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
      });
      return true;
    } catch {
      // Сеть отвалилась во время обновления. Сессию не стираем: телефон в зале
      // теряет вайфай постоянно, и терять из-за этого вход было бы жестоко.
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();

  return refreshInFlight;
}

type RequestOptions = RequestInit & { retryOnAuthFailure?: boolean };

async function request(path: string, options: RequestOptions = {}): Promise<Response> {
  const { retryOnAuthFailure = true, ...init } = options;
  const session = getSession();
  const headers = new Headers(init.headers);
  if (session) headers.set('Authorization', `Bearer ${session.accessToken}`);

  const resp = await fetch(`/api${path}`, { ...init, headers });
  if (resp.status !== 401 || !retryOnAuthFailure) return resp;

  // Токен протух посреди смены — обновляем и повторяем ровно один раз.
  if (!(await refreshSession())) return resp;
  return request(path, { ...options, retryOnAuthFailure: false });
}

export async function api<T = unknown>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const resp = await request(path, { ...options, headers });
  if (!resp.ok) throw new ApiError(await readError(resp), resp.status);
  return resp.status === 204 ? (null as T) : ((await resp.json()) as T);
}

/** Запрос без сессии — экран входа. */
export async function apiPublic<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }
  const resp = await fetch(`/api${path}`, { ...options, headers });
  if (!resp.ok) throw new ApiError(await readError(resp), resp.status);
  return (await resp.json()) as T;
}

type TokenPairResponse = {
  access_token: string;
  refresh_token: string;
  expires_in: number;
};

export type Me = {
  id: number;
  venue_id: number;
  venue_name: string;
  name: string;
  nickname: string | null;
  email: string | null;
  role: string;
  language: string;
};

/** Кто вошёл. По роли решается, какой кабинет показывать. */
export function fetchMe(): Promise<Me> {
  return api<Me>('/auth/me');
}

/** То же, но с явным токеном — для момента входа, когда сессии ещё нет. */
async function fetchMeWithToken(accessToken: string): Promise<Me> {
  const resp = await fetch('/api/auth/me', {
    headers: { Authorization: `Bearer ${accessToken}` },
  });
  if (!resp.ok) throw new ApiError(await readError(resp), resp.status);
  return (await resp.json()) as Me;
}

/** Собрать сессию из пары токенов: кто это — спрашиваем у сервера, не у клиента.
 *
 * Токен передаём в запрос напрямую и в хранилище пишем только готовую сессию.
 * Промежуточная запись «токен есть, остальное пустое» уже один раз стоила нам
 * рабочего входа, и полагаться на её валидность больше не будем.
 */
async function completeLogin(tokens: TokenPairResponse): Promise<Session> {
  const me = await fetchMeWithToken(tokens.access_token);
  const session: Session = {
    accessToken: tokens.access_token,
    refreshToken: tokens.refresh_token,
    employeeId: me.id,
    venueId: me.venue_id,
    venueName: me.venue_name,
    role: me.role,
    name: me.name,
    language: me.language,
  };
  saveSession(session);
  // Телефон запоминает заведение вошедшего: дальше смена входит на нём по PIN,
  // и экран выбора покажет своих, а не чужих.
  setDeviceVenue(me.venue_id);
  return session;
}

/** Вход по почте и паролю — основной способ. */
export async function loginWithEmail(email: string, password: string): Promise<Session> {
  const tokens = await apiPublic<TokenPairResponse>('/auth/login-email', {
    method: 'POST',
    body: JSON.stringify({ email: email.trim(), password }),
  });
  return completeLogin(tokens);
}

export type SignupRequest = {
  venue_name: string;
  manager_name: string;
  email: string;
  password: string;
};

/** Зарегистрировать заведение. Токены приходят сразу — второй раз пароль не спрашиваем. */
export async function signupVenue(payload: SignupRequest): Promise<Session> {
  const result = await apiPublic<TokenPairResponse & { venue_id: number; venue_name: string }>(
    '/signup/venue',
    { method: 'POST', body: JSON.stringify(payload) },
  );
  return completeLogin(result);
}

/** Быстрый вход по PIN — для смены в зале, где почту вводить неудобно.
 *
 * Сессию собирает completeLogin по ответу /auth/me. Раньше экран входа строил её
 * сам и подставлял номер заведения из константы сборки — у сотрудника чужой
 * точки сессия указывала не туда. Кто вошёл и куда относится, знает сервер. */
export async function loginWithPin(employeeId: number, pin: string): Promise<Session> {
  const tokens = await apiPublic<TokenPairResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ employee_id: employeeId, pin }),
  });
  return completeLogin(tokens);
}

export type StageMetrics = {
  asr_ms: number;
  search_ms: number;
  answer_ms: number;
  tts_ms: number;
  total_ms: number;
};

export type VoiceResult = {
  intent: 'ask' | 'send_group' | 'send_person' | 'empty' | 'ignored';
  query_text: string;
  answer_text: string;
  audio_base64: string | null;
  mime_type: string;
  grounded_on: string[];
  degraded: 'asr' | 'answer' | 'tts' | null;
  delivered_to: number[];
  group: string | null;
  person_name: string | null;
  metrics: StageMetrics;
};

/** Кому уходит голосовая реплика, если во фразе не назвали адресата. */
export type VoiceTarget = { group?: string; employeeId?: number };

/** Отправить запись с кнопки.
 *
 * target — то, что выбрано на экране. Сервер применяет его только когда в самой
 * фразе обращения не было: сказанное вслух («кухня, два лагмана») всегда
 * сильнее выбранного пальцем.
 */
export async function sendVoice(
  blob: Blob,
  alwaysOn = false,
  target?: VoiceTarget,
): Promise<VoiceResult> {
  const form = new FormData();
  form.append('audio', blob, 'clip.pcm');
  form.append('always_on', String(alwaysOn));
  if (target?.employeeId !== undefined) form.append('to_employee_id', String(target.employeeId));
  else if (target?.group) form.append('to_group', target.group);
  const resp = await request('/voice/push-to-talk', { method: 'POST', body: form });
  if (!resp.ok) throw new ApiError(await readError(resp), resp.status);
  return (await resp.json()) as VoiceResult;
}

/** Открыть канал рации. Тикет одноразовый и живёт меньше минуты. */
export async function openCommsSocket(): Promise<WebSocket> {
  const { ticket } = await api<{ ticket: string }>('/auth/ws-ticket', { method: 'POST' });
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return new WebSocket(`${proto}://${location.host}/api/ws/comms?ticket=${encodeURIComponent(ticket)}`);
}

export type IncomingMessage = {
  type: 'voice' | 'text';
  utterance_id: number;
  from_id: number;
  from_name: string;
  text: string;
  language: string;
  translated: boolean;
  translation_failed: boolean;
  audio_base64: string | null;
  mime_type: string;
};

/** Проиграть ответ ассистента или голос коллеги. */
export function playAudio(base64: string, mime = 'audio/mpeg'): Promise<void> {
  return new Audio(`data:${mime};base64,${base64}`).play().catch(() => undefined);
}

// --- KPI (app/api/kpi.py) -------------------------------------------------
//
// --- Обучение и тесты ---------------------------------------------------------
//
// Типы повторяют app/schemas/training.py дословно. До этого кабинет держал тесты
// в памяти браузера: управляющий собирал тест, назначал его смене — и всё это
// исчезало при перезаходе, а до сотрудника не доходило никогда.

export type TestQuestionIn = {
  question: string;
  options: string[];
  correct_index: number;
  explain?: string | null;
  source?: string | null;
};

export type TestCreateIn = {
  title: string;
  description?: string;
  /** Один из TEST_SOURCES: errors, questions, knowledge, file, prompt. */
  source: string;
  source_detail?: string;
  deadline?: string | null;
  pass_score?: number;
  questions: TestQuestionIn[];
};

export type TestQuestionOut = {
  id: number;
  position: number;
  question: string;
  options: string[];
  correct_index: number;
  explain: string | null;
  source: string | null;
};

export type TestResultSummary = {
  employee_id: number;
  score_percent: number;
  passed: boolean;
  completed_at: string;
};

export type TestOut = {
  id: number;
  title: string;
  description: string;
  source: string;
  source_detail: string;
  created_at: string;
  created_by_employee_id: number;
  deadline: string | null;
  pass_score: number;
  questions: TestQuestionOut[];
  assigned_employee_ids: number[];
  results: TestResultSummary[];
};

export type TestForEmployee = {
  id: number;
  title: string;
  description: string;
  deadline: string | null;
  pass_score: number;
  questions: { id: number; position: number; question: string; options: string[] }[];
  completed: boolean;
  score_percent: number | null;
};

export type TestReviewQuestion = {
  id: number;
  position: number;
  question: string;
  options: string[];
  correct_index: number;
  given_index: number;
  is_correct: boolean;
};

export type TestResult = {
  test_id: number;
  employee_id: number;
  score_percent: number;
  passed: boolean;
  completed_at: string;
  review: TestReviewQuestion[];
};

export function createTest(venueId: number, payload: TestCreateIn): Promise<TestOut> {
  return api<TestOut>(`/venues/${venueId}/tests`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

export function fetchTests(venueId: number): Promise<TestOut[]> {
  return api<TestOut[]>(`/venues/${venueId}/tests`);
}

export function assignTest(
  venueId: number,
  testId: number,
  employeeIds: number[],
): Promise<TestOut> {
  return api<TestOut>(`/venues/${venueId}/tests/${testId}/assign`, {
    method: 'POST',
    body: JSON.stringify({ employee_ids: employeeIds }),
  });
}

/** Мои назначенные тесты — кабинет сотрудника. Без правильных ответов. */
export function fetchMyTests(venueId: number): Promise<TestForEmployee[]> {
  return api<TestForEmployee[]>(`/venues/${venueId}/tests/mine`);
}

export function submitTest(
  venueId: number,
  testId: number,
  answers: number[],
): Promise<TestResult> {
  return api<TestResult>(`/venues/${venueId}/tests/${testId}/submit`, {
    method: 'POST',
    body: JSON.stringify({ answers }),
  });
}

/** Вопрос, на который ассистент не нашёл ответа — app/schemas/staff.py FaqGapOut. */
export type FaqGap = {
  question: string;
  miss_count: number;
  last_asked_at: string;
  sample_query: string;
};

/**
 * Где смена спотыкается на самом деле.
 *
 * Это настоящие вопросы из зала, на которые ассистент не смог ответить по меню:
 * дыра либо в техкарте, либо в знании смены. Единственный честный источник для
 * режима «тест по ошибкам» — разбора диалогов у нас нет и в пилот он не входит.
 */
export function fetchFaqGaps(venueId: number, days = 30): Promise<FaqGap[]> {
  return api<FaqGap[]>(`/venues/${venueId}/faq/gaps?days=${days}`);
}

/** Кто на смене прямо сейчас — дословно app/schemas/insights.py PresenceOut. */
export type Presence = {
  online_employee_ids: number[];
  online_names: string[];
};

/**
 * Кто сейчас на связи, по данным сервера.
 *
 * До этого экраны гадали сами: кабинет считал всех офлайн (поле в карточке
 * никем не заполнялось), а экран смены считал «в эфире» того, кто говорил по
 * рации последние пять минут. Молчащий человек с включённым телефоном при этом
 * числился вне сети — и управляющий видел пустую смену там, где все на месте.
 */
export function fetchPresence(venueId: number): Promise<Presence> {
  return api<Presence>(`/venues/${venueId}/presence`);
}

/** Сотрудник точки — дословно app/schemas/staff.py EmployeeOut. */
export type StaffMember = {
  id: number;
  name: string;
  nickname: string | null;
  role: string;
  language: string;
  is_active: boolean;
  hired_at: string;
};

/**
 * Смена точки. Управляющий в списке есть — он такой же сотрудник, и цель себе
 * ставит через тот же список.
 *
 * До этого кабинет ни разу не спрашивал у сервера, кто в смене: список брался
 * из пустого локального хранилища и был пуст ВСЕГДА, даже у заведения с полным
 * штатом. Из-за этого раздел «Сотрудники и KPI» выглядел одинаково у нового
 * заведения и у работающего — и поставить цель подчинённому было некому.
 */
export function fetchStaff(venueId: number): Promise<StaffMember[]> {
  return api<StaffMember[]>(`/venues/${venueId}/staff`);
}

// Метрики, которые Onvy реально считает — app/db/models/enums.py KPI_METRICS.
// Выручка, средний чек и конверсия сюда сознательно не входят: без интеграции
// с кассой их не из чего посчитать, а цель без источника — это ложь управляющему.

export type KpiMetric = 'dialogs' | 'response_sec' | 'autonomy' | 'help_requests';
export type KpiPeriod = 'day' | 'week' | 'month';

export type KpiSetIn = {
  metric: KpiMetric;
  /** Decimal на бэкенде — тем же способом, что и цены меню, отдаём как есть. */
  target: number;
  period: KpiPeriod;
  note?: string;
};

/** Дословно app/schemas/kpi.py KpiOut. current/progress_percent — null значит
 *  "по этой метрике за окно ещё нет данных", а не 0: показывать нужно прочерк. */
export type KpiOut = {
  id: number;
  employee_id: number;
  metric: string;
  target: string | number;
  current: number | null;
  progress_percent: number | null;
  period: KpiPeriod;
  period_start: string;
  period_end: string;
  set_by_employee_id: number;
  note: string | null;
};

/** Поставить/обновить цель одному сотруднику (управляющий может и себе — он тоже сотрудник точки). */
export function setEmployeeKpi(venueId: number, employeeId: number, payload: KpiSetIn): Promise<KpiOut> {
  return api<KpiOut>(`/venues/${venueId}/employees/${employeeId}/kpi`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/** Та же цель — сразу всем активным сотрудникам точки. */
export function setKpiForAllEmployees(venueId: number, payload: KpiSetIn): Promise<KpiOut[]> {
  return api<KpiOut[]>(`/venues/${venueId}/kpi/bulk`, {
    method: 'POST',
    body: JSON.stringify(payload),
  });
}

/** Все цели точки — кабинет руководителя. */
export function fetchVenueKpis(venueId: number): Promise<KpiOut[]> {
  return api<KpiOut[]>(`/venues/${venueId}/kpi`);
}

/** Цели одного сотрудника — свои видит он сам, чужие только управляющий. */
export function fetchEmployeeKpis(venueId: number, employeeId: number): Promise<KpiOut[]> {
  return api<KpiOut[]>(`/venues/${venueId}/employees/${employeeId}/kpi`);
}
