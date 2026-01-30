import torch
import torch.nn as nn
import numpy as np
from database import save_prediction, get_latest_prediction

class SimpleGNN(nn.Module):
    def __init__(self, input_dim, hidden_dim, output_dim):
        super(SimpleGNN, self).__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim)
        self.fc3 = nn.Linear(hidden_dim, output_dim)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.2)
    
    def forward(self, x, adj_matrix=None):
        x = self.relu(self.fc1(x))
        x = self.dropout(x)
        
        if adj_matrix is not None:
            x = torch.matmul(adj_matrix, x)
        
        x = self.relu(self.fc2(x))
        x = self.dropout(x)
        x = self.fc3(x)
        return x

def create_adjacency_matrix(correlation_dict, threshold=0.5):
    if not correlation_dict:
        return None
    
    tickers = list(correlation_dict.keys())
    n = len(tickers)
    adj_matrix = np.eye(n)
    
    ticker_to_idx = {ticker: i for i, ticker in enumerate(tickers)}
    
    for i, ticker1 in enumerate(tickers):
        for ticker2, corr in correlation_dict[ticker1].items():
            if ticker2 in ticker_to_idx and abs(corr) > threshold:
                j = ticker_to_idx[ticker2]
                adj_matrix[i][j] = abs(corr)
    
    row_sums = adj_matrix.sum(axis=1, keepdims=True)
    adj_matrix = adj_matrix / (row_sums + 1e-8)
    
    return torch.FloatTensor(adj_matrix)

def prepare_features(stock_data, window_size=10):
    if len(stock_data) < window_size:
        window_size = len(stock_data)
    
    recent_data = stock_data[-window_size:]
    prices = [d['close'] for d in recent_data]
    volumes = [d['volume'] for d in recent_data]
    
    price_changes = np.diff(prices) / np.array(prices[:-1])
    
    features = [
        prices[-1],
        np.mean(prices),
        np.std(prices),
        np.max(prices),
        np.min(prices),
        np.mean(price_changes) if len(price_changes) > 0 else 0,
        np.std(price_changes) if len(price_changes) > 0 else 0,
        np.mean(volumes),
        volumes[-1] / (np.mean(volumes) + 1e-8),
        (prices[-1] - prices[0]) / (prices[0] + 1e-8)
    ]
    
    return np.array(features)

def predict_stock_price(ticker, stock_id, stock_data, correlation_data=None):
    try:
        if len(stock_data) < 5:
            return {
                'predicted_price': stock_data[-1]['close'],
                'confidence': 0.5,
                'error': 'Insufficient data for prediction'
            }
        
        features = prepare_features(stock_data, window_size=20)
        
        input_dim = len(features)
        hidden_dim = 32
        output_dim = 1
        
        model = SimpleGNN(input_dim, hidden_dim, output_dim)
        model.eval()
        
        X = torch.FloatTensor(features).unsqueeze(0)
        
        adj_matrix = None
        if correlation_data and len(correlation_data) > 0:
            adj_matrix = create_adjacency_matrix({ticker: correlation_data})
            if adj_matrix is not None and adj_matrix.shape[0] > 0:
                adj_matrix = adj_matrix[0:1, 0:1]
        
        with torch.no_grad():
            if adj_matrix is not None and adj_matrix.shape[0] == X.shape[0]:
                prediction = model(X, adj_matrix)
            else:
                prediction = model(X)
        
        current_price = stock_data[-1]['close']
        price_std = np.std([d['close'] for d in stock_data[-20:]])
        
        price_change_pct = float(prediction[0][0].item()) * 0.1
        predicted_price = current_price * (1 + price_change_pct)
        
        predicted_price = max(current_price * 0.8, min(predicted_price, current_price * 1.2))
        
        confidence = max(0.6, min(0.95, 1.0 - abs(price_change_pct)))
        
        prediction_date = stock_data[-1]['date']
        save_prediction(stock_id, prediction_date, predicted_price, confidence)
        
        return {
            'predicted_price': round(predicted_price, 2),
            'current_price': round(current_price, 2),
            'confidence': round(confidence, 2),
            'prediction_change_pct': round(price_change_pct * 100, 2)
        }
        
    except Exception as e:
        current_price = stock_data[-1]['close'] if stock_data else 0
        return {
            'predicted_price': current_price,
            'confidence': 0.5,
            'error': f'Error in prediction: {str(e)}'
        }

def get_prediction_info(stock_id):
    try:
        prediction = get_latest_prediction(stock_id)
        if prediction:
            return {
                'predicted_price': prediction['predicted_price'],
                'confidence': prediction['confidence'],
                'prediction_date': prediction['prediction_date'],
                'created_at': prediction['created_at']
            }
        return None
    except Exception as e:
        return {'error': f'Error retrieving prediction: {str(e)}'}
