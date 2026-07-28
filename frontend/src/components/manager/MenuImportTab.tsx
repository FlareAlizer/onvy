// Импорт меню из CSV: сначала план (dry-run), потом применение тем же файлом —
// управляющий должен увидеть, что создастся/обновится/отклонится, прежде чем
// это попадёт в стоп-лист и меню официантов (см. app/api/menu.py import_menu).
//
// api() из lib/api.ts не годится для multipart — он всегда проставляет
// Content-Type: application/json, если есть тело запроса, и этим ломает
// границу form-data. Поэтому здесь — короткий прямой fetch с тем же
// Bearer-токеном, что и обычные запросы (см. отчёт агента: единственное
// осознанное исключение из "используй lib/api.ts").

import { useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, FileUp, UploadCloud } from 'lucide-react';
import { getSession } from '../../lib/api';

type ImportRow = {
  line_number: number;
  name: string;
  category: string | null;
  price: string | number | null;
  errors: string[];
};

type ImportUpdateRow = { row: ImportRow; menu_item_id: number };

type ImportPreview = {
  to_create: ImportRow[];
  to_update: ImportUpdateRow[];
  rejected: ImportRow[];
  applied: boolean;
};

async function uploadCsv(venueId: number, file: File, dryRun: boolean): Promise<ImportPreview> {
  const session = getSession();
  const form = new FormData();
  form.append('file', file);
  const resp = await fetch(`/api/venues/${venueId}/menu/import?dry_run=${dryRun}`, {
    method: 'POST',
    headers: session ? { Authorization: `Bearer ${session.accessToken}` } : undefined,
    body: form,
  });
  if (!resp.ok) {
    let message = 'Не удалось разобрать файл. Проверьте кодировку и разделитель.';
    try {
      const body = await resp.json();
      if (typeof body?.detail === 'string') message = body.detail;
    } catch {
      /* тело не JSON — оставляем общее сообщение */
    }
    throw new Error(message);
  }
  return resp.json();
}

type Phase = 'idle' | 'busy' | 'preview' | 'applied' | 'error';

export default function MenuImportTab() {
  const venueId = getSession()?.venueId;
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<Phase>('idle');
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  const pickFile = (f: File | null) => {
    setFile(f);
    setPreview(null);
    setPhase('idle');
  };

  const runPreview = async () => {
    if (!file || !venueId) return;
    setPhase('busy');
    try {
      const result = await uploadCsv(venueId, file, true);
      setPreview(result);
      setPhase('preview');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось разобрать файл.');
      setPhase('error');
    }
  };

  const runApply = async () => {
    if (!file || !venueId) return;
    setPhase('busy');
    try {
      const result = await uploadCsv(venueId, file, false);
      setPreview(result);
      setPhase('applied');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось применить импорт.');
      setPhase('error');
    }
  };

  const canApply = preview && !preview.applied && preview.to_create.length + preview.to_update.length > 0;

  return (
    <div className="flex h-full flex-col gap-5 overflow-y-auto px-5 pt-4 pb-6">
      <div>
        <h2 className="text-xl font-bold tracking-tight text-stone-50">Импорт меню</h2>
        <p className="mt-1 text-sm text-stone-400">
          Файл CSV: название, категория, цена, состав, аллергены, вес, время отдачи, острота —
          порядок колонок не важен, пустая ячейка значит «данных нет».
        </p>
      </div>

      <input
        ref={inputRef}
        type="file"
        accept=".csv,text/csv"
        className="hidden"
        onChange={(e) => pickFile(e.target.files?.[0] ?? null)}
      />
      <button
        onClick={() => inputRef.current?.click()}
        className="flex items-center justify-center gap-2 rounded-2xl border-2 border-dashed border-stone-700 px-5 py-6 text-base font-semibold text-stone-300 transition-transform duration-150 ease-out active:scale-[0.98]"
      >
        <UploadCloud size={22} />
        {file ? file.name : 'Выбрать файл CSV'}
      </button>

      {file && phase !== 'applied' && (
        <button
          onClick={runPreview}
          disabled={phase === 'busy'}
          className="rounded-2xl bg-stone-50 px-6 py-3.5 text-base font-semibold text-stone-950 transition-transform duration-150 ease-out active:scale-[0.97] disabled:opacity-50"
        >
          {phase === 'busy' && !preview ? 'Разбираю файл…' : 'Показать план импорта'}
        </button>
      )}

      {phase === 'error' && (
        <div className="flex items-start gap-2 rounded-xl bg-red-500/15 px-4 py-3 text-sm text-red-200">
          <AlertTriangle size={18} className="mt-0.5 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {preview && (
        <div className="space-y-4">
          <div className="grid grid-cols-3 gap-3">
            <StatChip label="Новые" value={preview.to_create.length} tone="emerald" />
            <StatChip label="Обновятся" value={preview.to_update.length} tone="sky" />
            <StatChip label="Отклонены" value={preview.rejected.length} tone="red" />
          </div>

          {preview.applied ? (
            <div className="flex items-center gap-2 rounded-xl bg-emerald-500/15 px-4 py-3 text-base font-medium text-emerald-300">
              <CheckCircle2 size={20} /> Импорт применён — позиции в меню обновлены
            </div>
          ) : (
            canApply && (
              <button
                onClick={runApply}
                disabled={phase === 'busy'}
                className="w-full rounded-2xl bg-emerald-500 px-6 py-3.5 text-base font-semibold text-stone-950 transition-transform duration-150 ease-out active:scale-[0.97] disabled:opacity-50"
              >
                {phase === 'busy' ? 'Применяю…' : `Применить (${preview.to_create.length + preview.to_update.length})`}
              </button>
            )
          )}

          {preview.rejected.length > 0 && (
            <div>
              <h3 className="mb-2 text-sm font-bold uppercase tracking-widest text-stone-500">
                Отклонённые строки — исправьте и загрузите заново
              </h3>
              <ul className="space-y-2">
                {preview.rejected.map((row) => (
                  <li key={row.line_number} className="rounded-xl bg-stone-900 px-4 py-3">
                    <p className="text-sm font-semibold text-stone-200">
                      Строка {row.line_number} · {row.name || '(без названия)'}
                    </p>
                    <p className="mt-1 text-sm text-red-300">{row.errors.join('; ')}</p>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(preview.to_create.length > 0 || preview.to_update.length > 0) && (
            <div>
              <h3 className="mb-2 text-sm font-bold uppercase tracking-widest text-stone-500">
                {preview.applied ? 'Применённые позиции' : 'Что изменится'}
              </h3>
              <ul className="space-y-1.5">
                {[...preview.to_create.map((r) => ({ r, tag: 'Новая' })), ...preview.to_update.map((u) => ({ r: u.row, tag: 'Обновление' }))].map(
                  ({ r, tag }) => (
                    <li
                      key={`${tag}-${r.line_number}`}
                      className="flex items-center justify-between rounded-xl bg-stone-900 px-4 py-2.5 text-sm"
                    >
                      <span className="truncate text-stone-100">{r.name}</span>
                      <span className="shrink-0 text-xs font-bold uppercase tracking-wide text-stone-500">
                        {tag}
                      </span>
                    </li>
                  ),
                )}
              </ul>
            </div>
          )}
        </div>
      )}

      {!file && (
        <p className="flex items-center gap-2 pt-4 text-sm text-stone-500">
          <FileUp size={16} /> Файл ещё не выбран
        </p>
      )}
    </div>
  );
}

function StatChip({ label, value, tone }: { label: string; value: number; tone: 'emerald' | 'sky' | 'red' }) {
  const toneCls =
    tone === 'emerald' ? 'text-emerald-300' : tone === 'sky' ? 'text-sky-300' : 'text-red-300';
  return (
    <div className="rounded-2xl bg-stone-900 px-3 py-3 text-center">
      <p className={`text-2xl font-bold ${toneCls}`}>{value}</p>
      <p className="mt-0.5 text-xs font-medium text-stone-500">{label}</p>
    </div>
  );
}
