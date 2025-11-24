import Chat from './components/Chat'

function App() {
  return (
    <div className="app">
      <div className="ai-disclosure-banner">
        <span className="ai-disclosure-icon">🤖</span>
        <span>You are chatting with an AI assistant powered by artificial intelligence.</span>
      </div>
      <header className="app-header">
        <h1>Agentic Assistant POC</h1>
        <p>Ask questions about Toyota/Lexus analytics (sales) and documentation (warranty, manuals)</p>
        <div className="language-notice">
          <span className="language-notice-icon">🌐</span>
          <span>This assistant only supports English language conversations.</span>
        </div>
      </header>
      <Chat />
    </div>
  )
}

export default App


