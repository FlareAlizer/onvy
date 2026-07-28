import { useCallback, useEffect, useRef, useState } from 'react';
import {
  BarChart3, BookOpen, Database, Flag, GraduationCap, Mic, Plus, TrendingUp, UserPlus,
} from 'lucide-react';
import type { AnalysisSummary, Course, Member, RopDashboard as Dash, Session } from '../types';
import { api, apiRaw, commsWsUrl, playBase64Mp3, postAudio } from '../lib/api';
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
  { label: 'База знаний', icon: <BookOpen className="w-4.5 h-4.5" /> },
  { label: 'Пригласить', icon: <UserPlus className="w-4.5 h-4.5" /> },
];

const DEMO_CATALOG = `Наушники Sony WH-1000XM5; 34990; 4; стеллаж A3; беспроводные, шумоподавление, 30ч; сони, наушники, xm5
Дрель Bosch GSB 13 RE; 5990; 12; зона B2; ударная, 600 Вт; дрель, бош
Кофемашина De'Longhi Magnifica; 42990; 3; витрина 5; автоматическая, капучинатор; кофемашина, делонги
Смартфон Samsung Galaxy A55; 33990; 8; стеллаж C1; 6.6", 128ГБ; самсунг, телефон
Пылесос Dyson V15; 54990; 2; зона D4; беспроводной, 60 мин; дайсон, пылесос`;

export default function ROPDashboard({ session, onLogout }: { session: Session; onLogout: () => void }) {
  const [active, setActive] = useState('Связь');
  const [online, setOnline] = useState<'connecting' | 'online' | 'lost'>('connecting');

  const [members, setMembers] = useState<Member[]>([]);
  const [dash, setDash] = useState<Dash | null>(null);
  const [analyses, setAnalyses] = useState<AnalysisSummary[]>([]);
  const [courses, setCourses] = useState<Course[]>([]);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [playCourse, setPlayCourse] = useState<Course | null>(null);
  const [qrSvg, setQrSvg] = useState('');

  const deptRef = useRef<number | null>(session.departmentId);

  const loadMembers = useCallback(async () => {
    if (!deptRef.current) {
      const depts = await api<{ id: number }[]>('/departments');
      deptRef.current = depts[0]?.id ?? null;
    }
    if (deptRef.current) setMembers(await api<Member[]>(`/departments/${deptRef.current}/members`));
  }, []);

  const loadAll = useCallback(() => {
    loadMembers().catch(() => {});
    api<Dash>('/dashboard/rop').then(setDash).catch(() => {});
    api<AnalysisSummary[]>('/analytics/analyses').then(setAnalyses).catch(() => {});
    api<Course[]>('/courses').then(setCourses).catch(() => {});
  }, [loadMembers]);

  useEffect(() => {
    loadAll();
    const t = setInterval(() => loadMembers().catch(() => {}), 5000);
    return () => clearInterval(t);
  }, [loadAll, loadMembers]);

  // WebSocket: менеджер онлайн и слышит голосовые ответы
  useEffect(() => {
    const ws = new WebSocket(commsWsUrl());
    ws.onopen = () => setOnline('online');
    ws.onclose = () => setOnline('lost');
    ws.onmessage = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.type === 'voice' && m.audio_base64) playBase64Mp3(m.audio_base64);
    };
    return () => ws.close();
  }, []);

  useEffect(() => {
    if (active !== 'Пригласить' || qrSvg) return;
    (async () => {
      if (!deptRef.current) {
        const depts = await api<{ id: number }[]>('/departments');
        deptRef.current = depts[0]?.id ?? null;
      }
      if (!deptRef.current) return;
      setQrSvg(await apiRaw(`/departments/${deptRef.current}/qr?base=${encodeURIComponent(location.origin)}`));
    })().catch((e) => setQrSvg(`<p class="text-xs text-rose-500">QR недоступен: ${e.message}</p>`));
  }, [active, qrSvg]);

  const kpiAvg = analyses.length ? Math.round(analyses.reduce((n, a) => n + a.kpi_score, 0) / analyses.length) : null;
  const soldCount = analyses.filter((a) => a.is_sold).length;

  const statusDot = (
    <>
      <div className={`w-1.5 h-1.5 rounded-full ${online === 'online' ? 'bg-emerald-500 animate-pulse' : online === 'lost' ? 'bg-rose-400' : 'bg-slate-300'}`} />
      <span className="text-[10px] text-slate-400 font-bold uppercase tracking-wider">
        {online === 'online' ? 'на связи' : online === 'lost' ? 'связь потеряна' : 'подключение…'}
      </span>
    </>
  );

  return (
    <Shell nav={NAV} active={active} onNav={(l) => { setActive(l); setDetailId(null); }} badge="Панель РОПа" userName={session.name} userStatus={statusDot} onLogout={onLogout}>
      {active === 'Связь' && <CommsSection session={session} members={members} />}

      {active === 'Аналитика' && (detailId !== null
        ? <AnalysisDetailView id={detailId} onBack={() => setDetailId(null)} />
        : <AnalyticsSection session={session} members={members} analyses={analyses} onOpen={setDetailId} onRefresh={loadAll} />)}

      {active === 'Показатели' && <MetricsSection dash={dash} analysesCount={analyses.length} soldCount={soldCount} kpiAvg={kpiAvg} />}

      {active === 'Цели' && <GoalsSection dash={dash} onCreated={loadAll} />}

      {active === 'Обучение' && (
        <LearnSection courses={courses} analyses={analyses} onCreated={loadAll} onOpen={setPlayCourse} />
      )}

      {active === 'База знаний' && <KnowledgeSection />}

      {active === 'Пригласить' && (
        <Section title="Пригласить в отдел">
          <Card className="text-center max-w-xl mx-auto">
            <div className="w-fit mx-auto mb-6 p-4 bg-slate-50 border border-slate-100 rounded-2xl [&_svg]:w-52 [&_svg]:h-52" dangerouslySetInnerHTML={{ __html: qrSvg || '<p class="text-xs text-slate-400">Загружаю QR…</p>' }} />
            <h3 className="text-lg font-bold text-slate-900 mb-2">QR-код быстрого подключения</h3>
            <p className="text-slate-400 text-xs max-w-sm mx-auto leading-relaxed font-medium">
              Сотрудники сканируют телефоном и заходят в этот отдел в роли «Сотрудник»,
              каждый выбирает свой язык. Код доступа уже зашит в ссылку.
            </p>
          </Card>
        </Section>
      )}

      {playCourse && <CoursePlayer course={playCourse} employeeId={session.employeeId} onClose={() => { setPlayCourse(null); loadAll(); }} />}
    </Shell>
  );
}

/* ---------- Связь: рация с переводом ---------- */

function CommsSection({ session, members }: { session: Session; members: Member[] }) {
  const [target, setTarget] = useState('');
  const [status, setStatus] = useState('Зажми кнопку и говори — каждый услышит на своём языке');

  const send = async (blob: Blob) => {
    setStatus('Отправляю…');
    try {
      const r = await postAudio<{ recognized_text: string; delivered_to: number[] }>('/comms/voice', blob, {
        sender_id: session.employeeId,
        recipient_id: target || null,
      });
      setStatus(`«${r.recognized_text}» → доставлено ${r.delivered_to.length}`);
    } catch (e) { setStatus(`Ошибка: ${e instanceof Error ? e.message : e}`); }
  };

  return (
    <Section title="Связь с отделом">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        <Card className="lg:col-span-7">
          <Label>Кому говорить</Label>
          <select value={target} onChange={(e) => setTarget(e.target.value)} className={inputCls}>
            <option value="">📢 Весь отдел (broadcast)</option>
            {members.filter((m) => m.id !== session.employeeId).map((m) => (
              <option key={m.id} value={m.id}>{m.name} ({m.language}){m.online ? ' — онлайн' : ' — офлайн'}</option>
            ))}
          </select>
          <div className="py-8"><PTTButton onClip={send} /></div>
          <p className="text-xs text-slate-400 text-center font-medium min-h-[16px]">{status}</p>
        </Card>

        <Card className="lg:col-span-5">
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">Ростер отдела</h4>
          <div className="space-y-3">
            {members.length === 0 && <p className="text-xs text-slate-400">Пока никого — покажи QR из раздела «Пригласить»</p>}
            {members.map((m) => (
              <div key={m.id} className="flex items-center justify-between text-xs font-semibold">
                <span className="text-slate-700">{m.name} <span className="text-slate-400 font-medium">· {m.language}</span></span>
                <span className={`flex items-center gap-1.5 ${m.online ? 'text-emerald-600' : 'text-slate-400'}`}>
                  <span className={`w-1.5 h-1.5 rounded-full ${m.online ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300'}`} />
                  {m.online ? 'онлайн' : 'офлайн'}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </Section>
  );
}

/* ---------- Аналитика диалогов ---------- */

function AnalyticsSection({ session, members, analyses, onOpen, onRefresh }: {
  session: Session; members: Member[]; analyses: AnalysisSummary[];
  onOpen: (id: number) => void; onRefresh: () => void;
}) {
  const [text, setText] = useState('');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const analyzeText = async () => {
    if (!text.trim()) return;
    setBusy(true);
    setMsg('Разбираю транскрипт… (до 2 минут)');
    try {
      const r = await api<{ dialogues_found: number }>('/analytics/analyze-text', {
        method: 'POST',
        body: JSON.stringify({ text, employee_id: session.employeeId }),
      });
      setMsg(`✅ Найдено диалогов: ${r.dialogues_found}`);
      setText('');
      onRefresh();
    } catch (e) { setMsg(`Ошибка: ${e instanceof Error ? e.message : e}`); }
    setBusy(false);
  };

  const nameOf = (id: number | null) => members.find((m) => m.id === id)?.name ?? (id ? `#${id}` : '—');

  return (
    <Section title="Аналитика отдела продаж">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8 items-stretch">
        <RecorderPanel employeeId={session.employeeId} onDone={onRefresh} />
        <Card>
          <h4 className="font-bold text-slate-800 text-sm mb-2">Загрузить транскрипт (способ Б)</h4>
          <p className="text-[11px] text-slate-400 font-medium mb-3">Вставь текст разговора — AI нарежет на диалоги и разберёт каждый</p>
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={5} placeholder="Здравствуйте! Подскажите, сколько стоят наушники?…" className={`${inputCls} font-mono resize-y`} />
          <button onClick={analyzeText} disabled={busy || !text.trim()} className="btn-primary w-full mt-3">
            {busy ? 'Разбираю…' : 'Разобрать текст'}
          </button>
          {msg && <p className="text-xs text-slate-400 font-medium mt-2">{msg}</p>}
        </Card>
      </div>

      <div className="flex items-center justify-between mb-4">
        <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Все разборы диалогов</h4>
        <span className="text-xs text-slate-400 font-semibold">{analyses.length} шт.</span>
      </div>
      <div className="space-y-3">
        {analyses.length === 0 && <Card><p className="text-xs text-slate-400 text-center">Разборов пока нет — запиши разговор или вставь транскрипт</p></Card>}
        {analyses.map((a) => (
          <div key={a.id} className="relative">
            <DialogueCard a={a} onClick={() => onOpen(a.id)} />
            <span className="absolute top-3 right-14 text-[9px] text-slate-300 font-bold">{nameOf(a.employee_id)}</span>
          </div>
        ))}
      </div>
    </Section>
  );
}

/* ---------- Показатели ---------- */

function MetricsSection({ dash, analysesCount, soldCount, kpiAvg }: {
  dash: Dash | null; analysesCount: number; soldCount: number; kpiAvg: number | null;
}) {
  return (
    <Section title="Дашборд отдела">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 mb-8">
        <StatCard label="Запросы ассистенту" value={String(dash?.total_assistant_queries ?? 0)} sub={`ответ найден: ${Math.round((dash?.assistant_hit_rate ?? 0) * 100)}%`} />
        <StatCard label="Реплики связи" value={String(dash?.total_messages ?? 0)} sub="рация + перевод" />
        <StatCard label="Диалогов разобрано" value={String(analysesCount)} sub={`продаж: ${soldCount}`} />
        <StatCard label="Средний KPI" value={kpiAvg === null ? '—' : `${kpiAvg}%`} sub="по разборам AI" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        <Card className="lg:col-span-7 !p-6">
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">Показатели команды</h4>
          <div className="overflow-x-auto">
            <table className="w-full text-left">
              <thead className="text-[10px] uppercase text-slate-400 border-b border-slate-100/50">
                <tr>
                  <th className="pb-3 font-semibold">Сотрудник</th>
                  <th className="pb-3 font-semibold">Статус</th>
                  <th className="pb-3 font-semibold">Очки</th>
                  <th className="pb-3 font-semibold">Запросы</th>
                </tr>
              </thead>
              <tbody className="text-xs">
                {(dash?.team ?? []).map((e) => (
                  <tr key={e.employee_id} className="border-b border-slate-100/50 last:border-0 hover:bg-slate-50/50">
                    <td className="py-3.5">
                      <div className="flex flex-col">
                        <span className="font-semibold text-slate-800 text-[13px]">{e.name}</span>
                        <span className="text-[9px] text-slate-400 font-semibold uppercase mt-0.5">{e.role === 'rop' ? 'РОП' : 'Сотрудник'} · {e.language}</span>
                      </div>
                    </td>
                    <td className="py-3.5">
                      <div className="flex items-center gap-2">
                        <div className={`w-1.5 h-1.5 rounded-full ${e.online ? 'bg-emerald-500 animate-pulse' : 'bg-slate-300'}`} />
                        <span className={`text-[10px] font-bold uppercase tracking-wider ${e.online ? 'text-emerald-600' : 'text-slate-400'}`}>{e.online ? 'на смене' : 'офлайн'}</span>
                      </div>
                    </td>
                    <td className="py-3.5 font-mono font-bold text-slate-800">{e.points} XP</td>
                    <td className="py-3.5 font-mono text-slate-400 font-medium">{e.assistant_queries}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>

        <Card className="lg:col-span-5 !p-6">
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest mb-4">Топ запросов к ассистенту</h4>
          <div className="space-y-4">
            {(dash?.top_queries ?? []).length === 0 && <p className="text-xs text-slate-400">Пока пусто</p>}
            {(dash?.top_queries ?? []).map((t, i) => {
              const max = dash!.top_queries[0]?.count || 1;
              return (
                <div key={i} className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-600 truncate pr-3">{t.query}</span>
                  <div className="flex items-center gap-3 shrink-0">
                    <div className="h-1.5 w-24 bg-slate-50 border border-slate-100 rounded-full overflow-hidden">
                      <div className="h-full bg-zinc-900 rounded-full" style={{ width: `${(t.count / max) * 100}%` }} />
                    </div>
                    <span className="text-[10px] font-mono font-bold text-slate-800 min-w-[15px]">{t.count}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </div>
    </Section>
  );
}

/* ---------- Цели ---------- */

function GoalsSection({ dash, onCreated }: { dash: Dash | null; onCreated: () => void }) {
  const [emp, setEmp] = useState('');
  const [title, setTitle] = useState('');
  const [target, setTarget] = useState('20');
  const [reward, setReward] = useState('50');
  const [msg, setMsg] = useState('');

  const create = async () => {
    if (!emp || !title.trim()) { setMsg('Выбери сотрудника и укажи название'); return; }
    try {
      await api('/goals', {
        method: 'POST',
        body: JSON.stringify({ employee_id: Number(emp), title: title.trim(), target: Number(target) || 1, reward_points: Number(reward) || 0 }),
      });
      setMsg('✅ Цель поставлена');
      setTitle('');
      onCreated();
    } catch (e) { setMsg(`Ошибка: ${e instanceof Error ? e.message : e}`); }
  };

  const allGoals = (dash?.team ?? []).flatMap((e) => e.goals.map((g) => ({ ...g, who: e.name })));

  return (
    <Section title="Цели сотрудникам">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        <Card className="lg:col-span-7">
          <span className="text-[10px] uppercase font-bold tracking-widest text-slate-400 block mb-1">Постановка задач</span>
          <h3 className="text-lg font-bold text-slate-900 mb-6">Создать новую цель</h3>
          <div className="space-y-5">
            <div>
              <Label>Сотрудник:</Label>
              <select value={emp} onChange={(e) => setEmp(e.target.value)} className={inputCls}>
                <option value="">— выбери —</option>
                {(dash?.team ?? []).map((e) => <option key={e.employee_id} value={e.employee_id}>{e.name}</option>)}
              </select>
            </div>
            <div>
              <Label>Название цели:</Label>
              <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Напр. 20 подсказок за смену" className={inputCls} />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div><Label>Целевое значение:</Label><input type="number" value={target} onChange={(e) => setTarget(e.target.value)} className={inputCls} /></div>
              <div><Label>Награда XP:</Label><input type="number" value={reward} onChange={(e) => setReward(e.target.value)} className={inputCls} /></div>
            </div>
            <button onClick={create} className="w-full btn-primary py-3 mt-2 font-semibold">Активировать цель</button>
            {msg && <p className="text-xs text-slate-400 font-medium">{msg}</p>}
          </div>
        </Card>

        <div className="lg:col-span-5 space-y-4">
          <h4 className="text-xs font-bold text-slate-400 uppercase tracking-widest">Действующие цели</h4>
          {allGoals.length === 0 && <Card><p className="text-xs text-slate-400">Целей пока нет</p></Card>}
          {allGoals.map((g) => (
            <GoalCard key={g.id} title={`${g.title} (${g.who})`} progress={g.progress} target={g.target} reward={g.reward_points} completed={g.done} />
          ))}
        </div>
      </div>
    </Section>
  );
}

/* ---------- Обучение ---------- */

function LearnSection({ courses, analyses, onCreated, onOpen }: {
  courses: Course[]; analyses: AnalysisSummary[]; onCreated: () => void; onOpen: (c: Course) => void;
}) {
  const [topic, setTopic] = useState('');
  const [useErrors, setUseErrors] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState('');

  const generate = async () => {
    if (!topic.trim()) { setMsg('Укажи тему курса'); return; }
    setBusy(true);
    setMsg('Генерирую курс… (до минуты)');
    try {
      let material = '';
      if (useErrors && analyses.length) {
        const details = await Promise.all(
          analyses.slice(0, 3).map((a) => api<{ analysis: { weaknesses?: string[]; mistakes_and_fixes?: { error: string; fix: string }[] } }>(`/analytics/analyses/${a.id}`)),
        );
        material = details
          .map((d) => [
            ...(d.analysis.weaknesses ?? []),
            ...(d.analysis.mistakes_and_fixes ?? []).map((m) => `Ошибка: ${m.error}. Надо: ${m.fix}`),
          ].join('\n'))
          .join('\n');
      }
      await api('/courses/generate', { method: 'POST', body: JSON.stringify({ topic: topic.trim(), material }) });
      setMsg('✅ Курс создан');
      setTopic('');
      onCreated();
    } catch (e) { setMsg(`Ошибка: ${e instanceof Error ? e.message : e}`); }
    setBusy(false);
  };

  return (
    <Section title="Обучение команды">
      <Card className="mb-8">
        <div className="flex flex-col lg:flex-row gap-6 items-end justify-between border-b border-slate-100 pb-6 mb-6">
          <div className="flex-1 w-full">
            <Label>Тема для генерации курса:</Label>
            <input value={topic} onChange={(e) => setTopic(e.target.value)} placeholder="Напр. Отработка возражений по цене" className={inputCls} />
          </div>
          <label className="flex items-center gap-3 shrink-0 py-2.5 cursor-pointer">
            <input type="checkbox" checked={useErrors} onChange={(e) => setUseErrors(e.target.checked)} className="w-4 h-4 rounded border-slate-300 accent-zinc-900" />
            <span className="text-xs font-semibold text-slate-500">Базировать на частых ошибках отдела</span>
          </label>
          <button onClick={generate} disabled={busy} className="btn-primary flex items-center gap-1.5 shrink-0 w-full lg:w-auto justify-center font-semibold">
            <Plus className="w-4 h-4" /> {busy ? 'Генерирую…' : 'Создать курс ИИ'}
          </button>
        </div>
        {msg && <p className="text-xs text-slate-400 font-medium mb-4">{msg}</p>}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {courses.length === 0 && <p className="text-xs text-slate-400 col-span-3">Курсов пока нет — сгенерируй первый</p>}
          {courses.map((c) => <CourseCard key={c.id} c={c} onClick={() => onOpen(c)} />)}
        </div>
      </Card>
    </Section>
  );
}

/* ---------- База знаний ---------- */

function KnowledgeSection() {
  const [p, setP] = useState({ name: '', price: '', stock: '', location: '', description: '', aliases: '' });
  const [bulk, setBulk] = useState('');
  const [msg1, setMsg1] = useState('');
  const [msg2, setMsg2] = useState('');

  const addOne = async () => {
    if (!p.name.trim()) { setMsg1('Укажи название'); return; }
    try {
      await api('/products', {
        method: 'POST',
        body: JSON.stringify({
          name: p.name, price: Number(p.price) || 0, stock: Number(p.stock) || 0,
          location: p.location, description: p.description, aliases: p.aliases,
        }),
      });
      setMsg1('✅ Добавлено');
      setP({ name: '', price: '', stock: '', location: '', description: '', aliases: '' });
    } catch (e) { setMsg1(`Ошибка: ${e instanceof Error ? e.message : e}`); }
  };

  const uploadBulk = async (text: string) => {
    const items = text.split(/\r?\n/).map((line) => line.split(';').map((x) => x.trim()))
      .filter((f) => f[0])
      .map((f) => ({ name: f[0], price: Number(f[1]) || 0, stock: Number(f[2]) || 0, location: f[3] ?? '', description: f[4] ?? '', aliases: f[5] ?? '' }));
    if (!items.length) { setMsg2('Не нашёл ни одной строки'); return; }
    try {
      const r = await api<{ created: number }>('/products/bulk', { method: 'POST', body: JSON.stringify({ items }) });
      setMsg2(`✅ Загружено товаров: ${r.created}`);
    } catch (e) { setMsg2(`Ошибка: ${e instanceof Error ? e.message : e}`); }
  };

  const set = (k: keyof typeof p) => (e: React.ChangeEvent<HTMLInputElement>) => setP({ ...p, [k]: e.target.value });

  return (
    <Section title="База знаний магазина">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        <Card className="lg:col-span-5">
          <h4 className="text-sm font-bold text-slate-900 mb-6 flex items-center gap-2"><Database className="w-4 h-4" /> Добавить один товар</h4>
          <div className="space-y-4">
            <div><Label>Название товара</Label><input value={p.name} onChange={set('name')} placeholder="Напр. Marshall Major IV" className={inputCls} /></div>
            <div className="grid grid-cols-2 gap-4">
              <div><Label>Цена, ₽</Label><input type="number" value={p.price} onChange={set('price')} placeholder="14990" className={inputCls} /></div>
              <div><Label>Остаток, шт</Label><input type="number" value={p.stock} onChange={set('stock')} placeholder="18" className={inputCls} /></div>
            </div>
            <div><Label>Расположение (склад/витрина)</Label><input value={p.location} onChange={set('location')} placeholder="Склад B, ячейка 14" className={inputCls} /></div>
            <div><Label>Ключевые преимущества</Label><input value={p.description} onChange={set('description')} placeholder="80 часов работы, быстрая зарядка" className={inputCls} /></div>
            <div><Label>Синонимы через запятую</Label><input value={p.aliases} onChange={set('aliases')} placeholder="маршал, наушники" className={inputCls} /></div>
            <button onClick={addOne} className="w-full btn-primary py-2.5 font-semibold mt-2">Сохранить товар</button>
            {msg1 && <p className="text-xs text-slate-400 font-medium">{msg1}</p>}
          </div>
        </Card>

        <Card className="lg:col-span-7">
          <h4 className="text-sm font-bold text-slate-900 mb-2">Импорт каталога товаров</h4>
          <p className="text-xs text-slate-400 font-medium mb-4">Строка = товар, поля через <b>;</b> — Название; цена; остаток; расположение; преимущества; синонимы</p>
          <textarea value={bulk} onChange={(e) => setBulk(e.target.value)} className={`${inputCls} h-44 font-mono resize-y mb-4`} placeholder="Название; цена; остаток; расположение; преимущества; синонимы…" />
          <div className="flex flex-col sm:flex-row gap-3">
            <button onClick={() => uploadBulk(bulk)} className="flex-1 btn-primary text-xs font-semibold">Загрузить каталог</button>
            <button onClick={() => { setBulk(DEMO_CATALOG); uploadBulk(DEMO_CATALOG); }} className="flex-1 px-4 py-2.5 bg-slate-50 text-slate-600 rounded-xl font-semibold text-xs hover:bg-slate-100 transition-all border border-slate-200 cursor-pointer">
              Заполнить демо-данными
            </button>
          </div>
          {msg2 && <p className="text-xs text-slate-400 font-medium mt-3">{msg2}</p>}
        </Card>
      </div>
    </Section>
  );
}
