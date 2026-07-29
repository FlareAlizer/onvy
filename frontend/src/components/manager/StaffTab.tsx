// Состав смены: кто заведён, добавление и перевыдача доступов.
//
// Главное здесь — правило: PIN и пароль показываются ОДИН раз, сразу после
// выдачи. В базе только хеши, посмотреть повторно нельзя даже управляющему.
// Поэтому выданные доступы держим на экране до явного закрытия и предупреждаем,
// что второго шанса не будет.

import { useCallback, useEffect, useState } from 'react';
import { AlertTriangle, Check, KeyRound, Loader2, RotateCcw, UserPlus } from 'lucide-react';
import { api, ApiError, getSession } from '../../lib/api';
import { LoadingState, ErrorState } from '../StateView';
import { roleLabel, languageLabel } from '../roles';

type StaffMember = {
  id: number;
  name: string;
  nickname: string | null;
  role: string;
  language: string;
  is_active: boolean;
};

type Access = {
  employee_id: number;
  name: string;
  nickname: string | null;
  role: string;
  language: string;
  pin: string;
  email: string | null;
  password: string | null;
};

const РОЛИ = ['waiter', 'kitchen', 'bar', 'host', 'manager'];
const ЯЗЫКИ = ['ru', 'uz', 'kk', 'ky', 'en', 'tg'];

export default function StaffTab() {
  const venueId = getSession()?.venueId ?? 1;
  const [staff, setStaff] = useState<StaffMember[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [форма, setФорма] = useState(false);
  const [доступ, setДоступ] = useState<Access | null>(null);

  const загрузить = useCallback(async () => {
    try {
      setStaff(await api<StaffMember[]>(`/venues/${venueId}/staff`));
      setError(null);
    } catch {
      setError('Не удалось загрузить состав смены');
    }
  }, [venueId]);

  useEffect(() => {
    void загрузить();
  }, [загрузить]);

  const перевыдать = async (member: StaffMember) => {
    try {
      const результат = await api<Access>(
        `/venues/${venueId}/staff/${member.id}/reset-access`,
        { method: 'POST' },
      );
      setДоступ(результат);
      void загрузить();
    } catch {
      setError('Не удалось перевыдать доступ');
    }
  };

  if (error && !staff) return <ErrorState message={error} onRetry={загрузить} />;
  if (!staff) return <LoadingState />;

  return (
    <div className="space-y-4">
      {доступ && <ДоступВыдан доступ={доступ} onClose={() => setДоступ(null)} />}

      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold">Состав смены</h2>
          <p className="text-sm text-stone-500">{staff.length} человек</p>
        </div>
        <button
          onClick={() => setФорма((v) => !v)}
          className="flex items-center gap-2 rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white"
        >
          <UserPlus size={18} />
          Добавить
        </button>
      </div>

      {форма && (
        <ФормаДобавления
          venueId={venueId}
          onDone={(результат) => {
            setДоступ(результат);
            setФорма(false);
            void загрузить();
          }}
          onCancel={() => setФорма(false)}
        />
      )}

      <ul className="space-y-2">
        {staff.map((member) => (
          <li
            key={member.id}
            className="flex items-center justify-between rounded-2xl border border-stone-200 bg-white px-4 py-3"
          >
            <div className="min-w-0">
              <p className="truncate font-medium">{member.name}</p>
              <p className="text-sm text-stone-500">
                {roleLabel(member.role)} · {languageLabel(member.language)}
                {member.nickname && ` · «${member.nickname}»`}
              </p>
            </div>
            <button
              onClick={() => void перевыдать(member)}
              title="Перевыдать PIN и пароль"
              className="flex shrink-0 items-center gap-1.5 rounded-xl border border-stone-300 px-3 py-2 text-sm text-stone-600"
            >
              <RotateCcw size={16} />
              Доступ
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function ФормаДобавления({
  venueId,
  onDone,
  onCancel,
}: {
  venueId: number;
  onDone: (доступ: Access) => void;
  onCancel: () => void;
}) {
  const [name, setName] = useState('');
  const [nickname, setNickname] = useState('');
  const [role, setRole] = useState('waiter');
  const [language, setLanguage] = useState('ru');
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const отправить = async () => {
    setError(null);
    setSubmitting(true);
    try {
      const результат = await api<Access>(`/venues/${venueId}/staff`, {
        method: 'POST',
        body: JSON.stringify({
          name,
          role,
          language,
          nickname: nickname.trim() || null,
          email: email.trim() || null,
        }),
      });
      onDone(результат);
    } catch (err) {
      // Сообщения сервера здесь содержательные («кличка совпадает с блюдом»),
      // показываем как есть — управляющему нужно понять, что поправить.
      setError(err instanceof ApiError ? err.message : 'Не получилось добавить');
    } finally {
      setSubmitting(false);
    }
  };

  const поле = 'mt-1 w-full rounded-xl border border-stone-300 px-3 py-2.5 text-base';

  return (
    <div className="space-y-3 rounded-2xl border border-stone-200 bg-stone-50 p-4">
      <label className="block">
        <span className="text-sm font-medium text-stone-600">Имя и фамилия</span>
        <input value={name} onChange={(e) => setName(e.target.value)} className={поле} />
      </label>

      <label className="block">
        <span className="text-sm font-medium text-stone-600">
          Кличка на смене <span className="text-stone-400">— по ней окликают голосом</span>
        </span>
        <input
          value={nickname}
          onChange={(e) => setNickname(e.target.value)}
          className={поле}
          placeholder="Азиз"
        />
      </label>

      <div className="grid grid-cols-2 gap-3">
        <label className="block">
          <span className="text-sm font-medium text-stone-600">Роль</span>
          <select value={role} onChange={(e) => setRole(e.target.value)} className={поле}>
            {РОЛИ.map((r) => (
              <option key={r} value={r}>
                {roleLabel(r)}
              </option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="text-sm font-medium text-stone-600">Язык</span>
          <select
            value={language}
            onChange={(e) => setLanguage(e.target.value)}
            className={поле}
          >
            {ЯЗЫКИ.map((l) => (
              <option key={l} value={l}>
                {languageLabel(l)}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="block">
        <span className="text-sm font-medium text-stone-600">
          Почта <span className="text-stone-400">— только если работает через кабинет</span>
        </span>
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className={поле}
          placeholder="необязательно"
        />
      </label>

      {error && (
        <p className="flex items-start gap-2 rounded-xl bg-red-50 px-3 py-2 text-sm text-red-700">
          <AlertTriangle size={16} className="mt-0.5 shrink-0" />
          {error}
        </p>
      )}

      <div className="flex gap-2 pt-1">
        <button
          onClick={() => void отправить()}
          disabled={submitting || name.trim().length < 2}
          className="flex flex-1 items-center justify-center gap-2 rounded-xl bg-emerald-600 py-2.5 font-medium text-white disabled:bg-stone-300"
        >
          {submitting ? <Loader2 size={18} className="animate-spin" /> : <Check size={18} />}
          Завести и выдать доступ
        </button>
        <button onClick={onCancel} className="rounded-xl px-4 py-2.5 text-stone-600">
          Отмена
        </button>
      </div>
    </div>
  );
}

function ДоступВыдан({ доступ, onClose }: { доступ: Access; onClose: () => void }) {
  return (
    <div className="rounded-2xl border-2 border-emerald-500 bg-emerald-50 p-4">
      <div className="flex items-start gap-2">
        <KeyRound size={20} className="mt-0.5 shrink-0 text-emerald-700" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-emerald-900">Доступ для {доступ.name}</p>
          <p className="mt-0.5 text-sm text-emerald-800">
            Запишите или сфотографируйте сейчас — второй раз не покажем.
            Забудете — перевыдайте кнопкой «Доступ».
          </p>

          <dl className="mt-3 space-y-1.5 font-mono text-base">
            <div className="flex gap-2">
              <dt className="w-20 shrink-0 font-sans text-sm text-emerald-700">PIN</dt>
              <dd className="font-semibold tracking-widest">{доступ.pin}</dd>
            </div>
            {доступ.email && (
              <>
                <div className="flex gap-2">
                  <dt className="w-20 shrink-0 font-sans text-sm text-emerald-700">Почта</dt>
                  <dd className="break-all">{доступ.email}</dd>
                </div>
                <div className="flex gap-2">
                  <dt className="w-20 shrink-0 font-sans text-sm text-emerald-700">Пароль</dt>
                  <dd className="break-all font-semibold">{доступ.password}</dd>
                </div>
              </>
            )}
          </dl>

          <button
            onClick={onClose}
            className="mt-4 rounded-xl bg-emerald-700 px-4 py-2 text-sm font-medium text-white"
          >
            Записал, скрыть
          </button>
        </div>
      </div>
    </div>
  );
}
