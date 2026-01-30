import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.neighbors import NearestNeighbors
from sklearn.cluster import KMeans
from database import save_cluster, get_cluster_info
from stock_service import get_multiple_stocks_data

def calculate_correlation_matrix(stock_prices_dict):
    tickers = list(stock_prices_dict.keys())
    if len(tickers) < 2:
        return {}
    
    prices_matrix = []
    for ticker in tickers:
        prices_matrix.append(stock_prices_dict[ticker])
    
    prices_array = np.array(prices_matrix)
    
    min_length = min([len(p) for p in prices_matrix])
    prices_array = np.array([p[:min_length] for p in prices_matrix])
    
    corr_matrix = np.corrcoef(prices_array)
    
    correlation_data = {}
    for i, ticker1 in enumerate(tickers):
        correlation_data[ticker1] = {}
        for j, ticker2 in enumerate(tickers):
            if i != j:
                correlation_data[ticker1][ticker2] = float(corr_matrix[i][j])
    
    return correlation_data

def perform_clustering(stocks_data, n_clusters=3):
    if len(stocks_data) < 2:
        return {}
    
    tickers = [s['ticker'] for s in stocks_data]
    prices_matrix = []
    
    min_length = min([len(s['prices']) for s in stocks_data])
    
    for stock in stocks_data:
        prices = stock['prices'][:min_length]
        returns = np.diff(prices) / prices[:-1]
        
        features = [
            np.mean(returns),
            np.std(returns),
            np.max(returns),
            np.min(returns),
            prices[-1] / prices[0] - 1
        ]
        prices_matrix.append(features)
    
    X = np.array(prices_matrix)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    n_clusters = min(n_clusters, len(stocks_data))
    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    clusters = kmeans.fit_predict(X_scaled)
    
    cluster_assignments = {}
    for ticker, cluster_id in zip(tickers, clusters):
        cluster_assignments[ticker] = int(cluster_id)
    
    return cluster_assignments

def find_similar_stocks(target_ticker, stocks_data, k=3):
    if len(stocks_data) < 2:
        return []
    
    tickers = [s['ticker'] for s in stocks_data]
    if target_ticker not in tickers:
        return []
    
    target_idx = tickers.index(target_ticker)
    
    min_length = min([len(s['prices']) for s in stocks_data])
    
    features_matrix = []
    for stock in stocks_data:
        prices = stock['prices'][:min_length]
        returns = np.diff(prices) / prices[:-1]
        
        features = [
            np.mean(returns),
            np.std(returns),
            np.max(returns),
            np.min(returns),
            prices[-1] / prices[0] - 1
        ]
        features_matrix.append(features)
    
    X = np.array(features_matrix)
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)
    
    k = min(k + 1, len(stocks_data))
    knn = NearestNeighbors(n_neighbors=k)
    knn.fit(X_scaled)
    
    distances, indices = knn.kneighbors([X_scaled[target_idx]])
    
    similar = []
    for i, dist in zip(indices[0], distances[0]):
        if i != target_idx:
            similar.append({
                'ticker': tickers[i],
                'similarity': float(1 / (1 + dist))
            })
    
    return similar

def analyze_stock_cluster(ticker, stock_id, all_tickers):
    try:
        stocks_data = get_multiple_stocks_data(all_tickers)
        
        if len(stocks_data) < 2:
            return {
                'cluster_id': 0,
                'similar_stocks': [],
                'correlation': {}
            }
        
        cluster_assignments = perform_clustering(stocks_data)
        cluster_id = cluster_assignments.get(ticker, 0)
        
        similar_stocks = find_similar_stocks(ticker, stocks_data, k=3)
        
        stock_prices = {s['ticker']: s['prices'] for s in stocks_data}
        correlation_matrix = calculate_correlation_matrix(stock_prices)
        
        save_cluster(stock_id, cluster_id, [s['ticker'] for s in similar_stocks])
        
        return {
            'cluster_id': cluster_id,
            'similar_stocks': similar_stocks,
            'correlation': correlation_matrix.get(ticker, {})
        }
        
    except Exception as e:
        return {
            'cluster_id': 0,
            'similar_stocks': [],
            'correlation': {},
            'error': f'Error in clustering: {str(e)}'
        }

def get_cluster_data(stock_id, ticker):
    try:
        cluster = get_cluster_info(stock_id)
        if cluster:
            return {
                'cluster_id': cluster['cluster_id'],
                'similar_stocks': cluster['similar_stocks'],
                'updated_at': cluster['updated_at']
            }
        return None
    except Exception as e:
        return {'error': f'Error retrieving cluster: {str(e)}'}
