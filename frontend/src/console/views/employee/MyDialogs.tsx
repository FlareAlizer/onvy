import { useMemo, useState } from 'react';
import { ArrowLeft, MessagesSquare } from 'lucide-react';
import { useStore } from '../../store';
import { PageHead } from '../../components/Shell';
import { Card, Chip, EmptyState, Segmented } from '../../components/ui';
import { MiniWave } from '../../components/Waveform';
import { DialogDetail } from '../../components/DialogDetail';
import { Donut, StatTile } from '../../components/charts';
import { humanDateTime, mmss, money, num, pct } from '../../lib/format';
import type { Dialog } from '../../types';

type Filter = 'all' | 'success' | 'lost';

export function DialogList({
  dialogs,
  onOpen,
  nameOf,
}: {
  dialogs: Dialog[];
  onOpen: (d: Dialog) => void;
  nameOf?: (d: Dialog) => string;
}) {
  const { profile } = useStore();
  const L = profile.labels;
  return (
    <ul className="divide-y divide-slate-100">
      {dialogs.map((d) => {
        const wins = d.moments.filter((m) => m.type === 'win').length;
        const misses = d.moments.filter((m) => m.type === 'miss').length;
        const helps = d.moments.filter((m) => m.type === 'help').length;
        return (
          <li key={d.id}>
            <button
              type="button"
              onClick={() => onOpen(d)}
              className="flex w-full flex-wrap items-center gap-x-4 gap-y-2 px-4 py-3.5 text-left transition hover:bg-slate-50 sm:flex-nowrap"
            >
              <div className="min-w-0 flex-1 basis-full sm:basis-auto">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="truncate text-[14px] font-semibold text-ink">{d.topic}</span>
                  {d.outcome === 'success' ? (
                    <Chip tone="good">{money(d.revenue, true)}</Chip>
                  ) : d.outcome === 'lost' ? (
                    <Chip tone="bad">{L.outcomeLost}</Chip>
                  ) : (
                    <Chip tone="neutral">{L.interaction}</Chip>
                  )}
                  {d.simulated && <Chip tone="neutral">Демо</Chip>}
                </div>
                <p className="num mt-1 truncate text-[12px] text-slate-500">
                  {nameOf ? `${nameOf(d)} · ` : ''}
                  {humanDateTime(d.startedAt)} · {mmss(d.durationSec)} · {d.category}
                </p>
              </div>

              <MiniWave wave={d.wave} moments={d.moments} />

              <div className="flex shrink-0 items-center gap-2">
                {wins > 0 && (
                  <span className="num inline-flex items-center gap-1 rounded-md bg-emerald-50 px-2 py-1 text-[11px] font-semibold text-emerald-700">
                    +{wins}
                  </span>
                )}
                {misses > 0 && (
                  <span className="num inline-flex items-center gap-1 rounded-md bg-rose-50 px-2 py-1 text-[11px] font-semibold text-rose-700">
                    −{misses}
                  </span>
                )}
                {helps > 0 && (
                  <span
                    className="num inline-flex items-center gap-1 rounded-md bg-amber-50 px-2 py-1 text-[11px] font-semibold text-amber-700"
                    title={`Обращений: ${L.helpTarget.toLowerCase()}`}
                  >
                    ?{helps}
                  </span>
                )}
                <span
                  className={`num w-12 shrink-0 text-right text-[13px] font-semibold ${
                    d.scriptScore >= 85
                      ? 'text-emerald-700'
                      : d.scriptScore >= 70
                        ? 'text-amber-700'
                        : 'text-rose-700'
                  }`}
                >
                  {d.scriptScore}%
                </span>
              </div>
            </button>
          </li>
        );
      })}
    </ul>
  );
}

export default function MyDialogs() {
  const { me, data, profile } = useStore();
  const L = profile.labels;
  const [open, setOpen] = useState<Dialog | null>(null);
  const [filter, setFilter] = useState<Filter>('all');

  const mine = useMemo(() => data.dialogs.filter((d) => d.employeeId === me?.id), [data.dialogs, me?.id]);
  const shown = filter === 'all' ? mine : mine.filter((d) => d.outcome === filter);

  if (!me) return null;

  if (open) {
    return (
      <>
        <button type="button" onClick={() => setOpen(null)} className="btn-quiet -ml-3 mb-4">
          <ArrowLeft size={16} /> Все {L.interactionPlural.toLowerCase()}
        </button>
        <PageHead title={open.topic} subtitle={open.category} />
        <DialogDetail dialog={open} />
      </>
    );
  }

  const success = mine.filter((d) => d.outcome === 'success').length;
  const lost = mine.filter((d) => d.outcome === 'lost').length;
  const consult = mine.length - success - lost;
  const totalWins = mine.reduce((a, d) => a + d.moments.filter((m) => m.type === 'win').length, 0);
  const totalMisses = mine.reduce((a, d) => a + d.moments.filter((m) => m.type === 'miss').length, 0);
  const totalHelps = mine.reduce((a, d) => a + d.helpRequests, 0);

  return (
    <>
      <PageHead
        title={`Мои ${L.interactionPlural.toLowerCase()}`}
        subtitle={`Каждый разговор с ${L.clientPlural.toLowerCase()} разобран по репликам: где сделали хорошо, а где потеряли результат.`}
      />

      {mine.length === 0 ? (
        <EmptyState
          icon={<MessagesSquare size={22} />}
          title="Разговоров пока нет"
          hint={`Подключите бейдж и начните смену — разбор появится здесь через несколько минут после разговора. Или запустите демо-диалог на главном экране.`}
        />
      ) : (
        <>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatTile label="Разговоров" value={mine.length} hint="за выбранный период" />
            <StatTile
              label={`Из них: ${L.outcomePlural.toLowerCase()}`}
              value={success}
              hint={`результативность ${pct((success / mine.length) * 100, 0)}`}
            />
            <StatTile label="Удачных приёмов" value={totalWins} hint="отметил Onvy" />
            <StatTile
              label="Ошибок и обращений"
              value={`${totalMisses} / ${totalHelps}`}
              hint={`ошибки / ${L.helpTarget.toLowerCase()}`}
            />
          </div>

          <div className="mt-4 grid gap-4 lg:grid-cols-[1fr_1.9fr]">
            <Card className="p-5">
              <h3 className="mb-4 text-[15px] font-semibold text-ink">Чем закончились</h3>
              <Donut
                segments={[
                  { label: L.outcome, value: success, color: 'var(--color-series-3)' },
                  { label: L.outcomeLost, value: lost, color: 'var(--color-series-2)' },
                  { label: 'Без результата', value: consult, color: 'var(--color-series-4)' },
                ].filter((s) => s.value > 0)}
                centerValue={pct((success / mine.length) * 100, 0)}
                centerLabel="результативность"
              />
            </Card>

            <Card>
              <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-4 py-3">
                <h3 className="text-[15px] font-semibold text-ink">Список разговоров</h3>
                <Segmented
                  size="sm"
                  value={filter}
                  onChange={setFilter}
                  options={[
                    { value: 'all', label: 'Все' },
                    { value: 'success', label: `С результатом` },
                    { value: 'lost', label: L.outcomeLost },
                  ]}
                />
              </div>
              {shown.length === 0 ? (
                <p className="px-4 py-8 text-center text-[14px] text-slate-500">
                  По этому фильтру разговоров нет.
                </p>
              ) : (
                <DialogList dialogs={shown} onOpen={setOpen} />
              )}
            </Card>
          </div>
        </>
      )}

      <p className="mt-4 text-[12px] text-muted">
        Демо-данные · записи диалогов симулированы, реального распознавания речи в прототипе нет.
      </p>
      <span className="sr-only">{num(mine.length)}</span>
    </>
  );
}
