const TARGET_SAMPLE_RATE = 16000;

export function createWavRecorder() {
  let audioContext = null;
  let sourceNode = null;
  let processorNode = null;
  let mediaStream = null;
  let chunks = [];
  let startedAt = null;

  async function start(source) {
    stopTracks();
    chunks = [];
    startedAt = Date.now();

    mediaStream =
      source === "system"
        ? await navigator.mediaDevices.getDisplayMedia({
            video: true,
            audio: {
              echoCancellation: false,
              noiseSuppression: false,
              autoGainControl: false,
            },
          })
        : await navigator.mediaDevices.getUserMedia({
            audio: {
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true,
            },
          });

    audioContext = new AudioContext();
    sourceNode = audioContext.createMediaStreamSource(mediaStream);
    processorNode = audioContext.createScriptProcessor(4096, 1, 1);

    processorNode.onaudioprocess = (event) => {
      chunks.push(new Float32Array(event.inputBuffer.getChannelData(0)));
    };

    sourceNode.connect(processorNode);
    processorNode.connect(audioContext.destination);
  }

  async function stop() {
    if (!audioContext || !processorNode) {
      return null;
    }

    processorNode.disconnect();
    sourceNode?.disconnect();
    stopTracks();

    const sourceSampleRate = audioContext.sampleRate;
    await audioContext.close();
    audioContext = null;
    sourceNode = null;
    processorNode = null;

    const samples = mergeChunks(chunks);
    const resampled = resample(samples, sourceSampleRate, TARGET_SAMPLE_RATE);
    const wavBlob = encodeWav(resampled, TARGET_SAMPLE_RATE);
    const durationMs = startedAt ? Date.now() - startedAt : 0;
    startedAt = null;
    chunks = [];

    return {
      blob: wavBlob,
      durationMs,
      filename: `smartdictate-${Date.now()}.wav`,
    };
  }

  function isRecording() {
    return Boolean(audioContext);
  }

  function stopTracks() {
    if (!mediaStream) {
      return;
    }
    for (const track of mediaStream.getTracks()) {
      track.stop();
    }
    mediaStream = null;
  }

  return {
    start,
    stop,
    isRecording,
  };
}

export function createPcmStreamRecorder() {
  let audioContext = null;
  let sourceNode = null;
  let processorNode = null;
  let muteNode = null;
  let mediaStream = null;
  let startedAt = null;

  async function start(source, onChunk) {
    stopTracks();
    startedAt = Date.now();

    mediaStream =
      source === "system"
        ? await navigator.mediaDevices.getDisplayMedia({
            video: true,
            audio: {
              echoCancellation: false,
              noiseSuppression: false,
              autoGainControl: false,
            },
          })
        : await navigator.mediaDevices.getUserMedia({
            audio: {
              echoCancellation: true,
              noiseSuppression: true,
              autoGainControl: true,
            },
          });

    audioContext = new AudioContext();
    sourceNode = audioContext.createMediaStreamSource(mediaStream);
    processorNode = audioContext.createScriptProcessor(4096, 1, 1);
    muteNode = audioContext.createGain();
    muteNode.gain.value = 0;

    processorNode.onaudioprocess = (event) => {
      const samples = new Float32Array(event.inputBuffer.getChannelData(0));
      const resampled = resample(samples, audioContext.sampleRate, TARGET_SAMPLE_RATE);
      const pcm = encodePcm16(resampled);
      if (pcm.byteLength > 0) {
        onChunk(pcm);
      }
    };

    sourceNode.connect(processorNode);
    processorNode.connect(muteNode);
    muteNode.connect(audioContext.destination);
  }

  async function stop() {
    if (!audioContext || !processorNode) {
      return null;
    }

    processorNode.disconnect();
    sourceNode?.disconnect();
    muteNode?.disconnect();
    stopTracks();

    await audioContext.close();
    audioContext = null;
    sourceNode = null;
    processorNode = null;
    muteNode = null;

    const durationMs = startedAt ? Date.now() - startedAt : 0;
    startedAt = null;
    return { durationMs };
  }

  function isRecording() {
    return Boolean(audioContext);
  }

  function stopTracks() {
    if (!mediaStream) {
      return;
    }
    for (const track of mediaStream.getTracks()) {
      track.stop();
    }
    mediaStream = null;
  }

  return {
    start,
    stop,
    isRecording,
  };
}

function mergeChunks(chunks) {
  const length = chunks.reduce((total, chunk) => total + chunk.length, 0);
  const merged = new Float32Array(length);
  let offset = 0;
  for (const chunk of chunks) {
    merged.set(chunk, offset);
    offset += chunk.length;
  }
  return merged;
}

function resample(samples, sourceRate, targetRate) {
  if (sourceRate === targetRate) {
    return samples;
  }

  const ratio = sourceRate / targetRate;
  const length = Math.round(samples.length / ratio);
  const resampled = new Float32Array(length);

  for (let index = 0; index < length; index += 1) {
    const sourceIndex = index * ratio;
    const left = Math.floor(sourceIndex);
    const right = Math.min(left + 1, samples.length - 1);
    const weight = sourceIndex - left;
    resampled[index] = samples[left] * (1 - weight) + samples[right] * weight;
  }

  return resampled;
}

function encodePcm16(samples) {
  const buffer = new ArrayBuffer(samples.length * 2);
  const view = new DataView(buffer);
  let offset = 0;
  for (const sample of samples) {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
    offset += 2;
  }
  return buffer;
}

function encodeWav(samples, sampleRate) {
  const bytesPerSample = 2;
  const buffer = new ArrayBuffer(44 + samples.length * bytesPerSample);
  const view = new DataView(buffer);

  writeString(view, 0, "RIFF");
  view.setUint32(4, 36 + samples.length * bytesPerSample, true);
  writeString(view, 8, "WAVE");
  writeString(view, 12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);
  view.setUint16(22, 1, true);
  view.setUint32(24, sampleRate, true);
  view.setUint32(28, sampleRate * bytesPerSample, true);
  view.setUint16(32, bytesPerSample, true);
  view.setUint16(34, 8 * bytesPerSample, true);
  writeString(view, 36, "data");
  view.setUint32(40, samples.length * bytesPerSample, true);

  let offset = 44;
  for (const sample of samples) {
    const clamped = Math.max(-1, Math.min(1, sample));
    view.setInt16(offset, clamped < 0 ? clamped * 0x8000 : clamped * 0x7fff, true);
    offset += bytesPerSample;
  }

  return new Blob([view], { type: "audio/wav" });
}

function writeString(view, offset, value) {
  for (let index = 0; index < value.length; index += 1) {
    view.setUint8(offset + index, value.charCodeAt(index));
  }
}
