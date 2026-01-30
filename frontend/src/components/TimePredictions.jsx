import { useState, useEffect, useRef } from 'react'

/**
 * TimePredictions.jsx
 *
 * Props:
 *  - ticker (string)
 *  - onPrediction(type, prediction) optional callback
 *  - currentPrice (number|null) canonical current price from parent
 *  - predictedPrice (number|null) canonical top-level predicted price from parent (may be null)
 *  - priceUpdates (object) optional map of live prices from websocket: { [TICKER]: { price, change, change_percent, ... } }
 *
 * Behavior:
 *  - Auto-fetch all 3 predictions when `ticker` changes
 *  - Buttons still available to manually refresh each prediction
 *  - Use live websocket price if available for the `current_price` shown
 *  - Keep parent callback `onPrediction` informed
 */

function TimePredictions({
  ticker,
  onPrediction,
  currentPrice = null,
  predictedPrice = null,
  priceUpdates = {}
}) {
  const [loading, setLoading] = useState({ fiveMin: false, hourly: false, daily: false })
  const [predictions, setPredictions] = useState({ fiveMin: null, hourly: null, daily: null })
  const [errors, setErrors] = useState({ fiveMin: null, hourly: null, daily: null })

  const API_URL = `${window.location.protocol}//${window.location.hostname}:3000`

  // requestId increments to ignore stale responses when ticker changes quickly
  const requestIdRef = useRef(0)

  const getCurrencySymbol = (t) => {
    if (t && (t.endsWith('.NS') || t.endsWith('.BO'))) return '₹'
    return '$'
  }

  const safeComputePercent = (curr, pred) => {
    if (curr == null || pred == null || Number(curr) === 0) return null
    return ((Number(pred) - Number(curr)) / Number(curr)) * 100
  }

  const getLivePriceForTicker = (t) => {
    if (!t || !priceUpdates) return null
    const entry = priceUpdates[t]
    if (!entry) return null
    const p = entry.price ?? entry.current_price ?? entry.last_price ?? null
    return p != null ? Number(p) : null
  }

  // fallbackCurrentPriority: 1) live websocket price (if provided) 2) parent currentPrice prop 3) data from endpoint
  const normalizePrediction = (raw, fallbackCurrent) => {
    if (!raw || typeof raw !== 'object') return null
    const copy = { ...raw }

    const live = getLivePriceForTicker(ticker)
    const canonicalCurrent = live != null
      ? Number(live)
      : (copy.current_price != null && !Number.isNaN(Number(copy.current_price))
        ? Number(copy.current_price)
        : (fallbackCurrent != null ? Number(fallbackCurrent) : null))

    copy.current_price = canonical_current_safe(canonicalCurrent)

    // predicted_price fallback
    if (copy.predicted_price != null) {
      copy.predicted_price = Number(copy.predicted_price)
    } else if (predictedPrice != null) {
      copy.predicted_price = Number(predictedPrice)
    } else {
      copy.predicted_price = null
    }

    // percent change: prefer backend, else compute
    if ((copy.percent_change == null || Number.isNaN(Number(copy.percent_change))) && copy.current_price != null && copy.predicted_price != null) {
      copy.percent_change = safeComputePercent(copy.current_price, copy.predicted_price)
    } else if (copy.percent_change != null) {
      copy.percent_change = Number(copy.percent_change)
    }

    if (copy.confidence != null) copy.confidence = Number(copy.confidence)

    return copy
  }

  // helper to ensure numeric or null
  function canonical_current_safe(v) {
    if (v == null || Number.isNaN(Number(v))) return null
    return Number(v)
  }

  // generic call + normalization
  const callAndSet = async (endpoint, stateKey, callbackKey) => {
    if (!ticker) return
    const localRequestId = ++requestIdRef.current
    setLoading(prev => ({ ...prev, [stateKey]: true }))
    setErrors(prev => ({ ...prev, [stateKey]: null }))

    try {
      const res = await fetch(`${API_URL}/${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker })
      })
      const data = await res.json()

      // stale check: if requestId changed (ticker changed or another call fired), ignore this response
      if (localRequestId !== requestIdRef.current) return

      if (data.error) {
        setErrors(prev => ({ ...prev, [stateKey]: data.error }))
        setPredictions(prev => ({ ...prev, [stateKey]: null }))
        return
      }

      // server might return { prediction: {...} } or the prediction directly
      const rawPrediction = data.prediction ?? data.pred ?? data
      const normalized = normalizePrediction(rawPrediction, currentPrice)

      setPredictions(prev => ({ ...prev, [stateKey]: normalized }))
      if (onPrediction) onPrediction(callbackKey, normalized)
    } catch (e) {
      // ignore stale exceptions if requestId differs
      if (localRequestId !== requestIdRef.current) return
      setErrors(prev => ({ ...prev, [stateKey]: 'Failed to fetch prediction' }))
      setPredictions(prev => ({ ...prev, [stateKey]: null }))
    } finally {
      if (localRequestId === requestIdRef.current) {
        setLoading(prev => ({ ...prev, [stateKey]: false }))
      }
    }
  }

  const fetch5MinPrediction = () => callAndSet('predict-5min', 'fiveMin', '5min')
  const fetchHourlyPrediction = () => callAndSet('predict-hourly', 'hourly', 'hourly')
  const fetchDailyPrediction = () => callAndSet('predict-daily', 'daily', 'daily')

  // auto-fetch when ticker changes (fetch all three but stagger quickly)
  useEffect(() => {
    // increment requestId so in-flight requests from previous ticker are ignored
    requestIdRef.current += 1
    const rid = requestIdRef.current

    if (!ticker) {
      // clear state if no ticker
      setPredictions({ fiveMin: null, hourly: null, daily: null })
      setErrors({ fiveMin: null, hourly: null, daily: null })
      setLoading({ fiveMin: false, hourly: false, daily: false })
      return
    }

    // small stagger to avoid all endpoints hitting at exactly same ms
    // Fire 5-min immediately, then hourly after 250ms, daily after 500ms
    fetch5MinPrediction()
    const h = setTimeout(() => { if (rid === requestIdRef.current) fetchHourlyPrediction() }, 250)
    const d = setTimeout(() => { if (rid === requestIdRef.current) fetchDailyPrediction() }, 500)

    return () => {
      clearTimeout(h)
      clearTimeout(d)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticker]) // intentionally only on ticker changes

  // when live websocket price updates arrive, update current_price field in UI for each existing prediction
  useEffect(() => {
    if (!ticker) return
    const live = getLivePriceForTicker(ticker)
    if (live == null) return

    setPredictions(prev => {
      const updated = { ...prev }
      Object.keys(prev).forEach(k => {
        if (prev[k]) {
          updated[k] = { ...prev[k], current_price: Number(live) }
          // recompute percent_change if predicted_price exists
          if (updated[k].predicted_price != null) {
            updated[k].percent_change = safeComputePercent(updated[k].current_price, updated[k].predicted_price)
          }
        }
      })
      return updated
    })
    // do not call onPrediction for micro price updates to avoid spamming parent; parent already receives final normalized predictions
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [priceUpdates?.[ticker]?.price, priceUpdates?.[ticker]?.current_price])

  const symbol = getCurrencySymbol(ticker)

  return (
    <div className="time-predictions">
      <h3>Time-Specific Predictions</h3>

      <div className="prediction-buttons">
        <button onClick={fetch5MinPrediction} disabled={loading.fiveMin || !ticker} className="predict-button">
          {loading.fiveMin ? 'Loading...' : '5-Min Prediction'}
        </button>

        <button onClick={fetchHourlyPrediction} disabled={loading.hourly || !ticker} className="predict-button">
          {loading.hourly ? 'Loading...' : '1-Hour Prediction'}
        </button>

        <button onClick={fetchDailyPrediction} disabled={loading.daily || !ticker} className="predict-button">
          {loading.daily ? 'Loading...' : 'Next-Day Prediction'}
        </button>
      </div>

      <div className="predictions-display">
        {/* 5-minute */}
        {errors.fiveMin && <div className="error-message">{errors.fiveMin}</div>}
        {predictions.fiveMin && (
          <div className="prediction-card">
            <h4>5-Minute Forecast</h4>
            <div className="prediction-details">
              <p><strong>Current:</strong> {symbol}{predictions.fiveMin.current_price != null ? predictions.fiveMin.current_price.toFixed(2) : 'N/A'}</p>
              <p><strong>Predicted:</strong> {symbol}{predictions.fiveMin.predicted_price != null ? predictions.fiveMin.predicted_price.toFixed(2) : 'N/A'}</p>
              <p className={(predictions.fiveMin.percent_change ?? 0) >= 0 ? 'positive' : 'negative'}>
                <strong>Change:</strong> {predictions.fiveMin.percent_change != null ? `${predictions.fiveMin.percent_change.toFixed(2)}%` : 'N/A'}
              </p>
              <p><strong>Confidence:</strong> {predictions.fiveMin.confidence != null ? `${Number(predictions.fiveMin.confidence).toFixed(1)}%` : 'N/A'}</p>
            </div>
          </div>
        )}

        {/* hourly */}
        {errors.hourly && <div className="error-message">{errors.hourly}</div>}
        {predictions.hourly && (
          <div className="prediction-card">
            <h4>1-Hour Forecast</h4>
            <div className="prediction-details">
              <p><strong>Current:</strong> {symbol}{predictions.hourly.current_price != null ? predictions.hourly.current_price.toFixed(2) : 'N/A'}</p>
              <p><strong>Predicted:</strong> {symbol}{predictions.hourly.predicted_price != null ? predictions.hourly.predicted_price.toFixed(2) : 'N/A'}</p>
              <p className={(predictions.hourly.percent_change ?? 0) >= 0 ? 'positive' : 'negative'}>
                <strong>Change:</strong> {predictions.hourly.percent_change != null ? `${predictions.hourly.percent_change.toFixed(2)}%` : 'N/A'}
              </p>
              <p><strong>Confidence:</strong> {predictions.hourly.confidence != null ? `${Number(predictions.hourly.confidence).toFixed(1)}%` : 'N/A'}</p>
            </div>
          </div>
        )}

        {/* daily */}
        {errors.daily && <div className="error-message">{errors.daily}</div>}
        {predictions.daily && (
          <div className="prediction-card">
            <h4>Next-Day Forecast</h4>
            <div className="prediction-details">
              <p><strong>Current:</strong> {symbol}{predictions.daily.current_price != null ? predictions.daily.current_price.toFixed(2) : 'N/A'}</p>
              <p><strong>Predicted:</strong> {symbol}{predictions.daily.predicted_price != null ? predictions.daily.predicted_price.toFixed(2) : 'N/A'}</p>
              <p className={(predictions.daily.percent_change ?? 0) >= 0 ? 'positive' : 'negative'}>
                <strong>Change:</strong> {predictions.daily.percent_change != null ? `${predictions.daily.percent_change.toFixed(2)}%` : 'N/A'}
              </p>
              <p><strong>Confidence:</strong> {predictions.daily.confidence != null ? `${Number(predictions.daily.confidence).toFixed(1)}%` : 'N/A'}</p>
              {predictions.daily.prediction_date && <p><strong>Date:</strong> {predictions.daily.prediction_date}</p>}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

export default TimePredictions
