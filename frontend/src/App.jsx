import { useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import StockPrediction from './components/StockPrediction'
import './App.css'

const queryClient = new QueryClient()

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div className="app">
        <header className="app-header">
          <h1>Stock Prediction Platform</h1>
          <p>AI-Powered Stock Analysis with GNN, Sentiment & Clustering</p>
        </header>
        <StockPrediction />
      </div>
    </QueryClientProvider>
  )
}

export default App
