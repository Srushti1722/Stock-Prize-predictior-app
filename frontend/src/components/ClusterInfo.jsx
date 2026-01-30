function ClusterInfo({ cluster }) {
  if (!cluster) {
    return <div className="no-data">No cluster data available</div>
  }

  return (
    <div className="cluster-info">
      <div className="cluster-id-section">
        <span className="cluster-label">Cluster ID:</span>
        <span className="cluster-value">#{cluster.cluster_id}</span>
      </div>

      {cluster.similar_stocks && cluster.similar_stocks.length > 0 && (
        <div className="similar-stocks">
          <h4>Similar Stocks:</h4>
          <div className="stocks-list">
            {cluster.similar_stocks.map((stock, index) => (
              <div key={index} className="stock-item">
                <span className="stock-ticker">{stock.ticker}</span>
                <span className="stock-similarity">
                  {(stock.similarity * 100).toFixed(0)}% similar
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {cluster.correlation && Object.keys(cluster.correlation).length > 0 && (
        <div className="correlation-list">
          <h4>Top Correlations:</h4>
          {Object.entries(cluster.correlation)
            .sort(([, a], [, b]) => Math.abs(b) - Math.abs(a))
            .slice(0, 5)
            .map(([ticker, corr]) => (
              <div key={ticker} className="correlation-item">
                <span className="corr-ticker">{ticker}</span>
                <div className="corr-bar-container">
                  <div 
                    className={`corr-bar ${corr > 0 ? 'positive' : 'negative'}`}
                    style={{ 
                      width: `${Math.abs(corr) * 100}%`,
                      marginLeft: corr < 0 ? `${100 - Math.abs(corr) * 100}%` : '0'
                    }}
                  />
                </div>
                <span className="corr-value">{corr.toFixed(2)}</span>
              </div>
            ))}
        </div>
      )}
    </div>
  )
}

export default ClusterInfo
