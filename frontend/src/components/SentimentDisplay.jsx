function SentimentDisplay({ sentiment }) {
  const getSentimentColor = (label) => {
    switch (label) {
      case 'positive':
        return '#22c55e'
      case 'negative':
        return '#ef4444'
      default:
        return '#94a3b8'
    }
  }

  const getSentimentIcon = (label) => {
    switch (label) {
      case 'positive':
        return '📈'
      case 'negative':
        return '📉'
      default:
        return '➡️'
    }
  }

  if (!sentiment) {
    return <div className="no-data">No sentiment data available</div>
  }

  return (
    <div className="sentiment-display">
      <div className="sentiment-main" style={{ borderColor: getSentimentColor(sentiment.sentiment_label) }}>
        <div className="sentiment-icon">{getSentimentIcon(sentiment.sentiment_label)}</div>
        <div className="sentiment-label" style={{ color: getSentimentColor(sentiment.sentiment_label) }}>
          {sentiment.sentiment_label?.toUpperCase()}
        </div>
        <div className="sentiment-score">
          Score: {sentiment.sentiment_score?.toFixed(3)}
        </div>
      </div>
      
      {sentiment.positive_prob !== undefined && (
        <div className="sentiment-breakdown">
          <div className="sentiment-bar">
            <span className="bar-label">Positive</span>
            <div className="bar-container">
              <div 
                className="bar-fill positive" 
                style={{ width: `${(sentiment.positive_prob * 100)}%` }}
              />
            </div>
            <span className="bar-value">{(sentiment.positive_prob * 100).toFixed(1)}%</span>
          </div>
          
          <div className="sentiment-bar">
            <span className="bar-label">Neutral</span>
            <div className="bar-container">
              <div 
                className="bar-fill neutral" 
                style={{ width: `${(sentiment.neutral_prob * 100)}%` }}
              />
            </div>
            <span className="bar-value">{(sentiment.neutral_prob * 100).toFixed(1)}%</span>
          </div>
          
          <div className="sentiment-bar">
            <span className="bar-label">Negative</span>
            <div className="bar-container">
              <div 
                className="bar-fill negative" 
                style={{ width: `${(sentiment.negative_prob * 100)}%` }}
              />
            </div>
            <span className="bar-value">{(sentiment.negative_prob * 100).toFixed(1)}%</span>
          </div>
        </div>
      )}
    </div>
  )
}

export default SentimentDisplay
