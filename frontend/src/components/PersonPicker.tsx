// Список коллег точки для личного обращения: «ткнуть пальцем» вместо того,
// чтобы называть имя голосом. Один компонент — используется и в рации
// управляющего, и на экране официанта.
//
// Список берём с публичного /auth/venues/{id}/employees (тот же, что на экране
// входа), но исключаем самого себя: говорить самому с собой незачем, и в
// рации это только лишняя кнопка.

import { useEffect, useState } from 'react';
import { Loader2, User, WifiOff } from 'lucide-react';
import { api } from '../lib/api';

export type PersonOption = { id: number; name: string; role: string };

type RawEmployee = PersonOption & { language: string };

const ROLE_LABEL: Record<string, string> = {
  waiter: 'официант',
  kitchen: 'кухня',
  bar: 'бар',
  host: 'хостес',
  manager: 'управляющий',
};

type State =
  | { kind: 'loading' }
  | { kind: 'error' }
  | { kind: 'ready'; people: PersonOption[] };

type Props = {
  venueId: number;
  excludeId: number;
  selectedId: number | null;
  /** null — снять выбор (например, повторное нажатие на уже выбранного). */
  onSelect: (person: PersonOption | null) => void;
};

export default function PersonPicker({ venueId, excludeId, selectedId, onSelect }: Props) {
  const [state, setState] = useState<State>({ kind: 'loading' });

  useEffect(() => {
    let cancelled = false;
    setState({ kind: 'loading' });
    api<RawEmployee[]>(`/auth/venues/${venueId}/employees`)
      .then((rows) => {
        if (cancelled) return;
        setState({ kind: 'ready', people: rows.filter((row) => row.id !== excludeId) });
      })
      .catch(() => {
        if (!cancelled) setState({ kind: 'error' });
      });
    return () => {
      cancelled = true;
    };
  }, [venueId, excludeId]);

  if (state.kind === 'loading') {
    return (
      <div className="flex items-center gap-2 py-2 text-sm text-stone-500">
        <Loader2 size={16} className="animate-spin" />
        Загружаю коллег…
      </div>
    );
  }

  if (state.kind === 'error') {
    return (
      <div className="flex items-center justify-between gap-2 py-2 text-sm text-amber-300">
        <span className="flex items-center gap-1.5">
          <WifiOff size={16} />
          Не удалось загрузить список
        </span>
        <button
          onClick={() => setState({ kind: 'loading' })}
          className="rounded-lg bg-stone-800 px-3 py-2 text-stone-200"
          style={{ minHeight: 44 }}
        >
          Повторить
        </button>
      </div>
    );
  }

  if (state.people.length === 0) {
    return <p className="py-2 text-sm text-stone-500">В этой точке больше никого нет.</p>;
  }

  return (
    <div className="-mx-5 flex gap-2 overflow-x-auto px-5 pb-1">
      {state.people.map((person) => {
        const active = person.id === selectedId;
        return (
          <button
            key={person.id}
            onClick={() => onSelect(active ? null : person)}
            style={{ minHeight: 44 }}
            className={`flex shrink-0 items-center gap-1.5 rounded-xl px-4 text-sm font-semibold transition-colors duration-150 ease-out ${
              active ? 'bg-emerald-500 text-stone-950' : 'bg-stone-900 text-stone-300'
            }`}
          >
            <User size={15} />
            {person.name}
            <span className={active ? 'font-normal text-stone-900/70' : 'font-normal text-stone-500'}>
              {ROLE_LABEL[person.role] ?? person.role}
            </span>
          </button>
        );
      })}
    </div>
  );
}
