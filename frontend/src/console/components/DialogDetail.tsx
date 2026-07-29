import { useRef, useState } from 'react';
import { AlertTriangle, Check, HandHelping, Lightbulb, ShieldAlert, Sparkles } from 'lucide-react';
import { DialogTrack } from './Waveform';
import { Card, Chip } from './ui';
import { useStore } from '../store';
import { humanDateTime, mmss, money, num, pct } from '../lib/format';
import type { Dialog, MomentType } from '../types';

const MOMENT_STYLE: Record<MomentType, { bg: string; icon: typeof Check; label: string }> = {
  win: { bg: 'bg-emerald-500', icon: Check, label: 'Удачно' },
  miss: { bg: 'bg-rose-500', icon: AlertTriangle, label: 'Ошибка' },
  help: { bg: 'bg-amber-500', icon: HandHelping, label: 'Обращение за помощью' },
};

export function DialogDetail({ dialog, who }: { dialog: Dialog; who?: string }) {
  const { profile } = useStore();
  const L = profile.labels;
  const [activeMoment, setActiveMoment] = useState<string | null>(null);
  const lineRefs = useRef<Record<string, HTMLLIElement | null>>({});

  const speakerMeta = {
    client: { name: L.client, cls: 'bg-slate-100 text-slate-600' },
    employee: { name: L.employee, cls: 'bg-brand-50 text-brand-700' },
    ai: { name: 'Подсказка Onvy', cls: 'bg-violet-50 text-violet-700' },
    colleague: { name: L.helpTarget, cls: 'bg-amber-50 text-amber-800' },
  };

  const outcomeMeta = {
    success: { label: L.outcome, tone: 'good' as const },
    lost: { label: L.outcomeLost, tone: 'bad' as const },
    consult: { label: `${L.interaction} без результата`, tone: 'neutral' as const },
  };

  const goToMoment = (id: string) => {
    setActiveMoment(id);
    const line = dialog.transcript.find((l) => l.momentId === id);
    if (line) lineRefs.current[line.id]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
  };

  const wins = dialog.moments.filter((m) => m.type === 'win');
  const misses = dialog.moments.filter((m) => m.type === 'miss');
  const helps = dialog.moments.filter((m) => m.type === 'help');
  const outcome = outcomeMeta[dialog.outcome];
  const unverified = dialog.transcript.filter((l) => l.unverified);

  return (
    <div className="space-y-4">
      {/* Шапка разговора */}
      <div className="flex flex-wrap items-center gap-2">
        <Chip tone={outcome.tone}>{outcome.label}</Chip>
        {dialog.revenue > 0 && <Chip tone="brand">{money(dialog.revenue)}</Chip>}
        <Chip tone={dialog.scriptScore >= 85 ? 'good' : dialog.scriptScore >= 70 ? 'warn' : 'bad'}>
          {L.script} {pct(dialog.scriptScore, 0)}
        </Chip>
        {dialog.simulated && <Chip tone="neutral">Демо-запись</Chip>}
        <span className="num text-[12px] text-slate-500">
          {humanDateTime(dialog.startedAt)} · {mmss(dialog.durationSec)} · ответ{' '}
          {dialog.responseSec.toFixed(1).replace('.', ',')} сек
          {who ? ` · ${who}` : ''}
        </span>
      </div>

      {unverified.length > 0 && (
        <div className="flex items-start gap-3 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <ShieldAlert size={17} className="mt-0.5 shrink-0 text-amber-600" />
          <div>
            <p className="text-[14px] font-semibold text-amber-900">
              Onvy отказался отвечать без подтверждения
            </p>
            <p className="mt-1 text-[13px] leading-relaxed text-amber-900">
              В диалоге прозвучал вопрос, по которому в базе не было подтверждённых данных. Вместо
              догадки система потребовала уточнить у {L.helpTargetGenitive}.
            </p>
          </div>
        </div>
      )}

      {/* Дорожка разговора */}
      <Card className="p-5">
        <div className="mb-1 flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-[15px] font-semibold text-ink">Дорожка разговора</h3>
            <p className="mt-0.5 text-[13px] text-slate-500">
              Onvy отметил {wins.length} удачных, {misses.length} ошибочных и {helps.length} моментов с
              обращением за помощью. Нажмите на маркер, чтобы перейти к реплике.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-[12px] text-slate-600">
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" /> Удачно
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-rose-500" /> Ошибка
            </span>
            <span className="inline-flex items-center gap-1.5">
              <span className="h-2.5 w-2.5 rounded-full bg-amber-500" /> Помощь
            </span>
          </div>
        </div>

        <DialogTrack
          wave={dialog.wave}
          moments={dialog.moments}
          activeMomentId={activeMoment}
          onSelectMoment={(m) => goToMoment(m.id)}
        />

        <div className="mt-1 flex justify-between text-[11px] text-slate-500">
          <span className="num">0:00</span>
          <span className="num">{mmss(dialog.durationSec)}</span>
        </div>
      </Card>

      {/* Позиции */}
      {dialog.items.length > 0 && (
        <Card className="p-5">
          <h3 className="mb-3 text-[15px] font-semibold text-ink">{L.items}</h3>
          <div className="overflow-x-auto scroll-thin">
            <table className="w-full min-w-[320px] text-sm">
              <thead>
                <tr className="border-b border-slate-200">
                  <th className="label pb-2 text-left">Позиция</th>
                  <th className="label pb-2 text-right">Кол-во</th>
                  <th className="label pb-2 text-right">Сумма</th>
                </tr>
              </thead>
              <tbody>
                {dialog.items.map((it) => (
                  <tr key={it.name} className="border-b border-slate-100 last:border-0">
                    <td className="py-2 text-slate-700">{it.name}</td>
                    <td className="num py-2 text-right text-slate-600">{it.qty}</td>
                    <td className="num py-2 text-right font-semibold text-ink">{num(it.price)} ₽</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {/* Итог */}
      <Card className="border-brand-200 bg-brand-50/50 p-5">
        <h3 className="mb-2 flex items-center gap-2 text-[15px] font-semibold text-brand-900">
          <Sparkles size={16} className="text-brand-600" />
          Разбор Onvy
        </h3>
        <p className="text-[14px] leading-relaxed text-brand-900">{dialog.summary}</p>
      </Card>

      <div className="grid gap-4 lg:grid-cols-[1fr_1.1fr]">
        <div className="space-y-4">
          <Card className="p-5">
            <h3 className="mb-3 text-[15px] font-semibold text-ink">Моменты разговора</h3>
            <ul className="space-y-2.5">
              {dialog.moments.map((m) => {
                const st = MOMENT_STYLE[m.type];
                const Icon = st.icon;
                return (
                  <li key={m.id}>
                    <button
                      type="button"
                      onClick={() => goToMoment(m.id)}
                      className={`flex w-full gap-3 rounded-lg border p-3 text-left transition ${
                        activeMoment === m.id
                          ? 'border-brand-300 bg-brand-50/60'
                          : 'border-slate-200 hover:border-slate-300 hover:bg-slate-50'
                      }`}
                    >
                      <span
                        className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-white ${st.bg}`}
                      >
                        <Icon size={13} strokeWidth={3} />
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block text-[14px] font-semibold text-ink">{m.title}</span>
                        <span className="mt-1 block text-[13px] leading-relaxed text-slate-600">{m.note}</span>
                      </span>
                    </button>
                  </li>
                );
              })}
            </ul>
          </Card>

          <Card className="p-5">
            <h3 className="mb-3 flex items-center gap-2 text-[15px] font-semibold text-ink">
              <span className="flex h-6 w-6 items-center justify-center rounded-md bg-amber-50 text-amber-600">
                <Lightbulb size={14} />
              </span>
              Что улучшить в следующий раз
            </h3>
            <ul className="space-y-2.5">
              {dialog.recommendations.map((r) => (
                <li key={r} className="flex gap-2.5 text-[14px] leading-relaxed text-slate-700">
                  <span className="mt-2 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" />
                  {r}
                </li>
              ))}
            </ul>
          </Card>
        </div>

        {/* Расшифровка */}
        <Card className="flex max-h-[640px] flex-col p-5">
          <h3 className="mb-3 text-[15px] font-semibold text-ink">Расшифровка</h3>
          <ul className="-mr-2 space-y-3 overflow-y-auto pr-2 scroll-thin">
            {dialog.transcript.map((l) => {
              const sp = speakerMeta[l.speaker];
              const flagged = l.momentId ? dialog.moments.find((m) => m.id === l.momentId) : null;
              const st = flagged ? MOMENT_STYLE[flagged.type] : null;
              const Icon = st?.icon;
              return (
                <li
                  key={l.id}
                  ref={(el) => {
                    lineRefs.current[l.id] = el;
                  }}
                  className={`rounded-lg p-3 transition ${
                    flagged && activeMoment === flagged.id
                      ? flagged.type === 'win'
                        ? 'bg-emerald-50 ring-2 ring-emerald-200'
                        : flagged.type === 'miss'
                          ? 'bg-rose-50 ring-2 ring-rose-200'
                          : 'bg-amber-50 ring-2 ring-amber-200'
                      : l.unverified
                        ? 'bg-amber-50/70'
                        : l.speaker === 'ai'
                          ? 'bg-violet-50/60'
                          : 'bg-slate-50/70'
                  }`}
                >
                  <div className="mb-1.5 flex items-center gap-2">
                    <span className={`rounded-md px-1.5 py-0.5 text-[10px] font-semibold ${sp.cls}`}>{sp.name}</span>
                    <span className="num text-[11px] text-slate-500">{mmss(l.at)}</span>
                    {flagged && st && Icon && (
                      <span
                        className={`ml-auto flex h-4 w-4 items-center justify-center rounded-full text-white ${st.bg}`}
                        title={flagged.title}
                      >
                        <Icon size={10} strokeWidth={3.5} />
                      </span>
                    )}
                  </div>
                  <p
                    className={`text-[14px] leading-relaxed ${
                      l.unverified
                        ? 'font-medium text-amber-900'
                        : l.speaker === 'ai'
                          ? 'text-violet-900 italic'
                          : 'text-slate-700'
                    }`}
                  >
                    {l.text}
                  </p>
                </li>
              );
            })}
          </ul>
        </Card>
      </div>
    </div>
  );
}
