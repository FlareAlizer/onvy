import React, { useMemo, useState } from 'react';
import { motion } from 'motion/react';
import { LogIn, ShieldCheck, User } from 'lucide-react';
import type { Session, UserRole } from '../types';
import { apiWithKey, saveSession } from '../lib/api';
import Logo from '../components/Logo';

interface EmployeeOut {
  id: number;
  name: string;
  role: 'rop' | 'employee';
  language: string;
  department_id: number | null;
}

const LANGS = [
  { v: 'ru', label: 'Русский' },
  { v: 'en', label: 'English' },
  { v: 'uz', label: 'O‘zbek' },
  { v: 'kk', label: 'Қазақ' },
  { v: 'tr', label: 'Türkçe' },
];

export default function AuthView({ onLogin }: { onLogin: (s: Session) => void }) {
  // Параметры QR-приглашения: /?key=...&dept=...&role=employee
  const qs = useMemo(() => new URLSearchParams(location.search), []);
  const qsKey = qs.get('key') ?? '';
  const qsDept = qs.get('dept');
  const invited = qs.get('role') === 'employee';

  const [selectedRole, setSelectedRole] = useState<UserRole | null>(invited ? 'employee' : null);
  const [apiKey, setApiKey] = useState(qsKey);
  const [name, setName] = useState('');
  const [language, setLanguage] = useState('ru');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const login = async () => {
    if (!selectedRole || !apiKey.trim() || !name.trim()) {
      setError('Заполни код доступа, имя и выбери роль');
      return;
    }
    setBusy(true);
    setError('');
    try {
      const body: Record<string, unknown> = {
        name: name.trim(),
        role: selectedRole === 'manager' ? 'rop' : 'employee',
        language,
      };
      if (qsDept) body.department_id = Number(qsDept);
      const emp = await apiWithKey<EmployeeOut>(apiKey.trim(), '/employees', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      const session: Session = {
        apiKey: apiKey.trim(),
        employeeId: emp.id,
        name: emp.name,
        role: emp.role === 'rop' ? 'manager' : 'employee',
        language: emp.language,
        departmentId: emp.department_id,
      };
      saveSession(session);
      history.replaceState(null, '', location.pathname); // убрать key из адресной строки
      onLogin(session);
    } catch (e) {
      setError(`Не удалось войти: ${e instanceof Error ? e.message : e}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="min-h-screen w-full bg-[#fafafa] flex flex-col items-center justify-center p-6 overflow-y-auto">
      <motion.div
        initial={{ opacity: 0, y: 15 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        className="w-full max-w-[420px]"
      >
        <div className="mb-8 flex justify-center">
          <Logo size="md" />
        </div>

        <div className="bg-white border border-zinc-200/60 rounded-3xl p-8 shadow-[0_8px_30px_rgb(0,0,0,0.02)]">
          <h2 className="text-xl font-semibold text-zinc-900 tracking-tight text-center mb-1">Войдите в кабинет</h2>
          <p className="text-zinc-400 text-xs text-center mb-6">
            {invited
              ? 'Ты присоединяешься к отделу по приглашению — укажи имя и свой язык'
              : 'Выберите вашу рабочую роль в системе речевой аналитики'}
          </p>

          {!invited && (
            <div className="space-y-3 mb-5">
              <RoleButton
                active={selectedRole === 'manager'}
                onClick={() => setSelectedRole('manager')}
                icon={<ShieldCheck className="w-4.5 h-4.5" />}
                label="Кабинет РОПа"
                description="Управление процессами, аналитика консультаций и обучение команды"
              />
              <RoleButton
                active={selectedRole === 'employee'}
                onClick={() => setSelectedRole('employee')}
                icon={<User className="w-4.5 h-4.5" />}
                label="Интерфейс сотрудника"
                description="Онлайн-ассистент, запись разговоров и личные результаты"
              />
            </div>
          )}

          <div className="space-y-3 mb-6">
            {!qsKey && (
              <Field label="Код доступа">
                <input
                  type="password"
                  inputMode="numeric"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="Код демо"
                  className="auth-input"
                />
              </Field>
            )}
            <Field label="Имя">
              <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Например, Иван" className="auth-input" />
            </Field>
            <Field label="Мой язык (на нём слышу коллег и ассистента)">
              <select value={language} onChange={(e) => setLanguage(e.target.value)} className="auth-input">
                {LANGS.map((l) => (
                  <option key={l.v} value={l.v}>{l.label}</option>
                ))}
              </select>
            </Field>
          </div>

          {error && <p className="text-xs text-rose-500 font-medium mb-4 text-center">{error}</p>}

          <button
            disabled={!selectedRole || busy}
            onClick={login}
            className="w-full py-3 bg-zinc-900 hover:bg-zinc-800 disabled:bg-zinc-100 disabled:text-zinc-300 text-white font-medium text-sm rounded-xl transition-all shadow-xs flex items-center justify-center gap-2 cursor-pointer"
          >
            {busy ? 'Входим…' : 'Войти в систему'} <LogIn className="w-4 h-4" />
          </button>
        </div>

        <div className="mt-8 text-center">
          <p className="text-[10px] text-zinc-400 font-medium uppercase tracking-widest">
            Onvy © 2026. Платформа умной речевой аналитики
          </p>
        </div>
      </motion.div>

      <style>{`
        .auth-input {
          width: 100%; padding: 10px 14px; border-radius: 12px; font-size: 13px;
          border: 1px solid rgb(228 228 231 / .8); background: rgb(250 250 250);
          outline: none; font-weight: 500; color: #18181b;
        }
        .auth-input:focus { border-color: #a1a1aa; }
      `}</style>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <label className="text-[10px] font-bold text-zinc-400 uppercase tracking-widest mb-1.5 block">{label}</label>
      {children}
    </div>
  );
}

function RoleButton({ active, onClick, icon, label, description }: {
  active: boolean;
  onClick: () => void;
  icon: React.ReactNode;
  label: string;
  description: string;
}) {
  return (
    <button
      onClick={onClick}
      className={`w-full p-4 rounded-xl border transition-all text-left flex items-start gap-4 cursor-pointer ${
        active ? 'border-zinc-900 bg-zinc-50 shadow-xs' : 'border-zinc-200/60 bg-white hover:border-zinc-300 hover:bg-zinc-50/50'
      }`}
    >
      <div className={`p-2 rounded-lg shrink-0 transition-colors ${active ? 'bg-zinc-950 text-white' : 'bg-zinc-100 text-zinc-500'}`}>
        {icon}
      </div>
      <div>
        <p className={`font-semibold text-sm ${active ? 'text-zinc-900' : 'text-zinc-700'}`}>{label}</p>
        <p className="text-xs text-zinc-400 mt-1 leading-relaxed">{description}</p>
      </div>
    </button>
  );
}
