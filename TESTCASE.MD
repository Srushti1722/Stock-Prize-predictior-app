# Test Plan — Stock Price Predictor App
**Author:** Srushti Tarnalle  
**Version:** 1.0  
**Date:** March 2026

---

## 1. Scope

This test plan covers unit and functional testing of the backend Python services for the **Stock Price Predictor** application.

**In scope:**
- `stock_service.py` — data fetch, DB persistence, price extraction utilities
- `recommendation_service.py` — composite signal scoring and trading category classification

**Out of scope:** Frontend UI, third-party API availability (yfinance, AlphaVantage), live DB integration tests.

---

## 2. Test Objectives

- Verify correctness of all core business logic functions
- Validate all input types and boundary conditions
- Confirm graceful error handling for invalid inputs and external failures
- Ensure recommendation scoring stays within expected bounds

---

## 3. Test Types

| Type | Description |
|------|-------------|
| Functional Testing | Core function behaviour with valid inputs |
| Negative Testing | Invalid, missing, or malformed inputs |
| Boundary Testing | Edge values (empty lists, zero confidence, <20 data points) |
| Regression Testing | Consistent outputs for identical inputs |
| Error Handling | DB failures, network exceptions, bad API responses |

---

## 4. Test Environment

- **Language:** Python 3.10+
- **Framework:** pytest
- **Mocking:** unittest.mock (patch, MagicMock)
- **Reporting:** pytest-html → `reports/report.html`
- **Run command:** `pytest tests/ -v --html=reports/report.html`

---

## 5. Test Cases

### 5.1 `get_canonical_current_price`

| ID | Description | Input | Expected Result | Status |
|----|-------------|-------|-----------------|--------|
| TC-01 | Dict with `current_price` key | `{'current_price': '152.75'}` | `152.75` (float) | ✅ PASS |
| TC-02 | Dict with `data` list | `{'data': [{...close: 109.5}]}` | `109.5` | ✅ PASS |
| TC-03 | Bare list of OHLCV dicts | `[{...}, {...close: 109.5}]` | `109.5` | ✅ PASS |
| TC-04 | Pandas DataFrame | `df['close'] = [100, 105, 112]` | `112.0` | ✅ PASS |
| TC-05 | None input | `None` | `None` | ✅ PASS |
| TC-06 | Empty dict | `{}` | `None` | ✅ PASS |
| TC-07 | Empty list | `[]` | `None` | ✅ PASS |
| TC-08 | Non-numeric price string | `{'current_price': 'N/A'}` | `None` | ✅ PASS |

### 5.2 `fetch_stock_data`

| ID | Description | Input | Expected Result | Status |
|----|-------------|-------|-----------------|--------|
| TC-09 | Valid ticker happy path | `'AAPL'` | All 6 keys present, no error | ✅ PASS |
| TC-10 | Ticker normalised to uppercase | `'aapl'` | `ticker == 'AAPL'` | ✅ PASS |
| TC-11 | Empty yfinance history | `'INVALID_XYZ'` | `{'error': 'No data available...'}` | ✅ PASS |
| TC-12 | DB add_stock failure | Mock returns `None` | `{'error': '...database...'}` | ✅ PASS |
| TC-13 | 120-row history capped to 60 | 120-row DataFrame | `len(data) <= 60` | ✅ PASS |
| TC-14 | OHLCV keys in each record | Valid ticker | All 6 OHLCV fields in every record | ✅ PASS |
| TC-15 | current_price = last close | Valid ticker | `current_price == 106.0` | ✅ PASS |

### 5.3 `get_stock_info`

| ID | Description | Input | Expected Result | Status |
|----|-------------|-------|-----------------|--------|
| TC-16 | Valid ticker in DB | `'AAPL'` | All 5 keys present | ✅ PASS |
| TC-17 | Unknown ticker | `'UNKNOWN'` | `{'error': '...not found...'}` | ✅ PASS |
| TC-18 | current_price from last close | DB returns 3 rows | `current_price == 109.5` | ✅ PASS |
| TC-19 | Limit param respected | `limit=20` | `len(data) <= 20` | ✅ PASS |
| TC-20 | DB exception handled | Mock raises Exception | `{'error': ...}` | ✅ PASS |

### 5.4 `get_multiple_stocks_data`

| ID | Description | Input | Expected Result | Status |
|----|-------------|-------|-----------------|--------|
| TC-21 | Known tickers return results | `['AAPL']` | List with 1 entry | ✅ PASS |
| TC-22 | Unknown tickers skipped | `['NOPE', 'FAKE']` | `[]` | ✅ PASS |
| TC-23 | Prices are floats | `['AAPL']` | All prices are float | ✅ PASS |
| TC-24 | Mixed valid/invalid tickers | `['AAPL', 'FAKE']` | Only AAPL returned | ✅ PASS |
| TC-25 | Empty input list | `[]` | `[]` | ✅ PASS |

### 5.5 `fetch_intraday_yf`

| ID | Description | Input | Expected Result | Status |
|----|-------------|-------|-----------------|--------|
| TC-26 | Valid ticker returns data + price | `'AAPL'` | `data` list + `current_price` | ✅ PASS |
| TC-27 | Empty intraday history | Empty DataFrame | `{'error': ...}` | ✅ PASS |
| TC-28 | current_price = last intraday close | 5-min data | `current_price == 104.5` | ✅ PASS |
| TC-29 | Date includes time component | 5-min data | `':'` in date string | ✅ PASS |
| TC-30 | Network exception handled | Mock raises Exception | `{'error': ...}` | ✅ PASS |

### 5.6 `generate_recommendation`

| ID | Description | Input | Expected Result | Status |
|----|-------------|-------|-----------------|--------|
| TC-31 | Required keys always present | No signals | All 5 keys present | ✅ PASS |
| TC-32 | Category is valid label | Strong buy daily | One of 5 valid labels | ✅ PASS |
| TC-33 | Score is float | Strong buy daily | `isinstance(score, float)` | ✅ PASS |
| TC-34 | Rationale is list | Any input | `isinstance(rationale, list)` | ✅ PASS |
| TC-35 | Disclaimer non-empty | Any input | Non-empty string | ✅ PASS |
| TC-36 | Timestamp present with signals | Strong buy daily | `'timestamp'` in result | ✅ PASS |
| TC-37 | inputs_used tracks signals | daily + sentiment + history | All 3 flagged True | ✅ PASS |
| TC-38 | No signals defaults to Hold | No params | `category == 'Hold'`, `score == 0` | ✅ PASS |
| TC-39 | Strong Buy on high confidence | `percent_change=2.5, conf=75` | `'Strong Buy'` | ✅ PASS |
| TC-40 | Strong Sell on high neg confidence | `percent_change=-2.5, conf=70` | `'Strong Sell'` | ✅ PASS |
| TC-41 | Low confidence → Hold | `confidence=45` | `'Hold'` | ✅ PASS |
| TC-42 | Positive sentiment boosts score | Daily + positive sentiment | Score ≥ daily-only score | ✅ PASS |
| TC-43 | Negative sentiment lowers score | Daily + negative sentiment | Score ≤ daily-only score | ✅ PASS |
| TC-44 | Bullish momentum in rationale | Upward history 20 days | `'bullish'` in rationale | ✅ PASS |
| TC-45 | limit_targets on Strong Buy | conf=75 + CI | `limit_targets` dict present | ✅ PASS |
| TC-46 | Stop loss < current price on Buy | CI provided | `stop_loss < current_price` | ✅ PASS |
| TC-47 | Take profit > current price on Buy | CI provided | `take_profit > current_price` | ✅ PASS |
| TC-48 | Error in daily_pred ignored | `{'error': 'timeout'}` | No crash, valid response | ✅ PASS |
| TC-49 | <20 history skips momentum | 10-record history | `'momentum'` not in inputs_used | ✅ PASS |
| TC-50 | Score in [-1, 1] range | All bullish signals | `-1 <= score <= 1` | ✅ PASS |

---

## 6. Defect Log

| Defect ID | Module | Description | Severity | Status |
|-----------|--------|-------------|----------|--------|
| BUG-01 | `get_canonical_current_price` | Non-numeric string crashes float() cast | Medium | Fixed via try/except |
| BUG-02 | `fetch_stock_data` | DB failure returns None stock_id silently | High | Fixed — returns error dict |
| BUG-03 | `get_stock_info` | get_stock_data returns newest-first; reversed() handles it | Low | Handled |

---

## 7. Entry & Exit Criteria

**Entry:** All backend service files present; pytest and dependencies installed.  
**Exit:** All 50 test cases pass; 0 failures; HTML report generated.
