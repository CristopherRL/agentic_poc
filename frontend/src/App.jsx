import Chat from './components/Chat'

function App() {
  return (
    <div className="app">
      <header className="app-header">
        <h1>Agentic Assistant POC</h1>
        <p>Ask questions about Toyota/Lexus analytics (sales) and documentation (warranty, manuals)</p>
      </header>
      <Chat />
    </div>
  )
}

export default App


