import { useEffect, useRef, useState } from 'react'
import './App.css'

const starterPrompts = [
  'What time is it right now?',
  'Generate a UUID for me.',
  'Calculate (12 + 8) * 3.',
  'What is the weather in Bengaluru?',
]

function createThreadId() {
  return `thread-${Date.now()}`
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

function App() {
  const recognitionRef = useRef(null)
  const textareaRef = useRef(null)
  const [threadId, setThreadId] = useState(createThreadId())
  const [messages, setMessages] = useState([
    {
      role: 'assistant',
      text: 'Ask me for time, date, system info, math, random numbers, UUIDs, or weather.',
    },
  ])
  const [input, setInput] = useState('')
  const [pendingReview, setPendingReview] = useState(null)
  const [editedArgsText, setEditedArgsText] = useState('')
  const [isEditingReview, setIsEditingReview] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [voiceStatus, setVoiceStatus] = useState('Idle')
  const [autoSpeak, setAutoSpeak] = useState(true)
  const [speechRate, setSpeechRate] = useState(1)
  const [browserVoices, setBrowserVoices] = useState([])
  const [selectedVoiceId, setSelectedVoiceId] = useState('')
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
    if (typeof window === 'undefined' || !window.speechSynthesis) {
      return undefined
    }

    const syncVoices = () => {
      const voices = window.speechSynthesis.getVoices()
      setBrowserVoices(voices)
      if (!selectedVoiceId && voices.length > 0) {
        setSelectedVoiceId(voices[0].voiceURI)
      }
    }

    syncVoices()
    window.speechSynthesis.addEventListener('voiceschanged', syncVoices)

    return () => {
      window.speechSynthesis.removeEventListener('voiceschanged', syncVoices)
    }
  }, [selectedVoiceId])

  useEffect(() => {
    return () => {
      recognitionRef.current?.stop?.()
      window.speechSynthesis?.cancel?.()
    }
  }, [])

  function speakAssistantReply(text) {
    if (!autoSpeak || !text || typeof window === 'undefined' || !window.speechSynthesis) {
      return
    }

    const utterance = new SpeechSynthesisUtterance(text)
    utterance.rate = speechRate

    if (selectedVoiceId) {
      const selectedVoice = browserVoices.find((voice) => voice.voiceURI === selectedVoiceId)
      if (selectedVoice) {
        utterance.voice = selectedVoice
      }
    }

    window.speechSynthesis.cancel()
    window.speechSynthesis.speak(utterance)
  }

  function handleAgentResponse(data) {
    if (data.type === 'assistant') {
      const reply = data.message || '(no response)'
      setMessages((current) => [
        ...current,
        { role: 'assistant', text: reply },
      ])
      setPendingReview(null)
      setEditedArgsText('')
      setIsEditingReview(false)
      setVoiceStatus('Idle')
      speakAssistantReply(reply)
      return
    }

    if (data.type === 'review_required') {
      setPendingReview(data.review)
      setEditedArgsText(JSON.stringify(data.review.args, null, 2))
      setIsEditingReview(false)
      setVoiceStatus('Review required')
    }
  }

  async function sendMessage(nextText) {
    const message = (nextText ?? input).trim()
    if (!message || isLoading || pendingReview) {
      return
    }

    setMessages((current) => [...current, { role: 'user', text: message }])
    setInput('')
    setIsLoading(true)

    try {
      const data = await postJson('/api/chat', {
        thread_id: threadId,
        message,
      })
      handleAgentResponse(data)
    } catch (error) {
      setMessages((current) => [
        ...current,
        { role: 'system', text: `Error: ${error.message}` },
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
        setMessages((current) => [
          ...current,
          { role: 'system', text: 'Error: edited tool args must be valid JSON.' },
        ])
        return
      }
    }

    setIsLoading(true)
    try {
      const data = await postJson('/api/review', {
        thread_id: threadId,
        decision,
        edited_args: editedArgs,
        reject_message: decision === 'reject' ? 'User rejected the weather request.' : undefined,
      })
      handleAgentResponse(data)
    } catch (error) {
      setMessages((current) => [
        ...current,
        { role: 'system', text: `Error: ${error.message}` },
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
    window.speechSynthesis?.cancel?.()
    setMessages([
      {
        role: 'assistant',
        text: 'New thread started. Ask me anything that can be handled offline.',
      },
    ])
  }

  function stopVoiceInput() {
    recognitionRef.current?.stop?.()
    recognitionRef.current = null
    setIsListening(false)
  }

  function toggleVoiceInput() {
    if (pendingReview || isLoading) {
      return
    }

    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      setMessages((current) => [
        ...current,
        { role: 'system', text: 'Error: this browser does not support speech recognition.' },
      ])
      return
    }

    if (isListening) {
      stopVoiceInput()
      setVoiceStatus('Idle')
      return
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
        stopVoiceInput()
      }
    }

    recognition.onerror = (event) => {
      setIsListening(false)
      setVoiceStatus('Voice error')
      setMessages((current) => [
        ...current,
        { role: 'system', text: `Error: voice input failed (${event.error}).` },
      ])
    }

    recognition.onend = () => {
      setIsListening(false)
      recognitionRef.current = null
      setVoiceStatus((current) =>
        current === 'Voice captured. Edit or send.' ? current : 'Idle'
      )
    }

    recognition.start()
  }

  return (
    <main className="app-shell">
      <section className="workspace">
        <aside className="sidebar">
          <div className="sidebar-top">
            <p className="eyebrow">Basic Agent</p>
            <button className="primary-btn sidebar-btn" onClick={resetConversation}>
              New Chat
            </button>
          </div>

          <div className="sidebar-section">
            <span className="thread-label">Thread</span>
            <code>{threadId}</code>
          </div>

          <div className="sidebar-section">
            <span className="thread-label">Quick Prompts</span>
            <div className="quick-actions">
              {starterPrompts.map((prompt) => (
                <button
                  key={prompt}
                  className="chip"
                  onClick={() => sendMessage(prompt)}
                  disabled={isLoading || Boolean(pendingReview)}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>

          <div className="sidebar-section sidebar-note">
            Chat history can live here next.
          </div>

          <div className="sidebar-section">
            <span className="thread-label">Voice</span>
            <div className="voice-settings">
              <label className="voice-toggle">
                <input
                  type="checkbox"
                  checked={autoSpeak}
                  onChange={(event) => setAutoSpeak(event.target.checked)}
                />
                <span>Speak assistant replies</span>
              </label>

              <label className="voice-field">
                <span>Voice</span>
                <select
                  value={selectedVoiceId}
                  onChange={(event) => setSelectedVoiceId(event.target.value)}
                >
                  {browserVoices.length === 0 && <option value="">Default browser voice</option>}
                  {browserVoices.map((voice) => (
                    <option key={voice.voiceURI} value={voice.voiceURI}>
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

              <p className="voice-status">{voiceStatus}</p>
            </div>
          </div>
        </aside>

        <div className="chat-card">
          <div className="chat-header compact">
            <div>
              <p className="panel-label">Conversation</p>
              <h2>Plain Chat</h2>
            </div>
            <span className={`status-pill ${pendingReview ? 'review' : 'ready'}`}>
              {pendingReview ? 'Waiting for review' : 'Ready'}
            </span>
          </div>

          <div className="message-list">
            {messages.map((message, index) => (
              <article key={`${message.role}-${index}`} className={`message ${message.role}`}>
                <p className="message-role">{message.role}</p>
                <pre>{message.text}</pre>
              </article>
            ))}

            {pendingReview && (
              <article className="message review">
                <p className="message-role">review</p>
                <div className="review-inline">
                  <strong>{pendingReview.tool_name}</strong>
                  <p>{pendingReview.description}</p>

                  {!isEditingReview && (
                    <>
                      <pre className="args-preview">
                        {JSON.stringify(pendingReview.args, null, 2)}
                      </pre>
                      <div className="review-actions">
                        <button
                          type="button"
                          className="approve-btn"
                          onClick={() => submitReview('approve')}
                          disabled={isLoading}
                        >
                          Approve
                        </button>
                        <button
                          type="button"
                          className="edit-btn"
                          onClick={() => setIsEditingReview(true)}
                          disabled={isLoading}
                        >
                          Edit
                        </button>
                        <button
                          type="button"
                          className="reject-btn"
                          onClick={() => submitReview('reject')}
                          disabled={isLoading}
                        >
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
                        <button
                          type="button"
                          className="approve-btn"
                          onClick={() => submitReview('edit')}
                          disabled={isLoading}
                        >
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

            {isLoading && (
              <article className="message assistant loading">
                <p className="message-role">assistant</p>
                <div className="loader">
                  <span />
                  <span />
                  <span />
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
              placeholder={
                pendingReview
                  ? 'Resolve the review first to continue this thread.'
                  : 'Ask the agent something...'
              }
              disabled={isLoading || Boolean(pendingReview)}
            />
            <button
              type="button"
              className={`mic-btn ${isListening ? 'recording' : ''}`}
              onClick={toggleVoiceInput}
              disabled={isLoading || Boolean(pendingReview)}
              title={isListening ? 'Stop voice input' : 'Start voice input'}
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
