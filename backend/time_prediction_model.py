# backend/time_prediction_model.py
import os
import json
import torch
import torch.nn as nn
import torch.optim as optim
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple

# ================================
# Basic models
# ================================
class TimePredictionGNN(nn.Module):
    """
    Placeholder GNN-style model kept for compatibility.
    """
    def __init__(self, input_dim, hidden_dim=64, output_dim=1, dropout=0.3):
        super(TimePredictionGNN, self).__init__()
        self.fc1 = nn.Linear(input_dim, hidden_dim)
        self.fc2 = nn.Linear(hidden_dim, hidden_dim // 2)
        self.fc3 = nn.Linear(hidden_dim // 2, output_dim)
        self.dropout = nn.Dropout(dropout)
        self.relu = nn.ReLU()

    def forward(self, x, adj=None):
        if adj is not None:
            try:
                x = torch.mm(adj, x)
            except Exception:
                pass
        x = self.fc1(x)
        x = self.relu(x)
        x = self.dropout(x)
        x = self.fc2(x)
        x = self.relu(x)
        x = self.dropout(x)
        x = self.fc3(x)
        return x


class CorrectionNN(nn.Module):
    """
    Small correction network that takes a hand-crafted feature vector and predicts
    an additive correction to a base rule-based prediction.
    """
    def __init__(self, input_dim: int = 16, hidden_dim: int = 64):
        super(CorrectionNN, self).__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.BatchNorm1d(hidden_dim),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, max(8, hidden_dim // 2)),
            nn.ReLU(),
            nn.BatchNorm1d(max(8, hidden_dim // 2)),
            nn.Dropout(0.1),
            nn.Linear(max(8, hidden_dim // 2), 1)
        )

    def forward(self, x):
        return self.net(x).squeeze(-1)


# ================================
# Utilities / indicators
# ================================
def normalize_array(arr: np.ndarray) -> np.ndarray:
    arr = np.array(arr, dtype=np.float32)
    if arr.size == 0:
        return arr
    mu = np.nanmean(arr)
    sigma = np.nanstd(arr)
    if sigma < 1e-6:
        return arr - mu
    return (arr - mu) / sigma


def safe_div(a: float, b: float, eps: float = 1e-9) -> float:
    return a / (b + eps)


def compute_rsi(prices: np.ndarray, period: int = 14) -> float:
    if len(prices) < 2:
        return 50.0
    deltas = np.diff(prices)
    seed = deltas[-period:] if len(deltas) >= period else deltas
    gains = seed[seed > 0].sum() / (len(seed)+1e-9)
    losses = -seed[seed < 0].sum() / (len(seed)+1e-9)
    rs = safe_div(gains, losses)
    rsi = 100 - (100 / (1 + rs))
    return float(np.clip(rsi, 0, 100))


def compute_atr(highs: np.ndarray, lows: np.ndarray, closes: np.ndarray, period: int = 14) -> float:
    if len(closes) < 2:
        return 0.0
    highs = np.array(highs)
    lows = np.array(lows)
    closes = np.array(closes)
    tr_list = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        tr_list.append(tr)
    atr = np.mean(tr_list[-period:]) if tr_list else 0.0
    return float(atr)


def bollinger_width(prices: np.ndarray, window: int = 20) -> float:
    if len(prices) < 2:
        return 0.0
    s = pd.Series(prices)
    std = s.rolling(window).std().iloc[-1] if len(s) >= window else s.std()
    center = s.rolling(window).mean().iloc[-1] if len(s) >= window else s.mean()
    if center == 0 or np.isnan(center):
        return 0.0
    return float((2 * std) / center)


def on_balance_volume(prices: np.ndarray, volumes: np.ndarray) -> float:
    if len(prices) < 2 or len(volumes) < 2:
        return 0.0
    obv = 0.0
    for i in range(1, len(prices)):
        if prices[i] > prices[i-1]:
            obv += volumes[i]
        elif prices[i] < prices[i-1]:
            obv -= volumes[i]
    return float(obv)


# ================================
# Feature builders
# ================================
def intraday_feature_vector(data: List[Dict[str, Any]]) -> np.ndarray:
    df = pd.DataFrame(data)
    closes = df['close'].values
    volumes = df['volume'].values if 'volume' in df.columns else np.ones(len(closes))
    highs = df['high'].values if 'high' in df.columns else closes
    lows = df['low'].values if 'low' in df.columns else closes

    vec = []
    # Basic stats
    vec.append(closes[-1])                        # last close
    vec.append(np.mean(closes[-10:]))             # mean last 10
    vec.append(np.std(closes[-10:]))              # std last 10
    vec.append(volumes[-1])                       # last volume
    vec.append(np.mean(volumes[-10:]))            # avg vol
    # Momentum indicators
    vec.append((closes[-1] - closes[-3]) / (closes[-3] + 1e-9) if len(closes) >= 3 else 0.0)
    vec.append((closes[-1] - np.mean(closes[-5:])) / (np.mean(closes[-5:]) + 1e-9) if len(closes) >= 1 else 0.0)
    # EMA spread
    s = pd.Series(closes)
    vec.append(float(s.ewm(span=3).mean().iloc[-1] - s.ewm(span=8).mean().iloc[-1]))
    # micro returns
    recent_returns = np.diff(closes[-6:]) / (closes[-6:-1] + 1e-9) if len(closes) >= 6 else np.array([0.0])
    recent_returns_list = list(recent_returns[-4:]) if len(recent_returns) >= 4 else list(recent_returns) + [0]*(4-len(recent_returns))
    vec.extend(recent_returns_list)
    # volatility & volume change
    vec.append(float(np.std(recent_returns) if recent_returns.size > 0 else 0.0))
    vec.append(float(np.mean(volumes[-3:]) / (np.mean(volumes[-20:]) + 1e-9)) if len(volumes) >= 3 else float(np.mean(volumes)))
    # normalized RSI and bollinger
    vec.append(float(compute_rsi(closes[-15:] if len(closes) >= 15 else closes, period=14)))
    vec.append(float(bollinger_width(closes, window=14)))
    # OBV
    vec.append(float(on_balance_volume(closes, volumes)))
    vec = np.array(vec, dtype=np.float32)
    vec_norm = normalize_array(vec)
    return vec_norm


def daily_feature_vector(data: List[Dict[str, Any]]) -> np.ndarray:
    df = pd.DataFrame(data)
    closes = df['close'].values
    volumes = df['volume'].values if 'volume' in df.columns else np.ones(len(closes))
    highs = df['high'].values if 'high' in df.columns else closes
    lows = df['low'].values if 'low' in df.columns else closes

    vec = []
    vec.append(closes[-1])
    vec.append(np.mean(closes[-5:]) if len(closes) >= 5 else np.mean(closes))
    vec.append(np.mean(closes[-10:]) if len(closes) >= 10 else np.mean(closes))
    vec.append(np.std(closes[-10:]) if len(closes) >= 2 else 0.0)
    vec.append(np.mean(volumes[-5:]) if len(volumes) >= 5 else np.mean(volumes))
    vec.append((closes[-1] - closes[-5]) / (closes[-5] + 1e-9) if len(closes) >= 5 else 0.0)
    vec.append(compute_rsi(closes[-20:] if len(closes) >= 20 else closes, period=14))
    vec.append(bollinger_width(closes, window=20))
    vec.append(on_balance_volume(closes, volumes))
    vec.append(compute_atr(highs, lows, closes, period=14))
    vec = np.array(vec, dtype=np.float32)
    return normalize_array(vec)


# ================================
# Model persistence helpers
# ================================
MODEL_DIR = os.environ.get('MODEL_DIR', 'models')
CORRECTION_MODEL_FILENAME = os.path.join(MODEL_DIR, 'correction_nn.pth')

def ensure_model_dir():
    if not os.path.isdir(MODEL_DIR):
        os.makedirs(MODEL_DIR, exist_ok=True)

def save_correction_model(model: CorrectionNN, path: Optional[str] = None):
    ensure_model_dir()
    path = path or CORRECTION_MODEL_FILENAME
    torch.save(model.state_dict(), path)
    meta = {'saved_at': datetime.utcnow().isoformat(), 'torch_version': torch.__version__}
    meta_path = path + '.meta.json'
    with open(meta_path, 'w') as f:
        json.dump(meta, f)

def load_correction_model(path: Optional[str] = None, device: Optional[str] = None) -> Optional[CorrectionNN]:
    path = path or CORRECTION_MODEL_FILENAME
    if not os.path.isfile(path):
        return None
    if device is None:
        device = 'cuda' if torch.cuda.is_available() else 'cpu'
    map_loc = torch.device(device)
    try:
        state = torch.load(path, map_location=map_loc)
    except Exception:
        return None

    # Try to infer input dim from saved state dict
    input_dim = None
    try:
        # common key pattern 'net.0.weight' or similar
        for k, v in state.items():
            if k.endswith('.weight') and len(v.shape) == 2:
                input_dim = v.shape[1]
                break
    except Exception:
        input_dim = None

    # fallback candidate dims
    candidates = [input_dim] if input_dim else []
    candidates += [16, 18, 20, 24, 32]
    last_exc = None
    for cand in [c for c in candidates if c]:
        try:
            model = CorrectionNN(input_dim=int(cand))
            model.load_state_dict(state)
            model.to(map_loc)
            model.eval()
            return model
        except Exception as e:
            last_exc = e
            continue
    # final attempt: try to create with default dim and load ignoring missing keys
    try:
        model = CorrectionNN(input_dim=16)
        model.load_state_dict(state, strict=False)
        model.to(map_loc)
        model.eval()
        return model
    except Exception as e:
        print("Failed to load correction model:", e, last_exc)
        return None


# ================================
# Apply correction (robust)
# ================================
def apply_correction(base_pred_price: float,
                     data: List[Dict[str, Any]],
                     prediction_type: str,
                     correction_model: Optional[CorrectionNN] = None) -> Tuple[float, float]:
    """
    Returns (corrected_price, correction_amount)
    Pads/truncates feature vector to model input_dim if needed.
    """
    if correction_model is None:
        return base_pred_price, 0.0
    try:
        if prediction_type in ('5_min', '1_hour'):
            fv = intraday_feature_vector(data)
        else:
            fv = daily_feature_vector(data)

        # infer expected input size
        expected_in = None
        try:
            for layer in correction_model.net:
                if isinstance(layer, nn.Linear):
                    expected_in = layer.in_features
                    break
        except Exception:
            expected_in = None

        fv = fv.astype(np.float32)
        if expected_in is not None and fv.size != expected_in:
            if fv.size < expected_in:
                pad = np.zeros(expected_in - fv.size, dtype=np.float32)
                fv = np.concatenate([fv, pad])
            elif fv.size > expected_in:
                fv = fv[:expected_in]

        x = torch.tensor(fv.reshape(1, -1), dtype=torch.float32)
        device = next(correction_model.parameters()).device
        x = x.to(device)
        correction_model.eval()
        with torch.no_grad():
            correction = correction_model(x).item()
        corrected_price = float(base_pred_price + correction)
        return corrected_price, float(correction)
    except Exception:
        return base_pred_price, 0.0


# ================================
# Prediction functions (rule-based + correction)
# ================================
def predict_five_minutes(data: List[Dict[str, Any]],
                         model: Optional[Any] = None,
                         correction_model: Optional[CorrectionNN] = None) -> Dict[str, Any]:
    try:
        if len(data) < 10:
            return {'error': 'Insufficient data for 5-minute prediction', 'required': 10}

        df = pd.DataFrame(data)
        closes = df['close'].values[-30:]
        volumes = df['volume'].values[-30:] if 'volume' in df.columns else np.ones(len(closes))

        current_price = float(closes[-1])
        s = pd.Series(closes)
        ema_3 = s.ewm(span=3, adjust=False).mean().iloc[-1]
        ema_5 = s.ewm(span=5, adjust=False).mean().iloc[-1]
        ema_8 = s.ewm(span=8, adjust=False).mean().iloc[-1]

        recent_closes = closes[-6:]
        micro_returns = np.diff(recent_closes) / (recent_closes[:-1] + 1e-9) if len(recent_closes) >= 2 else np.array([0.0])
        avg_micro_return = float(np.mean(micro_returns)) if len(micro_returns) > 0 else 0.0

        momentum = float((closes[-1] - closes[-3]) / (closes[-3] + 1e-9)) if len(closes) >= 3 else 0.0
        immediate_trend = float((ema_3 - ema_5) / (ema_5 + 1e-9))
        broader_trend = float((ema_5 - ema_8) / (ema_8 + 1e-9))

        recent_vol = float(np.mean(volumes[-3:])) if len(volumes) >= 3 else float(np.mean(volumes))
        avg_vol = float(np.mean(volumes)) if len(volumes) > 0 else 1.0
        volume_factor = min(1.3, max(0.7, recent_vol / (avg_vol + 1e-9)))

        predicted_change_pct = (
            avg_micro_return * 0.45 +
            immediate_trend * 0.30 +
            broader_trend * 0.15 +
            momentum * 0.10
        ) * 100 * volume_factor

        predicted_change_pct = float(np.clip(predicted_change_pct, -3.0, 3.0))
        base_predicted_price = current_price * (1 + predicted_change_pct / 100.0)

        corrected_price, correction_amt = apply_correction(base_predicted_price, data, '5_min', correction_model)

        price_change = corrected_price - current_price
        volatility = float(np.std(micro_returns) * 100) if len(micro_returns) > 0 else 1.0
        confidence = float(88 * np.exp(-volatility * 0.05))
        confidence -= (abs(correction_amt) / (current_price + 1e-9)) * 100
        confidence = float(max(70, confidence))
        confidence = round(confidence, 2)

        return {
            'prediction_type': '5_min',
            'current_price': float(current_price),
            'predicted_price': float(corrected_price),
            'price_change': float(price_change),
            'percent_change': float((corrected_price - current_price) / (current_price + 1e-9) * 100),
            'confidence': float(confidence),
            'prediction_time': (datetime.now() + timedelta(minutes=5)).isoformat(),
            'correction_applied': float(correction_amt)
        }

    except Exception as e:
        return {'error': f'Error in 5-minute prediction: {str(e)}'}


def predict_one_hour(data: List[Dict[str, Any]],
                     model: Optional[Any] = None,
                     correction_model: Optional[CorrectionNN] = None) -> Dict[str, Any]:
    try:
        if len(data) < 20:
            return {'error': 'Insufficient data for 1-hour prediction', 'required': 20}

        df = pd.DataFrame(data)
        closes = df['close'].values[-80:]
        volumes = df['volume'].values[-80:] if 'volume' in df.columns else np.ones(len(closes))
        highs = df['high'].values[-80:] if 'high' in df.columns else closes
        lows = df['low'].values[-80:] if 'low' in df.columns else closes

        current_price = float(closes[-1])

        s = pd.Series(closes)
        ema_5 = s.ewm(span=5, adjust=False).mean().iloc[-1]
        ema_10 = s.ewm(span=10, adjust=False).mean().iloc[-1]
        ema_20 = s.ewm(span=20, adjust=False).mean().iloc[-1]
        macd = float(ema_10 - ema_20)

        rsi = float(compute_rsi(closes[-30:] if len(closes) >= 30 else closes, period=14))
        rsi_factor = (50 - rsi) / 100.0

        momentum = float((closes[-1] - closes[-5]) / (closes[-5] + 1e-9)) if len(closes) >= 5 else 0.0

        price_ranges = (np.array(highs[-20:]) - np.array(lows[-20:])) / (np.array(closes[-20:]) + 1e-9)
        avg_volatility = float(np.nanmean(price_ranges)) if len(price_ranges) > 0 else 0.0

        recent_vol = float(np.mean(volumes[-6:])) if len(volumes) >= 6 else float(np.mean(volumes))
        avg_vol = float(np.mean(volumes[-40:])) if len(volumes) >= 1 else 1.0
        vol_factor = min(1.4, max(0.7, recent_vol / (avg_vol + 1e-9)))

        base_change = (
            0.28 * ((ema_5 - ema_10) / (ema_10 + 1e-9)) +
            0.22 * ((ema_10 - ema_20) / (ema_20 + 1e-9)) +
            0.2 * momentum +
            0.15 * (macd / (current_price + 1e-9)) +
            0.15 * rsi_factor
        )

        predicted_change_pct = float(np.clip(base_change * 100 * vol_factor, -6.0, 6.0))
        base_predicted_price = current_price * (1 + predicted_change_pct / 100.0)

        corrected_price, correction_amt = apply_correction(base_predicted_price, data, '1_hour', correction_model)

        price_change = corrected_price - current_price
        recent_returns = np.diff(closes[-12:]) / (closes[-12:-1] + 1e-9) if len(closes) >= 12 else np.array([0.0])
        volatility_metric = float(np.std(recent_returns) * 100) if recent_returns.size > 0 else 1.0
        confidence = float(87 * np.exp(-volatility_metric * 0.04) - avg_volatility * 8)
        confidence = float(min(90, max(58, confidence - (abs(correction_amt) / (current_price + 1e-9)) * 120)))

        return {
            'prediction_type': '1_hour',
            'current_price': float(current_price),
            'predicted_price': float(corrected_price),
            'price_change': float(price_change),
            'percent_change': float((corrected_price - current_price) / (current_price + 1e-9) * 100),
            'confidence': float(confidence),
            'prediction_time': (datetime.now() + timedelta(hours=1)).isoformat(),
            'correction_applied': float(correction_amt)
        }

    except Exception as e:
        return {'error': f'Error in 1-hour prediction: {str(e)}'}


def predict_next_day(data: List[Dict[str, Any]],
                     model: Optional[Any] = None,
                     correction_model: Optional[CorrectionNN] = None) -> Dict[str, Any]:
    try:
        if len(data) < 30:
            return {'error': 'Insufficient data for next-day prediction', 'required': 30}

        df = pd.DataFrame(data)
        closes = df['close'].values[-120:]
        volumes = df['volume'].values[-120:] if 'volume' in df.columns else np.ones(len(closes))
        highs = df['high'].values[-120:] if 'high' in df.columns else closes
        lows = df['low'].values[-120:] if 'low' in df.columns else closes

        current_price = float(closes[-1])

        sma_5 = float(pd.Series(closes).rolling(5).mean().iloc[-1])
        sma_10 = float(pd.Series(closes).rolling(10).mean().iloc[-1])
        sma_20 = float(pd.Series(closes).rolling(20).mean().iloc[-1])
        ema_10 = float(pd.Series(closes).ewm(span=10, adjust=False).mean().iloc[-1])
        ema_20 = float(pd.Series(closes).ewm(span=20, adjust=False).mean().iloc[-1])
        macd = float(ema_10 - ema_20)

        bb_width = float(bollinger_width(closes, window=20))
        rsi = float(compute_rsi(closes[-70:] if len(closes) >= 70 else closes, period=14))
        rsi_factor = (50 - rsi) / 100.0

        momentum_3d = float((closes[-1] - closes[-3]) / (closes[-3] + 1e-9)) if len(closes) >= 3 else 0.0
        momentum_5d = float((closes[-1] - closes[-5]) / (closes[-5] + 1e-9)) if len(closes) >= 5 else 0.0
        recent_closes = closes[-20:]
        recent_returns = np.diff(recent_closes) / (recent_closes[:-1] + 1e-9) if len(recent_closes) >= 2 else np.array([0.0])
        avg_daily_return = float(np.mean(recent_returns))

        price_ranges = (np.array(highs[-20:]) - np.array(lows[-20:])) / (np.array(closes[-20:]) + 1e-9)
        avg_volatility = float(np.nanmean(price_ranges)) if len(price_ranges) > 0 else 0.0
        vol_factor = min(1.35, max(0.7, (np.mean(volumes[-5:]) / (np.mean(volumes[-30:]) + 1e-9)))) if len(volumes) >= 5 else 1.0

        base_change = (
            0.25 * ((sma_5 - sma_10) / (sma_10 + 1e-9)) +
            0.18 * ((ema_10 - ema_20) / (ema_20 + 1e-9)) +
            0.15 * (macd / (current_price + 1e-9)) +
            0.15 * momentum_3d +
            0.10 * momentum_5d +
            0.10 * avg_daily_return +
            0.07 * rsi_factor
        )

        predicted_change_pct = float(np.clip(base_change * 100 * vol_factor, -9.0, 9.0))
        base_predicted_price = current_price * (1 + predicted_change_pct / 100.0)

        corrected_price, correction_amt = apply_correction(base_predicted_price, data, 'next_day', correction_model)

        price_change = corrected_price - current_price

        volatility_metric = float(np.std(recent_returns) * 100) if recent_returns.size > 0 else 1.0
        confidence = float(90 * np.exp(-volatility_metric * 0.035) - bb_width * 12)
        confidence = float(min(92, max(55, confidence - (abs(correction_amt) / (current_price + 1e-9)) * 150)))

        next_day = datetime.now() + timedelta(days=1)
        while next_day.weekday() >= 5:
            next_day += timedelta(days=1)

        return {
            'prediction_type': 'next_day',
            'current_price': float(current_price),
            'predicted_price': float(corrected_price),
            'price_change': float(price_change),
            'percent_change': float((corrected_price - current_price) / (current_price + 1e-9) * 100),
            'confidence': float(confidence),
            'prediction_date': next_day.strftime('%Y-%m-%d'),
            'correction_applied': float(correction_amt)
        }

    except Exception as e:
        return {'error': f'Error in next-day prediction: {str(e)}'}


def predict_with_confidence_interval(data: List[Dict[str, Any]],
                                     prediction_type: str = 'next_day',
                                     correction_model: Optional[CorrectionNN] = None) -> Dict[str, Any]:
    if prediction_type == '5_min':
        result = predict_five_minutes(data, correction_model=correction_model)
    elif prediction_type == '1_hour':
        result = predict_one_hour(data, correction_model=correction_model)
    else:
        result = predict_next_day(data, correction_model=correction_model)

    if 'error' in result:
        return result

    predicted_price = result.get('predicted_price', 0.0)
    confidence = float(result.get('confidence', 50.0))

    if predicted_price <= 0:
        return {'error': 'Invalid prediction price - please try again later'}

    uncertainty = (100.0 - confidence) / 100.0
    if prediction_type == '5_min':
        price_range = abs(predicted_price) * 0.02 * (1 + uncertainty)
    elif prediction_type == '1_hour':
        price_range = abs(predicted_price) * 0.04 * (1 + uncertainty)
    else:
        price_range = abs(predicted_price) * 0.06 * (1 + uncertainty)

    result['confidence_interval'] = {
        'lower': float(max(0.0, predicted_price - price_range)),
        'upper': float(predicted_price + price_range)
    }
    return result


# ================================
# Build training set helper
# ================================
def build_correction_training_set(hist_data: List[Dict[str, Any]],
                                  timeframe: str = 'next_day',
                                  base_predictor_func=None,
                                  lookback_window: int = 70) -> Tuple[np.ndarray, np.ndarray]:
    X_list = []
    y_list = []
    for end_idx in range(lookback_window, len(hist_data) - 1):
        window = hist_data[end_idx - lookback_window:end_idx]
        next_point = hist_data[end_idx]
        if base_predictor_func is None:
            closes = np.array([d['close'] for d in window])
            base_pred = float(closes[-1] * (1 + np.mean(np.diff(closes) / (closes[:-1] + 1e-9))))
        else:
            try:
                base_res = base_predictor_func(window)
                if isinstance(base_res, dict) and 'predicted_price' in base_res:
                    base_pred = float(base_res['predicted_price'])
                elif isinstance(base_res, (float, int)):
                    base_pred = float(base_res)
                else:
                    base_pred = float(window[-1]['close'])
            except Exception:
                base_pred = float(window[-1]['close'])

        if timeframe in ('5_min', '1_hour'):
            feat = intraday_feature_vector(window)
        else:
            feat = daily_feature_vector(window)

        actual_price = float(next_point['close'])
        residual = actual_price - base_pred

        X_list.append(feat)
        y_list.append(float(residual))

    if not X_list:
        return np.empty((0,)), np.empty((0,))
    X = np.vstack(X_list)
    y = np.array(y_list, dtype=np.float32)
    return X, y


# ================================
# Optional intraday yfinance helper
# ================================
def fetch_intraday_yf(ticker: str, interval: str = '5m', period: str = '7d') -> Dict[str, Any]:
    try:
        t = ticker.upper().strip()
        tk = __import__('yfinance').Ticker(t)
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


# ================================
# Demo / self-test
# ================================
if __name__ == '__main__':
    # small self-test with synthetic data
    import random
    def synth(min_len=200):
        arr = []
        price = 100.0
        for i in range(min_len):
            drift = random.uniform(-0.5, 0.5)
            price = max(0.1, price * (1 + drift/100.0))
            arr.append({
                'timestamp': i,
                'open': price * (1 - random.uniform(0, 0.002)),
                'high': price * (1 + random.uniform(0, 0.005)),
                'low': price * (1 - random.uniform(0, 0.005)),
                'close': price,
                'volume': random.randint(100, 1000)
            })
        return arr

    demo_data = synth(300)
    # instantiate correction model (untrained) just for API compatibility
    corr_model = CorrectionNN(input_dim=intraday_feature_vector(demo_data[-80:]).size, hidden_dim=64)
    res_5 = predict_five_minutes(demo_data[-40:], correction_model=corr_model)
    res_1h = predict_one_hour(demo_data[-120:], correction_model=corr_model)
    res_nd = predict_next_day(demo_data[-200:], correction_model=corr_model)
    print('5-min demo:', res_5)
    print('1-hour demo:', res_1h)
    print('next-day demo:', res_nd)
