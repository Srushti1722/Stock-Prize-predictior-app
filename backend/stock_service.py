# backend/stock_service.py
import yfinance as yf
import pandas as pd
from typing import List, Dict, Any, Optional

# DB helpers (must exist in your project)
from database import add_stock, get_stock_by_ticker, save_stock_data, get_stock_data

# -------------------------
# Utility: canonical current price retriever
# -------------------------
def get_canonical_current_price(source: Any) -> Optional[float]:
    """
    Return canonical current price from a variety of possible sources:
      - dict with 'current_price' key
      - dict with 'data' list where each element has 'close'
      - pandas DataFrame-like object with 'close' column
      - list of dicts where last element has 'close'
    Returns float or None if not found.
    """
    try:
        if source is None:
            return None

        # If passed a dict with explicit key
        if isinstance(source, dict):
            cp = source.get('current_price')
            if cp is not None:
                try:
                    return float(cp)
                except Exception:
                    return None
            data = source.get('data')
            if isinstance(data, list) and data:
                last = data[-1]
                if isinstance(last, dict) and 'close' in last:
                    try:
                        return float(last.get('close'))
                    except Exception:
                        return None
            return None

        # If pandas DataFrame-like
        if hasattr(source, 'empty') and hasattr(source, 'iloc') and hasattr(source, 'columns'):
            try:
                if not source.empty and 'close' in source.columns:
                    return float(source['close'].iloc[-1])
            except Exception:
                return None
            return None

        # If list of dicts
        if isinstance(source, list) and source:
            last = source[-1]
            if isinstance(last, dict) and 'close' in last:
                try:
                    return float(last.get('close'))
                except Exception:
                    return None
            return None

    except Exception:
        return None

    return None


# -------------------------
# fetch_stock_data
# -------------------------
def fetch_stock_data(ticker: str, period: str = '1y') -> Dict[str, Any]:
    """
    Fetch historical data from yfinance for `ticker`, save to DB and return a dict:
    {
      'ticker': 'AAPL',
      'name': 'Apple Inc.',
      'stock_id': 12,
      'data': [ ... last N records ... ],
      'current_price': float,
      'info': { marketCap, sector, industry }
    }
    On error returns {'error': '...'}
    """
    try:
        ticker = ticker.upper().strip()
        stock = yf.Ticker(ticker)
        info = {}
        try:
            info = stock.info or {}
        except Exception:
            info = {}

        # Try to fetch history
        hist = pd.DataFrame()
        try:
            hist = stock.history(period=period)
        except Exception:
            hist = pd.DataFrame()

        if hist.empty:
            return {'error': f'No data available for ticker: {ticker}'}

        stock_name = info.get('longName') or info.get('shortName') or ticker

        # Add to DB (returns id)
        stock_id = None
        try:
            stock_id = add_stock(ticker, stock_name)
        except Exception:
            # fallback: try to lookup existing
            try:
                existing = get_stock_by_ticker(ticker)
                stock_id = existing['id'] if existing else None
            except Exception:
                stock_id = None

        if stock_id is None:
            return {'error': 'Failed to add stock to database'}

        # Convert history to list of dicts (ascending dates)
        data_list: List[Dict[str, Any]] = []
        for idx, row in hist.iterrows():
            try:
                data_list.append({
                    'date': idx.strftime('%Y-%m-%d'),
                    'open': float(row.get('Open', 0.0)),
                    'high': float(row.get('High', 0.0)),
                    'low': float(row.get('Low', 0.0)),
                    'close': float(row.get('Close', 0.0)),
                    'volume': int(row.get('Volume', 0))
                })
            except Exception:
                continue

        # Save to DB (best-effort)
        try:
            save_stock_data(stock_id, data_list)
        except Exception:
            # ignore DB save errors - still return fetched data
            pass

        current_price = None
        try:
            current_price = float(hist['Close'].iloc[-1])
        except Exception:
            current_price = None

        result = {
            'ticker': ticker,
            'name': stock_name,
            'stock_id': stock_id,
            'data': data_list[-60:],  # return last 60 records
            'current_price': current_price,
            'info': {
                'marketCap': info.get('marketCap'),
                'sector': info.get('sector'),
                'industry': info.get('industry')
            }
        }
        return result

    except Exception as e:
        return {'error': f'Error fetching stock data: {str(e)}'}


# -------------------------
# get_stock_info
# -------------------------
def get_stock_info(ticker: str, limit: int = 60) -> Dict[str, Any]:
    """
    Read stock_info from DB using get_stock_by_ticker and get_stock_data.
    Returns:
      {
        'ticker': 'SBIN.NS',
        'name': 'State Bank of India',
        'stock_id': 3,
        'data': [ {date, open, high, low, close, volume}, ... ],
        'current_price': float or None
      }
    On error returns {'error': '...'}
    """
    try:
        t = ticker.upper().strip()
        stock_record = get_stock_by_ticker(t)
        if not stock_record:
            return {'error': f'Stock {t} not found in database'}

        stock_id = stock_record['id']
        rows = get_stock_data(stock_id, limit=limit)

        # rows expected to be list-like of dicts with keys date, open, high, low, close, volume
        data_list: List[Dict[str, Any]] = []
        try:
            # attempt to reverse if rows are returned newest-first
            for row in reversed(rows):
                data_list.append({
                    'date': row['date'],
                    'open': float(row['open']),
                    'high': float(row['high']),
                    'low': float(row['low']),
                    'close': float(row['close']),
                    'volume': int(row['volume'])
                })
        except Exception:
            # best-effort fallback to forward iteration
            data_list = []
            for row in rows:
                try:
                    data_list.append({
                        'date': row['date'],
                        'open': float(row['open']),
                        'high': float(row['high']),
                        'low': float(row['low']),
                        'close': float(row['close']),
                        'volume': int(row['volume'])
                    })
                except Exception:
                    continue

        current_price = None
        if data_list:
            try:
                current_price = float(data_list[-1]['close'])
            except Exception:
                current_price = None

        return {
            'ticker': stock_record['ticker'],
            'name': stock_record['name'],
            'stock_id': stock_id,
            'data': data_list,
            'current_price': current_price
        }

    except Exception as e:
        return {'error': f'Error retrieving stock info: {str(e)}'}


# -------------------------
# get_multiple_stocks_data
# -------------------------
def get_multiple_stocks_data(tickers: List[str], limit: int = 30) -> List[Dict[str, Any]]:
    """
    For a list of tickers, returns a list:
      [ { 'ticker': 'AAPL', 'stock_id': 12, 'prices': [close1, close2, ...] }, ... ]
    Only returns entries for tickers found in DB with available data.
    """
    results: List[Dict[str, Any]] = []
    for t in tickers:
        try:
            ticker = t.upper().strip()
            stock_record = get_stock_by_ticker(ticker)
            if not stock_record:
                continue
            rows = get_stock_data(stock_record['id'], limit=limit)
            if not rows:
                continue
            # reversed(rows) to get chronological closes if DB returns newest-first
            closes = []
            try:
                closes = [float(r['close']) for r in reversed(rows)]
            except Exception:
                # fallback: try forward order
                try:
                    closes = [float(r['close']) for r in rows]
                except Exception:
                    closes = []
            if closes:
                results.append({
                    'ticker': ticker,
                    'stock_id': stock_record['id'],
                    'prices': closes
                })
        except Exception:
            continue
    return results


# -------------------------
# Optional helper: lightweight intraday fetch from yfinance (fallback)
# -------------------------
def fetch_intraday_yf(ticker: str, interval: str = '5m', period: str = '7d') -> Dict[str, Any]:
    """
    Lightweight function to fetch intraday data from yfinance.
    Returns {'data': [ {date, open, high, low, close, volume}, ... ], 'current_price': float}
    or {'error': '...'}
    """
    try:
        t = ticker.upper().strip()
        tk = yf.Ticker(t)
        try:
            hist = tk.history(period=period, interval=interval)
        except Exception:
            hist = pd.DataFrame()
        if hist.empty:
            return {'error': 'No intraday data available'}
        data_list = []
        for idx, row in hist.iterrows():
            try:
                data_list.append({
                    'date': idx.strftime('%Y-%m-%d %H:%M:%S'),
                    'open': float(row.get('Open', 0.0)),
                    'high': float(row.get('High', 0.0)),
                    'low': float(row.get('Low', 0.0)),
                    'close': float(row.get('Close', 0.0)),
                    'volume': int(row.get('Volume', 0))
                })
            except Exception:
                continue
        current_price = None
        try:
            current_price = float(data_list[-1]['close'])
        except Exception:
            current_price = None
        return {'data': data_list, 'current_price': current_price}
    except Exception as e:
        return {'error': str(e)}
