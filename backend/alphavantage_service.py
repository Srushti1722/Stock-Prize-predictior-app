import requests
import os
from datetime import datetime

ALPHA_VANTAGE_API_KEY = os.environ.get('ALPHA_VANTAGE_API_KEY', '')
BASE_URL = 'https://www.alphavantage.co/query'

def fetch_intraday_data(ticker, interval='5min'):
    """
    Fetch intraday stock data for 1-hour predictions
    Interval options: 1min, 5min, 15min, 30min, 60min
    """
    try:
        if not ALPHA_VANTAGE_API_KEY:
            return {'error': 'Alpha Vantage API key not configured'}
        
        params = {
            'function': 'TIME_SERIES_INTRADAY',
            'symbol': ticker,
            'interval': interval,
            'apikey': ALPHA_VANTAGE_API_KEY,
            'outputsize': 'full'
        }
        
        response = requests.get(BASE_URL, params=params, timeout=10)
        data = response.json()
        
        if 'Error Message' in data:
            return {'error': f"Invalid ticker: {ticker}"}
        
        if 'Note' in data:
            return {'error': 'API rate limit reached. Please try again later.'}
        
        time_series_key = f'Time Series ({interval})'
        if time_series_key not in data:
            return {'error': 'No intraday data available'}
        
        time_series = data[time_series_key]
        
        intraday_data = []
        for timestamp, values in sorted(time_series.items()):
            intraday_data.append({
                'timestamp': timestamp,
                'open': float(values['1. open']),
                'high': float(values['2. high']),
                'low': float(values['3. low']),
                'close': float(values['4. close']),
                'volume': int(values['5. volume'])
            })
        
        return {
            'ticker': ticker.upper(),
            'interval': interval,
            'data': intraday_data[-100:],
            'current_price': intraday_data[-1]['close'] if intraday_data else None
        }
        
    except requests.exceptions.Timeout:
        return {'error': 'Request timeout. Please try again.'}
    except Exception as e:
        return {'error': f'Error fetching intraday data: {str(e)}'}

def fetch_daily_data(ticker):
    """
    Fetch daily stock data for next-day predictions
    """
    try:
        if not ALPHA_VANTAGE_API_KEY:
            return {'error': 'Alpha Vantage API key not configured'}
        
        params = {
            'function': 'TIME_SERIES_DAILY',
            'symbol': ticker,
            'apikey': ALPHA_VANTAGE_API_KEY,
            'outputsize': 'full'
        }
        
        response = requests.get(BASE_URL, params=params, timeout=10)
        data = response.json()
        
        if 'Error Message' in data:
            return {'error': f"Invalid ticker: {ticker}"}
        
        if 'Note' in data:
            return {'error': 'API rate limit reached. Please try again later.'}
        
        if 'Time Series (Daily)' not in data:
            return {'error': 'No daily data available'}
        
        time_series = data['Time Series (Daily)']
        
        daily_data = []
        for date, values in sorted(time_series.items()):
            daily_data.append({
                'date': date,
                'open': float(values['1. open']),
                'high': float(values['2. high']),
                'low': float(values['3. low']),
                'close': float(values['4. close']),
                'volume': int(values['5. volume'])
            })
        
        return {
            'ticker': ticker.upper(),
            'data': daily_data[-252:],
            'current_price': daily_data[-1]['close'] if daily_data else None
        }
        
    except requests.exceptions.Timeout:
        return {'error': 'Request timeout. Please try again.'}
    except Exception as e:
        return {'error': f'Error fetching daily data: {str(e)}'}

def fetch_technical_indicators(ticker, indicator='SMA', interval='daily', time_period=10):
    """
    Fetch technical indicators for enhanced predictions
    Indicators: SMA, EMA, RSI, MACD, BBANDS, etc.
    """
    try:
        if not ALPHA_VANTAGE_API_KEY:
            return {'error': 'Alpha Vantage API key not configured'}
        
        params = {
            'function': indicator,
            'symbol': ticker,
            'interval': interval,
            'time_period': time_period,
            'series_type': 'close',
            'apikey': ALPHA_VANTAGE_API_KEY
        }
        
        response = requests.get(BASE_URL, params=params, timeout=10)
        data = response.json()
        
        if 'Error Message' in data:
            return {'error': f"Invalid ticker: {ticker}"}
        
        if 'Note' in data:
            return {'error': 'API rate limit reached'}
        
        technical_key = f'Technical Analysis: {indicator}'
        if technical_key not in data:
            return {'error': 'No technical data available'}
        
        return {
            'ticker': ticker.upper(),
            'indicator': indicator,
            'data': data[technical_key]
        }
        
    except Exception as e:
        return {'error': f'Error fetching technical indicators: {str(e)}'}

def get_company_overview(ticker):
    """
    Get comprehensive company information
    """
    try:
        if not ALPHA_VANTAGE_API_KEY:
            return {'error': 'Alpha Vantage API key not configured'}
        
        params = {
            'function': 'OVERVIEW',
            'symbol': ticker,
            'apikey': ALPHA_VANTAGE_API_KEY
        }
        
        response = requests.get(BASE_URL, params=params, timeout=10)
        data = response.json()
        
        if not data or 'Symbol' not in data:
            return {'error': f"No company data available for {ticker}"}
        
        return {
            'ticker': data.get('Symbol'),
            'name': data.get('Name'),
            'description': data.get('Description'),
            'sector': data.get('Sector'),
            'industry': data.get('Industry'),
            'market_cap': data.get('MarketCapitalization'),
            'pe_ratio': data.get('PERatio'),
            '52_week_high': data.get('52WeekHigh'),
            '52_week_low': data.get('52WeekLow'),
            'dividend_yield': data.get('DividendYield')
        }
        
    except Exception as e:
        return {'error': f'Error fetching company overview: {str(e)}'}
