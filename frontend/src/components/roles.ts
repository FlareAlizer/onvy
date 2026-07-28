// Человеко-читаемые подписи ролей и языков сотрудника. Общие для экрана входа
// и кабинета управляющего — роль/язык встречаются в обоих на каждом шагу.

export const ROLE_LABELS: Record<string, string> = {
  waiter: 'Официант',
  kitchen: 'Кухня',
  bar: 'Бар',
  host: 'Хостес',
  manager: 'Управляющий',
};

export function roleLabel(role: string): string {
  return ROLE_LABELS[role] ?? role;
}

export const LANGUAGE_LABELS: Record<string, string> = {
  ru: 'Русский',
  uz: "O'zbek",
  kk: 'Қазақша',
  ky: 'Кыргызча',
  en: 'English',
  tg: 'Тоҷикӣ',
};

export function languageLabel(language: string): string {
  return LANGUAGE_LABELS[language] ?? language;
}
