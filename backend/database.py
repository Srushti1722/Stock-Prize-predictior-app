import sqlite3
import json
from datetime import datetime
from contextlib import contextmanager

DATABASE_PATH = 'stocks.db'

def init_db():
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ticker TEXT UNIQUE NOT NULL,
            name TEXT,
            last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stock_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            open REAL,
            high REAL,
            low REAL,
            close REAL,
            volume INTEGER,
            FOREIGN KEY (stock_id) REFERENCES stocks (id),
            UNIQUE(stock_id, date)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id INTEGER NOT NULL,
            prediction_date TEXT NOT NULL,
            predicted_price REAL NOT NULL,
            confidence REAL,
            prediction_type TEXT DEFAULT 'general',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (stock_id) REFERENCES stocks (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS sentiment_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id INTEGER NOT NULL,
            sentiment_score REAL NOT NULL,
            sentiment_label TEXT NOT NULL,
            analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (stock_id) REFERENCES stocks (id)
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS clusters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            stock_id INTEGER NOT NULL,
            cluster_id INTEGER NOT NULL,
            similar_stocks TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (stock_id) REFERENCES stocks (id),
            UNIQUE(stock_id)
        )
    ''')
    
    conn.commit()
    conn.close()

@contextmanager
def get_db_connection():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()

def add_stock(ticker, name=None):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                'INSERT INTO stocks (ticker, name) VALUES (?, ?)',
                (ticker.upper(), name)
            )
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            cursor.execute('SELECT id FROM stocks WHERE ticker = ?', (ticker.upper(),))
            result = cursor.fetchone()
            return result[0] if result else None

def get_stock_by_ticker(ticker):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM stocks WHERE ticker = ?', (ticker.upper(),))
        return cursor.fetchone()

def save_stock_data(stock_id, data_list):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        for data in data_list:
            try:
                cursor.execute('''
                    INSERT OR REPLACE INTO stock_data 
                    (stock_id, date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (stock_id, data['date'], data['open'], data['high'], 
                      data['low'], data['close'], data['volume']))
            except Exception as e:
                print(f"Error saving data point: {e}")
                continue

def save_prediction(stock_id, prediction_date, predicted_price, confidence, prediction_type='general'):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO predictions (stock_id, prediction_date, predicted_price, confidence, prediction_type)
            VALUES (?, ?, ?, ?, ?)
        ''', (stock_id, prediction_date, predicted_price, confidence, prediction_type))
        return cursor.lastrowid

def save_sentiment(stock_id, sentiment_score, sentiment_label):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO sentiment_analysis (stock_id, sentiment_score, sentiment_label)
            VALUES (?, ?, ?)
        ''', (stock_id, sentiment_score, sentiment_label))
        return cursor.lastrowid

def save_cluster(stock_id, cluster_id, similar_stocks):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO clusters (stock_id, cluster_id, similar_stocks, updated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ''', (stock_id, cluster_id, json.dumps(similar_stocks)))
        return cursor.lastrowid

def get_stock_data(stock_id, limit=100):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM stock_data 
            WHERE stock_id = ? 
            ORDER BY date DESC 
            LIMIT ?
        ''', (stock_id, limit))
        return cursor.fetchall()

def get_latest_prediction(stock_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM predictions 
            WHERE stock_id = ? 
            ORDER BY created_at DESC 
            LIMIT 1
        ''', (stock_id,))
        return cursor.fetchone()

def get_latest_sentiment(stock_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM sentiment_analysis 
            WHERE stock_id = ? 
            ORDER BY analyzed_at DESC 
            LIMIT 1
        ''', (stock_id,))
        return cursor.fetchone()

def get_cluster_info(stock_id):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            SELECT * FROM clusters 
            WHERE stock_id = ? 
            ORDER BY updated_at DESC 
            LIMIT 1
        ''', (stock_id,))
        return cursor.fetchone()
