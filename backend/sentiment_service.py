from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import yfinance as yf
from database import save_sentiment, get_latest_sentiment

model_name = "ProsusAI/finbert"
tokenizer = None
model = None

def load_sentiment_model():
    global tokenizer, model
    try:
        if tokenizer is None or model is None:
            tokenizer = AutoTokenizer.from_pretrained(model_name)
            model = AutoModelForSequenceClassification.from_pretrained(model_name)
            model.eval()
        return True
    except Exception as e:
        print(f"Error loading FinBERT model: {e}")
        return False

def get_stock_news_text(ticker):
    try:
        stock = yf.Ticker(ticker)
        news = stock.news
        
        if not news or len(news) == 0:
            return f"{ticker} stock performance analysis"
        
        texts = []
        for article in news[:5]:
            if 'title' in article:
                texts.append(article['title'])
        
        return ' '.join(texts) if texts else f"{ticker} stock performance"
    except Exception as e:
        return f"{ticker} stock market analysis"

def analyze_sentiment(ticker, stock_id):
    try:
        if not load_sentiment_model():
            return {
                'sentiment_score': 0.0,
                'sentiment_label': 'neutral',
                'error': 'Failed to load sentiment model'
            }
        
        text = get_stock_news_text(ticker)
        
        inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=512, padding=True)
        
        with torch.no_grad():
            outputs = model(**inputs)
            predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
        
        labels = ['negative', 'neutral', 'positive']
        scores = predictions[0].tolist()
        
        sentiment_label = labels[scores.index(max(scores))]
        sentiment_score = scores[2] - scores[0]
        
        save_sentiment(stock_id, sentiment_score, sentiment_label)
        
        return {
            'sentiment_score': round(sentiment_score, 4),
            'sentiment_label': sentiment_label,
            'positive_prob': round(scores[2], 4),
            'neutral_prob': round(scores[1], 4),
            'negative_prob': round(scores[0], 4)
        }
        
    except Exception as e:
        return {
            'sentiment_score': 0.0,
            'sentiment_label': 'neutral',
            'error': f'Error analyzing sentiment: {str(e)}'
        }

def get_sentiment_info(stock_id):
    try:
        sentiment = get_latest_sentiment(stock_id)
        if sentiment:
            return {
                'sentiment_score': sentiment['sentiment_score'],
                'sentiment_label': sentiment['sentiment_label'],
                'analyzed_at': sentiment['analyzed_at']
            }
        return None
    except Exception as e:
        return {'error': f'Error retrieving sentiment: {str(e)}'}
