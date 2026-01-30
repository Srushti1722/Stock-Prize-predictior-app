function CorrelationGraph({ ticker, correlationMatrix }) {
  if (!correlationMatrix || Object.keys(correlationMatrix).length === 0) {
    return <div className="no-data">No correlation data available</div>
  }

  const allTickers = Object.keys(correlationMatrix)
  const targetCorrelations = correlationMatrix[ticker] || {}

  const sortedCorrelations = Object.entries(targetCorrelations)
    .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
    .slice(0, 10)

  return (
    <div className="correlation-graph">
      <div className="correlation-matrix">
        {sortedCorrelations.map(([relatedTicker, correlation]) => (
          <div key={relatedTicker} className="correlation-row">
            <div className="correlation-header">
              <span className="ticker-pair">{ticker} - {relatedTicker}</span>
              <span className={`correlation-value ${correlation > 0.5 ? 'strong-positive' : correlation < -0.5 ? 'strong-negative' : ''}`}>
                {correlation.toFixed(3)}
              </span>
            </div>
            <div className="correlation-bar-wrapper">
              <div className="correlation-bar-track">
                <div className="zero-line"></div>
                <div 
                  className={`correlation-bar-fill ${correlation > 0 ? 'positive' : 'negative'}`}
                  style={{
                    width: `${Math.abs(correlation) * 50}%`,
                    [correlation > 0 ? 'left' : 'right']: '50%'
                  }}
                />
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="correlation-legend">
        <div className="legend-item">
          <div className="legend-color positive"></div>
          <span>Positive Correlation</span>
        </div>
        <div className="legend-item">
          <div className="legend-color negative"></div>
          <span>Negative Correlation</span>
        </div>
      </div>
    </div>
  )
}

export default CorrelationGraph
