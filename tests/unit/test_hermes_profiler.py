from functions.hermes_profiler import app


def test_hermes_profiler():
    data = app.lambda_handler(None, "")
    assert 0 <= data["stock_price"] <= 100
