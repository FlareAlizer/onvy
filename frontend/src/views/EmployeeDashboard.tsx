import { useCallback, useEffect, useRef, useState } from 'react';
import { BarChart3, Flag, GraduationCap, Languages, Mic, Sparkles, TrendingUp } from 'lucide-react';
import type { AnalysisSummary, Course, EmployeeStats, Member, Session } from '../types';
import { api, commsWsUrl, playBase64Mp3, postAudio, saveSession } from '../lib/api';
import { WakeListener } from '../lib/recorder';
import {
  AnalysisDetailView, Card, CourseCard, CoursePlayer, DialogueCard, GoalCard, Label,
  PTTButton, RecorderPanel, Section, Shell, StatCard, inputCls,
} from '../components/shared';

const NAV = [
  { label: 'Связь', icon: <Mic className="w-4.5 h-4.5" /> },
  { label: 'Аналитика', icon: <BarChart3 className="w-4.5 h-4.5" /> },
  { label: 'Показатели', icon: <TrendingUp className="w-4.5 h-4.5" /> },
  { label: 'Цели', icon: <Flag className="w-4.5 h-4.5" /> },
  { label: 'Обучение', icon: <GraduationCap className="w-4.5 h-4.5" /> },
];

const LANGS = [
  { v: 'ru', label: 'Русский' }, { v: 'en', label: 'English' }, { v: 'uz', label: 'O‘zbek' },
  { v: 'kk', label: 'Қазақ' }, { v: 'tr', label: 'Türkçe' },
];

interface Incoming {
  sender_id: number;
  text: string;
  original_text: string;
  source_language: string;
  translated: boolean;
}

export default function EmployeeDashboard({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const [active, setActive] = useState('Связь');
  const [online, setOnline] = useState<'connecting' | 'online' | 'lost'>('connecting');
  const [members, setMembers] = useState<Member[]>([]);
  const [incoming, setIncoming] = useState<Incoming[]>([]);
  const [stats, setStats] = useState<EmployeeStats | null>(null);
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [playCourse, setPlayCourse] = useState<Course | null>(null);

  const deptRef = useRef<number | null>(session.departmentId);

  const loadAll = useCallback(() => {
    api<EmployeeStats>(`/dashboard/employee/${session.employeeId}`).then(setStats).catch(() => {});
    api<AnalysisSummary[]>(`/analytics/analyses?employee_id=${session.employeeId}`).then(setAnalyses).catch(() => {});
    api<Course[]>(`/courses?employee_id=${session.employeeId}`).then(setCourses).catch(() => {});
    if (deptRef.current) api<Member[]>(`/departments/${deptRef.current}/members`).then(setMembers).catch(() => {});
  }, [session.employeeId]);

  useEffect(() => {
    loadAll();
    const t = setInterval(() => {
      if (deptRef.current) api<Member[]>(`/departments/${deptRef.current}/members`).then(setMembers).catch(() => {});
    }, 5000);
    return () => clearInterval(t);
  }, [loadAll]);

  // WebSocket доставки входящих реплик — держим всегда, играем голос автоматически.
  useEffect(() => {
    const ws = new WebSocket(commsWsUrl());
    ws.onopen = () => setOnline('online');
    ws.onclose = () => setOnline('lost');
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.error) return;
      setIncoming((prev) => [m as Incoming, ...prev].slice(0, 30));
      if (m.type === 'voice' && m.audio_base64) playBase64Mp3(m.audio_base64);
    };
    return () => ws.close();
  }, []);

  const myKpi = analyses.length ? Math.round(analyses.reduce((n, a) => n + a.kpi_score, 0) / analyses.length) : null;

  const statusDot = (
    <>
      <div className={`w-1.5 h-1.5 rounded-full ${online === 'online' ? 'bg-emerald-500 animate-pulse' : online === 'lost' ? 'bg-rose-400' : 'bg-slate-300'}`} />
      <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">
        {online === 'online' ? 'на смене' : online === 'lost' ? 'связь потеряна' : 'подключение…'}
      </span>
    </>
  );

  return (
    <Shell nav={NAV} active={active} onNav={(l) => { setActive(l); setDetailId(null); }} badge="Кабинет Сотрудника" userName={session.name} userStatus={statusDot} onLogout={onLogout}>
      {active === 'Связь' && (
        <CommsSection session={session} members={members} incoming={incoming} />
      )}

      {active === 'Аналитика' && (detailId !== null
        ? <AnalysisDetailView id={detailId} onBack={() => setDetailId(null)} />
        : (
          <Section title="Разбор моих диалогов">
            <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
              <div className="lg:col-span-5"><RecorderPanel employeeId={session.employeeId} onDone={loadAll} /></div>
              <div className="lg:col-span-7 space-y-4">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Мои последние консультации</h4>
                  <span className="text-xs text-slate-400 font-semibold">{analyses.length} шт.</span>
                </div>
                {analyses.length === 0 && <Card><p className="text-xs text-slate-400 text-center">Запиши разговор — AI разберёт его и подскажет, что улучшить</p></Card>}
                {analyses.map((a) => <DialogueCard key={a.id} a={a} onClick={() => setDetailId(a.id)} />)}
              </div>
            </div>
          </Section>
        ))}

      {active === 'Показатели' && (
        <Section title="Моя эффективность">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
            <StatCard label="Очки опыта" value={`${stats?.points ?? 0} XP`} sub="геймификация" />
            <StatCard label="Запросы ассистенту" value={String(stats?.assistant_queries ?? 0)} sub="всего" />
            <StatCard label="Реплики связи" value={String(stats?.messages_sent ?? 0)} sub="отправлено" />
            <StatCard label="Средний KPI" value={myKpi === null ? '—' : `${myKpi}%`} sub="по последним разборам" />
          </div>
        </Section>
      )}

      {active === 'Цели' && (
        <Section title="Мои текущие цели">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {(stats?.goals ?? []).length === 0 && <Card><p className="text-xs text-slate-400">Целей пока нет — их ставит РОП</p></Card>}
            {(stats?.goals ?? []).map((g) => (
              <GoalCard key={g.id} title={g.title} progress={g.progress} target={g.target} reward={g.reward_points} completed={g.done} />
            ))}
          </div>
        </Section>
      )}

      {active === 'Обучение' && (
        <Section title="Моё обучение">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {courses.length === 0 && <Card><p className="text-xs text-slate-400">Курсы появятся, когда РОП их создаст</p></Card>}
            {courses.map((c) => <CourseCard key={c.id} c={c} onClick={() => setPlayCourse(c)} />)}
          </div>
        </Section>
      )}

      {playCourse && <CoursePlayer course={playCourse} employeeId={session.employeeId} onClose={() => { setPlayCourse(null); loadAll(); }} />}
    </Shell>
  );
}

/* ---------- Связь: рация + ассистент + язык ---------- */

function CommsSection({ session, members, incoming }: { session: Session; members: Member[]; incoming: Incoming[] }) {
  const [target, setTarget] = useState('');
  const [commsMsg, setCommsMsg] = useState('');
  const [askMsg, setAskMsg] = useState('');
  const [answer, setAnswer] = useState<{ q: string; a: string } | null>(null);
  const [lang, setLang] = useState(session.language);
  const [langMsg, setLangMsg] = useState('');

  const sendVoice = async (blob: Blob) => {
    setCommsMsg('Отправляю…');
    try {
      const r = await postAudio<{ recognized_text: string; delivered_to: number[] }>('/comms/voice', blob, {
        sender_id: session.employeeId, recipient_id: target || null,
      });
      setCommsMsg(`Отправлено: «${r.recognized_text}» → ${r.delivered_to.length} онлайн`);
    } catch (e) { setCommsMsg(`Ошибка: ${e instanceof Error ? e.message : e}`); }
  };

  type AskResult = {
    query_text: string; answer_text: string; audio_base64: string;
    intent: string; connect_target_id: number | null; connect_whole_department: boolean;
  };

  const handleAskResult = async (r: AskResult, play?: (b64: string) => Promise<void>) => {
    if (r.intent === 'ignored') {
      // Показываем, что услышали — видно, что пайплайн жив и чего не хватило.
      setAskMsg(r.query_text ? `Слышу: «${r.query_text}» — жду обращения «Онви…»` : '');
      return;
    }
    setAnswer({ q: r.query_text || '—', a: r.answer_text });
    setAskMsg('');
    // «Онви, соедини с …» → ассистент сам подставляет получателя в рацию.
    if (r.intent === 'connect') {
      setTarget(r.connect_whole_department ? '' : String(r.connect_target_id ?? ''));
      setCommsMsg(`🔗 Онви: ${r.answer_text}`);
    }
    if (r.audio_base64) {
      if (play) await play(r.audio_base64);
      else playBase64Mp3(r.audio_base64);
    }
  };

  const ask = async (blob: Blob) => {
    setAskMsg('Думаю…');
    try {
      await handleAskResult(await postAudio<AskResult>('/voice/assistant', blob, { employee_id: session.employeeId }));
    } catch (e) { setAskMsg(`Ошибка: ${e instanceof Error ? e.message : e}`); }
  };

  // --- Режим «Онви всегда слушает»: микрофон открыт, сервер реагирует только на «Онви…» ---
  const [handsFree, setHandsFree] = useState(false);
  const [hfState, setHfState] = useState<'idle' | 'speech' | 'sending'>('idle');
  const listenerRef = useRef<WakeListener | null>(null);

  const toggleHandsFree = async () => {
    if (handsFree) {
      await listenerRef.current?.stop();
      listenerRef.current = null;
      setHandsFree(false);
      setAskMsg('');
      return;
    }
    const listener = new WakeListener(
      async (blob) => {
        try {
          const r = await postAudio<AskResult>('/voice/assistant', blob, {
            employee_id: session.employeeId, require_wake: 1,
          });
          // Звук — через WebAudio-контекст слушателя: на телефонах обычный
          // Audio().play() вне жеста блокируется; заодно busy на время ответа.
          await handleAskResult(r, (b64) => listener.playMp3(b64));
        } catch (e) {
          setAskMsg(`Ошибка: ${e instanceof Error ? e.message : e}`);
        }
      },
      setHfState,
    );
    try {
      await listener.start();
      listenerRef.current = listener;
      setHandsFree(true);
      setAskMsg('');
    } catch (e) {
      setAskMsg(`Микрофон недоступен: ${e instanceof Error ? e.message : e}`);
    }
  };

  // Выключаем микрофон при уходе со страницы.
  useEffect(() => () => { void listenerRef.current?.stop(); }, []);

  const changeLang = async (v: string) => {
    setLang(v);
    try {
      await api(`/employees/${session.employeeId}`, { method: 'PATCH', body: JSON.stringify({ language: v }) });
      saveSession({ ...session, language: v });
      setLangMsg(`Сохранено: ${v}`);
    } catch (e) { setLangMsg(`Ошибка: ${e instanceof Error ? e.message : e}`); }
  };

  return (
    <Section title="Связь и ассистент">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        <div className="lg:col-span-7 space-y-6">
          <Card>
            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">📻 Рация с переводом</h4>
            <Label>Кому говорить</Label>
            <select value={target} onChange={(e) => setTarget(e.target.value)} className={inputCls}>
              <option value="">📢 Всему отделу</option>
              {members.filter((m) => m.id !== session.employeeId).map((m) => (
                <option key={m.id} value={m.id}>{m.name} ({m.language}){m.online ? ' — онлайн' : ' — офлайн'}</option>
              ))}
            </select>
            <div className="py-6"><PTTButton onClip={sendVoice} /></div>
            <p className="text-xs text-slate-400 text-center font-medium min-h-[16px]">{commsMsg}</p>
          </Card>

          <Card>
            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4 flex items-center gap-2">
              <Sparkles className="w-4 h-4 text-yellow-500" /> Голосовой ассистент «Онви»
            </h4>
            <button
              onClick={toggleHandsFree}
              className={`w-full mb-3 py-3 rounded-xl border text-xs font-bold transition-all cursor-pointer ${
                handsFree
                  ? hfState === 'speech' ? 'border-emerald-400 bg-emerald-50 text-emerald-700 animate-pulse'
                  : hfState === 'sending' ? 'border-indigo-400 bg-indigo-50 text-indigo-700'
                  : 'border-emerald-300 bg-emerald-50/60 text-emerald-600'
                  : 'border-slate-200 bg-slate-50 text-slate-500 hover:border-slate-400'
              }`}
            >
              {handsFree
                ? hfState === 'speech' ? '🎙 Слышу речь…'
                : hfState === 'sending' ? '🧠 Распознаю…'
                : '🟢 Онви слушает — скажи «Онви, …» (нажми, чтобы выключить)'
                : '🎙 Включить режим «Онви слушает» (без кнопки)'}
            </button>
            <div className="py-2"><PTTButton onClip={ask} size="md" label="Или зажми и говори" /></div>
            <p className="text-xs text-slate-400 text-center font-medium min-h-[16px]">{askMsg || '«Онви, что в составе…» — ответит голосом · «Онви, соедини с Иваном» — включит рацию'}</p>
            {answer && (
              <div className="mt-4 p-4 bg-slate-50 border border-slate-100 rounded-2xl text-xs space-y-1.5">
                <p><span className="font-bold text-slate-400">Вы:</span> <span className="font-medium text-slate-700">{answer.q}</span></p>
                <p><span className="font-bold text-indigo-600">Ассистент:</span> <span className="font-medium text-slate-800">{answer.a}</span></p>
              </div>
            )}
          </Card>
        </div>

        <div className="lg:col-span-5 space-y-6">
          <Card className="!p-6">
            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-3 flex items-center gap-2">
              <Languages className="w-4 h-4" /> Мой язык
            </h4>
            <p className="text-[11px] text-slate-400 font-medium mb-3">На нём я слышу коллег и ассистента</p>
            <select value={lang} onChange={(e) => changeLang(e.target.value)} className={inputCls}>
              {LANGS.map((l) => <option key={l.v} value={l.v}>{l.label}</option>)}
            </select>
            {langMsg && <p className="text-[11px] text-slate-400 font-medium mt-2">{langMsg}</p>}
          </Card>

          <Card className="!p-6">
            <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">Входящие (играют голосом сами)</h4>
            <div className="space-y-3 max-h-[320px] overflow-y-auto pr-1">
              {incoming.length === 0 && <p className="text-xs text-slate-400">Пока пусто</p>}
              {incoming.map((m, i) => (
                <div key={i} className="p-3 bg-slate-50 border border-slate-100 rounded-xl text-xs">
                  <div className="flex items-center justify-between mb-1">
                    <span className="font-bold text-slate-700">#{m.sender_id}</span>
                    {m.translated && <span className="text-[9px] font-bold text-indigo-600 bg-indigo-50 border border-indigo-100 px-1.5 py-0.5 rounded uppercase">переведено</span>}
                  </div>
                  <p className="font-medium text-slate-800">{m.text}</p>
                  {m.translated && <p className="text-[10px] text-slate-400 mt-1">ориг. ({m.source_language}): {m.original_text}</p>}
                </div>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </Section>
  );
}
