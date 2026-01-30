# backend/app.py
import os
import threading
import time
import traceback

from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit

# local modules
from database import init_db, get_stock_by_ticker
from stock_service import (
    fetch_stock_data,
    get_stock_info,
    get_multiple_stocks_data,
    get_canonical_current_price,
)
from sentiment_service import analyze_sentiment, get_sentiment_info
from clustering_service import (
    analyze_stock_cluster,
    get_cluster_data,
    calculate_correlation_matrix,
)
from gnn_model import predict_stock_price, get_prediction_info
from alphavantage_service import fetch_intraday_data, fetch_daily_data, get_company_overview
from time_prediction_model import predict_with_confidence_interval, load_correction_model
from recommendation_service import generate_recommendation
import yfinance as yf

# -------------------------
# Flask + SocketIO setup
# -------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SESSION_SECRET", "dev-secret-key-change-in-production")
CORS(app)
# use threading mode to match your current setup
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

# -------------------------
# Initialize DB and models
# -------------------------
init_db()

# Load optional correction model once at startup (if available)
# load_correction_model() is implemented in time_prediction_model.py (safe to return None)
try:
    correction_model = load_correction_model()
    if correction_model is not None:
        print("Correction model loaded and ready.")
    else:
        print("No correction model found or failed to load (proceeding without).")
except Exception as e:
    correction_model = None
    print("Error loading correction model:", e)

# -------------------------
# HTTP endpoints
# -------------------------
@app.route("/health", methods=["GET"])
def health_check():
    return jsonify({"status": "healthy", "service": "Stock Prediction API", "version": "1.0.0"}), 200


@app.route("/add-stock", methods=["POST"])
def add_stock_endpoint():
    try:
        data = request.get_json()
        if not data or "ticker" not in data:
            return jsonify({"error": "Ticker symbol is required"}), 400

        ticker = data["ticker"].upper()
        existing_stock = get_stock_by_ticker(ticker)
        if existing_stock:
            return (
                jsonify(
                    {
                        "message": f"Stock {ticker} already exists",
                        "ticker": ticker,
                        "stock_id": existing_stock["id"],
                    }
                ),
                200,
            )

        result = fetch_stock_data(ticker)
        if "error" in result:
            return jsonify(result), 400

        return jsonify({"message": f"Stock {ticker} added successfully", "data": result}), 201

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/predict", methods=["POST"])
def predict_endpoint():
    """
    Main prediction endpoint — returns:
      - canonical current price (single source of truth)
      - gnn/top-level prediction (prediction_result)
      - time-specific predictions (5_min, 1_hour, next_day) using predict_with_confidence_interval
      - sentiment, cluster, correlation, recommendation
    Important: each time-prediction receives the correction_model loaded at startup to keep results consistent.
    """
    try:
        data = request.get_json()
        if not data or "ticker" not in data:
            return jsonify({"error": "Ticker symbol is required"}), 400

        ticker = data["ticker"].upper()
        tickers_for_correlation = data.get("tickers", [ticker])

        stock_record = get_stock_by_ticker(ticker)
        if not stock_record:
            fetch_result = fetch_stock_data(ticker)
            if "error" in fetch_result:
                return jsonify(fetch_result), 400
            stock_record = get_stock_by_ticker(ticker)

        stock_id = stock_record["id"]
        stock_info = get_stock_info(ticker)
        if "error" in stock_info:
            return jsonify(stock_info), 400

        # canonical current price (prefer get_canonical_current_price)
        canonical_price = get_canonical_current_price(stock_info)
        if canonical_price is None:
            canonical_price = stock_info.get("current_price")

        # compute sentiment & clusters
        sentiment_result = analyze_sentiment(ticker, stock_id)
        cluster_result = analyze_stock_cluster(ticker, stock_id, tickers_for_correlation)

        # GNN prediction (keep existing signature)
        prediction_result = predict_stock_price(
            ticker, stock_id, stock_info.get("data", []), cluster_result.get("correlation", {})
        )
        if isinstance(prediction_result, dict):
            # Attach canonical price so frontend has a single source of truth
            prediction_result["current_price"] = canonical_price

        # correlation matrix across requested tickers
        stocks_data = get_multiple_stocks_data(tickers_for_correlation)
        correlation_matrix = calculate_correlation_matrix({s["ticker"]: s["prices"] for s in stocks_data})

        # time-specific predictions — pass correction_model so they are consistent
        five_min_pred = None
        hourly_pred = None
        daily_pred = None

        # fetch intraday 1min
        try:
            intraday_1min_result = fetch_intraday_data(ticker, interval="1min")
            if "error" in intraday_1min_result:
                intraday_1min_result = {"data": stock_info.get("data", [])[-30:], "current_price": stock_info.get("current_price")}
            five_min_pred = predict_with_confidence_interval(
                intraday_1min_result.get("data", []), "5_min", correction_model=correction_model
            )
            if isinstance(five_min_pred, dict):
                five_min_pred["current_price"] = canonical_price
        except Exception:
            five_min_pred = None

        # fetch intraday 5min for 1-hour pred
        try:
            intraday_5min_result = fetch_intraday_data(ticker, interval="5min")
            if "error" in intraday_5min_result:
                intraday_5min_result = {"data": stock_info.get("data", []), "current_price": stock_info.get("current_price")}
            hourly_pred = predict_with_confidence_interval(
                intraday_5min_result.get("data", []), "1_hour", correction_model=correction_model
            )
            if isinstance(hourly_pred, dict):
                hourly_pred["current_price"] = canonical_price
        except Exception:
            hourly_pred = None

        # daily prediction
        try:
            daily_result = fetch_daily_data(ticker)
            if "error" in daily_result:
                daily_result = {"data": stock_info.get("data", []), "current_price": stock_info.get("current_price")}
            daily_pred = predict_with_confidence_interval(daily_result.get("data", []), "next_day", correction_model=correction_model)
            if isinstance(daily_pred, dict):
                daily_pred["current_price"] = canonical_price
        except Exception:
            daily_pred = None

        recommendation = generate_recommendation(
            ticker,
            five_min_pred=five_min_pred,
            hourly_pred=hourly_pred,
            daily_pred=daily_pred,
            sentiment=sentiment_result,
            historical_data=stock_info.get("data", []),
        )

        return (
            jsonify(
                {
                    "ticker": ticker,
                    "stock_info": {"name": stock_info.get("name"), "current_price": canonical_price, "data": stock_info.get("data", [])[-30:]},
                    "prediction": prediction_result,
                    "sentiment": sentiment_result,
                    "cluster": {
                        "cluster_id": cluster_result.get("cluster_id"),
                        "similar_stocks": cluster_result.get("similar_stocks", []),
                        "correlation": cluster_result.get("correlation", {}),
                    },
                    "correlation_matrix": correlation_matrix,
                    "time_predictions": {"5_min": five_min_pred, "1_hour": hourly_pred, "next_day": daily_pred},
                    "recommendation": recommendation,
                }
            ),
            200,
        )

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/stock/<ticker>", methods=["GET"])
def get_stock_endpoint(ticker):
    try:
        ticker = ticker.upper()
        stock_record = get_stock_by_ticker(ticker)
        if not stock_record:
            return jsonify({"error": f"Stock {ticker} not found"}), 404

        stock_id = stock_record["id"]
        stock_info = get_stock_info(ticker)
        sentiment = get_sentiment_info(stock_id)
        cluster = get_cluster_data(stock_id, ticker)
        prediction = get_prediction_info(stock_id)

        return jsonify({"ticker": ticker, "stock_info": stock_info, "sentiment": sentiment, "cluster": cluster, "prediction": prediction}), 200

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/stocks", methods=["GET"])
def list_stocks():
    try:
        from database import get_db_connection

        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT ticker, name FROM stocks ORDER BY ticker")
            stocks = cursor.fetchall()
            return jsonify({"stocks": [{"ticker": s["ticker"], "name": s["name"]} for s in stocks]}), 200
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# ------- Shorter predict endpoints that use the same correction_model -------
@app.route("/predict-5min", methods=["POST"])
def predict_5min_endpoint():
    try:
        data = request.get_json()
        if not data or "ticker" not in data:
            return jsonify({"error": "Ticker symbol is required"}), 400

        ticker = data["ticker"].upper()
        intraday_result = fetch_intraday_data(ticker, interval="1min")
        source = "alphavantage"
        if "error" in intraday_result:
            source = "yfinance"
            stock_record = get_stock_by_ticker(ticker)
            if not stock_record:
                fetch_result = fetch_stock_data(ticker)
                if "error" in fetch_result:
                    return jsonify({"error": "Failed to fetch stock data"}), 400
                stock_record = get_stock_by_ticker(ticker)

            stock_info = get_stock_info(ticker)
            if "error" in stock_info or "data" not in stock_info:
                return jsonify({"error": "No historical data available"}), 400

            intraday_result = {"data": stock_info["data"][-30:], "current_price": stock_info.get("current_price")}

        prediction = predict_with_confidence_interval(intraday_result.get("data", []), "5_min", correction_model=correction_model)
        if isinstance(prediction, dict):
            canonical_price = get_canonical_current_price(intraday_result) or intraday_result.get("current_price")
            prediction["current_price"] = canonical_price
        else:
            canonical_price = get_canonical_current_price(intraday_result) or intraday_result.get("current_price")

        if "error" in prediction:
            return jsonify(prediction), 400

        return jsonify({"ticker": ticker, "prediction": prediction, "data_source": source, "current_price": canonical_price, "message": "5-minute prediction generated successfully"}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/predict-hourly", methods=["POST"])
def predict_hourly_endpoint():
    try:
        data = request.get_json()
        if not data or "ticker" not in data:
            return jsonify({"error": "Ticker symbol is required"}), 400

        ticker = data["ticker"].upper()
        intraday_result = fetch_intraday_data(ticker, interval="5min")
        source = "alphavantage"
        if "error" in intraday_result:
            source = "yfinance"
            stock_record = get_stock_by_ticker(ticker)
            if not stock_record:
                fetch_result = fetch_stock_data(ticker)
                if "error" in fetch_result:
                    return jsonify({"error": "Failed to fetch stock data"}), 400
                stock_record = get_stock_by_ticker(ticker)

            stock_info = get_stock_info(ticker)
            if "error" in stock_info or "data" not in stock_info:
                return jsonify({"error": "No historical data available"}), 400

            intraday_result = {"data": stock_info["data"], "current_price": stock_info.get("current_price")}

        prediction = predict_with_confidence_interval(intraday_result.get("data", []), "1_hour", correction_model=correction_model)
        canonical_price = get_canonical_current_price(intraday_result) or intraday_result.get("current_price")
        if isinstance(prediction, dict):
            prediction["current_price"] = canonical_price

        if "error" not in prediction:
            stock_record = get_stock_by_ticker(ticker)
            if stock_record and prediction.get("predicted_price", 0) > 0:
                from database import save_prediction

                save_prediction(stock_record["id"], prediction.get("prediction_time", ""), prediction["predicted_price"], prediction["confidence"], "1_hour")

        return jsonify({"ticker": ticker, "source": source, "current_price": canonical_price, "prediction": prediction}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/predict-daily", methods=["POST"])
def predict_daily_endpoint():
    try:
        data = request.get_json()
        if not data or "ticker" not in data:
            return jsonify({"error": "Ticker symbol is required"}), 400

        ticker = data["ticker"].upper()
        daily_result = fetch_daily_data(ticker)
        source = "alphavantage"
        if "error" in daily_result:
            source = "yfinance"
            stock_record = get_stock_by_ticker(ticker)
            if not stock_record:
                fetch_result = fetch_stock_data(ticker)
                if "error" in fetch_result:
                    return jsonify({"error": "Failed to fetch stock data"}), 400
                stock_record = get_stock_by_ticker(ticker)

            stock_info = get_stock_info(ticker)
            if "error" in stock_info or "data" not in stock_info:
                return jsonify({"error": "No historical data available"}), 400

            daily_result = {"data": stock_info["data"], "current_price": stock_info.get("current_price")}

        prediction = predict_with_confidence_interval(daily_result.get("data", []), "next_day", correction_model=correction_model)
        canonical_price = get_canonical_current_price(daily_result) or daily_result.get("current_price")
        if isinstance(prediction, dict):
            prediction["current_price"] = canonical_price

        if "error" not in prediction:
            stock_record = get_stock_by_ticker(ticker)
            if stock_record and prediction.get("predicted_price", 0) > 0:
                from database import save_prediction

                save_prediction(stock_record["id"], prediction.get("prediction_date", ""), prediction["predicted_price"], prediction["confidence"], "next_day")

        return jsonify({"ticker": ticker, "source": source, "current_price": canonical_price, "prediction": prediction}), 200

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/company-overview/<ticker>", methods=["GET"])
def company_overview_endpoint(ticker):
    try:
        ticker = ticker.upper()
        overview = get_company_overview(ticker)
        return jsonify(overview), 200
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


# -------------------------
# WebSocket / real-time price broadcasting
# -------------------------
tracked_stocks = set()
price_update_thread = None
stop_updates = False


def fetch_realtime_price(ticker):
    """
    Use yfinance to fetch latest intraday close and compute change vs previous close.
    Keep this function resilient and return None on errors.
    """
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="1d")
        if not hist.empty:
            current_price = float(hist["Close"].iloc[-1])
            prev_close = float(info.get("previousClose", current_price))
            change = current_price - prev_close
            change_percent = (change / prev_close * 100) if prev_close else 0.0
            return {"ticker": ticker, "price": current_price, "change": change, "change_percent": change_percent, "timestamp": time.time()}
    except Exception as e:
        print(f"Error fetching price for {ticker}: {e}")
    return None


def broadcast_price_updates():
    global stop_updates
    print("Starting real-time price update thread...")
    while not stop_updates:
        if tracked_stocks:
            for t in list(tracked_stocks):
                try:
                    price_data = fetch_realtime_price(t)
                    if price_data:
                        # guarded emit to avoid server write-after-close exceptions
                        try:
                            socketio.emit("price_update", price_data, namespace="/")
                        except Exception:
                            # log but continue; don't let an exception kill the thread
                            print("Emit failed for", t, "-", traceback.format_exc())
                except Exception:
                    print("Error in broadcast loop for", t, traceback.format_exc())
        time.sleep(10)


@socketio.on("connect")
def handle_connect():
    print("Client connected")
    # Send immediate updates for any tracked stocks (best-effort)
    try:
        for t in list(tracked_stocks):
            try:
                price_data = fetch_realtime_price(t)
                if price_data:
                    emit("price_update", price_data)
            except Exception:
                continue
    except Exception:
        print("Error during connect handler:", traceback.format_exc())


@socketio.on("disconnect")
def handle_disconnect():
    print("Client disconnected")


@socketio.on("track_stock")
@socketio.on("track_stock")
def handle_track_stock(data):
    try:
        ticker = (data.get("ticker") or "").upper()
        if not ticker:
            return
        # add to tracked set (idempotent)
        if ticker not in tracked_stocks:
            tracked_stocks.add(ticker)
            print("Now tracking:", ticker)
            # emit an immediate price update (best-effort)
            try:
                price_data = fetch_realtime_price(ticker)
                if price_data:
                    # send to all clients on namespace; avoid broken 'broadcast' kwarg
                    socketio.emit("price_update", price_data, namespace="/")
            except Exception:
                print("Immediate emit failed:", traceback.format_exc())

        # confirm to caller
        emit("tracking_confirmed", {"ticker": ticker})
    except Exception:
        print("Error in track_stock:", traceback.format_exc())


@socketio.on("untrack_stock")
def handle_untrack_stock(data):
    try:
        ticker = (data.get("ticker") or "").upper()
        if not ticker:
            return
        if ticker in tracked_stocks:
            tracked_stocks.remove(ticker)
            print("Stopped tracking:", ticker)
            emit("tracking_stopped", {"ticker": ticker})
    except Exception:
        print("Error in untrack_stock:", traceback.format_exc())


# -------------------------
# Entrypoint
# -------------------------
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 3000))
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() == "true"

    price_update_thread = threading.Thread(target=broadcast_price_updates, daemon=True)
    price_update_thread.start()

    # Run socketio — keep allow_unsafe_werkzeug to match your prior environment if necessary.
    socketio.run(app, host="0.0.0.0", port=port, debug=debug_mode, allow_unsafe_werkzeug=True)
