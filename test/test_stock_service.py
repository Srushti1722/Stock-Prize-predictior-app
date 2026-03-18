# =============================================================================
# tests/test_stock_service.py
# Unit tests for stock_service.py — Stock Price Predictor App
# Author: Srushti Tarnalle | EY GDS Testing Portfolio
#
# Run:  pytest tests/ -v --html=reports/report.html
# Deps: pip install pytest pytest-html
# =============================================================================

import pytest
from unittest.mock import patch, MagicMock
import pandas as pd

# ── import the modules under test ──────────────────────────────────────────
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from stock_service import (
    get_canonical_current_price,
    fetch_stock_data,
    get_stock_info,
    get_multiple_stocks_data,
    fetch_intraday_yf,
)


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def sample_data_list():
    """Reusable list of OHLCV dicts (chronological order)."""
    return [
        {'date': '2025-01-01', 'open': 100.0, 'high': 105.0, 'low': 99.0,  'close': 102.0, 'volume': 1000000},
        {'date': '2025-01-02', 'open': 102.0, 'high': 108.0, 'low': 101.0, 'close': 106.0, 'volume': 1200000},
        {'date': '2025-01-03', 'open': 106.0, 'high': 110.0, 'low': 104.0, 'close': 109.5, 'volume': 950000},
    ]

@pytest.fixture
def mock_db_add_stock():
    """Mock add_stock to return a fake stock_id without touching a real DB."""
    with patch('stock_service.add_stock', return_value=42) as m:
        yield m

@pytest.fixture
def mock_db_get_stock():
    with patch('stock_service.get_stock_by_ticker',
               return_value={'id': 42, 'ticker': 'AAPL', 'name': 'Apple Inc.'}) as m:
        yield m

@pytest.fixture
def mock_db_save():
    with patch('stock_service.save_stock_data', return_value=None) as m:
        yield m

@pytest.fixture
def mock_db_get_data(sample_data_list):
    with patch('stock_service.get_stock_data', return_value=list(reversed(sample_data_list))) as m:
        yield m


# =============================================================================
# TC-01 to TC-08  |  get_canonical_current_price
# =============================================================================

class TestGetCanonicalCurrentPrice:
    """Validates the price extraction utility across all supported input shapes."""

    def test_TC01_dict_with_current_price_key(self):
        """TC-01: Returns float when dict has explicit 'current_price'."""
        result = get_canonical_current_price({'current_price': '152.75'})
        assert result == 152.75
        assert isinstance(result, float)

    def test_TC02_dict_with_data_list(self, sample_data_list):
        """TC-02: Extracts last close from dict['data'] list."""
        result = get_canonical_current_price({'data': sample_data_list})
        assert result == 109.5

    def test_TC03_list_of_dicts_returns_last_close(self, sample_data_list):
        """TC-03: Extracts last close from a bare list of OHLCV dicts."""
        result = get_canonical_current_price(sample_data_list)
        assert result == 109.5

    def test_TC04_dataframe_input(self):
        """TC-04: Extracts last close from a pandas DataFrame."""
        df = pd.DataFrame({'close': [100.0, 105.0, 112.0]})
        result = get_canonical_current_price(df)
        assert result == 112.0

    def test_TC05_none_input_returns_none(self):
        """TC-05: Returns None when input is None."""
        assert get_canonical_current_price(None) is None

    def test_TC06_empty_dict_returns_none(self):
        """TC-06: Returns None for empty dict (no 'current_price' or 'data')."""
        assert get_canonical_current_price({}) is None

    def test_TC07_empty_list_returns_none(self):
        """TC-07: Returns None for empty list."""
        assert get_canonical_current_price([]) is None

    def test_TC08_non_numeric_current_price_returns_none(self):
        """TC-08: Returns None if 'current_price' value cannot be cast to float."""
        assert get_canonical_current_price({'current_price': 'not_a_number'}) is None


# =============================================================================
# TC-09 to TC-15  |  fetch_stock_data
# =============================================================================

class TestFetchStockData:
    """Functional tests for the yfinance fetch-and-persist pipeline."""

    def _make_fake_hist(self):
        """Helper: returns a minimal DataFrame mimicking yfinance output."""
        dates = pd.date_range('2025-01-01', periods=5, freq='D')
        return pd.DataFrame({
            'Open':   [100, 101, 102, 103, 104],
            'High':   [105, 106, 107, 108, 109],
            'Low':    [99,  100, 101, 102, 103],
            'Close':  [102, 103, 104, 105, 106],
            'Volume': [1e6, 1e6, 1e6, 1e6, 1e6],
        }, index=dates)

    @patch('stock_service.save_stock_data')
    @patch('stock_service.add_stock', return_value=1)
    @patch('stock_service.yf.Ticker')
    def test_TC09_valid_ticker_returns_expected_keys(self, mock_ticker, mock_add, mock_save):
        """TC-09: Valid ticker returns dict with all required top-level keys."""
        inst = MagicMock()
        inst.history.return_value = self._make_fake_hist()
        inst.info = {'longName': 'Apple Inc.', 'marketCap': 2e12}
        mock_ticker.return_value = inst

        result = fetch_stock_data('AAPL')

        assert 'error' not in result
        for key in ('ticker', 'name', 'stock_id', 'data', 'current_price', 'info'):
            assert key in result, f"Missing key: {key}"

    @patch('stock_service.save_stock_data')
    @patch('stock_service.add_stock', return_value=1)
    @patch('stock_service.yf.Ticker')
    def test_TC10_ticker_is_uppercased(self, mock_ticker, mock_add, mock_save):
        """TC-10: Ticker is normalised to uppercase regardless of input case."""
        inst = MagicMock()
        inst.history.return_value = self._make_fake_hist()
        inst.info = {}
        mock_ticker.return_value = inst

        result = fetch_stock_data('aapl')
        assert result.get('ticker') == 'AAPL'

    @patch('stock_service.yf.Ticker')
    def test_TC11_empty_history_returns_error(self, mock_ticker):
        """TC-11: Returns error dict when yfinance returns no historical data."""
        inst = MagicMock()
        inst.history.return_value = pd.DataFrame()   # empty
        inst.info = {}
        mock_ticker.return_value = inst

        result = fetch_stock_data('INVALID_XYZ')
        assert 'error' in result
        assert 'No data available' in result['error']

    @patch('stock_service.save_stock_data')
    @patch('stock_service.add_stock', return_value=None)   # DB returns None = failure
    @patch('stock_service.get_stock_by_ticker', return_value=None)
    @patch('stock_service.yf.Ticker')
    def test_TC12_db_failure_returns_error(self, mock_ticker, mock_get, mock_add, mock_save):
        """TC-12: Returns error when stock cannot be persisted to the database."""
        inst = MagicMock()
        inst.history.return_value = self._make_fake_hist()
        inst.info = {}
        mock_ticker.return_value = inst

        result = fetch_stock_data('AAPL')
        assert 'error' in result
        assert 'database' in result['error'].lower()

    @patch('stock_service.save_stock_data')
    @patch('stock_service.add_stock', return_value=5)
    @patch('stock_service.yf.Ticker')
    def test_TC13_data_list_capped_at_60_records(self, mock_ticker, mock_add, mock_save):
        """TC-13: Returned data list never exceeds 60 records (last-60 slice)."""
        dates = pd.date_range('2024-01-01', periods=120, freq='D')
        big_df = pd.DataFrame({
            'Open': [100]*120, 'High': [105]*120, 'Low': [99]*120,
            'Close': [102]*120, 'Volume': [1e6]*120,
        }, index=dates)
        inst = MagicMock()
        inst.history.return_value = big_df
        inst.info = {}
        mock_ticker.return_value = inst

        result = fetch_stock_data('AAPL')
        assert len(result['data']) <= 60

    @patch('stock_service.save_stock_data')
    @patch('stock_service.add_stock', return_value=7)
    @patch('stock_service.yf.Ticker')
    def test_TC14_each_data_record_has_ohlcv_keys(self, mock_ticker, mock_add, mock_save):
        """TC-14: Every record in data list contains date, open, high, low, close, volume."""
        inst = MagicMock()
        inst.history.return_value = self._make_fake_hist()
        inst.info = {}
        mock_ticker.return_value = inst

        result = fetch_stock_data('MSFT')
        for record in result['data']:
            for field in ('date', 'open', 'high', 'low', 'close', 'volume'):
                assert field in record, f"Missing field '{field}' in data record"

    @patch('stock_service.save_stock_data')
    @patch('stock_service.add_stock', return_value=8)
    @patch('stock_service.yf.Ticker')
    def test_TC15_current_price_matches_last_close(self, mock_ticker, mock_add, mock_save):
        """TC-15: current_price equals the Close of the most recent row in history."""
        inst = MagicMock()
        inst.history.return_value = self._make_fake_hist()
        inst.info = {}
        mock_ticker.return_value = inst

        result = fetch_stock_data('TSLA')
        assert result['current_price'] == 106.0


# =============================================================================
# TC-16 to TC-20  |  get_stock_info
# =============================================================================

class TestGetStockInfo:
    """Tests for the DB-read path (no live network calls)."""

    def test_TC16_valid_ticker_returns_all_keys(self, mock_db_get_stock, mock_db_get_data):
        """TC-16: Known ticker returns dict with ticker, name, stock_id, data, current_price."""
        result = get_stock_info('AAPL')
        assert 'error' not in result
        for key in ('ticker', 'name', 'stock_id', 'data', 'current_price'):
            assert key in result

    def test_TC17_unknown_ticker_returns_error(self):
        """TC-17: Ticker absent from DB returns error dict."""
        with patch('stock_service.get_stock_by_ticker', return_value=None):
            result = get_stock_info('UNKNOWN')
        assert 'error' in result
        assert 'not found' in result['error'].lower()

    def test_TC18_current_price_derived_from_last_close(self, mock_db_get_stock, mock_db_get_data):
        """TC-18: current_price equals the close of the chronologically last data record."""
        result = get_stock_info('AAPL')
        # fixture data has close values [102, 106, 109.5]; last = 109.5
        assert result['current_price'] == 109.5

    def test_TC19_data_respects_limit_parameter(self, mock_db_get_stock):
        """TC-19: Data length does not exceed the limit passed to get_stock_info."""
        big_data = [
            {'date': f'2025-01-{i:02d}', 'open': 100.0, 'high': 105.0,
             'low': 99.0, 'close': 102.0, 'volume': 1000000}
            for i in range(1, 41)
        ]
        with patch('stock_service.get_stock_data', return_value=big_data):
            result = get_stock_info('AAPL', limit=20)
        assert len(result['data']) <= 20

    def test_TC20_db_exception_returns_error(self):
        """TC-20: Gracefully returns error dict when DB raises an exception."""
        with patch('stock_service.get_stock_by_ticker', side_effect=Exception('DB down')):
            result = get_stock_info('AAPL')
        assert 'error' in result


# =============================================================================
# TC-21 to TC-25  |  get_multiple_stocks_data
# =============================================================================

class TestGetMultipleStocksData:
    """Tests for the batch ticker fetch utility."""

    def test_TC21_returns_list_for_known_tickers(self, mock_db_get_stock, mock_db_get_data):
        """TC-21: Returns a non-empty list for tickers found in the DB."""
        result = get_multiple_stocks_data(['AAPL'])
        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]['ticker'] == 'AAPL'

    def test_TC22_skips_unknown_tickers(self):
        """TC-22: Tickers not in DB are silently skipped; result list stays empty."""
        with patch('stock_service.get_stock_by_ticker', return_value=None):
            result = get_multiple_stocks_data(['NOPE', 'FAKE'])
        assert result == []

    def test_TC23_prices_list_is_floats(self, mock_db_get_stock, mock_db_get_data):
        """TC-23: 'prices' array contains only floats."""
        result = get_multiple_stocks_data(['AAPL'])
        assert all(isinstance(p, float) for p in result[0]['prices'])

    def test_TC24_mixed_valid_invalid_tickers(self, mock_db_get_data):
        """TC-24: Mixed list returns only valid entries, ignores missing ones."""
        def side_effect(ticker):
            if ticker == 'AAPL':
                return {'id': 1, 'ticker': 'AAPL', 'name': 'Apple Inc.'}
            return None

        with patch('stock_service.get_stock_by_ticker', side_effect=side_effect):
            result = get_multiple_stocks_data(['AAPL', 'FAKE'])
        assert len(result) == 1
        assert result[0]['ticker'] == 'AAPL'

    def test_TC25_empty_input_returns_empty_list(self):
        """TC-25: Empty ticker list returns empty result list."""
        result = get_multiple_stocks_data([])
        assert result == []


# =============================================================================
# TC-26 to TC-30  |  fetch_intraday_yf
# =============================================================================

class TestFetchIntradayYf:
    """Tests for the intraday yfinance fallback."""

    def _make_intraday_df(self):
        idx = pd.date_range('2025-01-01 09:30', periods=5, freq='5min')
        return pd.DataFrame({
            'Open':   [100, 101, 102, 103, 104],
            'High':   [101, 102, 103, 104, 105],
            'Low':    [99,  100, 101, 102, 103],
            'Close':  [100.5, 101.5, 102.5, 103.5, 104.5],
            'Volume': [5000, 6000, 7000, 8000, 9000],
        }, index=idx)

    @patch('stock_service.yf.Ticker')
    def test_TC26_valid_ticker_returns_data_and_price(self, mock_ticker):
        """TC-26: Valid ticker returns dict with 'data' list and 'current_price'."""
        inst = MagicMock()
        inst.history.return_value = self._make_intraday_df()
        mock_ticker.return_value = inst

        result = fetch_intraday_yf('AAPL')
        assert 'error' not in result
        assert 'data' in result
        assert 'current_price' in result

    @patch('stock_service.yf.Ticker')
    def test_TC27_empty_history_returns_error(self, mock_ticker):
        """TC-27: Returns error dict when no intraday data is available."""
        inst = MagicMock()
        inst.history.return_value = pd.DataFrame()
        mock_ticker.return_value = inst

        result = fetch_intraday_yf('AAPL')
        assert 'error' in result

    @patch('stock_service.yf.Ticker')
    def test_TC28_current_price_matches_last_record(self, mock_ticker):
        """TC-28: current_price equals the close of the last intraday record."""
        inst = MagicMock()
        inst.history.return_value = self._make_intraday_df()
        mock_ticker.return_value = inst

        result = fetch_intraday_yf('AAPL')
        assert result['current_price'] == 104.5

    @patch('stock_service.yf.Ticker')
    def test_TC29_date_format_includes_time(self, mock_ticker):
        """TC-29: Each record's 'date' field contains a time component (intraday)."""
        inst = MagicMock()
        inst.history.return_value = self._make_intraday_df()
        mock_ticker.return_value = inst

        result = fetch_intraday_yf('AAPL')
        for record in result['data']:
            assert ':' in record['date'], "Expected HH:MM:SS in intraday date string"

    @patch('stock_service.yf.Ticker')
    def test_TC30_exception_returns_error_dict(self, mock_ticker):
        """TC-30: Returns error dict when yfinance raises an unexpected exception."""
        inst = MagicMock()
        inst.history.side_effect = Exception('Network timeout')
        mock_ticker.return_value = inst

        result = fetch_intraday_yf('AAPL')
        assert 'error' in result
