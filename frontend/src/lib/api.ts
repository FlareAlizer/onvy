// Клиент API Onvy: сессия в localStorage + fetch с ключом + WebSocket-URL.

import type { Session } from '../types';

const KEY = 'onvy_session';

export function saveSession(s: Session): void {
  localStorage.setItem(KEY, JSON.stringify(s));
}

export function getSession(): Session | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const s = JSON.parse(raw);
    return s && s.apiKey && s.employeeId ? (s as Session) : null;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  localStorage.removeItem(KEY);
}

function headers(extra: Record<string, string> = {}): Record<string, string> {
  const s = getSession();
  return { 'X-API-Key': s?.apiKey ?? '', ...extra };
}

/** JSON-запрос к API. Бросает Error с текстом ответа при не-2xx. */
export async function api<T = unknown>(path: string, opts: RequestInit = {}): Promise<T> {
  const resp = await fetch(`/api${path}`, {
    ...opts,
    headers: headers({ 'Content-Type': 'application/json', ...(opts.headers as Record<string, string>) }),
  });
  if (!resp.ok) throw new Error((await resp.text()) || String(resp.status));
  return resp.status === 204 ? (null as T) : ((await resp.json()) as T);
}

/** Логин без сессии (ключ передаётся явно — сессии ещё нет). */
export async function apiWithKey<T>(apiKey: string, path: string, opts: RequestInit = {}): Promise<T> {
  const resp = await fetch(`/api${path}`, {
    ...opts,
    headers: { 'X-API-Key': apiKey, 'Content-Type': 'application/json' },
  });
  if (!resp.ok) throw new Error((await resp.text()) || String(resp.status));
  return (await resp.json()) as T;
}

/** Отправка аудио (multipart) с доп. полями. */
export async function postAudio<T>(path: string, blob: Blob, fields: Record<string, string | number | null> = {}): Promise<T> {
  const form = new FormData();
  form.append('audio', blob, 'clip.pcm');
  for (const [k, v] of Object.entries(fields)) {
    if (v !== null && v !== undefined && v !== '') form.append(k, String(v));
  }
  const resp = await fetch(`/api${path}`, { method: 'POST', headers: headers(), body: form });
  if (!resp.ok) throw new Error((await resp.text()) || String(resp.status));
  return (await resp.json()) as T;
}

/** Сырой GET (SVG QR-кода). */
export async function apiRaw(path: string): Promise<string> {
  const resp = await fetch(`/api${path}`, { headers: headers() });
  if (!resp.ok) throw new Error((await resp.text()) || String(resp.status));
  return resp.text();
}

/** URL WebSocket-канала доставки реплик. */
export function commsWsUrl(): string {
  const s = getSession();
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${location.host}/api/ws/comms/${s?.employeeId}?api_key=${encodeURIComponent(s?.apiKey ?? '')}`;
}

/** Проиграть base64-MP3 (ответ ассистента / голос коллеги). */
export function playBase64Mp3(b64: string): void {
  void new Audio(`data:audio/mp3;base64,${b64}`).play().catch(() => {});
}
