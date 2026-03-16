class AudioCapture {
  constructor() {
    this.audioContext = null
    this.processor = null
    this.stream = null
    this.isRecording = false
    this.onChunk = null
    this.sampleRate = 16000
  }

  async start(onChunk) {
    if (this.isRecording) {
      return true
    }

    this.onChunk = onChunk

    try {
      this.stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: this.sampleRate,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })

      const AudioContextClass = window.AudioContext || window.webkitAudioContext
      this.audioContext = new AudioContextClass({ sampleRate: this.sampleRate })

      const source = this.audioContext.createMediaStreamSource(this.stream)
      this.processor = this.audioContext.createScriptProcessor(4096, 1, 1)

      source.connect(this.processor)
      this.processor.connect(this.audioContext.destination)

      this.processor.onaudioprocess = (event) => {
        const channelData = event.inputBuffer.getChannelData(0)
        const pcmData = this.floatTo16BitPCM(channelData)
        this.onChunk?.(pcmData)
      }

      this.isRecording = true
      return true
    } catch {
      this.cleanup()
      return false
    }
  }

  stop() {
    if (!this.isRecording) {
      return
    }

    this.cleanup()
    this.isRecording = false
  }

  cleanup() {
    if (this.processor) {
      this.processor.disconnect()
      this.processor = null
    }

    if (this.audioContext) {
      this.audioContext.close()
      this.audioContext = null
    }

    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop())
      this.stream = null
    }

    this.onChunk = null
  }

  floatTo16BitPCM(float32Array) {
    const int16Array = new Int16Array(float32Array.length)
    for (let index = 0; index < float32Array.length; index += 1) {
      const sample = Math.max(-1, Math.min(1, float32Array[index]))
      int16Array[index] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
    }
    return int16Array
  }
}

const audioCapture = new AudioCapture()

export function isServerRecordingSupported() {
  return Boolean(
    navigator?.mediaDevices?.getUserMedia &&
    (window.AudioContext || window.webkitAudioContext)
  )
}

export function buildWavBlob(int16Chunks, sampleRate = 16000) {
  const totalLength = int16Chunks.reduce((sum, chunk) => sum + chunk.length, 0)
  const pcmData = new Int16Array(totalLength)

  let offset = 0
  for (const chunk of int16Chunks) {
    pcmData.set(chunk, offset)
    offset += chunk.length
  }

  const wavBuffer = new ArrayBuffer(44 + pcmData.length * 2)
  const view = new DataView(wavBuffer)

  const writeString = (position, value) => {
    for (let index = 0; index < value.length; index += 1) {
      view.setUint8(position + index, value.charCodeAt(index))
    }
  }

  writeString(0, 'RIFF')
  view.setUint32(4, 36 + pcmData.length * 2, true)
  writeString(8, 'WAVE')
  writeString(12, 'fmt ')
  view.setUint32(16, 16, true)
  view.setUint16(20, 1, true)
  view.setUint16(22, 1, true)
  view.setUint32(24, sampleRate, true)
  view.setUint32(28, sampleRate * 2, true)
  view.setUint16(32, 2, true)
  view.setUint16(34, 16, true)
  writeString(36, 'data')
  view.setUint32(40, pcmData.length * 2, true)

  let position = 44
  for (const sample of pcmData) {
    view.setInt16(position, sample, true)
    position += 2
  }

  return new Blob([wavBuffer], { type: 'audio/wav' })
}

export default audioCapture
