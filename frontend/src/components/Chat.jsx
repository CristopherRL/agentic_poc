import { useState, useEffect } from 'react'
import Message from './Message'

const API_URL = import.meta.env.VITE_API_URL || (import.meta.env.PROD ? '' : 'http://localhost:8000')

function Chat() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [rateLimitInfo, setRateLimitInfo] = useState(null)
  const [sessionId, setSessionId] = useState(() => {
    // Load session_id from localStorage on mount
    return localStorage.getItem('sessionId') || null
  })

  const handleSubmit = async (e) => {
    e.preventDefault()
    
    if (!input.trim() || loading) return

    const question = input.trim()
    setInput('')
    setError(null)
    setLoading(true)

    // Add user message
    const userMessage = {
      id: Date.now(),
      type: 'user',
      content: question,
    }
    setMessages((prev) => [...prev, userMessage])

    try {
      const response = await fetch(`${API_URL}/api/v1/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          question,
          session_id: sessionId 
        }),
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`)
      }

      const data = await response.json()

      // Save session_id to localStorage
      if (data.session_id) {
        setSessionId(data.session_id)
        localStorage.setItem('sessionId', data.session_id)
      }

      // Update rate limit info
      if (data.rate_limit_info) {
        setRateLimitInfo(data.rate_limit_info)
      }

      // Add assistant message
      const assistantMessage = {
        id: Date.now() + 1,
        type: 'assistant',
        content: data.answer || 'No answer provided',
        sqlQuery: data.sql_query,
        citations: data.citations || [],
        toolTrace: data.tool_trace || [],
      }
      setMessages((prev) => [...prev, assistantMessage])
    } catch (err) {
      setError(err.message)
      const errorMessage = {
        id: Date.now() + 1,
        type: 'error',
        content: `Error: ${err.message}`,
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="chat-container">
      {rateLimitInfo && (
        <div className="rate-limit-badge">
          <span className="rate-limit-label">Interactions remaining:</span>
          <span className="rate-limit-value">
            {rateLimitInfo.remaining_interactions} / {rateLimitInfo.daily_limit}
          </span>
        </div>
      )}
      <div className="messages-container">
        {messages.length === 0 && (
          <div className="empty-state">
            <p>Start a conversation by asking a question!</p>
            {rateLimitInfo && (
              <div className="rate-limit-info-empty">
                <p className="rate-limit-text">
                  You have <strong>{rateLimitInfo.remaining_interactions}</strong> of{' '}
                  <strong>{rateLimitInfo.daily_limit}</strong> interactions remaining today.
                </p>
              </div>
            )}
            <p className="examples">
              Examples:
              <br />• "Monthly RAV4 HEV sales in Germany in 2024"
              <br />• "What is the standard Toyota warranty for Europe?"
              <br />• "Compare Toyota vs Lexus SUV sales in Western Europe in 2024"
            </p>
          </div>
        )}
        {messages.map((message) => (
          <Message key={message.id} message={message} />
        ))}
        {loading && (
          <div className="message assistant">
            <div className="message-content">
              <div className="loading-dots">
                <span></span>
                <span></span>
                <span></span>
              </div>
            </div>
          </div>
        )}
      </div>
      <form onSubmit={handleSubmit} className="input-form">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a question..."
          disabled={loading}
          maxLength={2000}
          className="input-field"
        />
        <button type="submit" disabled={loading || !input.trim()} className="submit-button">
          Send
        </button>
      </form>
      {error && <div className="error-banner">{error}</div>}
    </div>
  )
}

export default Chat


