import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts'

function VolumeChart({ data }) {
  if (!data || data.length === 0) {
    return <div className="chart-placeholder">No volume data available</div>
  }

  const chartData = data.slice(-30).map(item => ({
    date: item.date.substring(5),
    volume: item.volume / 1000000,
    color: item.close >= item.open ? '#10b981' : '#ef4444'
  }))

  return (
    <div className="chart-container">
      <h3>Trading Volume (Millions)</h3>
      <ResponsiveContainer width="100%" height={200}>
        <BarChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="#374151" />
          <XAxis dataKey="date" stroke="#9ca3af" />
          <YAxis stroke="#9ca3af" />
          <Tooltip 
            contentStyle={{ backgroundColor: '#1f2937', border: '1px solid #374151' }}
            labelStyle={{ color: '#f3f4f6' }}
            formatter={(value) => `${value.toFixed(2)}M`}
          />
          <Bar 
            dataKey="volume" 
            fill="#6366f1"
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}

export default VolumeChart
