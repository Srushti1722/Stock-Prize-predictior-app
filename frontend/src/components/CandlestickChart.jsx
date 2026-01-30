import { ComposedChart, Bar, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts'

function CandlestickChart({ data }) {
  if (!data || data.length === 0) {
    return <div className="chart-placeholder">No data available for candlestick chart</div>
  }

  const chartData = data.slice(-30).map(item => ({
    date: item.date.substring(5),
    open: item.open,
    high: item.high,
    low: item.low,
    close: item.close,
    volume: item.volume,
    color: item.close >= item.open ? '#10b981' : '#ef4444'
  }))

  return (
    <div className="chart-container">
      <h3>Price Chart (OHLC)</h3>
      <ResponsiveContainer width="100%" height={300}>
        <ComposedChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis dataKey="date" stroke="#9ca3af" />
          <YAxis stroke="#9ca3af" domain={['auto', 'auto']} />
          <Tooltip 
            contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
            labelStyle={{ color: '#f3f4f6' }}
          />
          <Legend />
          <Line 
            type="monotone" 
            dataKey="high" 
            stroke="#3b82f6" 
            strokeWidth={2}
            dot={false}
            name="High"
          />
          <Line 
            type="monotone" 
            dataKey="low" 
            stroke="#f59e0b" 
            strokeWidth={2}
            dot={false}
            name="Low"
          />
          <Line 
            type="monotone" 
            dataKey="close" 
            stroke="#8b5cf6" 
            strokeWidth={3}
            dot={false}
            name="Close"
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}

export default CandlestickChart
