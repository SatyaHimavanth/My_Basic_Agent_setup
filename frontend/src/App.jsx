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
  const listEndRef = useRef(null)

  useEffect(() => {
    listEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, pendingReview])

  function handleAgentResponse(data) {
    if (data.type === 'assistant') {
      setMessages((current) => [
        ...current,
        { role: 'assistant', text: data.message || '(no response)' },
      ])
      setPendingReview(null)
      setEditedArgsText('')
      setIsEditingReview(false)
      return
    }

    if (data.type === 'review_required') {
      setPendingReview(data.review)
      setEditedArgsText(JSON.stringify(data.review.args, null, 2))
      setIsEditingReview(false)
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
    setMessages([
      {
        role: 'assistant',
        text: 'New thread started. Ask me anything that can be handled offline.',
      },
    ])
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
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder={
                pendingReview
                  ? 'Resolve the review first to continue this thread.'
                  : 'Ask the agent something...'
              }
              disabled={isLoading || Boolean(pendingReview)}
            />
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
