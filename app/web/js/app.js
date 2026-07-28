// Общие помощники веб-клиента Onvy: хранение сессии и запросы к API.

const Onvy = (() => {
  const KEY = "onvy_session";

  function save(session) {
    localStorage.setItem(KEY, JSON.stringify(session));
  }

  function get() {
    try {
      return JSON.parse(localStorage.getItem(KEY)) || {};
    } catch {
      return {};
    }
  }

  function clear() {
    localStorage.removeItem(KEY);
  }

  function requireSession() {
    const s = get();
    if (!s.apiKey || !s.employeeId) {
      window.location.href = "/";
      throw new Error("no session");
    }
    return s;
  }

  // JSON-запрос к API с ключом.
  async function api(path, opts = {}) {
    const s = get();
    const headers = Object.assign(
      { "Content-Type": "application/json", "X-API-Key": s.apiKey || "" },
      opts.headers || {}
    );
    const resp = await fetch("/api" + path, Object.assign({}, opts, { headers }));
    if (!resp.ok) throw new Error((await resp.text()) || resp.status);
    return resp.status === 204 ? null : resp.json();
  }

  // Отправка аудио (multipart) с доп. полями формы.
  async function postAudio(path, blob, fields = {}) {
    const s = get();
    const form = new FormData();
    form.append("audio", blob, "clip.pcm");
    for (const [k, v] of Object.entries(fields)) {
      if (v !== null && v !== undefined) form.append(k, v);
    }
    const resp = await fetch("/api" + path, {
      method: "POST",
      headers: { "X-API-Key": s.apiKey || "" },
      body: form,
    });
    if (!resp.ok) throw new Error((await resp.text()) || resp.status);
    return resp.json();
  }

  // GET сырого текста (например, SVG QR) с ключом.
  async function apiRaw(path) {
    const s = get();
    const resp = await fetch("/api" + path, { headers: { "X-API-Key": s.apiKey || "" } });
    if (!resp.ok) throw new Error((await resp.text()) || resp.status);
    return resp.text();
  }

  // Проиграть base64-MP3 (ответ ассистента / голос коллеги).
  function playBase64Mp3(b64) {
    const audio = new Audio("data:audio/mp3;base64," + b64);
    audio.play();
  }

  // Push-to-talk: удерживать кнопку, чтобы говорить; onStop(blob) при отпускании.
  function bindTalk(btn, onStop) {
    let active = false;
    const start = async (ev) => {
      ev.preventDefault();
      if (active) return;
      active = true;
      btn.classList.add("rec");
      try {
        await OnvyRecorder.start();
      } catch (e) {
        active = false;
        btn.classList.remove("rec");
        alert("Нет доступа к микрофону: " + e.message);
      }
    };
    const stop = async (ev) => {
      ev.preventDefault();
      if (!active) return;
      active = false;
      btn.classList.remove("rec");
      onStop(await OnvyRecorder.stop());
    };
    btn.addEventListener("pointerdown", start);
    btn.addEventListener("pointerup", stop);
    btn.addEventListener("pointerleave", stop);
    btn.addEventListener("contextmenu", (e) => e.preventDefault());
  }

  // Подключить WebSocket доставки входящих реплик; onMessage(obj) на каждую.
  function connectComms(onOpen, onMessage, onClose) {
    const s = get();
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(
      `${proto}://${location.host}/api/ws/comms/${s.employeeId}?api_key=${encodeURIComponent(s.apiKey)}`
    );
    ws.onopen = onOpen || null;
    ws.onclose = onClose || null;
    ws.onmessage = (ev) => onMessage(JSON.parse(ev.data));
    return ws;
  }

  return {
    save, get, clear, requireSession, api, apiRaw, postAudio,
    playBase64Mp3, bindTalk, connectComms,
  };
})();
