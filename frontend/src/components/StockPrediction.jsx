import { useState, useEffect, useMemo, useRef } from 'react'
import axios from 'axios'
import useWebSocket from '../hooks/useWebSocket'
import PriceChart from './PriceChart'
import SentimentDisplay from './SentimentDisplay'
import ClusterInfo from './ClusterInfo'
import CorrelationGraph from './CorrelationGraph'
import CandlestickChart from './CandlestickChart'
import VolumeChart from './VolumeChart'
import PredictionChart from './PredictionChart'
import TimePredictions from './TimePredictions'
import RecommendationDisplay from './RecommendationDisplay'

const API_URL = `${window.location.protocol}//${window.location.hostname}:3000`

/**
 * StockPrediction.jsx
 * - Uses a single canonical currentPrice derived from backend (stock_info.current_price || last historical close)
 * - Applies websocket updates to that canonical price only when values actually change (prevents infinite updates)
 * - Ensures track/untrack is idempotent (trackedRef)
 * - Passes canonical price to TimePredictions and PriceChart so all UI sections show consistent numbers
 */

function StockPrediction() {
  const [ticker, setTicker] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [predictionData, setPredictionData] = useState(null)
  const [timePredictions, setTimePredictions] = useState({ hourly: null, daily: null })
  const { isConnected, priceUpdates, trackStock, untrackStock } = useWebSocket(API_URL)

  // track which ticker we're currently subscribed to (avoid repeated emits)
  const trackedRef = useRef(null)

  // keep a ref copy of predictionData for websocket effect (avoid using object identity as dependency)
  const predictionDataRef = useRef(predictionData)
  useEffect(() => { predictionDataRef.current = predictionData }, [predictionData])

  // Idempotent track/untrack: run when ticker or predictionData changes
  useEffect(() => {
    if (!ticker || !predictionData) return

    // only track if not already tracking same ticker
    if (trackedRef.current === ticker) return

    // attempt track
    try {
      trackStock(ticker)
      trackedRef.current = ticker
    } catch (err) {
      console.warn('trackStock error', err)
    }

    // cleanup: untrack the previously tracked ticker
    return () => {
      try {
        if (trackedRef.current) {
          untrackStock(trackedRef.current)
          trackedRef.current = null
        }
      } catch (err) {
        // ignore cleanup error
      }
    }
    // note: trackStock/untrackStock are stable from hook; include them in deps
  }, [ticker, predictionData, trackStock, untrackStock])

  // Apply websocket price updates to canonical price inside predictionData.
  // Use ref to avoid dependency cycles. Only update state when meaningful change occurs.
  useEffect(() => {
    if (!predictionDataRef.current || !ticker) return

    const wsEntry = priceUpdates?.[ticker]
    if (!wsEntry) return

    const incomingPrice = wsEntry.price != null ? Number(wsEntry.price) : NaN
    const incomingChange = wsEntry.change
    const incomingPct = wsEntry.change_percent

    // stored values from last snapshot
    const saved = predictionDataRef.current.stock_info ?? {}
    const savedPrice = saved.current_price != null ? Number(saved.current_price) : NaN
    const savedChange = saved.price_change
    const savedPct = saved.price_change_percent

    const EPS = 1e-6
    const priceDifferent = Number.isFinite(incomingPrice) && Math.abs(incomingPrice - (Number(savedPrice) || 0)) > EPS
    const changeDifferent = incomingChange !== savedChange
    const pctDifferent = incomingPct !== savedPct

    if (!priceDifferent && !changeDifferent && !pctDifferent) {
      // no meaningful changes -> avoid setState (prevents re-render loops)
      return
    }

    // safe functional update; final check inside to avoid races
    setPredictionData(prev => {
      if (!prev) return prev
      const prevSaved = prev.stock_info ?? {}
      const prevSavedPrice = prevSaved.current_price != null ? Number(prevSaved.current_price) : NaN

      if (
        Number.isFinite(prevSavedPrice) &&
        Math.abs(prevSavedPrice - incomingPrice) <= EPS &&
        prevSaved.price_change === incomingChange &&
        prevSaved.price_change_percent === incomingPct
      ) {
        return prev
      }

      return {
        ...prev,
        stock_info: {
          ...prev.stock_info,
          current_price: Number.isFinite(incomingPrice) ? incomingPrice : prev.stock_info?.current_price,
          price_change: incomingChange ?? prev.stock_info?.price_change,
          price_change_percent: incomingPct ?? prev.stock_info?.price_change_percent
        }
      }
    })
  }, [priceUpdates, ticker]) // intentionally not depending on predictionData

  // Fetch predictions from backend
  const handlePredict = async () => {
    if (!ticker.trim()) {
      setError('Please enter a stock ticker')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const response = await axios.post(`${API_URL}/predict`, {
        ticker: ticker.toUpperCase(),
        tickers: [ticker.toUpperCase(), 'AAPL', 'GOOGL', 'MSFT', 'AMZN']
      })

      // backend returns canonical stock_info.current_price inside response.data
      setPredictionData(response.data)
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to fetch prediction')
    } finally {
      setLoading(false)
    }
  }

  // Add stock endpoint (then call predict)
  const handleAddStock = async () => {
    if (!ticker.trim()) {
      setError('Please enter a stock ticker')
      return
    }

    setLoading(true)
    setError(null)

    try {
      await axios.post(`${API_URL}/add-stock`, {
        ticker: ticker.toUpperCase()
      })
      // re-run prediction after successful add
      handlePredict()
    } catch (err) {
      setError(err.response?.data?.error || 'Failed to add stock')
      setLoading(false)
    }
  }

  const handleTimePrediction = (type, prediction) => {
    setTimePredictions(prev => ({
      ...prev,
      [type]: prediction
    }))
  }

  const popularStocks = {
    us: ['AAPL', 'TSLA', 'GOOGL', 'MSFT', 'NVDA'],
    indian: ['RELIANCE.NS', 'TCS.NS', 'HDFCBANK.NS', 'INFY.NS', 'SBIN.NS']
  }

  const handleQuickSelect = (selectedTicker) => {
    setTicker(selectedTicker)
  }

  const getCurrencySymbol = (ticker) => {
    if (!ticker) return '$'
    if (ticker.endsWith('.NS') || ticker.endsWith('.BO')) {
      return '₹'
    }
    return '$'
  }

  // Canonical current price: prefer backend current_price, else fallback to last historical close
  const currentPrice = useMemo(() => {
    if (!predictionData) return null
    const backendPrice = predictionData?.stock_info?.current_price
    if (backendPrice != null && !Number.isNaN(Number(backendPrice))) {
      return Number(backendPrice)
    }
    const hist = predictionData?.stock_info?.data
    if (Array.isArray(hist) && hist.length) {
      const last = hist[hist.length - 1]
      if (last && last.close != null && !Number.isNaN(Number(last.close))) {
        return Number(last.close)
      }
    }
    return null
  }, [predictionData])

  // predicted top-level price (from backend)
  const predictedPrice = useMemo(() => {
    if (!predictionData) return null
    const pred = predictionData?.prediction?.predicted_price ?? null
    return pred != null ? Number(pred) : null
  }, [predictionData])

  // percent change utility using canonical currentPrice
  const computeChangePct = (current, predicted) => {
    if (current == null || predicted == null || Number(current) === 0) return null
    return ((Number(predicted) - Number(current)) / Number(current)) * 100
  }

  const formatCurrency = (v) => {
    if (v == null || Number.isNaN(Number(v))) return 'N/A'
    return `${getCurrencySymbol(predictionData?.ticker ?? '')}${Number(v).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`
  }

  // memoize arrays to avoid unnecessary child renders
  const memoStockData = useMemo(() => predictionData?.stock_info?.data ?? [], [predictionData?.stock_info?.data])
  const memoPredictions = useMemo(() => ({
    general: predictionData?.prediction ?? null,
    hourly: timePredictions.hourly ?? null,
    daily: timePredictions.daily ?? null
  }), [predictionData?.prediction, timePredictions.hourly, timePredictions.daily])

  // small debug logs while developing (remove in prod)
  useEffect(() => {
    // console.debug('canonical currentPrice', currentPrice)
    // console.debug('backend predictedPrice', predictedPrice)
    // console.debug('timePredictions', timePredictions)
  }, [currentPrice, predictedPrice, timePredictions])

  return (
    <div className="stock-prediction">
      <div className="input-section">
        <div className="input-group">
          <input
            type="text"
            value={ticker}
            onChange={(e) => setTicker(e.target.value.toUpperCase())}
            placeholder="Enter ticker: AAPL (US) or RELIANCE.NS (India)"
            className="ticker-input"
            onKeyPress={(e) => e.key === 'Enter' && handlePredict()}
          />
          <button onClick={handlePredict} disabled={loading} className="btn-primary">
            {loading ? 'Loading...' : 'Predict'}
          </button>
          <button onClick={handleAddStock} disabled={loading} className="btn-secondary">
            Add Stock
          </button>
          <div className={`connection-status ${isConnected ? 'connected' : 'disconnected'}`}>
            <span className="status-dot"></span>
            {isConnected ? 'Live Updates' : 'Offline'}
          </div>
        </div>

        <div className="market-examples">
          <div className="market-group">
            <span className="market-label">🇺🇸 US Stocks:</span>
            <div className="quick-select-buttons">
              {popularStocks.us.map(stock => (
                <button
                  key={stock}
                  onClick={() => handleQuickSelect(stock)}
                  className="quick-select-btn"
                  disabled={loading}
                >
                  {stock}
                </button>
              ))}
            </div>
          </div>
          <div className="market-group">
            <span className="market-label">🇮🇳 Indian Stocks (NSE):</span>
            <div className="quick-select-buttons">
              {popularStocks.indian.map(stock => (
                <button
                  key={stock}
                  onClick={() => handleQuickSelect(stock)}
                  className="quick-select-btn"
                  disabled={loading}
                >
                  {stock.replace('.NS', '')}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="format-hint">
          <span className="hint-icon">💡</span>
          <span>For Indian stocks, add <strong>.NS</strong> for NSE (e.g., RELIANCE.NS) or <strong>.BO</strong> for BSE (e.g., 500325.BO)</span>
        </div>

        {error && <div className="error-message">{error}</div>}
      </div>

      {predictionData && (
        <div className="results-section">
          <div className="stock-header">
            <h2>{predictionData.ticker}</h2>
            <p className="stock-name">{predictionData.stock_info?.name}</p>
            <div className="price-info">
              <div className="current-price">
                <span className="label">Current Price:</span>
                <span className="value">{formatCurrency(currentPrice)}</span>
              </div>
              <div className="predicted-price">
                <span className="label">Predicted Price:</span>
                <span className="value">{predictedPrice != null ? formatCurrency(predictedPrice) : 'N/A'}</span>
              </div>
              <div className="confidence">
                <span className="label">Confidence:</span>
                <span className="value">
                  {predictionData.prediction?.confidence != null
                    ? `${Math.round(predictionData.prediction.confidence * 100)}%`
                    : 'N/A'}
                </span>
              </div>
            </div>
          </div>

          <div className="time-predictions-section">
            {/* Pass canonical currentPrice & predictedPrice so the 5-min/1-hour/next-day cards use same values */}
            <TimePredictions 
              ticker={predictionData.ticker} 
              onPrediction={handleTimePrediction}
              currentPrice={currentPrice}
              predictedPrice={predictedPrice}
              priceUpdates={priceUpdates}
            />

          </div>

          {predictionData.recommendation && (
            <div className="recommendation-section">
              <RecommendationDisplay recommendation={predictionData.recommendation} />
            </div>
          )}

          <div className="grid-container">
            <div className="grid-item full-width">
              <CandlestickChart data={memoStockData} />
            </div>

            <div className="grid-item full-width">
              <VolumeChart data={memoStockData} />
            </div>

            <div className="grid-item full-width">
              <PredictionChart
                historicalData={memoStockData}
                predictions={memoPredictions}
              />
            </div>

            <div className="grid-item chart-section">
              <h3>Price History & Prediction</h3>
              <PriceChart
                data={memoStockData}
                // ensure PriceChart receives canonical current price (if it needs it)
                prediction={{ ...predictionData.prediction, current_price: currentPrice }}
              />
            </div>

            <div className="grid-item sentiment-section">
              <h3>Sentiment Analysis</h3>
              <SentimentDisplay sentiment={predictionData.sentiment} />
            </div>

            <div className="grid-item cluster-section">
              <h3>Cluster Information</h3>
              <ClusterInfo cluster={predictionData.cluster} />
            </div>

            <div className="grid-item correlation-section">
              <h3>Stock Correlations</h3>
              <CorrelationGraph
                ticker={predictionData.ticker}
                correlationMatrix={predictionData.correlation_matrix}
              />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default StockPrediction
