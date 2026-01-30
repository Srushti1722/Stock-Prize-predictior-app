import React, { useMemo } from 'react'
import { 
  LineChart, 
  Line, 
  XAxis, 
  YAxis, 
  CartesianGrid, 
  Tooltip, 
  Legend, 
  ResponsiveContainer 
} from 'recharts'

function PriceChart({ data, prediction }) {

  // 🔒 Prevent re-renders: memoize chart data
  const chartData = useMemo(() => {
    const baseData = data.map((item) => ({
      date: item.date,
      price: Number(item.close),
      isPrediction: false
    }))

    if (prediction && prediction.predicted_price) {
      baseData.push({
        date: 'Prediction',
        price: Number(prediction.predicted_price),
        isPrediction: true,
        actualPrice: prediction.current_price
      })
    }

    return baseData
  }, [data, prediction])

  // 🔒 Lock Y-axis (fix fluctuation)
  const { minY, maxY } = useMemo(() => {
    if (!chartData.length) return { minY: 'auto', maxY: 'auto' }

    const prices = chartData.map(d => d.price)
    const min = Math.min(...prices)
    const max = Math.max(...prices)
    const pad = Math.max((max - min) * 0.05, 1) // 5% padding or at least 1 point

    return {
      minY: min - pad,
      maxY: max + pad
    }
  }, [chartData])

  return (
    <ResponsiveContainer width="100%" height={300}>
      <LineChart data={chartData}>
        <CartesianGrid strokeDasharray="3 3" />

        <XAxis
          dataKey="date"
          tick={{ fontSize: 12 }}
          interval={Math.floor(chartData.length / 6)}
        />

        {/* 🔒 FIX: Lock Y-axis domain to stabilize chart */}
        <YAxis 
          tick={{ fontSize: 12 }} 
          domain={[minY, maxY]} 
        />

        <Tooltip />
        <Legend />

        <Line 
          type="monotone"
          dataKey="price"
          stroke="#8884d8"
          strokeWidth={2}
          dot={{ r: 2 }}
          name="Price"
          isAnimationActive={false}  // ❌ animation creates jitter → disabled
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

export default React.memo(PriceChart)  // 🔒 FIX: Prevent unnecessary re-renders
