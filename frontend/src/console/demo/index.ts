import type { AppData, Dialog, Employee, IndustryKey } from '../types';
import { electronicsSpace } from './electronics';
import { diySpace } from './diy';
import { horecaSpace } from './horeca';
import { makeWave } from './shared';

export interface DemoSpaceDef {
  key: string;
  label: string;
  hint: string;
  industry: IndustryKey;
  make: () => AppData;
}

/** Готовые демо-пространства. Каждое — своя отрасль на одном и том же ядре. */
export const DEMO_SPACES: DemoSpaceDef[] = [
  {
    key: 'horeca',
    label: 'Чайхона №1',
    hint: '3 ресторана · 7 официантов',
    industry: 'horeca',
    make: horecaSpace,
  },
  {
    key: 'electronics',
    label: 'Розничная сеть · электроника',
    hint: 'Стартех · 4 магазина · 8 консультантов',
    industry: 'electronics',
    make: electronicsSpace,
  },
  {
    key: 'diy',
    label: 'DIY и строительные материалы',
    hint: 'Мастерский · 3 гипермаркета · 7 консультантов',
    industry: 'diy',
    make: diySpace,
  },
];

export const DEFAULT_SPACE = 'horeca';

export function makeSpace(key: string): AppData {
  return (DEMO_SPACES.find((s) => s.key === key) ?? DEMO_SPACES[0]).make();
}

/** Пустая компания — состояние после регистрации, без демо-данных. */
export function emptyData(space: string): AppData {
  return {
    space,
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

interface ScenarioStep {
  speaker: 'client' | 'employee' | 'ai' | 'colleague';
  text: string;
  moment?: { type: 'win' | 'miss' | 'help'; title: string; note: string };
  unverified?: boolean;
}

interface Scenario {
  category: string;
  topic: string;
  items: { name: string; qty: number; price: number }[];
  steps: ScenarioStep[];
  summary: string;
  recommendations: string[];
  scriptScore: number;
  responseSec: number;
}

/**
 * Сценарии демо-диалога по отраслям. Кнопка «Запустить демо-диалог»
 * в кабинете сотрудника проигрывает подходящий и кладёт результат в аналитику РОПа.
 */
const SCENARIOS: Partial<Record<IndustryKey, Scenario>> = {
  horeca: {
    category: 'Аллергены',
    topic: 'Демо-обслуживание: аллергены и стоп-лист',
    items: [
      { name: 'Люля-кебаб из баранины', qty: 2, price: 1_400 },
      { name: 'Салат «Ташкент»', qty: 1, price: 450 },
      { name: 'Айран', qty: 2, price: 400 },
    ],
    scriptScore: 88,
    responseSec: 3.4,
    steps: [
      { speaker: 'client', text: 'Добрый вечер! Что посоветуете из мяса? И скажите, в люля есть орехи — у меня аллергия.' },
      {
        speaker: 'ai',
        text: 'Информация не подтверждена. Вопрос касается аллергена — уточните состав у кухни или в карте блюда, не отвечайте по памяти.',
        unverified: true,
        moment: { type: 'win', title: 'Onvy остановил ответ по памяти', note: 'На вопрос об аллергене система не даёт догадку, а требует подтверждения. Это защита гостя и ресторана.' },
      },
      { speaker: 'employee', text: 'Секунду, уточню у кухни — по аллергенам отвечаю только точно.', moment: { type: 'help', title: 'Уточнил состав у кухни', note: 'Правильное действие: по аллергену подтверждение обязательно.' } },
      { speaker: 'colleague', text: 'В люля из баранины орехов нет. Есть зира и кориандр.' },
      { speaker: 'employee', text: 'Уточнил: орехов в люля нет, из специй — зира и кориандр. Если на них реакции нет, блюдо безопасно.', moment: { type: 'win', title: 'Дал подтверждённый ответ', note: 'Гость получил факт, а не предположение.' } },
      { speaker: 'client', text: 'Отлично. Тогда два люля и салат «Ташкент». И долму ещё.' },
      { speaker: 'ai', text: 'Подсказка: долма в стоп-листе с 18:40. Ближайшая замена — манты с бараниной.' },
      { speaker: 'employee', text: 'Долма сегодня закончилась, могу предложить манты — тот же формат подачи. Или оставим два люля и салат?', moment: { type: 'win', title: 'Проверил стоп-лист до подтверждения', note: 'Замена предложена сразу, заказ не пришлось исправлять при госте.' } },
      { speaker: 'client', text: 'Давайте без мантов, хватит.' },
      { speaker: 'ai', text: 'Подсказка: к баранине предложите айран — сбивает жирность, берут в 71 % заказов.' },
      { speaker: 'employee', text: 'К баранине очень хорошо идёт айран. Возьмёте пару?', moment: { type: 'win', title: 'Предложил напиток', note: 'Этап стандарта выполнен, чек вырос на 400 ₽.' } },
      { speaker: 'client', text: 'Давайте.' },
      { speaker: 'employee', text: 'Принял заказ. Приятного вечера!', moment: { type: 'miss', title: 'Не предложен десерт', note: 'Чак-чак к чаю после горячего — резерв ещё 400–800 ₽ к чеку.' } },
    ],
    summary:
      'Демо-обслуживание записано. Ключевое сделано верно: на вопрос об аллергене официант не ответил по памяти, а подтвердил состав у кухни; стоп-лист проверен до подтверждения заказа, напиток предложен. Не хватило только десерта.',
    recommendations: [
      'Аллергены — единственный случай, где догадка недопустима. Подтверждение у кухни обязательно.',
      'Проверка стоп-листа до подтверждения заказа полностью убирает исправления при госте.',
      'Добавьте десерт к чаю в конце — это самый простой прирост чека.',
    ],
  },
  electronics: {
    category: 'Выбор техники',
    topic: 'Демо-консультация: выбор смартфона',
    items: [
      { name: 'iPhone 15 Pro 256 ГБ', qty: 1, price: 110_000 },
      { name: 'Защитное стекло', qty: 1, price: 1_500 },
    ],
    scriptScore: 84,
    responseSec: 3.2,
    steps: [
      { speaker: 'client', text: 'Здравствуйте, выбираю смартфон. Не пойму, стоит ли переплачивать за Pro.' },
      { speaker: 'employee', text: 'Давайте разберёмся по задаче. Что для вас важнее — камера, игры или просто чтобы долго работал?', moment: { type: 'win', title: 'Выявил потребность до показа', note: 'Вопрос о задаче до витрины — этап №1 скрипта.' } },
      { speaker: 'client', text: 'Много снимаю, особенно детей на улице.' },
      { speaker: 'ai', text: 'Подсказка: под съёмку движения — 5x телефото и улучшенная стабилизация. Это два ключевых отличия Pro.' },
      { speaker: 'employee', text: 'Тогда Pro оправдан: пятикратный зум и лучше стабилизация — ребёнок в движении не смажется.', moment: { type: 'win', title: 'Назвал отличия под задачу', note: 'Два аргумента вместо списка характеристик.' } },
      { speaker: 'client', text: 'А если разобью? Дорогая ведь вещь.' },
      { speaker: 'ai', text: 'Подсказка: прямой запрос на защиту покупки. Предложите расширенную гарантию — 12 000 ₽ к чеку.' },
      { speaker: 'employee', text: 'Возьмите защитное стекло, оно недорогое.', moment: { type: 'miss', title: 'Не предложил расширенную гарантию', note: 'Клиент сам обозначил страх повредить технику. Стекло закрывает вопрос частично.' } },
      { speaker: 'client', text: 'Хорошо, берём Pro и стекло.' },
      { speaker: 'employee', text: 'Отлично, оформляю.', moment: { type: 'win', title: 'Закрыл сделку без затягивания', note: 'От согласия до кассы — меньше минуты.' } },
    ],
    summary:
      'Демо-консультация записана. Потребность выявлена до показа товара, отличия названы под задачу клиента. Упущена расширенная гарантия — клиент сам дал сигнал фразой «а если разобью».',
    recommendations: [
      '«А если разобью» — это запрос на гарантию, а не на стекло. Предлагайте её первой.',
      'Приём «два отличия под задачу» работает. Закрепите формулировку.',
    ],
  },
  diy: {
    category: 'Подбор материала',
    topic: 'Демо-консультация: подбор грунтовки',
    items: [
      { name: 'Грунтовка глубокого проникновения, 10 л', qty: 2, price: 4_800 },
      { name: 'Штукатурка гипсовая, 30 кг', qty: 14, price: 29_400 },
    ],
    scriptScore: 86,
    responseSec: 3.6,
    steps: [
      { speaker: 'client', text: 'Здравствуйте, нужна грунтовка. Буду штукатурить стены.' },
      { speaker: 'employee', text: 'Уточню сразу: какое основание — кирпич, бетон, газобетон? И помещение отапливается?', moment: { type: 'win', title: 'Уточнил основание до подбора', note: 'Без основания рекомендация превращается в угадывание.' } },
      { speaker: 'client', text: 'Газобетон. Отапливается, ремонт в квартире.' },
      { speaker: 'ai', text: 'Подсказка: газобетон сильно впитывает. Нужна грунтовка глубокого проникновения в два слоя, универсальная не подойдёт.' },
      { speaker: 'employee', text: 'Тогда берём глубокого проникновения и наносим в два слоя. Универсальная на газобетоне не удержит штукатурку.', moment: { type: 'win', title: 'Рекомендовал совместимый состав', note: 'Ошибка совместимости на этом основании — самая частая причина рекламаций.' } },
      { speaker: 'client', text: 'Понял. А сколько нужно?' },
      { speaker: 'employee', text: 'Какая площадь? Посчитаем точно, чтобы не ездить второй раз.', moment: { type: 'win', title: 'Посчитал расход при клиенте', note: 'Расчёт удерживает клиента и добавляет материалы в чек.' } },
      { speaker: 'client', text: 'Восемнадцать квадратов.' },
      { speaker: 'employee', text: '18 квадратов в два слоя — две канистры по 10 литров. Штукатурки при слое 10 мм понадобится 14 мешков.' },
      { speaker: 'ai', text: 'Подсказка: предупредите о межслойной сушке и предложите маяки — без них слой не вывести.' },
      { speaker: 'employee', text: 'Оформляем. Второй слой грунта — только после высыхания первого.', moment: { type: 'miss', title: 'Не предложены маяки и правило', note: 'Сопутствующие материалы следуют из технологии работ. Клиент вернётся за ними отдельно.' } },
    ],
    summary:
      'Демо-консультация записана. Основание уточнено до подбора, состав рекомендован совместимый, расход посчитан при клиенте. Не собраны сопутствующие материалы, хотя технология их требует.',
    recommendations: [
      'После расчёта объёма сразу добавляйте маяки, правило и сетку — это часть работ, а не допродажа.',
      'Связка «основание — расчёт — технология» отработана верно, продолжайте.',
    ],
  },
};

/** Сценарий по умолчанию — для отраслей без готового демо-диалога. */
const FALLBACK: Scenario = SCENARIOS.electronics!;

/** Собирает записанный диалог из сценария отрасли. */
export function makeDemoDialog(
  industry: IndustryKey,
  employee: Employee,
  seq: number,
): Dialog {
  const sc = SCENARIOS[industry] ?? FALLBACK;
  const total = sc.steps.length;
  const durationSec = 180 + total * 22;
  const moments: Dialog['moments'] = [];
  const transcript: Dialog['transcript'] = [];

  sc.steps.forEach((step, i) => {
    const at = Math.round(((i + 1) / (total + 1)) * durationSec);
    const lineId = `sl${seq}-${i}`;
    let momentId: string | undefined;
    if (step.moment) {
      momentId = `sm${seq}-${i}`;
      moments.push({
        id: momentId,
        at: Math.round(((i + 1) / (total + 1)) * 100),
        type: step.moment.type,
        title: step.moment.title,
        note: step.moment.note,
      });
    }
    transcript.push({
      id: lineId,
      at,
      speaker: step.speaker,
      text: step.text,
      momentId,
      unverified: step.unverified,
    });
  });

  return {
    id: `sim${seq}-${Date.now().toString(36)}`,
    employeeId: employee.id,
    pointId: employee.pointId,
    startedAt: new Date().toISOString().slice(0, 19),
    durationSec,
    outcome: 'success',
    revenue: sc.items.reduce((a, it) => a + it.price, 0),
    scriptScore: sc.scriptScore,
    responseSec: sc.responseSec,
    category: sc.category,
    topic: sc.topic,
    items: sc.items,
    helpRequests: sc.steps.filter((s) => s.moment?.type === 'help').length,
    hasCue: true,
    wave: makeWave(1000 + seq),
    moments,
    transcript,
    summary: sc.summary,
    recommendations: sc.recommendations,
    simulated: true,
  };
}
