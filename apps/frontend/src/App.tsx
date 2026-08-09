import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import {
  Send,
  Loader2,
  FileText,
  Terminal,
  List,
  AlertTriangle,
  Activity,
  History,
  ClipboardList,
  PackageSearch,
} from 'lucide-react'

const API_BASE = '/api'

interface Message {
  id: string
  role: 'user' | 'assistant'
  content: string
  citations?: Citation[]
  mcpTrace?: TraceItem[]
  queryPlan?: string[]
  confidence?: number
  timestamp: string
}

interface Citation {
  citation_id: string
  source: string
  asset_id?: string
  asset_name?: string
  doc_type?: string
  score: number
  chunk_index?: number
}

interface TraceItem {
  tool: string
  input?: any
  output?: any
  error?: string
  timestamp: string
}

interface ChatResponse {
  session_id: string
  answer: string
  citations: Citation[]
  mcp_trace: TraceItem[]
  query_plan: string[]
  confidence: number
  timestamp: string
}

function App() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sessionId, setSessionId] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<'citations' | 'trace' | 'plan'>('citations')
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const getConfidenceLevel = (confidence?: number) => {
    if (!confidence) return 'low'
    if (confidence >= 0.7) return 'high'
    if (confidence >= 0.4) return 'medium'
    return 'low'
  }

  const handleSend = async (e?: React.FormEvent) => {
    e?.preventDefault()
    if (!input.trim() || isLoading) return

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: 'user',
      content: input,
      timestamp: new Date().toISOString(),
    }

    setMessages(prev => [...prev, userMessage])
    const currentInput = input
    setInput('')
    setIsLoading(true)

    try {
      const response = await axios.post<ChatResponse>(`${API_BASE}/chat`, {
        message: currentInput,
        session_id: sessionId,
      })

      if (!sessionId) {
        setSessionId(response.data.session_id)
      }

      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: response.data.answer,
        citations: response.data.citations,
        mcpTrace: response.data.mcp_trace,
        queryPlan: response.data.query_plan,
        confidence: response.data.confidence,
        timestamp: response.data.timestamp,
      }

      setMessages(prev => [...prev, assistantMessage])
    } catch (error) {
      const errorMessage: Message = {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: 'Error: Failed to get response from server. Please check if the backend is running.',
        timestamp: new Date().toISOString(),
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const renderMarkdown = (content: string) => {
    return (
      <div className="markdown-content" dangerouslySetInnerHTML={{ __html: simpleMarkdown(content) }} />
    )
  }

  const simpleMarkdown = (text: string): string => {
    return text
      .replace(/### (.*?)(?:\n|$)/g, '<h3>$1</h3>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`(.*?)`/g, '<code>$1</code>')
      .replace(/```(\w+)?\n([\s\S]*?)```/g, '<pre><code>$2</code></pre>')
      .replace(/^- (.*?)(?:\n|$)/gm, '<li>$1</li>')
      .replace(/(<li>.*<\/li>)/s, '<ul>$1</ul>')
      .replace(/\n/g, '<br/>')
  }

  const ConfidenceMeter = ({ value }: { value?: number }) => {
    const pct = Math.round((value || 0) * 100)
    const level = getConfidenceLevel(value)
    return (
      <span className={`confidence-meter confidence-${level}`}>
        <span className="confidence-track">
          <span className="confidence-fill" style={{ width: `${pct}%` }} />
        </span>
        <span className="confidence-value">{pct}%</span>
      </span>
    )
  }

  const CitationItem = ({ citation }: { citation: Citation }) => (
    <div className="citation-item">
      <div className="citation-id">{citation.citation_id} · {citation.source}</div>
      <div className="citation-source">
        {citation.asset_name && `Asset: ${citation.asset_name}`}
        {citation.asset_id && ` (${citation.asset_id})`}
        {citation.doc_type && ` | Type: ${citation.doc_type}`}
      </div>
      <div className="citation-score-row">
        <span className="confidence-track" style={{ width: 60 }}>
          <span
            className="confidence-fill"
            style={{ width: `${Math.round(citation.score * 100)}%`, background: 'var(--green)' }}
          />
        </span>
        <span className="citation-score">{(citation.score * 100).toFixed(1)}% relevance</span>
      </div>
    </div>
  )

  const TraceEntry = ({ trace }: { trace: TraceItem }) => (
    <div className="trace-item">
      <div className="trace-head">
        <span>{trace.tool}</span>
        <span className="trace-time">{new Date(trace.timestamp).toLocaleTimeString()}</span>
      </div>
      {trace.input && <pre>{JSON.stringify(trace.input, null, 2)}</pre>}
      {trace.error && <span className="trace-error">Error: {trace.error}</span>}
    </div>
  )

  const allCitations = messages.flatMap(m => m.citations || [])
  const allTrace = messages.flatMap(m => m.mcpTrace || [])
  const lastPlan = messages[messages.length - 1]?.queryPlan

  return (
    <div className="app">
      <header className="header">
        <div className="header-brand">
          <span className="icon-badge">
            <AlertTriangle size={18} />
          </span>
          <div>
            <h1>Maintenance Copilot</h1>
            <div className="subtitle">Alarm Intelligence &amp; Work-Order Assistant</div>
          </div>
        </div>
        <div className="status">
          <span className="status-dot" />
          <span>Backend Connected</span>
        </div>
      </header>

      <main className="main">
        <div className="chat-container">
          <div className="messages">
            {messages.length === 0 && (
              <div className="welcome">
                <div className="welcome-icon">
                  <Activity size={24} />
                </div>
                <h2>Welcome to Maintenance Copilot</h2>
                <p>Ask about alarms, maintenance history, procedures, or spare parts.</p>
                <div className="examples">
                  <button
                    className="example-btn"
                    onClick={() => {
                      setInput('What alarms occurred on Boiler Feed Pump 101 in the last 30 days?')
                      handleSend()
                    }}
                  >
                    <Activity size={15} />
                    "What alarms occurred on Boiler Feed Pump 101 in the last 30 days?"
                  </button>
                  <button
                    className="example-btn"
                    onClick={() => {
                      setInput('Show me maintenance history for Compressor 201')
                      handleSend()
                    }}
                  >
                    <History size={15} />
                    "Show me maintenance history for Compressor 201"
                  </button>
                  <button
                    className="example-btn"
                    onClick={() => {
                      setInput('What is the surge alarm response procedure for compressors?')
                      handleSend()
                    }}
                  >
                    <ClipboardList size={15} />
                    "What is the surge alarm response procedure for compressors?"
                  </button>
                  <button
                    className="example-btn"
                    onClick={() => {
                      setInput('What are the critical spare parts for pumps?')
                      handleSend()
                    }}
                  >
                    <PackageSearch size={15} />
                    "What are the critical spare parts for pumps?"
                  </button>
                </div>
              </div>
            )}

            {messages.map(message => (
              <div key={message.id} className={`message ${message.role}`}>
                <div className="message-tag">{message.role === 'user' ? 'You' : 'Copilot'}</div>
                <div className="message-content">{renderMarkdown(message.content)}</div>
                {message.role === 'assistant' && (
                  <div className="message-meta">
                    <ConfidenceMeter value={message.confidence} />
                    <span>{new Date(message.timestamp).toLocaleTimeString()}</span>
                  </div>
                )}
              </div>
            ))}

            {isLoading && (
              <div className="message assistant">
                <div className="message-tag">Copilot</div>
                <div className="message-content loading">
                  <Loader2 size={15} />
                  <span>Analyzing...</span>
                </div>
              </div>
            )}

            <div ref={messagesEndRef} />
          </div>

          <form className="input-area" onSubmit={handleSend}>
            <div className="input-wrapper">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Ask about alarms, maintenance, procedures, spare parts..."
                disabled={isLoading}
                rows={2}
              />
              <button type="submit" className="send-button" disabled={isLoading || !input.trim()}>
                <Send size={18} />
              </button>
            </div>
          </form>
        </div>

        <aside className="side-panel">
          <div className="panel" style={{ flex: 1 }}>
            <div className="panel-header">
              <div className="panel-eyebrow">Sources &amp; Analysis</div>
            </div>
            <div className="tab-bar">
              <button
                className={`tab-btn ${activeTab === 'citations' ? 'active' : ''}`}
                onClick={() => setActiveTab('citations')}
              >
                <FileText size={13} />
                Citations
              </button>
              
              <button
                className={`tab-btn ${activeTab === 'plan' ? 'active' : ''}`}
                onClick={() => setActiveTab('plan')}
              >
                <List size={13} />
                Plan
              </button>

              <button
                className={`tab-btn ${activeTab === 'trace' ? 'active' : ''}`}
                onClick={() => setActiveTab('trace')}
              >
                <Terminal size={13} />
                Trace
              </button>
            </div>

            {activeTab === 'citations' && (
              <div className="panel-body">
                {allCitations.map((citation, idx) => (
                  <CitationItem key={idx} citation={citation} />
                ))}
                {allCitations.length === 0 && (
                  <div className="panel-empty">No citations available yet</div>
                )}
              </div>
            )}

            {activeTab === 'plan' && (
              <div className="panel-body plan-list">
                {lastPlan?.map((step, idx) => (
                  <div key={idx} className="plan-item">
                    <span className="plan-index">{String(idx + 1).padStart(2, '0')}</span>
                    {step}
                  </div>
                ))}
                {(!lastPlan || lastPlan.length === 0) && (
                  <div className="panel-empty">No query plan available yet</div>
                )}
              </div>
            )}

            {activeTab === 'trace' && (
              <div className="panel-body">
                {allTrace.map((trace, idx) => (
                  <TraceEntry key={idx} trace={trace} />
                ))}
                {allTrace.length === 0 && (
                  <div className="panel-empty">No MCP trace available yet</div>
                )}
              </div>
            )}
          </div>
        </aside>
      </main>
    </div>
  )
}

export default App