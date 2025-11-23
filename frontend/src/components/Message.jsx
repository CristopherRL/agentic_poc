function Message({ message }) {
  const { type, content, sqlQuery, citations, toolTrace } = message

  return (
    <div className={`message ${type}`}>
      <div className="message-header">
        <span className="message-type">
          {type === 'user' ? 'You' : type === 'error' ? 'Error' : 'Assistant'}
        </span>
      </div>
      <div className="message-content">
        <p>{content}</p>
        
        {sqlQuery && (
          <details className="details-section">
            <summary>SQL Query</summary>
            <pre className="sql-query">{sqlQuery}</pre>
          </details>
        )}

        {citations && citations.length > 0 && (
          <details className="details-section">
            <summary>Citations ({citations.length})</summary>
            <div className="citations">
              {citations.map((citation, idx) => (
                <div key={idx} className="citation">
                  <strong>{citation.source_document}</strong>
                  {citation.page && <span> - Page {citation.page}</span>}
                  <p className="citation-content">{citation.content}</p>
                </div>
              ))}
            </div>
          </details>
        )}

        {toolTrace && toolTrace.length > 0 && (
          <details className="details-section">
            <summary>Tool Trace</summary>
            <ul className="tool-trace">
              {toolTrace.map((trace, idx) => (
                <li key={idx}>{trace}</li>
              ))}
            </ul>
          </details>
        )}
      </div>
    </div>
  )
}

export default Message


