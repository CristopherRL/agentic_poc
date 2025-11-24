import { useState, useRef, useEffect } from 'react'
import { Send, Menu, Plus, X, FileText, Database, Brain, Copy, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card } from '@/components/ui/card'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion'
import { cn } from '@/lib/utils'
import ReactMarkdown from 'react-markdown'

const API_URL = import.meta.env.VITE_API_URL || (import.meta.env.PROD ? '' : 'http://localhost:8000')

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [rateLimitInfo, setRateLimitInfo] = useState(null)
  const [sessionId, setSessionId] = useState(() => {
    return localStorage.getItem('sessionId') || null
  })
  const [error, setError] = useState(null)
  const scrollRef = useRef(null)
  const inputRef = useRef(null)

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (scrollRef.current) {
      // Find the viewport element inside ScrollArea
      const viewport = scrollRef.current.querySelector('[data-radix-scroll-area-viewport]')
      if (viewport) {
        viewport.scrollTop = viewport.scrollHeight
      }
    }
  }, [messages, isLoading])

  const handleSend = async () => {
    if (!input.trim() || isLoading) return

    const userMessage = {
      id: Date.now().toString(),
      role: 'user',
      content: input.trim(),
      timestamp: new Date(),
    }

    setMessages((prev) => [...prev, userMessage])
    const question = input.trim()
    setInput('')
    setError(null)
    setIsLoading(true)

    try {
      const response = await fetch(`${API_URL}/api/v1/ask`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question,
          session_id: sessionId,
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

      const assistantMessage = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: '',
        answer: data.answer || '',
        sql_query: data.sql_query,
        citations: data.citations || [],
        tool_trace: data.tool_trace || [],
        timestamp: new Date(),
      }

      setMessages((prev) => [...prev, assistantMessage])
    } catch (err) {
      setError(err.message)
      const errorMessage = {
        id: (Date.now() + 1).toString(),
        role: 'error',
        content: `Error: ${err.message}`,
        timestamp: new Date(),
      }
      setMessages((prev) => [...prev, errorMessage])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleNewChat = () => {
    setMessages([])
    setError(null)
    inputRef.current?.focus()
  }

  return (
    <div className="flex h-screen bg-background">
      {/* AI Disclosure Banner */}
      <div className="fixed top-0 left-0 right-0 z-50 bg-primary/10 border-b border-border px-4 py-2 text-center text-sm text-foreground">
        <span className="inline-flex items-center gap-2">
          <span>🤖</span>
          <span>You are chatting with an AI assistant powered by artificial intelligence.</span>
        </span>
      </div>

      {/* Sidebar */}
      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 w-64 transform border-r border-border bg-card transition-transform duration-300 ease-in-out lg:relative lg:translate-x-0',
          sidebarOpen ? 'translate-x-0' : '-translate-x-full',
          'pt-12'
        )}
      >
        <div className="flex h-full flex-col">
          {/* Sidebar Header */}
          <div className="flex items-center justify-between border-b border-border p-4">
            <h2 className="text-lg font-semibold text-foreground">Chat History</h2>
            <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setSidebarOpen(false)}>
              <X className="h-4 w-4" />
            </Button>
          </div>

          {/* New Chat Button */}
          <div className="p-4">
            <Button onClick={handleNewChat} className="w-full" variant="default">
              <Plus className="mr-2 h-4 w-4" />
              New Chat
            </Button>
          </div>

          {/* Rate Limit Info */}
          {rateLimitInfo && (
            <div className="px-4 pb-4">
              <div className="rounded-lg border border-border bg-muted/50 p-3 text-sm">
                <div className="font-medium text-foreground">Interactions remaining</div>
                <div className="mt-1 text-lg font-semibold text-primary">
                  {rateLimitInfo.remaining_interactions} / {rateLimitInfo.daily_limit}
                </div>
              </div>
            </div>
          )}

          {/* Language Notice */}
          <div className="px-4 pb-4">
            <div className="rounded-lg border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
              <span className="inline-flex items-center gap-1">
                <span>🌐</span>
                <span>This assistant only supports English language conversations.</span>
              </span>
            </div>
          </div>

          {/* Sidebar Footer */}
          <div className="mt-auto border-t border-border p-4">
            <div className="flex items-center gap-3">
              <div className="h-8 w-8 rounded-full bg-primary" />
              <div className="flex-1 text-sm">
                <div className="font-medium text-foreground">Agentic Assistant</div>
                <div className="text-xs text-muted-foreground">v1.0</div>
              </div>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <div className="flex flex-1 flex-col pt-12">
        {/* Header */}
        <header className="flex items-center justify-between border-b border-border bg-card px-4 py-3">
          <div className="flex items-center gap-3">
            <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => setSidebarOpen(true)}>
              <Menu className="h-5 w-5" />
            </Button>
            <div>
              <h1 className="text-lg font-semibold text-foreground">Agentic Assistant</h1>
              <p className="text-xs text-muted-foreground">SQL Analytics & Document Retrieval</p>
            </div>
          </div>
          {rateLimitInfo && (
            <div className="hidden md:flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Remaining:</span>
              <span className="font-semibold text-primary">
                {rateLimitInfo.remaining_interactions}/{rateLimitInfo.daily_limit}
              </span>
            </div>
          )}
        </header>

        {/* Messages Area */}
        <ScrollArea className="flex-1 p-4">
          <div ref={scrollRef} className="mx-auto max-w-4xl space-y-6">
            {messages.length === 0 && (
              <div className="flex h-full min-h-[400px] items-center justify-center">
                <div className="text-center">
                  <Brain className="mx-auto h-12 w-12 text-muted-foreground" />
                  <h2 className="mt-4 text-xl font-semibold text-foreground">Start a Conversation</h2>
                  <p className="mt-2 text-sm text-muted-foreground">Ask me anything about your data or documents</p>
                  {rateLimitInfo && (
                    <div className="mt-4 rounded-lg border border-border bg-muted/50 p-4 text-sm">
                      <p className="text-muted-foreground">
                        You have <strong className="text-foreground">{rateLimitInfo.remaining_interactions}</strong> of{' '}
                        <strong className="text-foreground">{rateLimitInfo.daily_limit}</strong> interactions remaining today.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {messages.map((message) => (
              <ChatMessage key={message.id} message={message} />
            ))}

            {isLoading && <LoadingMessage />}
          </div>
        </ScrollArea>

        {/* Input Area */}
        <div className="border-t border-border bg-card p-4">
          <div className="mx-auto max-w-4xl">
            {error && (
              <div className="mb-2 rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2 text-sm text-destructive">
                {error}
              </div>
            )}
            <div className="flex gap-2">
              <Input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyPress={handleKeyPress}
                placeholder="Ask about your data or documents..."
                className="flex-1"
                disabled={isLoading}
                maxLength={2000}
              />
              <Button onClick={handleSend} disabled={isLoading || !input.trim()}>
                <Send className="h-4 w-4" />
              </Button>
            </div>
            <p className="mt-2 text-center text-xs text-muted-foreground">
              AI can make mistakes. Verify important information from sources.
            </p>
          </div>
        </div>
      </div>

      {/* Overlay for mobile sidebar */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-30 bg-black/50 lg:hidden" onClick={() => setSidebarOpen(false)} />
      )}
    </div>
  )
}

// Chat Message Component
function ChatMessage({ message }) {
  if (message.role === 'user') {
    return (
      <div className="flex justify-end">
        <div className="max-w-[80%] rounded-lg bg-primary px-4 py-3 text-primary-foreground">
          <p className="text-sm">{message.content}</p>
        </div>
      </div>
    )
  }

  if (message.role === 'error') {
    return (
      <div className="flex justify-start">
        <Card className="max-w-[85%] border-destructive bg-destructive/10 p-4">
          <p className="text-sm text-destructive">{message.content}</p>
        </Card>
      </div>
    )
  }

  return (
    <div className="flex justify-start">
      <div className="max-w-[85%] space-y-3">
        {/* Answer */}
        {message.answer && (
          <Card className="p-4">
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <ReactMarkdown>{message.answer}</ReactMarkdown>
            </div>
          </Card>
        )}

        {/* SQL Query */}
        {message.sql_query && (
          <Card className="overflow-hidden">
            <Accordion type="single" collapsible>
              <AccordionItem value="sql" className="border-none">
                <AccordionTrigger className="px-4 py-3 hover:no-underline">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Database className="h-4 w-4 text-blue-500" />
                    <span>Generated SQL Query</span>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="px-0 pb-0">
                  <CodeBlock code={message.sql_query} language="sql" />
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </Card>
        )}

        {/* Tool Trace */}
        {message.tool_trace && message.tool_trace.length > 0 && (
          <Card className="overflow-hidden">
            <Accordion type="single" collapsible>
              <AccordionItem value="trace" className="border-none">
                <AccordionTrigger className="px-4 py-3 hover:no-underline">
                  <div className="flex items-center gap-2 text-sm font-medium">
                    <Brain className="h-4 w-4 text-purple-500" />
                    <span>View Reasoning Steps</span>
                  </div>
                </AccordionTrigger>
                <AccordionContent className="px-4 pb-4">
                  <ol className="space-y-2">
                    {message.tool_trace.map((step, index) => (
                      <li key={index} className="flex gap-3 text-sm">
                        <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-muted text-xs font-medium text-muted-foreground">
                          {index + 1}
                        </span>
                        <span className="pt-0.5 text-foreground">{step}</span>
                      </li>
                    ))}
                  </ol>
                </AccordionContent>
              </AccordionItem>
            </Accordion>
          </Card>
        )}

        {/* Citations */}
        {message.citations && message.citations.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center gap-2 px-1">
              <FileText className="h-4 w-4 text-muted-foreground" />
              <span className="text-xs font-medium text-muted-foreground">Sources</span>
            </div>
            <div className="grid gap-2 sm:grid-cols-2">
              {message.citations.map((citation, index) => (
                <Card key={index} className="cursor-pointer p-3 transition-colors hover:bg-accent">
                  <div className="flex items-start gap-2">
                    <FileText className="mt-0.5 h-4 w-4 shrink-0 text-blue-500" />
                    <div className="min-w-0 flex-1">
                      <div className="truncate text-sm font-medium text-foreground">{citation.source_document}</div>
                      {citation.page && <div className="mt-1 text-xs text-muted-foreground">Page {citation.page}</div>}
                      <p className="mt-2 line-clamp-2 text-xs text-muted-foreground">{citation.content}</p>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// Loading Message Component
function LoadingMessage() {
  return (
    <div className="flex justify-start">
      <Card className="max-w-[85%] p-4">
        <div className="flex items-center gap-3">
          <div className="flex gap-1">
            <div className="h-2 w-2 animate-bounce rounded-full bg-primary [animation-delay:-0.3s]" />
            <div className="h-2 w-2 animate-bounce rounded-full bg-primary [animation-delay:-0.15s]" />
            <div className="h-2 w-2 animate-bounce rounded-full bg-primary" />
          </div>
          <span className="text-sm text-muted-foreground">Thinking...</span>
        </div>
      </Card>
    </div>
  )
}

// Code Block Component with Copy functionality
function CodeBlock({ code, language = 'code' }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className="relative bg-[#1e1e1e] text-[#d4d4d4]">
      <div className="flex items-center justify-between border-b border-white/10 px-4 py-2">
        <span className="text-xs font-medium uppercase text-white/60">{language || 'code'}</span>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-white/60 hover:bg-white/10 hover:text-white"
          onClick={handleCopy}
        >
          {copied ? (
            <>
              <Check className="mr-1 h-3 w-3" />
              Copied
            </>
          ) : (
            <>
              <Copy className="mr-1 h-3 w-3" />
              Copy
            </>
          )}
        </Button>
      </div>
      <pre className="overflow-x-auto p-4">
        <code className="font-mono text-sm leading-relaxed">{code}</code>
      </pre>
    </div>
  )
}

export default App

