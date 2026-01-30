import React, { useMemo, useRef } from 'react';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  ComposedChart
} from 'recharts';

/**
 * PredictionChart
 * - Stabilizes chart data so tiny/noisy parent updates do not re-render the chart.
 * - Locks Y axis using a small padding to avoid autoscale jumps.
 * - Disables animation to avoid visual twitch.
 *
 * Props:
 * - historicalData: array of { date: string, close: number, ... }
 * - predictions: { hourly?, daily?, general? } (predicted_price, confidence_interval)
 */

function PredictionChart({ historicalData = [], predictions = null }) {
  // Early return for no data
  if (!historicalData || historicalData.length === 0) {
    return <div className="chart-placeholder">No historical data for predictions</div>;
  }

  // Build a new candidate chartData from props (pure transformation)
  const candidateChartData = useMemo(() => {
    // Keep only last 20 historical points (matching your original)
    const slice = historicalData.slice(-20);
    const pts = slice.map(item => ({
      date: typeof item.date === 'string' ? item.date.substring(5) : String(item.date),
      actual: item.close != null ? Number(item.close) : null,
      type: 'historical'
    }));

    if (predictions) {
      if (predictions.hourly) {
        pts.push({
          date: '1hr',
          predicted: Number(predictions.hourly.predicted_price),
          lower: predictions.hourly.confidence_interval?.lower != null ? Number(predictions.hourly.confidence_interval.lower) : null,
          upper: predictions.hourly.confidence_interval?.upper != null ? Number(predictions.hourly.confidence_interval.upper) : null,
          type: 'prediction'
        });
      }
      if (predictions.daily) {
        pts.push({
          date: 'Next',
          predicted: Number(predictions.daily.predicted_price),
          lower: predictions.daily.confidence_interval?.lower != null ? Number(predictions.daily.confidence_interval.lower) : null,
          upper: predictions.daily.confidence_interval?.upper != null ? Number(predictions.daily.confidence_interval.upper) : null,
          type: 'prediction'
        });
      }
      if (predictions.general) {
        pts.push({
          date: 'GNN',
          predicted: Number(predictions.general.predicted_price),
          type: 'prediction'
        });
      }
    }

    return pts;
  }, [historicalData, predictions]);

  // Use a ref to store the last *rendered* chartData and a numeric summary to decide whether to update
  const lastRef = useRef({
    chartData: candidateChartData,
    summary: null
  });

  // Helper: compute a tiny numeric summary that detects substantive change
  const computeSummary = (arr) => {
    // summary: min/max of actual and predicted, last actual value
    const actuals = arr.map(d => (d.actual != null ? d.actual : NaN)).filter(Number.isFinite);
    const preds = arr.map(d => (d.predicted != null ? d.predicted : NaN)).filter(Number.isFinite);

    const minActual = actuals.length ? Math.min(...actuals) : NaN;
    const maxActual = actuals.length ? Math.max(...actuals) : NaN;
    const minPred = preds.length ? Math.min(...preds) : NaN;
    const maxPred = preds.length ? Math.max(...preds) : NaN;
    const lastActual = actuals.length ? actuals[actuals.length - 1] : NaN;

    return { minActual, maxActual, minPred, maxPred, lastActual, len: arr.length };
  };

  // Compute candidate summary
  const candSummary = useMemo(() => computeSummary(candidateChartData), [candidateChartData]);

  // Decide update: if last summary missing -> update. Else compare numeric diffs with tolerance.
  const shouldUpdate = (() => {
    const prev = lastRef.current.summary;
    if (!prev) return true; // first time
    // Tolerance: allow tiny numeric noise (e.g., < 0.01 absolute) and small length change
    const EPS = 0.01; // 1 cent tolerance; adjust if your prices are large
    // If length changed significantly, update
    if (Math.abs(candSummary.len - prev.len) > 0) return true;
    // If any of the key stats changed by more than EPS, update
    const keys = ['minActual', 'maxActual', 'minPred', 'maxPred', 'lastActual'];
    for (let k of keys) {
      const a = Number(candSummary[k]);
      const b = Number(prev[k]);
      if (Number.isNaN(a) && Number.isNaN(b)) continue;
      if (Number.isNaN(a) !== Number.isNaN(b)) return true;
      if (Math.abs(a - b) > EPS) return true;
    }
    // Otherwise treat as same (no update)
    return false;
  })();

  // Stabilize chartData: only replace lastRef.chartData when shouldUpdate true
  if (shouldUpdate) {
    lastRef.current.chartData = candidateChartData;
    lastRef.current.summary = candSummary;
  }
  const chartData = lastRef.current.chartData;

  // Compute Y axis bounds from stable chartData (min/max across actual & predicted)
  const { minY, maxY } = useMemo(() => {
    const values = chartData.flatMap(d => {
      const arr = [];
      if (d.actual != null && Number.isFinite(d.actual)) arr.push(d.actual);
      if (d.predicted != null && Number.isFinite(d.predicted)) arr.push(d.predicted);
      if (d.lower != null && Number.isFinite(d.lower)) arr.push(d.lower);
      if (d.upper != null && Number.isFinite(d.upper)) arr.push(d.upper);
      return arr;
    });
    if (!values.length) return { minY: 'auto', maxY: 'auto' };
    const min = Math.min(...values);
    const max = Math.max(...values);
    const range = Math.max(max - min, 1e-6);
    const padding = Math.max(range * 0.04, 1); // 4% or at least 1 unit
    // Round nicely
    const floorMin = Math.floor((min - padding) * 100) / 100;
    const ceilMax = Math.ceil((max + padding) * 100) / 100;
    return { minY: floorMin, maxY: ceilMax };
  }, [chartData]);

  // Tooltip formatter
  const tooltipFormatter = (value) => {
    if (value == null || Number.isNaN(Number(value))) return 'N/A';
    return `$${Number(value).toFixed(2)}`;
  };

  return (
    <div className="chart-container">
      <h3>Price Predictions with Confidence Intervals</h3>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis dataKey="date" stroke="#9ca3af" />
          <YAxis stroke="#9ca3af" domain={[minY, maxY]} />
          <Tooltip
            contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
            labelStyle={{ color: '#f3f4f6' }}
            formatter={(value) => tooltipFormatter(value)}
          />
          <Legend />

          <Line
            type="monotone"
            dataKey="actual"
            stroke="#8b5cf6"
            strokeWidth={2}
            dot={false}
            name="Historical Price"
            isAnimationActive={false}
          />

          <Line
            type="monotone"
            dataKey="predicted"
            stroke="#10b981"
            strokeWidth={3}
            dot={{ fill: '#10b981', r: 6 }}
            name="Predicted Price"
            isAnimationActive={false}
          />

          {/* Confidence band: render as area between upper and lower.
              Recharts Area draws filled areas individually; for aesthetic,
              we draw upper and lower with same fill & opacity. */}
          <Area
            type="monotone"
            dataKey="upper"
            stroke="none"
            fill="#6366f1"
            fillOpacity={0.12}
            isAnimationActive={false}
            name="Confidence Upper"
          />

          <Area
            type="monotone"
            dataKey="lower"
            stroke="none"
            fill="#6366f1"
            fillOpacity={0.12}
            isAnimationActive={false}
            name="Confidence Lower"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

// Memoize the component so React won't re-render it unless parent props cause actual updates
export default React.memo(PredictionChart);
