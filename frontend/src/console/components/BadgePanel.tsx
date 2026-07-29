import { useEffect, useState } from 'react';
import {
  BatteryFull,
  BatteryLow,
  BatteryMedium,
  Bluetooth,
  BluetoothOff,
  Check,
  Mic,
  Radio,
  SlidersHorizontal,
  TriangleAlert,
} from 'lucide-react';
import { LiveBars } from './Waveform';
import { Chip, Modal, Progress } from './ui';
import { useStore } from '../store';

function BatteryIcon({ level }: { level: number }) {
  if (level > 60) return <BatteryFull size={15} className="text-emerald-600" />;
  if (level > 20) return <BatteryMedium size={15} className="text-amber-500" />;
  return <BatteryLow size={15} className="text-rose-600" />;
}

/**
 * Плашка бейджа — первый блок в обоих кабинетах.
 * Для сотрудника это состояние его устройства, для руководителя — покрытие смены.
 */
export function EmployeeBadgePanel() {
  const { me, profile } = useStore();
  const L = profile.labels;
  const [connected, setConnected] = useState(me?.badgeOnline ?? false);
  const [onShift, setOnShift] = useState(me?.badgeOnline ?? false);
  const [calibrating, setCalibrating] = useState(false);
  const [calibStep, setCalibStep] = useState(0);
  const [micQuality, setMicQuality] = useState(me?.micQuality ?? 0);
  const battery = me?.badgeBattery ?? 100;

  useEffect(() => {
    if (!calibrating || calibStep >= 3) return;
    const t = setTimeout(() => setCalibStep((s) => s + 1), 1300);
    return () => clearTimeout(t);
  }, [calibrating, calibStep]);

  useEffect(() => {
    if (calibStep >= 3) setMicQuality(96);
  }, [calibStep]);

  const startCalibration = () => {
    setCalibStep(0);
    setCalibrating(true);
  };

  return (
    <>
      <section className="card overflow-hidden">
        <div className="flex flex-col gap-5 p-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <div
              className={`relative flex h-12 w-12 shrink-0 items-center justify-center rounded-xl transition ${
                connected ? 'bg-brand-600 text-white' : 'bg-slate-100 text-slate-500'
              }`}
            >
              <Radio size={22} />
              {connected && (
                <span className="absolute -top-0.5 -right-0.5 flex h-3 w-3">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex h-3 w-3 rounded-full border-2 border-white bg-emerald-500" />
                </span>
              )}
            </div>

            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <h2 className="text-[15px] font-semibold text-ink">{L.device}</h2>
                {connected ? (
                  <Chip tone="good" icon={<Bluetooth size={11} />}>
                    Подключён
                  </Chip>
                ) : (
                  <Chip tone="bad" icon={<BluetoothOff size={11} />}>
                    Нет связи
                  </Chip>
                )}
              </div>
              <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[12px] text-slate-500">
                <span className="inline-flex items-center gap-1.5">
                  <BatteryIcon level={battery} />
                  <span className="num">{battery}%</span> заряд
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <Mic size={13} className={connected && micQuality >= 80 ? 'text-brand-600' : 'text-slate-300'} />
                  {connected ? (
                    micQuality > 0 ? (
                      <>
                        микрофон <span className="num">{micQuality}%</span>
                      </>
                    ) : (
                      'нужна калибровка'
                    )
                  ) : (
                    'микрофон недоступен'
                  )}
                </span>
                <span className="num">ID BDG-{(me?.id ?? 'e0').slice(-4).toUpperCase()}</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="hidden items-center gap-3 rounded-lg bg-slate-50 px-3.5 py-2.5 sm:flex">
              <LiveBars
                active={connected && onShift}
                bars={12}
                height={24}
                color={connected && onShift ? 'var(--color-brand-600)' : '#cbd5e1'}
              />
              <span className="text-[11px] leading-tight font-semibold text-slate-500">
                {connected && onShift ? (
                  <>
                    Идёт смена
                    <br />
                    <span className="text-emerald-700">запись активна</span>
                  </>
                ) : (
                  <>
                    Смена
                    <br />
                    не начата
                  </>
                )}
              </span>
            </div>

            <div className="flex flex-1 gap-2 sm:flex-none">
              <button type="button" className="btn-ghost flex-1 sm:flex-none" onClick={startCalibration}>
                <SlidersHorizontal size={15} /> Калибровка
              </button>
              {connected ? (
                <button
                  type="button"
                  className={onShift ? 'btn-ghost flex-1 sm:flex-none' : 'console-btn-primary flex-1 sm:flex-none'}
                  onClick={() => setOnShift(!onShift)}
                >
                  {onShift ? 'Завершить смену' : 'Начать смену'}
                </button>
              ) : (
                <button type="button" className="console-btn-primary flex-1 sm:flex-none" onClick={() => setConnected(true)}>
                  Подключить
                </button>
              )}
            </div>
          </div>
        </div>

        {!connected && (
          <div className="flex items-start gap-2.5 border-t border-amber-100 bg-amber-50 px-5 py-3">
            <TriangleAlert size={15} className="mt-0.5 shrink-0 text-amber-600" />
            <p className="text-[13px] text-amber-900">
              Пока бейдж не подключён, {L.interactionPlural.toLowerCase()} не записываются и подсказки в
              ухо не приходят. Достаньте гарнитуру из дока и нажмите «Подключить».
            </p>
          </div>
        )}
        {connected && micQuality === 0 && (
          <div className="flex items-start gap-2.5 border-t border-amber-100 bg-amber-50 px-5 py-3">
            <TriangleAlert size={15} className="mt-0.5 shrink-0 text-amber-600" />
            <p className="text-[13px] text-amber-900">
              Микрофон не откалиброван под шум зала. Пройдите калибровку — это меньше минуты.
            </p>
          </div>
        )}
      </section>

      <Modal
        open={calibrating}
        onClose={() => setCalibrating(false)}
        title="Калибровка микрофона"
        subtitle="Настраиваем бейдж под шум вашей точки — занимает меньше минуты."
        width="max-w-lg"
      >
        <ol className="space-y-3">
          {[
            'Замеряем фоновый шум',
            `Произнесите обычным голосом приветствие ${L.clientGenitivePlural}`,
            'Подбираем порог срабатывания под ваш голос',
          ].map((s, i) => (
            <li
              key={s}
              className={`flex items-start gap-3 rounded-lg border p-3.5 transition ${
                calibStep > i
                  ? 'border-emerald-200 bg-emerald-50'
                  : calibStep === i
                    ? 'border-brand-300 bg-brand-50/60'
                    : 'border-slate-200'
              }`}
            >
              <span
                className={`mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-semibold ${
                  calibStep > i
                    ? 'bg-emerald-500 text-white'
                    : calibStep === i
                      ? 'bg-brand-600 text-white'
                      : 'bg-slate-100 text-slate-500'
                }`}
              >
                {calibStep > i ? <Check size={13} strokeWidth={3} /> : i + 1}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[14px] text-ink">{s}</p>
                {calibStep === i && (
                  <div className="mt-2.5">
                    <LiveBars active bars={22} height={20} color="var(--color-brand-600)" />
                  </div>
                )}
              </div>
            </li>
          ))}
        </ol>

        {calibStep >= 3 && (
          <div className="mt-5 rounded-lg border border-emerald-200 bg-emerald-50 p-4">
            <p className="flex items-center gap-2 text-[14px] font-semibold text-emerald-900">
              <Check size={16} /> Бейдж откалиброван
            </p>
            <p className="mt-1 text-[13px] text-emerald-800">
              Порог шума 62 дБ, качество микрофона 96 %. Можно начинать смену.
            </p>
            <button type="button" className="console-btn-primary mt-3.5" onClick={() => setCalibrating(false)}>
              Готово
            </button>
          </div>
        )}
      </Modal>
    </>
  );
}

/** Для руководителя: сколько устройств в эфире и где провал покрытия. */
export function RopBadgePanel() {
  const { data, profile } = useStore();
  const L = profile.labels;
  const online = data.employees.filter((e) => e.badgeOnline).length;
  const total = data.employees.length;
  const offline = data.employees.filter((e) => !e.badgeOnline);
  const share = total ? (online / total) * 100 : 0;
  const lowMic = data.employees.filter((e) => e.badgeOnline && e.micQuality > 0 && e.micQuality < 80);
  const avgBattery = online
    ? Math.round(
        data.employees.filter((e) => e.badgeOnline).reduce((a, e) => a + e.badgeBattery, 0) / online,
      )
    : 0;

  return (
    <section className="card p-5">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex items-center gap-4">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-xl bg-brand-600 text-white">
            <Radio size={22} />
          </div>
          <div>
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="text-[15px] font-semibold text-ink">Бейджи в эфире</h2>
              <Chip tone={total === 0 ? 'neutral' : share >= 80 ? 'good' : share >= 50 ? 'warn' : 'bad'}>
                {online} из {total}
              </Chip>
            </div>
            <p className="mt-1.5 text-[12px] text-slate-500">
              {total === 0
                ? `${L.employeePlural} ещё не подключились — привязывать бейджи пока не к кому.`
                : offline.length === 0
                  ? 'Вся смена на связи — диалоги пишутся полностью.'
                  : `Не на связи: ${offline.map((e) => e.name.split(' ')[0]).join(', ')}. Записи этих смен не попадут в аналитику.`}
            </p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-5">
          <div className="hidden sm:block">
            <LiveBars active={online > 0} bars={14} height={26} color="var(--color-brand-600)" />
          </div>
          {online > 0 && (
            <div>
              <p className="label">Средний заряд</p>
              <p className="num mt-0.5 text-[15px] font-semibold text-ink">{avgBattery}%</p>
            </div>
          )}
          <div className="w-full min-w-[180px] lg:w-52">
            <div className="mb-1.5 flex items-baseline justify-between">
              <span className="label">Покрытие смены</span>
              <span className="num text-[13px] font-semibold text-ink">{Math.round(share)}%</span>
            </div>
            <Progress
              value={share}
              tone={total === 0 ? 'brand' : share >= 80 ? 'good' : share >= 50 ? 'warn' : 'bad'}
            />
          </div>
        </div>
      </div>

      {(offline.length > 0 || lowMic.length > 0) && (
        <ul className="mt-4 flex flex-wrap gap-2 border-t border-slate-100 pt-4">
          {offline.map((e) => (
            <li
              key={e.id}
              className="inline-flex items-center gap-2 rounded-md bg-slate-50 px-2.5 py-1.5 text-[12px] text-slate-600"
            >
              <BluetoothOff size={13} className="text-slate-500" />
              {e.name}
              <span className="num text-slate-500">· заряд {e.badgeBattery}%</span>
            </li>
          ))}
          {lowMic.map((e) => (
            <li
              key={`mic-${e.id}`}
              className="inline-flex items-center gap-2 rounded-md bg-amber-50 px-2.5 py-1.5 text-[12px] text-amber-800"
            >
              <Mic size={13} className="text-amber-600" />
              {e.name}
              <span className="num">· микрофон {e.micQuality}%</span>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
