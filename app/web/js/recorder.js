// Захват микрофона в браузере → сырой PCM 16 kHz mono 16-bit LE.
// Такой формат принимает Yandex SpeechKit (format=lpcm) без транскодинга/ffmpeg.
// getUserMedia требует защищённый контекст: работает на localhost и по HTTPS.

const OnvyRecorder = (() => {
  const TARGET_RATE = 16000;
  let audioCtx = null;
  let stream = null;
  let processor = null;
  let source = null;
  let chunks = [];

  async function start() {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    source = audioCtx.createMediaStreamSource(stream);
    processor = audioCtx.createScriptProcessor(4096, 1, 1);
    chunks = [];
    processor.onaudioprocess = (e) => {
      chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    };
    source.connect(processor);
    processor.connect(audioCtx.destination);
  }

  function _flatten(buffers) {
    const length = buffers.reduce((n, b) => n + b.length, 0);
    const out = new Float32Array(length);
    let offset = 0;
    for (const b of buffers) {
      out.set(b, offset);
      offset += b.length;
    }
    return out;
  }

  function _downsample(input, inRate) {
    if (inRate === TARGET_RATE) return input;
    const ratio = inRate / TARGET_RATE;
    const outLength = Math.floor(input.length / ratio);
    const out = new Float32Array(outLength);
    for (let i = 0; i < outLength; i++) {
      out[i] = input[Math.floor(i * ratio)];
    }
    return out;
  }

  function _toInt16(floats) {
    const buf = new ArrayBuffer(floats.length * 2);
    const view = new DataView(buf);
    for (let i = 0; i < floats.length; i++) {
      const s = Math.max(-1, Math.min(1, floats[i]));
      view.setInt16(i * 2, s < 0 ? s * 0x8000 : s * 0x7fff, true);
    }
    return buf;
  }

  // Останавливает запись и возвращает Blob с PCM (16 kHz, mono, int16 LE).
  async function stop() {
    const inRate = audioCtx.sampleRate;
    processor.disconnect();
    source.disconnect();
    stream.getTracks().forEach((t) => t.stop());
    await audioCtx.close();

    const pcm16 = _toInt16(_downsample(_flatten(chunks), inRate));
    return new Blob([pcm16], { type: "application/octet-stream" });
  }

  return { start, stop };
})();
