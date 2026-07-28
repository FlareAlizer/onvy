// Общие компоненты кабинетов: каркас с сайдбаром, PTT, разбор диалога, плеер курса.

import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import {
  AlertCircle, CheckCircle2, ChevronLeft, ChevronRight, LogOut, Menu, Mic, Play, Sparkles, X,
} from 'lucide-react';
import type { AnalysisDetail, AnalysisSummary, Course } from '../types';
import { api, postAudio } from '../lib/api';
import { startRecording, stopRecording } from '../lib/recorder';
import Logo from './Logo';

/* ---------- Каркас: сайдбар + шапка + мобильное меню ---------- */

export interface NavItem { label: string; icon: React.ReactNode }

export function Shell({ nav, active, onNav, badge, userName, userStatus, onLogout, children }: {
  nav: NavItem[];
  active: string;
  onNav: (label: string) => void;
  badge: string;
  userName: string;
  userStatus: React.ReactNode;
  onLogout: () => void;
  children: React.ReactNode;
}) {
  const [menuOpen, setMenuOpen] = useState(false);

  const items = (close?: boolean) => (
    <nav className="flex-1 space-y-1">
      {nav.map((n) => (
        <div
          key={n.label}
          onClick={() => { onNav(n.label); if (close) setMenuOpen(false); }}
          className={`flex items-center gap-3 px-4 py-3 transition-all cursor-pointer rounded-xl group ${
            active === n.label ? 'bg-zinc-950 text-white font-semibold shadow-xs' : 'text-slate-500 hover:bg-slate-50 hover:text-slate-900 font-medium'
          }`}
        >
          {n.icon}
          <span className="text-[13px] tracking-tight">{n.label}</span>
        </div>
      ))}
    </nav>
  );

  const logout = (
    <div className="mt-auto border-t border-slate-100 pt-4">
      <button onClick={onLogout} className="flex items-center gap-3 w-full px-4 py-2.5 text-xs font-semibold text-slate-400 hover:text-rose-500 hover:bg-rose-50/50 rounded-xl transition-all cursor-pointer">
        <LogOut className="w-4.5 h-4.5" /> Выйти
      </button>
    </div>
  );

  return (
    <div className="flex h-full w-full bg-[#fafafa] overflow-hidden text-slate-800">
      <aside className="w-[240px] hidden md:flex flex-col bg-white border-r border-slate-200/60 shrink-0 p-4">
        <div className="h-16 flex items-center px-2 mb-6"><Logo size="sm" /></div>
        {items()}
        {logout}
      </aside>

      <AnimatePresence>
        {menuOpen && (
          <>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 0.4 }} exit={{ opacity: 0 }} onClick={() => setMenuOpen(false)} className="fixed inset-0 bg-black z-40 md:hidden" />
            <motion.aside
              initial={{ x: '-100%' }} animate={{ x: 0 }} exit={{ x: '-100%' }}
              transition={{ type: 'spring', damping: 25, stiffness: 200 }}
              className="fixed inset-y-0 left-0 w-[240px] bg-white z-50 flex flex-col p-4 shadow-xl md:hidden"
            >
              <div className="h-16 flex items-center justify-between px-2 mb-6">
                <Logo size="sm" />
                <button onClick={() => setMenuOpen(false)} className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-50 cursor-pointer"><X className="w-5 h-5" /></button>
              </div>
              {items(true)}
              {logout}
            </motion.aside>
          </>
        )}
      </AnimatePresence>

      <main className="flex-1 flex flex-col min-w-0 bg-[#fafafa]">
        <header className="h-20 flex items-center justify-between px-4 md:px-10 border-b border-slate-200/40 bg-white shrink-0">
          <div className="flex items-center gap-3">
            <button onClick={() => setMenuOpen(true)} className="p-2 -ml-2 rounded-lg text-slate-500 hover:bg-slate-100 hover:text-slate-800 md:hidden cursor-pointer"><Menu className="w-6 h-6" /></button>
            <span className="text-xs font-bold text-zinc-900 bg-zinc-100 border border-zinc-200 px-2.5 py-1 rounded-md uppercase tracking-wider">{badge}</span>
          </div>
          <div className="flex items-center gap-3 md:gap-4">
            <div className="flex flex-col items-end">
              <p className="text-sm font-semibold text-slate-800">{userName}</p>
              <div className="flex items-center gap-1.5 mt-0.5">{userStatus}</div>
            </div>
            <div className="w-9 h-9 rounded-xl bg-slate-100 border border-slate-200 flex items-center justify-center font-bold text-slate-700 text-xs">
              {userName.slice(0, 2).toUpperCase()}
            </div>
          </div>
        </header>

        <div className="flex-1 overflow-y-auto px-4 py-6 md:px-10 md:py-8">
          <AnimatePresence mode="wait">
            <motion.div key={active} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} transition={{ duration: 0.25, ease: [0.16, 1, 0.3, 1] }} className="h-full">
              {children}
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
    </div>
  );
}

export function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="h-full">
      <h2 className="text-xl font-bold tracking-tight text-slate-900 mb-6">{title}</h2>
      {children}
    </section>
  );
}

export function Card({ className = '', children }: { className?: string; children: React.ReactNode }) {
  return <div className={`bg-white border border-slate-200/60 rounded-3xl p-6 md:p-8 shadow-[0_4px_24px_rgba(0,0,0,0.01)] ${className}`}>{children}</div>;
}

export function StatCard({ label, value, sub }: { label: string; value: string; sub: string }) {
  return (
    <div className="bg-white border border-slate-200/60 p-5 rounded-2xl shadow-[0_2px_8px_rgba(0,0,0,0.01)] flex flex-col justify-between min-h-[110px]">
      <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">{label}</p>
      <span className="text-2xl font-extrabold text-slate-800 font-mono tracking-tight my-1.5">{value}</span>
      <span className="text-[9px] font-bold px-2 py-0.5 rounded-md w-fit border text-indigo-600 bg-indigo-50/70 border-indigo-100">{sub}</span>
    </div>
  );
}

export function Label({ children }: { children: React.ReactNode }) {
  return <label className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1.5 block">{children}</label>;
}

export const inputCls = 'w-full bg-slate-50 border border-slate-200 rounded-xl py-2.5 px-4 outline-none focus:border-slate-400 text-xs font-medium text-slate-800';

/* ---------- Push-to-talk (удержание = запись) ---------- */

export function PTTButton({ onClip, size = 'lg', label = 'Держи и говори' }: {
  onClip: (blob: Blob) => void;
  size?: 'lg' | 'md';
  label?: string;
}) {
  const [rec, setRec] = useState(false);
  const activeRef = useRef(false);

  const begin = async (e: React.PointerEvent) => {
    e.preventDefault();
    if (activeRef.current) return;
    activeRef.current = true;
    setRec(true);
    try { await startRecording(); } catch (err) {
      activeRef.current = false; setRec(false);
      alert(`Нет доступа к микрофону: ${err instanceof Error ? err.message : err}`);
    }
  };
  const end = async (e: React.PointerEvent) => {
    e.preventDefault();
    if (!activeRef.current) return;
    activeRef.current = false;
    setRec(false);
    onClip(await stopRecording());
  };

  const dim = size === 'lg' ? 'w-32 h-32' : 'w-24 h-24';
  return (
    <button
      onPointerDown={begin} onPointerUp={end} onPointerLeave={end}
      onContextMenu={(e) => e.preventDefault()}
      className={`${dim} rounded-full flex flex-col items-center justify-center gap-1 transition-all shadow-md active:scale-95 select-none touch-none cursor-pointer mx-auto ${
        rec ? 'bg-rose-500 text-white shadow-rose-300' : 'bg-zinc-900 text-white hover:bg-zinc-800'
      }`}
      style={{ touchAction: 'none' }}
    >
      <Mic className={`w-6 h-6 ${rec ? 'animate-pulse' : ''}`} />
      <span className="text-[11px] font-semibold px-3 text-center leading-tight">{rec ? 'Говори…' : label}</span>
    </button>
  );
}

/* ---------- Карточка диалога в списке ---------- */

export function DialogueCard({ a, onClick }: { a: AnalysisSummary; onClick: () => void }) {
  return (
    <div onClick={onClick} className="bg-white border border-slate-200/60 p-5 rounded-2xl flex items-start gap-5 hover:border-slate-400 hover:shadow-xs transition-all cursor-pointer group">
      <div className="w-12 h-12 rounded-full border border-slate-100 bg-slate-50 flex items-center justify-center font-bold text-slate-700 text-sm font-mono group-hover:bg-zinc-950 group-hover:text-white transition-colors shrink-0">
        {a.kpi_score}
      </div>
      <div className="flex-1 min-w-0">
        <div className="flex items-center justify-between mb-1.5 gap-2">
          <h4 className="font-bold text-sm text-slate-800 truncate">Разбор #{a.id}</h4>
          {a.is_sold ? (
            <span className="text-[9px] font-bold text-emerald-600 bg-emerald-50 border border-emerald-100 px-2 py-0.5 rounded-md uppercase tracking-wider shrink-0">Продано</span>
          ) : (
            <span className="text-[9px] font-bold text-slate-400 bg-slate-50 border border-slate-100 px-2 py-0.5 rounded-md uppercase tracking-wider shrink-0">Без продажи</span>
          )}
        </div>
        <p className="text-xs text-slate-400 italic font-medium leading-relaxed line-clamp-2">«{a.summary || '—'}»</p>
      </div>
      <ChevronRight className="w-4.5 h-4.5 text-slate-300 group-hover:text-zinc-950 group-hover:translate-x-0.5 transition-all self-center shrink-0" />
    </div>
  );
}

/* ---------- Детальный разбор диалога (реальные данные из analysis JSON) ---------- */

export function AnalysisDetailView({ id, onBack }: { id: number; onBack: () => void }) {
  const [d, setD] = useState<AnalysisDetail | null>(null);
  const [err, setErr] = useState('');

  useEffect(() => {
    api<AnalysisDetail>(`/analytics/analyses/${id}`).then(setD).catch((e) => setErr(String(e.message ?? e)));
  }, [id]);

  if (err) return <p className="text-xs text-rose-500">{err}</p>;
  if (!d) return <p className="text-xs text-slate-400">Загружаю разбор…</p>;

  const a = d.analysis;
  const fixes = (a.mistakes_and_fixes ?? []).map((m) => `${m.error} → «${m.fix}»`);
  const howToFix = fixes.length ? fixes : (a.recommendations ?? []);
  const amount = a.deal_analysis?.detected_amount ?? 0;

  return (
    <Section title="Детальный разбор диалога">
      <button onClick={onBack} className="mb-6 flex items-center gap-1.5 text-slate-400 hover:text-slate-900 transition-colors text-sm font-medium cursor-pointer">
        <ChevronLeft className="w-4 h-4" /> Назад к списку
      </button>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        <div className="lg:col-span-8 space-y-6">
          <Card>
            <div className="flex items-center justify-between border-b border-slate-100 pb-6 mb-6">
              <div>
                <span className="text-[10px] font-bold text-indigo-600 uppercase tracking-widest block">AI Речевая Аналитика</span>
                <h4 className="text-lg font-bold text-slate-900 mt-1">Оценка качества консультации</h4>
              </div>
              <div className="flex flex-col items-end">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">KPI</span>
                <div className="px-3 py-1 bg-zinc-900 text-white rounded-full text-xs font-mono font-bold shadow-sm">{d.kpi_score}%</div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              <AnalysisList icon={<CheckCircle2 className="w-4.5 h-4.5" />} color="text-emerald-600" title="Что хорошо" items={a.strengths ?? []} />
              <AnalysisList icon={<AlertCircle className="w-4.5 h-4.5" />} color="text-rose-500" title="Что плохо" items={a.weaknesses ?? []} />
              <div className="p-5 bg-zinc-900 text-zinc-100 border border-zinc-800 rounded-2xl shadow-sm">
                <div className="flex items-center gap-2 text-zinc-300 mb-3">
                  <Sparkles className="w-4.5 h-4.5 text-yellow-400" />
                  <span className="text-xs font-bold uppercase tracking-wider">Как исправить</span>
                </div>
                <ul className="text-xs text-zinc-300 space-y-2.5 list-disc pl-4 leading-relaxed font-medium">
                  {howToFix.map((item, i) => <li key={i}>{item}</li>)}
                </ul>
              </div>
            </div>
          </Card>

          <Card>
            <h4 className="text-sm font-bold text-slate-900 tracking-tight mb-1">Транскрибация разговора</h4>
            <p className="text-xs text-slate-400 mb-6 font-medium">Разделено по ролям собеседников</p>
            <div className="space-y-4 max-h-[400px] overflow-y-auto pr-2">
              {(a.transcript_parsed ?? []).map((line, i) => {
                const isEmp = line.speaker !== 'Клиент';
                return (
                  <div key={i} className={`flex gap-3 ${isEmp ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[75%] rounded-2xl p-4 text-xs leading-relaxed ${
                      isEmp ? 'bg-zinc-900 text-zinc-50 rounded-br-none shadow-sm' : 'bg-slate-50 border border-slate-200/50 text-slate-800 rounded-bl-none'
                    }`}>
                      <p className={`text-[9px] uppercase font-bold tracking-wider mb-1.5 ${isEmp ? 'text-zinc-400' : 'text-slate-400'}`}>{line.speaker}</p>
                      <p className="font-medium text-[13px]">{line.text}</p>
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>

        <div className="lg:col-span-4 space-y-6">
          <Card className="!p-6">
            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">Детали сделки</h4>
            <div className="space-y-4 border-b border-slate-100 pb-4 mb-4 text-xs">
              <Row k="Сумма:" v={amount ? `${amount.toLocaleString('ru-RU')} ₽` : '—'} />
              <div className="flex justify-between items-center">
                <span className="text-slate-400 font-medium">Результат:</span>
                <span className={`px-2.5 py-0.5 rounded-full text-[9px] uppercase font-bold tracking-wider ${
                  d.is_sold ? 'text-emerald-600 bg-emerald-50 border border-emerald-100' : 'text-slate-400 bg-slate-100'
                }`}>{d.is_sold ? 'Продано' : 'Без продажи'}</span>
              </div>
            </div>
            <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1">AI-саммари разговора</span>
            <p className="text-xs text-slate-600 leading-relaxed font-medium italic">«{a.summary}»</p>

            {(a.filler_words?.length ?? 0) > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-100">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-2">Слова-паразиты</span>
                <div className="flex flex-wrap gap-1.5">
                  {a.filler_words!.map((f, i) => (
                    <span key={i} className="text-[10px] font-bold text-amber-700 bg-amber-50 border border-amber-100 px-2 py-0.5 rounded-md">{f.word} ×{f.count}</span>
                  ))}
                </div>
              </div>
            )}

            {(a.script_compliance?.length ?? 0) > 0 && (
              <div className="mt-4 pt-4 border-t border-slate-100 space-y-2">
                <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest block mb-1">Этапы скрипта</span>
                {a.script_compliance!.map((c, i) => (
                  <div key={i} className="flex items-center justify-between text-xs font-semibold">
                    <span className="text-slate-600">{c.label}</span>
                    <span className={c.status === 'success' ? 'text-emerald-600' : c.status === 'warning' ? 'text-amber-600' : 'text-rose-500'}>
                      {c.status === 'success' ? '✓ ок' : c.status === 'warning' ? '! частично' : '✕ провал'}
                    </span>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      </div>
    </Section>
  );
}

function AnalysisList({ icon, color, title, items }: { icon: React.ReactNode; color: string; title: string; items: string[] }) {
  return (
    <div className="p-5 bg-slate-50/50 border border-slate-100 rounded-2xl">
      <div className={`flex items-center gap-2 ${color} mb-3`}>
        {icon}
        <span className="text-xs font-bold uppercase tracking-wider">{title}</span>
      </div>
      <ul className="text-xs text-slate-600 space-y-2.5 list-disc pl-4 leading-relaxed font-medium">
        {items.length ? items.map((item, i) => <li key={i}>{item}</li>) : <li className="list-none text-slate-300">—</li>}
      </ul>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string }) {
  return (
    <div className="flex justify-between items-center">
      <span className="text-slate-400 font-medium">{k}</span>
      <span className="font-bold text-slate-800 font-mono">{v}</span>
    </div>
  );
}

/* ---------- Панель записи разговора → разбор ---------- */

export function RecorderPanel({ employeeId, onDone }: { employeeId: number; onDone: (dialogues: number) => void }) {
  const [state, setState] = useState<'idle' | 'rec' | 'busy'>('idle');
  const [msg, setMsg] = useState('');

  const toggle = async () => {
    if (state === 'idle') {
      try {
        await startRecording();
        setState('rec');
        setMsg('');
      } catch (e) { setMsg(`Нет доступа к микрофону: ${e instanceof Error ? e.message : e}`); }
      return;
    }
    if (state !== 'rec') return;
    setState('busy');
    setMsg('Транскрибирую и разбираю диалоги… (до 2 минут)');
    try {
      const blob = await stopRecording();
      const r = await postAudio<{ dialogues_found: number }>('/analytics/upload', blob, { employee_id: employeeId });
      setMsg(`✅ Найдено диалогов: ${r.dialogues_found}`);
      onDone(r.dialogues_found);
    } catch (e) { setMsg(`Ошибка: ${e instanceof Error ? e.message : e}`); }
    setState('idle');
  };

  return (
    <Card className="text-center">
      {state === 'busy' ? (
        <div className="py-8 space-y-4">
          <div className="w-8 h-8 border-3 border-zinc-950 border-r-transparent rounded-full animate-spin mx-auto" />
          <p className="font-bold text-slate-800 text-sm">{msg}</p>
        </div>
      ) : (
        <div className="space-y-5 py-4">
          <div className={`w-16 h-16 rounded-full border flex items-center justify-center mx-auto ${
            state === 'rec' ? 'bg-rose-50 border-rose-200 text-rose-500' : 'bg-slate-50 border-slate-100 text-slate-500'
          }`}>
            <Mic className={`w-6 h-6 ${state === 'rec' ? 'animate-pulse' : ''}`} />
          </div>
          <div>
            <h4 className="font-bold text-slate-800 text-sm">{state === 'rec' ? 'Идёт запись разговора…' : 'Записать живой разговор'}</h4>
            <p className="text-xs text-slate-400 mt-2 max-w-xs mx-auto leading-relaxed font-medium">
              AI сам найдёт диалоги в записи, разберёт сильные и слабые стороны и подскажет, как говорить лучше.
            </p>
          </div>
          <button onClick={toggle} className={`w-full py-3 rounded-xl font-semibold text-sm transition-all cursor-pointer ${
            state === 'rec' ? 'bg-rose-50 text-rose-600 border border-rose-100 hover:bg-rose-100' : 'btn-primary'
          }`}>
            {state === 'rec' ? 'Завершить и отправить на разбор' : 'Начать запись'}
          </button>
          {msg && <p className="text-xs text-slate-400 font-medium">{msg}</p>}
        </div>
      )}
    </Card>
  );
}

/* ---------- Курсы: карточка + плеер ---------- */

export function CourseCard({ c, onClick }: { c: Course; onClick: () => void }) {
  const done = c.progress >= 100;
  return (
    <div onClick={onClick} className="bg-white border border-slate-200/60 p-5 rounded-2xl group hover:border-slate-400 hover:shadow-2xs transition-all cursor-pointer flex flex-col justify-between min-h-[160px]">
      <div className="flex items-start justify-between">
        <div className="p-2.5 bg-slate-50 rounded-xl group-hover:bg-zinc-100 transition-colors border border-slate-100">
          <Play className="w-4 h-4 text-zinc-900 fill-zinc-900" />
        </div>
        {done && <span className="text-[8px] uppercase tracking-wider font-bold bg-emerald-50 text-emerald-600 border border-emerald-100 px-2 py-0.5 rounded">Готов</span>}
      </div>
      <div>
        <h4 className="font-bold text-slate-800 text-sm mb-1 mt-3">{c.title}</h4>
        <p className="text-[11px] text-slate-400 font-medium mb-3">{c.steps.length} шагов · {c.category}</p>
        <div className="w-full h-1 bg-slate-100 rounded-full overflow-hidden">
          <div className={`h-full transition-all duration-500 ${done ? 'bg-emerald-500' : 'bg-indigo-500'}`} style={{ width: `${c.progress}%` }} />
        </div>
      </div>
    </div>
  );
}

export function CoursePlayer({ course, employeeId, onClose }: { course: Course; employeeId: number; onClose: () => void }) {
  const [idx, setIdx] = useState(0);
  const [picked, setPicked] = useState<number | null>(null);
  const steps = course.steps;
  const finished = idx >= steps.length;

  const save = (pct: number) => {
    api('/courses/progress', {
      method: 'POST',
      body: JSON.stringify({ employee_id: employeeId, course_id: course.id, progress: pct }),
    }).catch(() => {});
  };

  const next = () => {
    const n = idx + 1;
    setPicked(null);
    setIdx(n);
    save(Math.min(100, Math.round((n / steps.length) * 100)));
  };

  const st = steps[idx];

  return (
    <div className="fixed inset-0 bg-black/45 z-50 flex items-start justify-center p-4 md:p-10 overflow-y-auto" onClick={onClose}>
      <div className="bg-white rounded-3xl max-w-xl w-full p-8 relative shadow-2xl" onClick={(e) => e.stopPropagation()}>
        <button onClick={onClose} className="absolute top-4 right-4 p-2 rounded-full bg-slate-50 text-slate-400 hover:text-slate-700 cursor-pointer"><X className="w-4 h-4" /></button>

        <span className="text-[10px] font-bold text-indigo-600 uppercase tracking-widest">{course.title}</span>
        <div className="flex gap-1.5 my-4">
          {steps.map((_, i) => (
            <span key={i} className={`h-1.5 flex-1 rounded-full ${i < idx || finished ? 'bg-indigo-500' : i === idx ? 'bg-indigo-300' : 'bg-slate-100'}`} />
          ))}
        </div>

        {finished ? (
          <div className="text-center py-10">
            <div className="text-5xl mb-4">🏆</div>
            <h3 className="text-lg font-bold text-slate-900">Курс пройден!</h3>
            <p className="text-xs text-slate-400 mt-1">+25 очков к твоему профилю</p>
          </div>
        ) : st.type === 'quiz' && st.question ? (
          <div>
            <h3 className="text-base font-bold text-slate-900 mb-4">{st.question.text}</h3>
            <div className="space-y-2.5">
              {st.question.options.map((o, i) => {
                const isRight = i === st.question!.correctOption;
                const state = picked === null ? '' : picked === i ? (isRight ? 'right' : 'wrong') : '';
                return (
                  <button
                    key={i}
                    onClick={() => {
                      setPicked(i);
                      if (isRight) setTimeout(next, 650);
                    }}
                    className={`w-full text-left p-3.5 rounded-xl border text-xs font-semibold transition-all cursor-pointer ${
                      state === 'right' ? 'border-emerald-400 bg-emerald-50 text-emerald-700'
                      : state === 'wrong' ? 'border-rose-300 bg-rose-50 text-rose-600'
                      : 'border-slate-200 bg-slate-50 text-slate-700 hover:border-slate-400'
                    }`}
                  >
                    {o}
                  </button>
                );
              })}
            </div>
          </div>
        ) : (
          <div>
            <h3 className="text-base font-bold text-slate-900 mb-3">{st.title}</h3>
            <p className="text-[13px] text-slate-600 leading-relaxed whitespace-pre-wrap mb-6">{st.content}</p>
            <button onClick={next} className="btn-primary">Дальше →</button>
          </div>
        )}
      </div>
    </div>
  );
}

/* ---------- Цель ---------- */

export function GoalCard({ title, progress, target, reward, completed }: { title: string; progress: number; target: number; reward: number; completed: boolean }) {
  const percent = Math.min(100, (progress / Math.max(1, target)) * 100);
  return (
    <div className="bg-white border border-slate-200/60 p-6 rounded-3xl flex flex-col justify-between min-h-[150px] shadow-xs">
      <div className="flex justify-between items-start mb-4">
        <div>
          <h4 className="font-bold text-slate-800 text-sm leading-snug">{title}</h4>
          <span className="text-[10px] text-slate-400 font-medium block mt-1">Персональная цель</span>
        </div>
        <span className={`text-[10px] font-bold px-2.5 py-0.5 rounded-full border shrink-0 ${
          completed ? 'bg-emerald-50 text-emerald-600 border-emerald-100' : 'bg-indigo-50 text-indigo-600 border-indigo-100'
        }`}>+{reward} XP</span>
      </div>
      <div className="space-y-2 mt-4">
        <div className="flex justify-between text-[9px] font-bold uppercase tracking-widest text-slate-400">
          <span>Прогресс выполнения</span>
          <span>{progress} / {target}</span>
        </div>
        <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
          <div className={`h-full transition-all duration-500 ${completed ? 'bg-emerald-500' : 'bg-indigo-500'}`} style={{ width: `${percent}%` }} />
        </div>
      </div>
    </div>
  );
}
