# =============================================================================
# tests/test_recommendation_service.py
# Unit tests for recommendation_service.py — Stock Price Predictor App
# Author: Srushti Tarnalle | EY GDS Testing Portfolio
#
# Run:  pytest tests/ -v --html=reports/report.html
# =============================================================================

import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from recommendation_service import generate_recommendation


# =============================================================================
# FIXTURES
# =============================================================================

@pytest.fixture
def strong_buy_daily():
    return {'percent_change': 2.5, 'confidence': 75,
            'current_price': 150.0,
            'confidence_interval': {'lower': 145.0, 'upper': 158.0}}

@pytest.fixture
def strong_sell_daily():
    return {'percent_change': -2.5, 'confidence': 70,
            'current_price': 150.0,
            'confidence_interval': {'lower': 142.0, 'upper': 155.0}}

@pytest.fixture
def neutral_daily():
    return {'percent_change': 0.1, 'confidence': 45}

@pytest.fixture
def positive_sentiment():
    return {'label': 'positive', 'score': 0.85}

@pytest.fixture
def negative_sentiment():
    return {'label': 'negative', 'score': 0.80}

@pytest.fixture
def historical_20():
    """20 days of realistic historical closes — upward trend."""
    base = 100.0
    return [{'close': base + i * 0.5} for i in range(20)]

@pytest.fixture
def historical_bearish():
    """20 days of falling closes."""
    base = 120.0
    return [{'close': base - i * 0.5} for i in range(20)]


# =============================================================================
# TC-31 to TC-38  |  Output schema & contract
# =============================================================================

class TestOutputSchema:
    """Every response must contain the required keys and correct types."""

    def test_TC31_required_keys_always_present(self):
        """TC-31: Result always contains category, score, rationale, disclaimer, inputs_used."""
        result = generate_recommendation('AAPL')
        for key in ('category', 'score', 'rationale', 'disclaimer', 'inputs_used'):
            assert key in result, f"Missing key: {key}"

    def test_TC32_category_is_valid_label(self, strong_buy_daily):
        """TC-32: Category is one of the five valid trading signals."""
        valid = {'Strong Buy', 'Buy', 'Hold', 'Sell', 'Strong Sell'}
        result = generate_recommendation('AAPL', daily_pred=strong_buy_daily)
        assert result['category'] in valid

    def test_TC33_score_is_float(self, strong_buy_daily):
        """TC-33: Score field is a float (not int, not string)."""
        result = generate_recommendation('AAPL', daily_pred=strong_buy_daily)
        assert isinstance(result['score'], float)

    def test_TC34_rationale_is_list(self, strong_buy_daily):
        """TC-34: Rationale is always a list (even if empty)."""
        result = generate_recommendation('AAPL', daily_pred=strong_buy_daily)
        assert isinstance(result['rationale'], list)

    def test_TC35_disclaimer_is_non_empty_string(self, strong_buy_daily):
        """TC-35: Disclaimer is a non-empty string on every response."""
        result = generate_recommendation('AAPL', daily_pred=strong_buy_daily)
        assert isinstance(result['disclaimer'], str)
        assert len(result['disclaimer']) > 0

    def test_TC36_timestamp_present_with_signals(self, strong_buy_daily):
        """TC-36: timestamp key is present when at least one signal is provided."""
        result = generate_recommendation('AAPL', daily_pred=strong_buy_daily)
        assert 'timestamp' in result

    def test_TC37_inputs_used_tracks_which_signals_provided(
            self, strong_buy_daily, positive_sentiment, historical_20):
        """TC-37: inputs_used correctly records which signal types were consumed."""
        result = generate_recommendation(
            'AAPL',
            daily_pred=strong_buy_daily,
            sentiment=positive_sentiment,
            historical_data=historical_20
        )
        assert result['inputs_used'].get('daily') is True
        assert result['inputs_used'].get('sentiment') is True
        assert result['inputs_used'].get('momentum') is True

    def test_TC38_no_signals_returns_hold(self):
        """TC-38: With no prediction or sentiment data, defaults to Hold."""
        result = generate_recommendation('AAPL')
        assert result['category'] == 'Hold'
        assert result['score'] == 0


# =============================================================================
# TC-39 to TC-44  |  Category classification logic
# =============================================================================

class TestCategoryClassification:

    def test_TC39_strong_buy_high_confidence(self, strong_buy_daily):
        """TC-39: High positive percent_change + high confidence → Strong Buy."""
        result = generate_recommendation('AAPL', daily_pred=strong_buy_daily)
        assert result['category'] == 'Strong Buy'

    def test_TC40_strong_sell_high_confidence(self, strong_sell_daily):
        """TC-40: High negative percent_change + high confidence → Strong Sell."""
        result = generate_recommendation('AAPL', daily_pred=strong_sell_daily)
        assert result['category'] == 'Strong Sell'

    def test_TC41_low_confidence_produces_hold(self, neutral_daily):
        """TC-41: Low confidence daily prediction should resolve to Hold."""
        result = generate_recommendation('AAPL', daily_pred=neutral_daily)
        assert result['category'] == 'Hold'

    def test_TC42_positive_sentiment_boosts_score(self, strong_buy_daily, positive_sentiment):
        """TC-42: Adding positive sentiment raises score vs daily signal alone."""
        without_sent = generate_recommendation('AAPL', daily_pred=strong_buy_daily)
        with_sent = generate_recommendation('AAPL', daily_pred=strong_buy_daily,
                                            sentiment=positive_sentiment)
        assert with_sent['score'] >= without_sent['score']

    def test_TC43_negative_sentiment_lowers_score(self, strong_buy_daily, negative_sentiment):
        """TC-43: Negative sentiment lowers the composite score."""
        without_sent = generate_recommendation('AAPL', daily_pred=strong_buy_daily)
        with_sent = generate_recommendation('AAPL', daily_pred=strong_buy_daily,
                                            sentiment=negative_sentiment)
        assert with_sent['score'] <= without_sent['score']

    def test_TC44_bullish_momentum_reflected_in_rationale(
            self, strong_buy_daily, historical_20):
        """TC-44: Bullish momentum signal appears in rationale text."""
        result = generate_recommendation(
            'AAPL', daily_pred=strong_buy_daily, historical_data=historical_20)
        momentum_mentioned = any('momentum' in r.lower() or 'bullish' in r.lower()
                                 for r in result['rationale'])
        assert momentum_mentioned


# =============================================================================
# TC-45 to TC-50  |  Limit targets & edge cases
# =============================================================================

class TestLimitTargetsAndEdgeCases:

    def test_TC45_strong_buy_includes_limit_targets_on_high_confidence(self, strong_buy_daily):
        """TC-45: Strong Buy with CF ≥ 0.6 includes limit_targets dict."""
        result = generate_recommendation('AAPL', daily_pred=strong_buy_daily)
        # CF is derived from confidence=75 → CF = 0.75, so limit_targets should appear
        assert 'limit_targets' in result
        for k in ('primary_buy', 'secondary_buy', 'stop_loss', 'take_profit'):
            assert k in result['limit_targets']

    def test_TC46_stop_loss_less_than_current_price_on_buy(self, strong_buy_daily):
        """TC-46: Stop-loss target is below current price for a Buy signal."""
        result = generate_recommendation('AAPL', daily_pred=strong_buy_daily)
        if 'limit_targets' in result:
            assert result['limit_targets']['stop_loss'] < strong_buy_daily['current_price']

    def test_TC47_take_profit_greater_than_current_price_on_buy(self, strong_buy_daily):
        """TC-47: Take-profit is above current price for a Buy signal."""
        result = generate_recommendation('AAPL', daily_pred=strong_buy_daily)
        if 'limit_targets' in result:
            assert result['limit_targets']['take_profit'] > strong_buy_daily['current_price']

    def test_TC48_error_in_daily_pred_is_ignored(self):
        """TC-48: daily_pred with 'error' key is treated as absent (no crash)."""
        bad_pred = {'error': 'Model timeout'}
        result = generate_recommendation('AAPL', daily_pred=bad_pred)
        assert 'category' in result   # should not raise

    def test_TC49_fewer_than_20_historical_points_skips_momentum(self):
        """TC-49: With < 20 historical records, momentum signal is not added."""
        short_history = [{'close': 100.0 + i} for i in range(10)]
        result = generate_recommendation('AAPL', historical_data=short_history)
        assert 'momentum' not in result['inputs_used']

    def test_TC50_score_clamped_reasonable_range(self, strong_buy_daily, positive_sentiment, historical_20):
        """TC-50: Score stays within [-1, 1] even with all bullish signals active."""
        result = generate_recommendation(
            'AAPL',
            daily_pred=strong_buy_daily,
            sentiment=positive_sentiment,
            historical_data=historical_20
        )
        assert -1.0 <= result['score'] <= 1.0
