import { useCallback, useEffect, useRef, useState } from 'react'
import audioCapture, { buildWavBlob, isServerRecordingSupported } from './services/audioCapture'
import './App.css'

function createThreadId() {
  return `thread-${Date.now()}`
}

function createMessageId(prefix) {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

async function postJson(path, payload) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  const data = await response.json()
  if (!response.ok) {
    throw new Error(data?.detail || 'Request failed')
  }

  return data
}

async function postJsonStream(path, payload, onEvent) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })

  if (!response.ok) {
    let detail = 'Request failed'
    try {
      const data = await response.json()
      detail = data?.detail || detail
    } catch {
      detail = response.statusText || detail
    }
    throw new Error(detail)
  }

  if (!response.body) {
    throw new Error('Streaming response is unavailable.')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { value, done } = await reader.read()
    buffer += decoder.decode(value || new Uint8Array(), { stream: !done })

    let boundaryIndex = buffer.indexOf('\n')
    while (boundaryIndex !== -1) {
      const line = buffer.slice(0, boundaryIndex).trim()
      buffer = buffer.slice(boundaryIndex + 1)

      if (line) {
        onEvent(JSON.parse(line))
      }

      boundaryIndex = buffer.indexOf('\n')
    }

    if (done) {
      const trailing = buffer.trim()
      if (trailing) {
        onEvent(JSON.parse(trailing))
      }
      break
    }
  }
}

function resolveDefaultMode(clientAvailable, serverAvailable) {
  if (clientAvailable) {
    return 'client'
  }
  if (serverAvailable) {
    return 'server'
  }
  return 'off'
}

function createActivityMessage() {
  return {
    id: createMessageId('activity'),
    role: 'activity',
    items: [],
    expanded: false,
  }
}

function App() {
  const recognitionRef = useRef(null)
  const textareaRef = useRef(null)
  const settingsPanelRef = useRef(null)
  const serverRecordingChunksRef = useRef([])

  const [threadId, setThreadId] = useState(createThreadId())
  const [messages, setMessages] = useState([
    {
      id: createMessageId('assistant'),
      role: 'assistant',
      text: 'I am a helpful assistant. How can I help you today?',
    },
  ])
  const [input, setInput] = useState('')
  const [pendingReview, setPendingReview] = useState(null)
  const [editedArgsText, setEditedArgsText] = useState('')
  const [isEditingReview, setIsEditingReview] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [voiceStatus, setVoiceStatus] = useState('Idle')
  const [showVoiceSettings, setShowVoiceSettings] = useState(false)
  const [speechRate, setSpeechRate] = useState(1)
  const [browserVoices, setBrowserVoices] = useState([])
  const [backendVoices, setBackendVoices] = useState([])
  const [browserVoiceId, setBrowserVoiceId] = useState('')
  const [backendVoiceId, setBackendVoiceId] = useState('')
  const [sttMode, setSttMode] = useState('off')
  const [ttsMode, setTtsMode] = useState('off')
  const [clientSTTAvailable, setClientSTTAvailable] = useState(false)
  const [clientTTSAvailable, setClientTTSAvailable] = useState(false)
  const [serverSTTAvailable, setServerSTTAvailable] = useState(false)
  const [serverTTSAvailable, setServerTTSAvailable] = useState(false)
  const [serverSTTReason, setServerSTTReason] = useState('')
  const [serverTTSReason, setServerTTSReason] = useState('')
  const [isOnline, setIsOnline] = useState(
    typeof navigator === 'undefined' ? true : navigator.onLine
  )
  const listEndRef = useRef(null)

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, pendingReview])

  useEffect(() => {
    const textarea = textareaRef.current
    if (!textarea) {
      return
    }

    textarea.style.height = 'auto'
    const computedStyle = window.getComputedStyle(textarea)
    const lineHeight = Number.parseFloat(computedStyle.lineHeight) || 24
    const verticalPadding =
      (Number.parseFloat(computedStyle.paddingTop) || 0) +
      (Number.parseFloat(computedStyle.paddingBottom) || 0)
    const maxHeight = lineHeight * 5 + verticalPadding
    const nextHeight = Math.min(textarea.scrollHeight, maxHeight)

    textarea.style.height = `${nextHeight}px`
    textarea.style.overflowY = textarea.scrollHeight > maxHeight ? 'auto' : 'hidden'
  }, [input])

  useEffect(() => {
    const browserSTTSupported = Boolean(window.SpeechRecognition || window.webkitSpeechRecognition)
    setClientSTTAvailable(browserSTTSupported && isOnline)

    if (typeof window === 'undefined' || !window.speechSynthesis) {
      setClientTTSAvailable(false)
      setBrowserVoices([])
      return undefined
    }

    let fallbackTimer = null
    const syncVoices = () => {
      const voices = window.speechSynthesis.getVoices()
      setBrowserVoices(voices)
      setClientTTSAvailable(voices.length > 0)
      if (!browserVoiceId && voices.length > 0) {
        setBrowserVoiceId(voices[0].voiceURI)
      }
    }

    syncVoices()
    fallbackTimer = window.setTimeout(syncVoices, 1200)
    window.speechSynthesis.addEventListener('voiceschanged', syncVoices)

    return () => {
      if (fallbackTimer) {
        window.clearTimeout(fallbackTimer)
      }
      window.speechSynthesis.removeEventListener('voiceschanged', syncVoices)
    }
  }, [browserVoiceId, isOnline])

  useEffect(() => {
    const handleOnline = () => setIsOnline(true)
    const handleOffline = () => setIsOnline(false)

    window.addEventListener('online', handleOnline)
    window.addEventListener('offline', handleOffline)

    return () => {
      window.removeEventListener('online', handleOnline)
      window.removeEventListener('offline', handleOffline)
    }
  }, [])

  useEffect(() => {
    const loadServerCapabilities = async () => {
      try {
        const response = await fetch('/api/voice/capabilities')
        const data = await response.json()
        if (!response.ok) {
          throw new Error(data?.detail || 'Failed to load voice capabilities.')
        }

        setServerSTTAvailable(Boolean(data?.stt?.available))
        setServerTTSAvailable(Boolean(data?.tts?.available))
        setServerSTTReason(data?.stt?.reason || '')
        setServerTTSReason(data?.tts?.reason || '')
        setBackendVoices(data?.tts?.voices || [])
        setBackendVoiceId(data?.tts?.default_voice_id || '')

        setSttMode((current) =>
          current === 'off'
            ? resolveDefaultMode(clientSTTAvailable, Boolean(data?.stt?.available))
            : current
        )
        setTtsMode((current) =>
          current === 'off'
            ? resolveDefaultMode(clientTTSAvailable, Boolean(data?.tts?.available))
            : current
        )
      } catch (error) {
        setServerSTTAvailable(false)
        setServerTTSAvailable(false)
        setServerSTTReason(error.message)
        setServerTTSReason(error.message)
      }
    }

    loadServerCapabilities()
  }, [clientSTTAvailable, clientTTSAvailable])

  useEffect(() => {
    setSttMode((current) => {
      if (current === 'client' && clientSTTAvailable) {
        return current
      }
      if (current === 'server' && serverSTTAvailable) {
        return current
      }
      return resolveDefaultMode(clientSTTAvailable, serverSTTAvailable)
    })
  }, [clientSTTAvailable, serverSTTAvailable])

  useEffect(() => {
    setTtsMode((current) => {
      if (current === 'client' && clientTTSAvailable) {
        return current
      }
      if (current === 'server' && serverTTSAvailable) {
        return current
      }
      return resolveDefaultMode(clientTTSAvailable, serverTTSAvailable)
    })
  }, [clientTTSAvailable, serverTTSAvailable])

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (showVoiceSettings && settingsPanelRef.current && !settingsPanelRef.current.contains(event.target)) {
        setShowVoiceSettings(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [showVoiceSettings])

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop?.()
      audioCapture.stop()
      window.speechSynthesis?.cancel?.()
    }
  }, [])

  const speakWithServer = useCallback(async (text) => {
    const response = await fetch('/api/voice/tts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        text,
        voice_id: backendVoiceId || null,
        speed: speechRate,
      }),
    })

    const data = await response.json()
    if (!response.ok) {
      throw new Error(data?.detail || 'Server TTS failed.')
    }

    if (!data.audio) {
      return
    }

    const audioBytes = atob(data.audio)
    const audioArray = new Uint8Array(audioBytes.length)
    for (let index = 0; index < audioBytes.length; index += 1) {
      audioArray[index] = audioBytes.charCodeAt(index)
    }

    const blob = new Blob([audioArray], { type: 'audio/wav' })
    const url = URL.createObjectURL(blob)
    const audio = new Audio(url)
    audio.onended = () => URL.revokeObjectURL(url)
    await audio.play()
  }, [backendVoiceId, speechRate])

  const speakWithClient = useCallback((text) => {
    if (!text || typeof window === 'undefined' || !window.speechSynthesis) {
      throw new Error('Client TTS is unavailable.')
    }

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = speechRate

    if (browserVoiceId) {
      const selectedVoice = browserVoices.find((voice) => voice.voiceURI === browserVoiceId)
      if (selectedVoice) {
        utterance.voice = selectedVoice
      }
    }

    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(utterance)
  }, [browserVoiceId, browserVoices, speechRate])

  const speakAssistantReply = useCallback(async (text) => {
    if (!text || ttsMode === 'off') {
      return
    }

    try {
      if (ttsMode === 'client') {
        if (!clientTTSAvailable) {
          throw new Error('Client TTS unavailable.')
        }
        speakWithClient(text)
        return
      }

      if (!serverTTSAvailable) {
        throw new Error('Server TTS unavailable.')
      }
      await speakWithServer(text)
    } catch {
      if (ttsMode === 'client' && serverTTSAvailable) {
        setTtsMode('server')
        setVoiceStatus('Client TTS unavailable. Switched to server TTS.')
        try {
          await speakWithServer(text)
          return
        } catch {
          setVoiceStatus('Voice playback failed.')
        }
      } else {
        setVoiceStatus('Voice playback failed.')
      }
    }
  }, [clientTTSAvailable, serverTTSAvailable, speakWithClient, speakWithServer, ttsMode])

  const appendStatusToActivity = useCallback((activityId, event) => {
    setMessages((current) =>
      current.map((message) => {
        if (message.id !== activityId || message.role !== 'activity') {
          return message
        }

        const nextItem = {
          text: event.text,
          detail: event.detail || '',
        }
        const items = message.items || []
        const previousItem = items[items.length - 1]
        if (
          previousItem &&
          previousItem.text === nextItem.text &&
          previousItem.detail === nextItem.detail
        ) {
          return message
        }

        return {
          ...message,
          items: [...items, nextItem],
        }
      })
    )
  }, [])

  const toggleActivityExpanded = useCallback((activityId) => {
    setMessages((current) =>
      current.map((message) => {
        if (message.id !== activityId || message.role !== 'activity') {
          return message
        }
        return {
          ...message,
          expanded: !message.expanded,
        }
      })
    )
  }, [])

  const handleAgentResponse = useCallback((data) => {
    if (data.type === 'assistant') {
      const reply = data.message || '(no response)'
      setMessages((current) => [
        ...current,
        { id: createMessageId('assistant'), role: 'assistant', text: reply },
      ])
      setPendingReview(null)
      setEditedArgsText('')
      setIsEditingReview(false)
      setVoiceStatus('Idle')
      void speakAssistantReply(reply)
      return
    }

    if (data.type === 'review_required') {
      setPendingReview(data.review)
      setEditedArgsText(JSON.stringify(data.review.args, null, 2))
      setIsEditingReview(false)
      setVoiceStatus('Review required')
    }
  }, [speakAssistantReply])

  async function sendMessage(nextText) {
    const message = (nextText ?? input).trim()
    if (!message || isLoading || pendingReview) {
      return
    }

    const activityMessage = createActivityMessage()

    setMessages((current) => [
      ...current,
      { id: createMessageId('user'), role: 'user', text: message },
      activityMessage,
    ])
    setInput('')
    setIsLoading(true)

    try {
      await postJsonStream('/api/chat/stream', {
        thread_id: threadId,
        message,
      }, (event) => {
        if (event.type === 'status') {
          appendStatusToActivity(activityMessage.id, event)
          return
        }
        handleAgentResponse(event)
      })
    } catch (error) {
      setMessages((current) => [
        ...current,
        { id: createMessageId('system'), role: 'system', text: `Error: ${error.message}` },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  async function submitReview(decision) {
    if (!pendingReview || isLoading) {
      return
    }

    let editedArgs
    if (decision === 'edit') {
      try {
        editedArgs = JSON.parse(editedArgsText)
      } catch {
        setMessages((current) => [...current, { role: 'system', text: 'Error: edited tool args must be valid JSON.' }])
        return
      }
    }

    setIsLoading(true)
    try {
      const activityMessage = createActivityMessage()
      setMessages((current) => [...current, activityMessage])

      await postJsonStream('/api/review/stream', {
        thread_id: threadId,
        decision,
        edited_args: editedArgs,
        reject_message: decision === 'reject' ? 'User rejected the weather request.' : undefined,
      }, (event) => {
        if (event.type === 'status') {
          appendStatusToActivity(activityMessage.id, event)
          return
        }
        handleAgentResponse(event)
      })
    } catch (error) {
      setMessages((current) => [
        ...current,
        { id: createMessageId('system'), role: 'system', text: `Error: ${error.message}` },
      ])
    } finally {
      setIsLoading(false)
    }
  }

  function resetConversation() {
    setThreadId(createThreadId())
    setPendingReview(null)
    setEditedArgsText('')
    setIsEditingReview(false)
    setInput('')
    setIsListening(false)
    setVoiceStatus('Idle')
    recognitionRef.current?.stop?.()
    audioCapture.stop()
    window.speechSynthesis?.cancel?.()
    setMessages([
      {
        id: createMessageId('assistant'),
        role: 'assistant',
        text: 'I am a helpful assistant. How can I help you today?',
      },
    ])
  }

  function stopClientVoiceInput() {
    recognitionRef.current?.stop?.()
    recognitionRef.current = null
    setIsListening(false)
  }

  async function stopServerVoiceInputAndTranscribe() {
    audioCapture.stop()
    setIsListening(false)
    setVoiceStatus('Transcribing with server STT...')

    try {
      const wavBlob = buildWavBlob(serverRecordingChunksRef.current)
      serverRecordingChunksRef.current = []

      const response = await fetch('/api/voice/stt', {
        method: 'POST',
        headers: { 'Content-Type': 'audio/wav' },
        body: wavBlob,
      })
      const data = await response.json()
      if (!response.ok) {
        throw new Error(data?.detail || 'Server STT failed.')
      }

      setInput((data.text || '').trim())
      setVoiceStatus(data.text ? 'Voice captured. Edit or send.' : 'No speech detected.')
    } catch (error) {
      setMessages((current) => [
        ...current,
        { id: createMessageId('system'), role: 'system', text: `Error: ${error.message}` },
      ])
      setVoiceStatus('Voice error')
    }
  }

  async function startServerVoiceInput() {
    if (!isServerRecordingSupported()) {
      throw new Error('This browser cannot record audio for server STT.')
    }

    serverRecordingChunksRef.current = []
    const success = await audioCapture.start((chunk) => {
      serverRecordingChunksRef.current.push(new Int16Array(chunk))
    })

    if (!success) {
      throw new Error('Unable to start server-side recording.')
    }

    setIsListening(true)
    setVoiceStatus('Recording for server STT...')
  }

  function startClientVoiceInput() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      throw new Error('Client speech recognition is unavailable.')
    }

    const recognition = new SpeechRecognition()
    recognition.lang = 'en-US'
    recognition.interimResults = true
    recognition.continuous = false

    recognition.onstart = () => {
      recognitionRef.current = recognition
      setIsListening(true)
      setVoiceStatus('Listening...')
    }

    recognition.onresult = (event) => {
      const transcript = Array.from(event.results)
        .map((result) => result[0]?.transcript ?? '')
        .join(' ')
        .trim()

      setInput(transcript)
      const lastResult = event.results[event.results.length - 1]
      if (lastResult?.isFinal && transcript) {
        setVoiceStatus('Voice captured. Edit or send.')
        stopClientVoiceInput()
      }
    }

    recognition.onerror = async (event) => {
      setIsListening(false)
      recognitionRef.current = null

      if (serverSTTAvailable) {
        setSttMode('server')
        setVoiceStatus(`Client STT failed (${event.error}). Switched to server STT.`)
        try {
          await startServerVoiceInput()
          return
        } catch (error) {
          setMessages((current) => [
            ...current,
            { id: createMessageId('system'), role: 'system', text: `Error: ${error.message}` },
          ])
        }
      } else {
        setMessages((current) => [
          ...current,
          { id: createMessageId('system'), role: 'system', text: `Error: voice input failed (${event.error}).` },
        ])
      }

      setVoiceStatus('Voice error')
    }

    recognition.onend = () => {
      setIsListening(false)
      recognitionRef.current = null
      setVoiceStatus((current) => (current === 'Voice captured. Edit or send.' ? current : 'Idle'))
    }

    recognition.start()
  }

  async function toggleVoiceInput() {
    if (pendingReview || isLoading || sttMode === 'off') {
      return
    }

    if (isListening) {
      if (sttMode === 'server') {
        await stopServerVoiceInputAndTranscribe()
      } else {
        stopClientVoiceInput()
        setVoiceStatus('Idle')
      }
      return
    }

    try {
      if (sttMode === 'client') {
        if (!clientSTTAvailable) {
          throw new Error('Client STT unavailable.')
        }
        startClientVoiceInput()
        return
      }

      if (!serverSTTAvailable) {
        throw new Error('Server STT unavailable.')
      }
      await startServerVoiceInput()
    } catch (error) {
      if (sttMode === 'client' && serverSTTAvailable) {
        setSttMode('server')
        setVoiceStatus('Client STT unavailable. Switched to server STT.')
        try {
          await startServerVoiceInput()
          return
        } catch (serverError) {
          setMessages((current) => [
            ...current,
            { id: createMessageId('system'), role: 'system', text: `Error: ${serverError.message}` },
          ])
        }
      } else {
        setMessages((current) => [
          ...current,
          { id: createMessageId('system'), role: 'system', text: `Error: ${error.message}` },
        ])
      }
      setVoiceStatus('Voice error')
    }
  }

  const currentVoiceOptions =
    ttsMode === 'server'
      ? backendVoices.map((voice) => ({
          id: voice.id,
          name: voice.languages ? `${voice.name} (${voice.languages})` : voice.name,
        }))
      : browserVoices.map((voice) => ({
          id: voice.voiceURI,
          name: `${voice.name} (${voice.lang})`,
        }))

  const currentVoiceId = ttsMode === 'server' ? backendVoiceId : browserVoiceId

  return (
    <main className="app-shell">
      <section className="workspace">
        <aside className="sidebar">
          <div className="sidebar-top">
            <p className="eyebrow">Assistant</p>
            <button className="primary-btn sidebar-btn" onClick={resetConversation}>
              New Chat
            </button>
          </div>

          <div className="sidebar-section sidebar-note">
            Voice controls are available from the top-right menu.
          </div>
        </aside>

        <div className="chat-card">
          <div className="chat-header compact">
            <div className="header-controls">
              <div className="settings-wrap" ref={settingsPanelRef}>
                <button
                  type="button"
                  className="voice-button"
                  onClick={() => setShowVoiceSettings((current) => !current)}
                >
                  Voice
                </button>

                {showVoiceSettings && (
                  <div className="settings-panel">
                    <div className="settings-section">
                      <span className="settings-title">Speech To Text</span>
                      <div className="mode-toggle">
                        {[
                          { value: 'off', label: 'Off', enabled: true, reason: '' },
                          {
                            value: 'client',
                            label: 'Client',
                            enabled: clientSTTAvailable,
                            reason: isOnline
                              ? 'Browser STT unavailable.'
                              : 'Client STT needs an internet connection.',
                          },
                          { value: 'server', label: 'Server', enabled: serverSTTAvailable, reason: serverSTTReason || 'Server STT unavailable.' },
                        ].map((option) => (
                          <button
                            key={option.value}
                            type="button"
                            className={`mode-option ${sttMode === option.value ? 'active' : ''}`}
                            disabled={!option.enabled}
                            title={option.enabled ? option.label : option.reason}
                            onClick={() => setSttMode(option.value)}
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    <div className="settings-section">
                      <span className="settings-title">Text To Speech</span>
                      <div className="mode-toggle">
                        {[
                          { value: 'off', label: 'Off', enabled: true, reason: '' },
                          { value: 'client', label: 'Client', enabled: clientTTSAvailable, reason: 'Browser voices unavailable.' },
                          { value: 'server', label: 'Server', enabled: serverTTSAvailable, reason: serverTTSReason || 'Server TTS unavailable.' },
                        ].map((option) => (
                          <button
                            key={option.value}
                            type="button"
                            className={`mode-option ${ttsMode === option.value ? 'active' : ''}`}
                            disabled={!option.enabled}
                            title={option.enabled ? option.label : option.reason}
                            onClick={() => setTtsMode(option.value)}
                          >
                            {option.label}
                          </button>
                        ))}
                      </div>
                    </div>

                    {ttsMode !== 'off' && (
                      <div className="settings-section">
                        <label className="voice-field">
                          <span>Voice</span>
                          <select
                            value={currentVoiceId}
                            onChange={(event) => {
                              if (ttsMode === 'server') {
                                setBackendVoiceId(event.target.value)
                              } else {
                                setBrowserVoiceId(event.target.value)
                              }
                            }}
                            disabled={currentVoiceOptions.length === 0}
                          >
                            {currentVoiceOptions.length === 0 && <option value="">No voices available</option>}
                            {currentVoiceOptions.map((voice) => (
                              <option key={voice.id} value={voice.id}>
                                {voice.name}
                              </option>
                            ))}
                          </select>
                        </label>

                        <label className="voice-field">
                          <span>Speech rate: {speechRate.toFixed(1)}x</span>
                          <input
                            type="range"
                            min="0.7"
                            max="1.4"
                            step="0.1"
                            value={speechRate}
                            onChange={(event) => setSpeechRate(Number(event.target.value))}
                          />
                        </label>
                      </div>
                    )}

                    <p className="voice-status panel-status">{voiceStatus}</p>
                  </div>
                )}
              </div>
            </div>
          </div>

          <div className="message-list">
            {messages.map((message, index) => (
              message.role === 'activity' ? (
                <article key={message.id || `${message.role}-${index}`} className="message activity">
                  <button
                    type="button"
                    className="activity-summary"
                    onClick={() => toggleActivityExpanded(message.id)}
                  >
                    <div className="activity-summary-copy">
                      <p className="message-role">activity</p>
                      <strong>
                        {message.items?.[message.items.length - 1]?.text || 'Working on your request.'}
                      </strong>
                      <span>
                        {message.expanded ? 'Hide details' : `Show details${message.items?.length ? ` (${message.items.length})` : ''}`}
                      </span>
                    </div>
                    <span className={`activity-chevron ${message.expanded ? 'expanded' : ''}`}>
                      ^
                    </span>
                  </button>

                  {message.expanded && (
                    <div className="activity-list">
                      {(message.items || []).map((item, itemIndex) => (
                        <div key={`${message.id}-item-${itemIndex}`} className="activity-item">
                          <span className="activity-dot" />
                          <div className="activity-copy">
                            <p>{item.text}</p>
                            {item.detail && <small>{item.detail}</small>}
                          </div>
                        </div>
                      ))}
                      {isLoading && index === messages.length - 1 && (
                        <div className="activity-item pending">
                          <span className="activity-dot" />
                          <div className="activity-copy">
                            <p>Working on your request.</p>
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </article>
              ) : (
                <article key={message.id || `${message.role}-${index}`} className={`message ${message.role}`}>
                  <p className="message-role">{message.role}</p>
                  <pre>{message.text}</pre>
                </article>
              )
            ))}

            {pendingReview && (
              <article className="message review">
                <p className="message-role">review</p>
                <div className="review-inline">
                  <strong>{pendingReview.tool_name}</strong>
                  <p>{pendingReview.description}</p>

                  {!isEditingReview && (
                    <>
                      <pre className="args-preview">{JSON.stringify(pendingReview.args, null, 2)}</pre>
                      <div className="review-actions">
                        <button type="button" className="approve-btn" onClick={() => submitReview('approve')} disabled={isLoading}>
                          Approve
                        </button>
                        <button type="button" className="edit-btn" onClick={() => setIsEditingReview(true)} disabled={isLoading}>
                          Edit
                        </button>
                        <button type="button" className="reject-btn" onClick={() => submitReview('reject')} disabled={isLoading}>
                          Reject
                        </button>
                      </div>
                    </>
                  )}

                  {isEditingReview && (
                    <>
                      <textarea
                        value={editedArgsText}
                        onChange={(event) => setEditedArgsText(event.target.value)}
                        rows={8}
                        className="review-editor"
                      />
                      <div className="review-actions">
                        <button type="button" className="approve-btn" onClick={() => submitReview('edit')} disabled={isLoading}>
                          Submit
                        </button>
                        <button
                          type="button"
                          className="secondary-btn"
                          onClick={() => {
                            setEditedArgsText(JSON.stringify(pendingReview.args, null, 2))
                            setIsEditingReview(false)
                          }}
                          disabled={isLoading}
                        >
                          Cancel
                        </button>
                      </div>
                    </>
                  )}
                </div>
              </article>
            )}
            <div ref={listEndRef} />
          </div>

          <form
            className="composer"
            onSubmit={(event) => {
              event.preventDefault()
              sendMessage()
            }}
          >
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key !== 'Enter') {
                  return
                }
                if (event.shiftKey) {
                  return
                }
                event.preventDefault()
                if (!isLoading && !pendingReview && input.trim()) {
                  sendMessage()
                }
              }}
              placeholder={pendingReview ? 'Resolve the review first to continue this thread.' : 'Ask the agent something...'}
              disabled={isLoading || Boolean(pendingReview)}
            />
            <button
              type="button"
              className={`mic-btn ${isListening ? 'recording' : ''}`}
              onClick={toggleVoiceInput}
              disabled={isLoading || Boolean(pendingReview) || sttMode === 'off'}
              title={
                sttMode === 'off'
                  ? 'Speech to text is turned off'
                  : isListening
                    ? 'Stop voice input'
                    : 'Start voice input'
              }
            >
              {isListening ? 'Stop' : 'Mic'}
            </button>
            <button type="submit" className="primary-btn" disabled={isLoading || Boolean(pendingReview) || !input.trim()}>
              Send
            </button>
          </form>
        </div>
      </section>
    </main>
  )
}

export default App
