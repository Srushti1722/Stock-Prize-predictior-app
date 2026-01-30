import numpy as np
from datetime import datetime

def generate_recommendation(ticker, five_min_pred=None, hourly_pred=None, daily_pred=None, sentiment=None, historical_data=None):
    """
    Generate trading recommendation based on multiple signals
    
    Args:
        ticker: Stock ticker symbol
        five_min_pred: 5-minute prediction result
        hourly_pred: 1-hour prediction result
        daily_pred: Next-day prediction result
        sentiment: Sentiment analysis result
        historical_data: Historical price data for momentum calculation
    
    Returns:
        dict: Recommendation with category, score, rationale, and limit targets
    """
    
    signals = {}
    rationale = []
    
    p_d = 0
    c_d = 50
    p_h = 0
    c_h = 50
    p_5m = 0
    c_5m = 50
    s = 0
    m = 0
    v = 0.02
    
    weights_sum = 0
    
    if daily_pred and 'error' not in daily_pred:
        p_d = daily_pred.get('percent_change', 0)
        c_d = daily_pred.get('confidence', 50)
        signals['daily'] = True
        weights_sum += 0.4
        
        direction = "up" if p_d > 0 else "down"
        rationale.append(f"Next-day prediction: {abs(p_d):.1f}% {direction} (confidence: {c_d:.0f}%)")
    
    if hourly_pred and 'error' not in hourly_pred:
        p_h = hourly_pred.get('percent_change', 0)
        c_h = hourly_pred.get('confidence', 50)
        signals['hourly'] = True
        weights_sum += 0.2
        
        direction = "up" if p_h > 0 else "down"
        rationale.append(f"1-hour prediction: {abs(p_h):.1f}% {direction} (confidence: {c_h:.0f}%)")
    
    if five_min_pred and 'error' not in five_min_pred:
        p_5m = five_min_pred.get('percent_change', 0)
        c_5m = five_min_pred.get('confidence', 50)
        signals['5min'] = True
        weights_sum += 0.1
        
        direction = "up" if p_5m > 0 else "down"
        rationale.append(f"5-minute prediction: {abs(p_5m):.1f}% {direction} (confidence: {c_5m:.0f}%)")
    
    if sentiment and 'error' not in sentiment:
        label = sentiment.get('label', 'neutral').lower()
        score = sentiment.get('score', 0.5)
        
        if label == 'positive':
            s = score
        elif label == 'negative':
            s = -score
        else:
            s = 0
        
        signals['sentiment'] = True
        weights_sum += 0.2
        rationale.append(f"Sentiment: {label.capitalize()} ({score:.0%} confidence)")
    
    if historical_data and len(historical_data) >= 20:
        try:
            closes = [d['close'] for d in historical_data[-20:]]
            sma_5 = np.mean(closes[-5:])
            sma_20 = np.mean(closes[-20:])
            
            m_raw = (sma_5 - sma_20) / sma_20
            m = np.sign(m_raw) * min(abs(m_raw), 0.03)
            
            returns = np.diff(closes) / closes[:-1]
            v = np.std(returns)
            
            signals['momentum'] = True
            weights_sum += 0.1
            
            trend = "bullish" if m > 0 else "bearish"
            rationale.append(f"Technical momentum: {trend} (volatility: {v*100:.1f}%)")
        except:
            pass
    
    if weights_sum == 0:
        return {
            'category': 'Hold',
            'score': 0,
            'rationale': ['Insufficient data for recommendation'],
            'disclaimer': 'This is not financial advice. Always do your own research.',
            'inputs_used': signals
        }
    
    weight_daily = 0.4 / weights_sum if 'daily' in signals else 0
    weight_hourly = 0.2 / weights_sum if 'hourly' in signals else 0
    weight_5min = 0.1 / weights_sum if '5min' in signals else 0
    weight_sentiment = 0.2 / weights_sum if 'sentiment' in signals else 0
    weight_momentum = 0.1 / weights_sum if 'momentum' in signals else 0
    
    F_raw = (weight_daily * np.tanh(p_d/2) + 
             weight_hourly * np.tanh(p_h/1) + 
             weight_5min * np.tanh(p_5m/0.5) +
             weight_sentiment * s + 
             weight_momentum * (m/0.03 if m != 0 else 0))
    
    if 'daily' in signals and 'hourly' in signals:
        CF = 0.5 * (c_d/100) + 0.35 * (c_h/100) + 0.15 * (c_5m/100) if '5min' in signals else 0.6 * (c_d/100) + 0.4 * (c_h/100)
    elif 'daily' in signals:
        CF = c_d / 100
    elif 'hourly' in signals:
        CF = c_h / 100
    else:
        CF = 0.5
    
    volatility_penalty = 1 - 0.5 * min(1, 4 * v)
    
    F = F_raw * CF * volatility_penalty
    
    category = 'Hold'
    limit_targets = None
    
    if F >= 0.50 and p_d >= 1.2 and c_d >= 65:
        category = 'Strong Buy'
        if daily_pred and 'confidence_interval' in daily_pred:
            ci = daily_pred['confidence_interval']
            current = daily_pred.get('current_price', 0)
            if current > 0:
                limit_targets = {
                    'primary_buy': round(max(0, ci['lower']), 2),
                    'secondary_buy': round(current - 0.25 * (current - ci['lower']), 2),
                    'stop_loss': round(max(0, current - (ci['upper'] - ci['lower'])), 2),
                    'take_profit': round(current + 1.5 * (ci['upper'] - ci['lower']), 2)
                }
    
    elif 0.20 <= F < 0.50 and p_d >= 0.3 and c_d >= 55:
        category = 'Buy'
        if daily_pred and 'confidence_interval' in daily_pred:
            ci = daily_pred['confidence_interval']
            current = daily_pred.get('current_price', 0)
            if current > 0:
                limit_targets = {
                    'primary_buy': round(max(0, ci['lower']), 2),
                    'secondary_buy': round(current - 0.25 * (current - ci['lower']), 2),
                    'stop_loss': round(max(0, current - (ci['upper'] - ci['lower'])), 2),
                    'take_profit': round(current + 1.0 * (ci['upper'] - ci['lower']), 2)
                }
    
    elif -0.50 < F <= -0.20 and p_d <= -0.3 and c_d >= 55:
        category = 'Sell'
        if daily_pred and 'confidence_interval' in daily_pred:
            ci = daily_pred['confidence_interval']
            current = daily_pred.get('current_price', 0)
            if current > 0:
                limit_targets = {
                    'primary_sell': round(ci['upper'], 2),
                    'secondary_sell': round(current + 0.25 * (ci['upper'] - current), 2),
                    'stop_loss': round(current + (ci['upper'] - ci['lower']), 2),
                    'take_profit': round(max(0, current - 1.0 * (ci['upper'] - ci['lower'])), 2)
                }
    
    elif F <= -0.50 and p_d <= -1.2 and c_d >= 65:
        category = 'Strong Sell'
        if daily_pred and 'confidence_interval' in daily_pred:
            ci = daily_pred['confidence_interval']
            current = daily_pred.get('current_price', 0)
            if current > 0:
                limit_targets = {
                    'primary_sell': round(ci['upper'], 2),
                    'secondary_sell': round(current + 0.25 * (ci['upper'] - current), 2),
                    'stop_loss': round(current + (ci['upper'] - ci['lower']), 2),
                    'take_profit': round(max(0, current - 1.5 * (ci['upper'] - ci['lower'])), 2)
                }
    
    else:
        category = 'Hold'
        if c_d < 50:
            rationale.append("Low confidence - holding recommended")
        elif abs(F) < 0.20:
            rationale.append("Neutral signals - no clear direction")
    
    result = {
        'category': category,
        'score': round(float(F), 3),
        'rationale': rationale,
        'disclaimer': 'This is not financial advice. Always do your own research and consult with a financial advisor.',
        'inputs_used': signals,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    if limit_targets and CF >= 0.6:
        result['limit_targets'] = limit_targets
    
    return result
