// Цифровая клавиатура на весь низ экрана — это НЕ экранная клавиатура телефона:
// три колонки, крупные кнопки под большой палец, никакого мелкого поля ввода.
// PIN не показывается цифрами — только точки-индикаторы, как в обычной блокировке телефона.

import { Delete } from 'lucide-react';

const KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '', '0', 'del'] as const;

export function PinPad({
  length,
  value,
  onChange,
  disabled,
}: {
  length: number;
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}) {
  const press = (key: string) => {
    if (disabled) return;
    if (key === 'del') {
      onChange(value.slice(0, -1));
      return;
    }
    if (value.length >= length) return;
    onChange(value + key);
  };

  return (
    <div>
      <div className="mb-6 flex items-center justify-center gap-4">
        {Array.from({ length }).map((_, i) => (
          <span
            key={i}
            className={`h-4 w-4 rounded-full border-2 border-stone-500 transition-colors duration-150 ease-out ${
              i < value.length ? 'bg-stone-50 border-stone-50' : 'bg-transparent'
            }`}
          />
        ))}
      </div>

      <div className="grid grid-cols-3 gap-3">
        {KEYS.map((key, i) =>
          key === '' ? (
            <div key={i} />
          ) : (
            <button
              key={i}
              type="button"
              disabled={disabled}
              onPointerDown={(e) => e.preventDefault()}
              onClick={() => press(key)}
              aria-label={key === 'del' ? 'Стереть цифру' : `Цифра ${key}`}
              className="flex h-[4.5rem] items-center justify-center rounded-2xl bg-stone-800 text-3xl font-semibold text-stone-50 transition-transform duration-150 ease-out active:scale-[0.95] active:bg-stone-700 disabled:opacity-40"
            >
              {key === 'del' ? <Delete size={28} /> : key}
            </button>
          ),
        )}
      </div>
    </div>
  );
}
