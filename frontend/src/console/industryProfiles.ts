import type { IndustryKey } from './types';

/**
 * Отраслевой профиль — единственное место, где живёт специфика бизнеса.
 * Компоненты не знают, магазин это или ресторан: они берут названия,
 * метрики и категории отсюда.
 */

export type MetricUnit = 'money' | 'pct' | 'count' | 'sec';

export interface MetricDef {
  key: string;
  label: string;
  unit: MetricUnit;
  /** Короткое пояснение под цифрой. */
  hint?: string;
  /** Показатель приходит из учётной системы, а не измеряется Onvy напрямую. */
  external?: boolean;
  /** Меньше — лучше (скорость ответа, обращения за помощью). */
  lowerIsBetter?: boolean;
}

export interface KnowledgeSourceDef {
  key: string;
  label: string;
  hint: string;
}

export interface IndustryLabels {
  /** Название отрасли для выбора при регистрации. */
  industry: string;
  industryHint: string;
  client: string;
  clientPlural: string;
  /** «вопросы …», «ответ на вопрос …» */
  clientGenitivePlural: string;
  employee: string;
  employeePlural: string;
  employeeRoles: string[];
  location: string;
  locationPlural: string;
  /** Формы для счёта: 1 ресторан, 3 ресторана, 5 ресторанов. */
  locationForms: [string, string, string];
  /** Взаимодействие с клиентом: консультация, обслуживание. */
  interaction: string;
  interactionPlural: string;
  /** Формы для счёта: 1 консультация, 3 консультации, 5 консультаций. */
  interactionForms: [string, string, string];
  /** «после каждого закрытого …» */
  interactionGenitive: string;
  /** «аналитика …», «разбор …» */
  interactionGenitivePlural: string;
  /** Результат взаимодействия: продажа, заказ. */
  outcome: string;
  outcomePlural: string;
  outcomeLost: string;
  /** Каталог знаний: ассортимент, меню. */
  catalog: string;
  /** Проверка доступности: остатки, стоп-лист. */
  availability: string;
  /** Дополнительная продажа: аксессуар, десерт. */
  upsell: string;
  /** К кому обращается сотрудник за помощью. */
  helpTarget: string;
  /** «обратиться к …» */
  helpTargetDative: string;
  /** «уточнить у …» */
  helpTargetGenitive: string;
  /** Рабочие зоны точки: отделы, зоны обслуживания. */
  zones: string;
  zonesPlaceholder: string;
  /** Позиции в чеке: товары, блюда. */
  items: string;
  /** Рабочий скрипт: скрипт продаж, стандарт обслуживания. */
  script: string;
  /** Плашка устройства. */
  device: string;
}

export interface IndustryProfile {
  key: IndustryKey;
  labels: IndustryLabels;
  /** Отраслевые метрики поверх универсального ядра. */
  metrics: MetricDef[];
  /** Из чего можно поставить KPI — универсальные плюс отраслевые. */
  kpiMetrics: MetricDef[];
  /** Источники базы знаний, которые загружает РОП. */
  knowledgeSources: KnowledgeSourceDef[];
  /** Категории вопросов и материалов. */
  categories: string[];
  /** Этапы рабочего скрипта. */
  scriptStages: string[];
  /** Типовые ошибки в диалоге. */
  errorTypes: string[];
  /** Направления обучения. */
  trainingCategories: string[];
  /** Дополнительные источники для генератора тестов. */
  testSources: string[];
  /** Пример подсказки Onvy — показывается на экране входа. */
  cues: { q: string; a: string }[];
}

/** Универсальное ядро: эти метрики Onvy измеряет в любой отрасли. */
export const CORE_METRICS: MetricDef[] = [
  { key: 'revenue', label: 'Выручка', unit: 'money', external: true },
  { key: 'deals', label: 'Продажи', unit: 'count', external: true },
  { key: 'dialogs', label: 'Взаимодействия', unit: 'count' },
  { key: 'avgCheck', label: 'Средний чек', unit: 'money', external: true },
  { key: 'conversion', label: 'Результативность', unit: 'pct' },
  { key: 'scriptCompliance', label: 'Выполнение скрипта', unit: 'pct' },
  { key: 'responseSec', label: 'Скорость ответа', unit: 'sec', lowerIsBetter: true },
  { key: 'autonomy', label: 'Решено самостоятельно', unit: 'pct' },
  { key: 'helpRequests', label: 'Обращения за помощью', unit: 'count', lowerIsBetter: true },
];

/** Ядро с подставленными отраслевыми названиями. */
function coreFor(labels: IndustryLabels): MetricDef[] {
  return CORE_METRICS.map((m) =>
    m.key === 'deals'
      ? { ...m, label: labels.outcomePlural }
      : m.key === 'dialogs'
        ? { ...m, label: labels.interactionPlural }
        : m.key === 'helpRequests'
          ? { ...m, label: `Обращения: ${labels.helpTarget.toLowerCase()}` }
          : m,
  );
}

const RETAIL_LABELS: IndustryLabels = {
  industry: 'Универсальный ритейл',
  industryHint: 'Розничная сеть с консультантами в зале',
  client: 'Покупатель',
  clientPlural: 'Покупатели',
  clientGenitivePlural: 'покупателей',
  employee: 'Консультант',
  employeePlural: 'Консультанты',
  employeeRoles: ['Стажёр', 'Консультант', 'Старший консультант'],
  location: 'Магазин',
  locationPlural: 'Магазины',
  locationForms: ['магазин', 'магазина', 'магазинов'],
  interaction: 'Консультация',
  interactionPlural: 'Консультации',
  interactionForms: ['консультация', 'консультации', 'консультаций'],
  interactionGenitive: 'консультации',
  interactionGenitivePlural: 'консультаций',
  outcome: 'Продажа',
  outcomePlural: 'Продажи',
  outcomeLost: 'Без продажи',
  catalog: 'Ассортимент',
  availability: 'Остатки',
  upsell: 'Допродажа',
  helpTarget: 'Коллега или склад',
  helpTargetDative: 'коллеге или складу',
  helpTargetGenitive: 'коллеги или склада',
  zones: 'Отделы',
  zonesPlaceholder: 'Торговый зал, склад, сервис',
  items: 'Товары в чеке',
  script: 'Скрипт продаж',
  device: 'Бейдж Onvy',
};

const RETAIL_METRICS: MetricDef[] = [
  { key: 'itemsPerCheck', label: 'Товаров в чеке', unit: 'count', external: true },
  { key: 'upsellRate', label: 'Доля допродаж', unit: 'pct' },
  { key: 'warrantyOffer', label: 'Предложена гарантия', unit: 'pct' },
  { key: 'accessoryOffer', label: 'Предложены аксессуары', unit: 'pct' },
  { key: 'stockQueries', label: 'Запросы по наличию', unit: 'count' },
  { key: 'stockEscalations', label: 'Обращения к складу', unit: 'count', lowerIsBetter: true },
  { key: 'missedStages', label: 'Пропущено этапов скрипта', unit: 'count', lowerIsBetter: true },
];

const RETAIL_SOURCES: KnowledgeSourceDef[] = [
  { key: 'catalog', label: 'Ассортимент', hint: 'Прайс или выгрузка товаров' },
  { key: 'specs', label: 'Характеристики', hint: 'Описания и параметры моделей' },
  { key: 'stock', label: 'Остатки', hint: 'Наличие по точкам' },
  { key: 'scripts', label: 'Скрипты продаж', hint: 'Стандарт консультации' },
  { key: 'promo', label: 'Акции', hint: 'Действующие предложения' },
  { key: 'terms', label: 'Доставка и гарантия', hint: 'Условия и сроки' },
];

const RETAIL_STAGES = [
  'Установление контакта',
  'Выявление потребности',
  'Презентация под задачу',
  'Работа с возражением',
  'Допродажа',
  'Закрытие сделки',
];

const RETAIL_ERRORS = [
  'Пропущено выявление потребности',
  'Нет следующего шага при уходе клиента',
  'Не предложены аксессуары',
  'Подтверждение будущей скидки',
  'Не предложена расширенная гарантия',
];

export const universal: IndustryProfile = {
  key: 'universal',
  labels: RETAIL_LABELS,
  metrics: RETAIL_METRICS,
  kpiMetrics: [...coreFor(RETAIL_LABELS), ...RETAIL_METRICS],
  knowledgeSources: RETAIL_SOURCES,
  categories: ['Выбор товара', 'Цена и рассрочка', 'Наличие', 'Гарантия и сервис', 'Акции', 'Доставка'],
  scriptStages: RETAIL_STAGES,
  errorTypes: RETAIL_ERRORS,
  trainingCategories: ['Знание ассортимента', 'Работа с возражениями', 'Стандарт консультации', 'Допродажи'],
  testSources: ['Ассортимент и характеристики', 'Скрипт продаж', 'Условия и гарантия'],
  cues: [
    { q: 'Чем эта модель отличается от прошлой?', a: 'Назовите два отличия под задачу покупателя, а не весь список характеристик.' },
    { q: 'Дороговато, подожду скидку.', a: 'Не подтверждайте скидку. Предложите рассрочку — платёж в месяц звучит меньше.' },
  ],
};

export const electronics: IndustryProfile = {
  ...universal,
  key: 'electronics',
  labels: {
    ...RETAIL_LABELS,
    industry: 'Электроника',
    industryHint: 'Смартфоны, ноутбуки, техника для дома',
    zonesPlaceholder: 'Смартфоны, ноутбуки, аксессуары',
  },
  categories: ['Выбор техники', 'Цена и рассрочка', 'Наличие', 'Гарантия и сервис', 'Trade-in', 'Аксессуары'],
  trainingCategories: ['Линейки и модели', 'Работа с возражениями', 'Стандарт консультации', 'Допродажи и гарантия'],
  testSources: ['Ассортимент и характеристики', 'Скрипт продаж', 'Гарантия и trade-in'],
  cues: [
    { q: 'Чем Pro отличается от обычной модели?', a: '5x телефото и стабилизация — под съёмку детей в движении.' },
    { q: 'Дороговато, подожду скидку.', a: 'Не подтверждайте скидку. Рассрочка 0-0-12 — платёж 11 600 ₽ в месяц.' },
    { q: 'А если разобью?', a: 'Прямой запрос на гарантию. Предложите сейчас — 12 000 ₽ к чеку.' },
  ],
};

const DIY_LABELS: IndustryLabels = {
  ...RETAIL_LABELS,
  industry: 'DIY и строительный ритейл',
  industryHint: 'Материалы, инструмент, отделка',
  employee: 'Продавец-консультант',
  employeePlural: 'Продавцы-консультанты',
  employeeRoles: ['Стажёр', 'Продавец-консультант', 'Специалист отдела'],
  location: 'Гипермаркет',
  locationPlural: 'Гипермаркеты',
  locationForms: ['гипермаркет', 'гипермаркета', 'гипермаркетов'],
  upsell: 'Сопутствующие материалы',
  helpTarget: 'Профильный специалист',
  helpTargetDative: 'профильному специалисту',
  helpTargetGenitive: 'профильного специалиста',
  zones: 'Отделы',
  zonesPlaceholder: 'Отделка, инструмент, сантехника, склад',
  items: 'Позиции в чеке',
  device: 'Бейдж Onvy',
};

const DIY_METRICS: MetricDef[] = [
  { key: 'pickAccuracy', label: 'Точность подбора', unit: 'pct' },
  { key: 'compatQuestions', label: 'Вопросы по совместимости', unit: 'count' },
  { key: 'specialistEscalations', label: 'Обращения к специалисту', unit: 'count', lowerIsBetter: true },
  { key: 'wrongAdvice', label: 'Ошибки в рекомендациях', unit: 'count', lowerIsBetter: true },
  { key: 'stockQueries', label: 'Запросы по складу', unit: 'count' },
  { key: 'companionSales', label: 'Сопутствующие материалы', unit: 'pct' },
];

export const diy: IndustryProfile = {
  key: 'diy',
  labels: DIY_LABELS,
  metrics: DIY_METRICS,
  kpiMetrics: [...coreFor(DIY_LABELS), ...DIY_METRICS],
  knowledgeSources: [
    { key: 'materials', label: 'Характеристики материалов', hint: 'Расход, основания, условия' },
    { key: 'compat', label: 'Совместимость', hint: 'Что с чем можно применять' },
    { key: 'usage', label: 'Способы применения', hint: 'Технологические карты' },
    { key: 'safety', label: 'Техника безопасности', hint: 'Ограничения и средства защиты' },
    { key: 'stock', label: 'Складские остатки', hint: 'Наличие и сроки поставки' },
    { key: 'scripts', label: 'Скрипты продаж', hint: 'Стандарт подбора' },
  ],
  categories: ['Подбор материала', 'Совместимость', 'Расход и объём', 'Инструмент', 'Безопасность', 'Наличие и доставка'],
  scriptStages: [
    'Уточнение задачи и основания',
    'Расчёт объёма',
    'Подбор совместимых материалов',
    'Предупреждение о технологии',
    'Сопутствующие материалы',
    'Закрытие сделки',
  ],
  errorTypes: [
    'Не уточнено основание и условия работ',
    'Рекомендация несовместимых материалов',
    'Не рассчитан расход',
    'Не предупредил о технике безопасности',
    'Не предложены сопутствующие материалы',
  ],
  trainingCategories: ['Совместимость материалов', 'Расчёт расхода', 'Техника безопасности', 'Подбор под задачу'],
  testSources: ['Характеристики материалов', 'Совместимость', 'Техника безопасности'],
  cues: [
    { q: 'Какую грунтовку взять под эту штукатурку?', a: 'Сначала уточните основание. На газобетон — глубокого проникновения, иначе штукатурка отойдёт.' },
    { q: 'Сколько мешков нужно на комнату?', a: 'Расход 8,5 кг/м² при слое 10 мм. Уточните площадь и слой, посчитаем вместе.' },
  ],
};

const HORECA_LABELS: IndustryLabels = {
  industry: 'Ресторан / HoReCa',
  industryHint: 'Рестораны, кафе, бары',
  client: 'Гость',
  clientPlural: 'Гости',
  clientGenitivePlural: 'гостей',
  employee: 'Официант',
  employeePlural: 'Официанты',
  employeeRoles: ['Стажёр', 'Официант', 'Старший официант'],
  location: 'Ресторан',
  locationPlural: 'Рестораны',
  locationForms: ['ресторан', 'ресторана', 'ресторанов'],
  interaction: 'Обслуживание',
  interactionPlural: 'Обслуживания',
  interactionForms: ['обслуживание', 'обслуживания', 'обслуживаний'],
  interactionGenitive: 'обслуживания',
  interactionGenitivePlural: 'обслуживаний',
  outcome: 'Заказ',
  outcomePlural: 'Заказы',
  outcomeLost: 'Без заказа',
  catalog: 'Меню',
  availability: 'Стоп-лист',
  upsell: 'Напиток или десерт',
  helpTarget: 'Кухня или менеджер',
  helpTargetDative: 'кухне или менеджеру',
  helpTargetGenitive: 'кухни или менеджера',
  zones: 'Зоны обслуживания',
  zonesPlaceholder: 'Основной зал, веранда, бар',
  items: 'Позиции в заказе',
  script: 'Стандарт обслуживания',
  device: 'Бейдж Onvy',
};

const HORECA_METRICS: MetricDef[] = [
  { key: 'itemsPerCheck', label: 'Позиций в заказе', unit: 'count', external: true },
  { key: 'drinkOffer', label: 'Предложен напиток', unit: 'pct' },
  { key: 'dessertOffer', label: 'Предложен десерт', unit: 'pct' },
  { key: 'compositionQuestions', label: 'Вопросы по составу', unit: 'count' },
  { key: 'allergenQuestions', label: 'Вопросы по аллергенам', unit: 'count' },
  { key: 'kitchenEscalations', label: 'Обращения к кухне', unit: 'count', lowerIsBetter: true },
  { key: 'orderCorrections', label: 'Исправления заказа', unit: 'count', lowerIsBetter: true },
  { key: 'stopListChecks', label: 'Проверки стоп-листа', unit: 'count' },
];

export const horeca: IndustryProfile = {
  key: 'horeca',
  labels: HORECA_LABELS,
  metrics: HORECA_METRICS,
  kpiMetrics: [...coreFor(HORECA_LABELS), ...HORECA_METRICS],
  knowledgeSources: [
    { key: 'menu', label: 'Меню', hint: 'Блюда, цены, категории' },
    { key: 'composition', label: 'Состав блюд', hint: 'Ингредиенты и способ приготовления' },
    { key: 'allergens', label: 'Аллергены', hint: 'Критично: ответ не должен быть догадкой' },
    { key: 'stoplist', label: 'Стоп-лист', hint: 'Чего сегодня нет' },
    { key: 'standards', label: 'Стандарты обслуживания', hint: 'Шаги сервиса' },
  ],
  categories: ['Состав блюда', 'Аллергены', 'Стоп-лист', 'Рекомендация блюда', 'Напитки', 'Время подачи'],
  scriptStages: [
    'Приветствие и подача меню',
    'Уточнение предпочтений',
    'Рекомендация блюда',
    'Проверка стоп-листа и аллергенов',
    'Предложение напитка или десерта',
    'Подтверждение заказа',
  ],
  errorTypes: [
    'Ответ по составу без проверки',
    'Не уточнил аллергены',
    'Не проверил стоп-лист',
    'Не предложен напиток',
    'Не предложен десерт',
    'Заказ подтверждён с ошибкой',
  ],
  trainingCategories: ['Знание меню', 'Аллергены и безопасность', 'Стандарт обслуживания', 'Допродажи'],
  testSources: ['Меню и состав', 'Аллергены', 'Стоп-лист', 'Стандарты обслуживания'],
  cues: [
    { q: 'В этом плове есть орехи? У меня аллергия.', a: 'Не отвечайте по памяти. В карте блюда орехов нет, но подтвердите у кухни — это аллерген.' },
    { q: 'Что посоветуете к люля-кебабу?', a: 'Айран или узбекский чай. К мясу гриль берут в 61 % заказов.' },
    { q: 'Долму, пожалуйста.', a: 'Долма в стоп-листе с 18:40. Предложите манты — ближайшая замена по вкусу.' },
  ],
};

const FURNITURE_LABELS: IndustryLabels = {
  ...RETAIL_LABELS,
  industry: 'Мебель',
  industryHint: 'Салоны мебели и товаров для дома',
  location: 'Салон',
  locationPlural: 'Салоны',
  locationForms: ['салон', 'салона', 'салонов'],
  upsell: 'Доп. услуга или комплект',
  helpTarget: 'Дизайнер или склад',
  helpTargetDative: 'дизайнеру или складу',
  helpTargetGenitive: 'дизайнера или склада',
  zonesPlaceholder: 'Гостиные, спальни, кухни, склад',
};

export const furniture: IndustryProfile = {
  ...universal,
  key: 'furniture',
  labels: FURNITURE_LABELS,
  kpiMetrics: [
    ...coreFor(FURNITURE_LABELS),
    { key: 'itemsPerCheck', label: 'Позиций в заказе', unit: 'count', external: true },
    { key: 'upsellRate', label: 'Доля допродаж', unit: 'pct' },
    { key: 'measureBooked', label: 'Записан замер', unit: 'pct' },
    { key: 'deliveryQuestions', label: 'Вопросы по доставке', unit: 'count' },
  ],
  metrics: [
    { key: 'itemsPerCheck', label: 'Позиций в заказе', unit: 'count', external: true },
    { key: 'upsellRate', label: 'Доля допродаж', unit: 'pct' },
    { key: 'measureBooked', label: 'Записан замер', unit: 'pct' },
    { key: 'deliveryQuestions', label: 'Вопросы по доставке', unit: 'count' },
  ],
  knowledgeSources: [
    { key: 'catalog', label: 'Каталог', hint: 'Коллекции, размеры, материалы' },
    { key: 'specs', label: 'Материалы и обивка', hint: 'Износостойкость, уход' },
    { key: 'stock', label: 'Наличие и сроки', hint: 'Склад и производство' },
    { key: 'terms', label: 'Доставка, сборка, замер', hint: 'Условия услуг' },
    { key: 'scripts', label: 'Скрипты продаж', hint: 'Стандарт консультации' },
  ],
  categories: ['Подбор модели', 'Материалы и уход', 'Размеры и замер', 'Сроки и доставка', 'Сборка', 'Рассрочка'],
  trainingCategories: ['Коллекции и материалы', 'Замер и доставка', 'Стандарт консультации', 'Допродажи'],
};

const SPORT_LABELS: IndustryLabels = {
  ...RETAIL_LABELS,
  industry: 'Спорт',
  industryHint: 'Спортивные товары и экипировка',
  zonesPlaceholder: 'Обувь, экипировка, тренажёры',
  upsell: 'Экипировка и уход',
  helpTarget: 'Коллега или склад',
};

export const sport: IndustryProfile = {
  ...universal,
  key: 'sport',
  labels: SPORT_LABELS,
  kpiMetrics: [
    ...coreFor(SPORT_LABELS),
    { key: 'itemsPerCheck', label: 'Товаров в чеке', unit: 'count', external: true },
    { key: 'upsellRate', label: 'Доля допродаж', unit: 'pct' },
    { key: 'fitCheck', label: 'Подбор по размеру', unit: 'pct' },
    { key: 'stockQueries', label: 'Запросы по наличию', unit: 'count' },
  ],
  metrics: [
    { key: 'itemsPerCheck', label: 'Товаров в чеке', unit: 'count', external: true },
    { key: 'upsellRate', label: 'Доля допродаж', unit: 'pct' },
    { key: 'fitCheck', label: 'Подбор по размеру', unit: 'pct' },
    { key: 'stockQueries', label: 'Запросы по наличию', unit: 'count' },
  ],
  categories: ['Подбор под вид спорта', 'Размер и посадка', 'Материалы', 'Наличие', 'Уход', 'Гарантия'],
  trainingCategories: ['Ассортимент по видам спорта', 'Подбор размера', 'Стандарт консультации', 'Допродажи'],
};

const FASHION_LABELS: IndustryLabels = {
  ...RETAIL_LABELS,
  industry: 'Одежда и косметика',
  industryHint: 'Fashion-ритейл и бьюти',
  zonesPlaceholder: 'Женский зал, мужской зал, примерочные',
  upsell: 'Комплект или уход',
  helpTarget: 'Коллега или склад',
};

export const fashion: IndustryProfile = {
  ...universal,
  key: 'fashion',
  labels: FASHION_LABELS,
  kpiMetrics: [
    ...coreFor(FASHION_LABELS),
    { key: 'itemsPerCheck', label: 'Вещей в чеке', unit: 'count', external: true },
    { key: 'upsellRate', label: 'Доля комплектов', unit: 'pct' },
    { key: 'fittingRoom', label: 'Доведено до примерочной', unit: 'pct' },
    { key: 'stockQueries', label: 'Запросы по размеру', unit: 'count' },
  ],
  metrics: [
    { key: 'itemsPerCheck', label: 'Вещей в чеке', unit: 'count', external: true },
    { key: 'upsellRate', label: 'Доля комплектов', unit: 'pct' },
    { key: 'fittingRoom', label: 'Доведено до примерочной', unit: 'pct' },
    { key: 'stockQueries', label: 'Запросы по размеру', unit: 'count' },
  ],
  categories: ['Подбор образа', 'Размер и посадка', 'Состав и уход', 'Наличие', 'Акции', 'Возврат'],
  trainingCategories: ['Коллекции и составы', 'Подбор образа', 'Стандарт консультации', 'Допродажи'],
};

export const other: IndustryProfile = {
  ...universal,
  key: 'other',
  labels: {
    ...RETAIL_LABELS,
    industry: 'Другое',
    industryHint: 'Своя сфера — термины можно оставить универсальными',
    employee: 'Сотрудник',
    employeePlural: 'Сотрудники',
    employeeRoles: ['Стажёр', 'Сотрудник', 'Старший сотрудник'],
    location: 'Точка',
    locationPlural: 'Точки',
    locationForms: ['точка', 'точки', 'точек'],
  },
};

export const INDUSTRY_PROFILES: Record<IndustryKey, IndustryProfile> = {
  universal,
  electronics,
  diy,
  furniture,
  sport,
  fashion,
  horeca,
  other,
};

/** Порядок в выпадающем списке при регистрации. */
export const INDUSTRY_ORDER: IndustryKey[] = [
  'universal',
  'electronics',
  'diy',
  'furniture',
  'sport',
  'fashion',
  'horeca',
  'other',
];

export function getProfile(key: IndustryKey | undefined): IndustryProfile {
  // По умолчанию — общепит: продукт делается для чайханы, и универсальный профиль
  // называл официантов «консультантами», а зал — «торговой точкой». Термины из
  // чужой отрасли на экране управляющего читаются как чужой продукт.
  return INDUSTRY_PROFILES[key ?? 'horeca'] ?? horeca;
}

/** Найти определение метрики в профиле — ядро плюс отраслевые. */
export function findMetric(profile: IndustryProfile, key: string): MetricDef {
  return (
    profile.kpiMetrics.find((m) => m.key === key) ??
    profile.metrics.find((m) => m.key === key) ?? { key, label: key, unit: 'count' }
  );
}
