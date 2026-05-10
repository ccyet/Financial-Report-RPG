from fundamental_pulse.ifind_adapter import parse_ifind_quarterly_response


def _parse_revenue(value, unit=None):
    record = {
        "ticker": "300750.SZ",
        "report_period": "2024Q1",
        "revenue": value,
    }
    if unit is not None:
        record["unit"] = unit
    return parse_ifind_quarterly_response([record], ticker="300750.SZ")[0]


def test_ifind_parser_keeps_yuan_values_unchanged():
    assert _parse_revenue(123, "元").revenue == 123


def test_ifind_parser_converts_ten_thousand_yuan_to_yuan():
    assert _parse_revenue(123, "万元").revenue == 1_230_000


def test_ifind_parser_converts_hundred_million_yuan_to_yuan():
    assert _parse_revenue(123, "亿元").revenue == 12_300_000_000


def test_ifind_parser_handles_missing_unit_without_crashing():
    record = _parse_revenue(123)

    assert record.revenue == 123
    assert record.unit == "CNY"
