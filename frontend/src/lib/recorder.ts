// Захват микрофона → сырой PCM 16 kHz mono 16-bit LE (формат lpcm Yandex STT).
// Работает на localhost и по HTTPS (требование браузера к getUserMedia).

const TARGET_RATE = 16000;

let audioCtx: AudioContext | null = null;
let stream: MediaStream | null = null;
let processor: ScriptProcessorNode | null = null;
let source: MediaStreamAudioSourceNode | null = null;
let chunks: Float32Array[] = [];

export async function startRecording(): Promise<void> {
  stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  audioCtx = new AudioContext();
  source = audioCtx.createMediaStreamSource(stream);
  processor = audioCtx.createScriptProcessor(4096, 1, 1);
  chunks = [];
  processor.onaudioprocess = (e) => {
    chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
  };
  source.connect(processor);
  processor.connect(audioCtx.destination);
}

function flatten(buffers: Float32Array[]): Float32Array {
  const length = buffers.reduce((n, b) => n + b.length, 0);
  const out = new Float32Array(length);
  let offset = 0;
  for (const b of buffers) {
    out.set(b, offset);
    offset += b.length;
  }
  return out;
}

function downsample(input: Float32Array, inRate: number): Float32Array {
  if (inRate === TARGET_RATE) return input;
  const ratio = inRate / TARGET_RATE;
  const outLength = Math.floor(input.length / ratio);
  const out = new Float32Array(outLength);
  for (let i = 0; i < outLength; i++) out[i] = input[Math.floor(i * ratio)];
  return out;
}

function toInt16(floats: Float32Array): ArrayBuffer {
  const buf = new ArrayBuffer(floats.length * 2);
  const view = new DataView(buf);
  for (let i = 0; i < floats.length; i++) {
    const s = Math.max(-1, Math.min(1, floats[i]));
    view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return buf;
}

/** Остановить запись и получить Blob с PCM (16 kHz, mono, int16 LE). */
export async function stopRecording(): Promise<Blob> {
  if (!audioCtx || !processor || !source || !stream) throw new Error('Запись не запущена');
  const inRate = audioCtx.sampleRate;
  processor.disconnect();
  source.disconnect();
  stream.getTracks().forEach((t) => t.stop());
  await audioCtx.close();
  const pcm16 = toInt16(downsample(flatten(chunks), inRate));
  audioCtx = null; processor = null; source = null; stream = null; chunks = [];
  return new Blob([pcm16], { type: 'application/octet-stream' });
}

/* ---------- Режим «Онви всегда слушает» ----------
 * Микрофон открыт постоянно. Детекция речи по громкости (RMS):
 * тихо → копим пре-ролл (чтобы слово «Онви» не обрезалось), громко → пишем
 * фразу, после ~1.2 c тишины отдаём готовый PCM-блоб наружу. Сервер сам решает,
 * было ли обращение «Онви» (require_wake=1). */

const BASE_RMS = 0.008;       // нижняя граница порога «говорят»
const NOISE_FACTOR = 2.5;     // порог = шум помещения × этот множитель
const SILENCE_MS = 1200;      // пауза, после которой фраза считается законченной
const MIN_SPEECH_MS = 400;    // короче — шум, не отправляем
const MAX_UTTERANCE_MS = 12000; // страховка от бесконечной фразы
const PREROLL_BUFFERS = 10;   // ~1 c пре-ролла при буфере 4096/44.1kHz

export class WakeListener {
  private ctx: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private processor: ScriptProcessorNode | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private preroll: Float32Array[] = [];
  private utterance: Float32Array[] = [];
  private speaking = false;
  private speechMs = 0;
  private silenceMs = 0;
  private busy = false; // пока запрос в полёте / играет ответ — не пишем новую фразу
  private noiseFloor = 0.004; // оценка фонового шума помещения (EMA)

  constructor(
    private onUtterance: (blob: Blob) => Promise<void>,
    private onState?: (s: 'idle' | 'speech' | 'sending') => void,
  ) {}

  /** Жив ли микрофон: и звуковой контекст запущен, и дорожка не остановлена. */
  жив(): boolean {
    const дорожка = this.stream?.getAudioTracks()[0];
    return this.ctx?.state === 'running' && !!дорожка && дорожка.readyState === 'live';
  }

  /**
   * Разбудить микрофон после возврата из фона.
   *
   * Телефон, погасив экран, усыпляет вкладку: AudioContext уходит в suspended и
   * сам не возвращается. Пока этого не делали, официант возвращался к телефону
   * и говорил в мёртвый микрофон — без единого признака, что его не слышат.
   *
   * Возвращает false, если поднять не вышло: дорожку могла забрать система, и
   * тогда нужен полный перезапуск слушателя.
   */
  async оживить(): Promise<boolean> {
    if (!this.ctx) return false;
    try {
      if (this.ctx.state === 'suspended') await this.ctx.resume();
    } catch {
      return false;
    }
    return this.жив();
  }

  async start(): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.ctx = new AudioContext();
    await this.ctx.resume().catch(() => {}); // Chrome может стартовать suspended
    this.source = this.ctx.createMediaStreamSource(this.stream);
    this.processor = this.ctx.createScriptProcessor(4096, 1, 1);
    const bufMs = (4096 / this.ctx.sampleRate) * 1000;

    this.processor.onaudioprocess = (e) => {
      const buf = new Float32Array(e.inputBuffer.getChannelData(0));
      if (this.busy) return; // ждём ответа на предыдущую фразу
      let sum = 0;
      for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
      const rms = Math.sqrt(sum / buf.length);
      // Адаптивный порог: фон меряем, пока никто не говорит.
      if (!this.speaking) this.noiseFloor = this.noiseFloor * 0.95 + rms * 0.05;
      const voiced = rms > Math.max(BASE_RMS, this.noiseFloor * NOISE_FACTOR);

      if (!this.speaking) {
        this.preroll.push(buf);
        if (this.preroll.length > PREROLL_BUFFERS) this.preroll.shift();
        if (voiced) {
          this.speaking = true;
          this.speechMs = bufMs;
          this.silenceMs = 0;
          this.utterance = [...this.preroll];
          this.preroll = [];
          this.onState?.('speech');
        }
        return;
      }

      this.utterance.push(buf);
      this.speechMs += bufMs;
      this.silenceMs = voiced ? 0 : this.silenceMs + bufMs;

      const done = this.silenceMs >= SILENCE_MS || this.speechMs >= MAX_UTTERANCE_MS;
      if (!done) return;

      const frames = this.utterance;
      this.speaking = false;
      this.utterance = [];
      if (this.speechMs - this.silenceMs < MIN_SPEECH_MS) { this.onState?.('idle'); return; }

      this.busy = true;
      this.onState?.('sending');
      const inRate = this.ctx?.sampleRate ?? 44100;
      const blob = new Blob([toInt16(downsample(flatten(frames), inRate))], { type: 'application/octet-stream' });
      void this.onUtterance(blob).finally(() => {
        this.busy = false;
        this.onState?.('idle');
      });
    };

    this.source.connect(this.processor);
    this.processor.connect(this.ctx.destination);
    this.onState?.('idle');
  }

  /** Проиграть MP3-ответ через тот же AudioContext — обходит блокировку
   * автоплея на мобильных.
   *
   * Микрофон в это время не подхватывает голос ассистента из динамика, но не
   * сам по себе: флаг busy держится, пока не завершится onUtterance, а тот
   * обязан **дождаться** этого метода. Вызвать его без await — значит снять
   * busy раньше конца фразы и получить зацикливание: ассистент услышит сам
   * себя и ответит на собственный ответ. */
  async playMp3(b64: string): Promise<void> {
    if (!this.ctx) return;
    try {
      const bytes = Uint8Array.from(atob(b64), (c) => c.charCodeAt(0));
      const audioBuf = await this.ctx.decodeAudioData(bytes.buffer.slice(0) as ArrayBuffer);
      await new Promise<void>((resolve) => {
        const src = this.ctx!.createBufferSource();
        src.buffer = audioBuf;
        src.connect(this.ctx!.destination);
        src.onended = () => resolve();
        src.start();
      });
    } catch { /* не смогли проиграть — не критично */ }
  }

  async stop(): Promise<void> {
    this.processor?.disconnect();
    this.source?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    if (this.ctx) await this.ctx.close().catch(() => {});
    this.ctx = null; this.stream = null; this.processor = null; this.source = null;
    this.preroll = []; this.utterance = []; this.speaking = false; this.busy = false;
  }
}
