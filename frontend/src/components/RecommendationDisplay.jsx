import { useState } from 'react'

const categoryColors = {
  'Strong Buy': '#10b981',
  'Buy': '#22c55e',
  'Hold': '#737373',
  'Sell': '#f97316',
  'Strong Sell': '#ef4444'
}

const categoryIcons = {
  'Strong Buy': '🚀',
  'Buy': '📈',
  'Hold': '⏸️',
  'Sell': '📉',
  'Strong Sell': '⛔'
}

function RecommendationDisplay({ recommendation }) {
  const [showDetails, setShowDetails] = useState(false)

  if (!recommendation || recommendation.error) {
    return null
  }

  const { category, score, rationale, limit_targets, disclaimer } = recommendation

  return (
    <div className="recommendation-display">
      <div className="recommendation-header">
        <h3>Trading Recommendation</h3>
      </div>

      <div className="recommendation-main">
        <div className="category-badge" style={{ backgroundColor: categoryColors[category] }}>
          <span className="category-icon">{categoryIcons[category]}</span>
          <span className="category-text">{category}</span>
        </div>
        
        <div className="score-indicator">
          <span className="score-label">Signal Strength</span>
          <div className="score-bar">
            <div 
              className="score-fill" 
              style={{ 
                width: `${Math.abs(score) * 50}%`,
                backgroundColor: score >= 0 ? categoryColors['Buy'] : categoryColors['Sell'],
                marginLeft: score >= 0 ? '50%' : `${50 - Math.abs(score) * 50}%`
              }}
            ></div>
            <div className="score-center"></div>
          </div>
          <div className="score-labels">
            <span>Strong Sell</span>
            <span>Neutral</span>
            <span>Strong Buy</span>
          </div>
        </div>
      </div>

      <div className="recommendation-rationale">
        <h4>Analysis</h4>
        <ul>
          {rationale && rationale.map((reason, index) => (
            <li key={index}>{reason}</li>
          ))}
        </ul>
      </div>

      {limit_targets && (
        <div className="limit-targets">
          <button 
            className="details-toggle" 
            onClick={() => setShowDetails(!showDetails)}
          >
            {showDetails ? '▼' : '▶'} Suggested Limit Orders
          </button>
          
          {showDetails && (
            <div className="targets-grid">
              {limit_targets.primary_buy && (
                <>
                  <div className="target-item">
                    <span className="target-label">Primary Buy Limit</span>
                    <span className="target-value">${limit_targets.primary_buy}</span>
                  </div>
                  <div className="target-item">
                    <span className="target-label">Secondary Buy Limit</span>
                    <span className="target-value">${limit_targets.secondary_buy}</span>
                  </div>
                  <div className="target-item">
                    <span className="target-label">Stop Loss</span>
                    <span className="target-value">${limit_targets.stop_loss}</span>
                  </div>
                  <div className="target-item">
                    <span className="target-label">Take Profit</span>
                    <span className="target-value">${limit_targets.take_profit}</span>
                  </div>
                </>
              )}
              {limit_targets.primary_sell && (
                <>
                  <div className="target-item">
                    <span className="target-label">Primary Sell Limit</span>
                    <span className="target-value">${limit_targets.primary_sell}</span>
                  </div>
                  <div className="target-item">
                    <span className="target-label">Secondary Sell Limit</span>
                    <span className="target-value">${limit_targets.secondary_sell}</span>
                  </div>
                  <div className="target-item">
                    <span className="target-label">Stop Loss</span>
                    <span className="target-value">${limit_targets.stop_loss}</span>
                  </div>
                  <div className="target-item">
                    <span className="target-label">Take Profit</span>
                    <span className="target-value">${limit_targets.take_profit}</span>
                  </div>
                </>
              )}
            </div>
          )}
        </div>
      )}

      <div className="disclaimer">
        <strong>⚠️ Disclaimer:</strong> {disclaimer}
      </div>
    </div>
  )
}

export default RecommendationDisplay
