from fundamental_pulse.ifind_adapter import normalize_report_period


def test_normalize_report_period_from_dash_date():
    assert normalize_report_period("2024-03-31") == "2024Q1"


def test_normalize_report_period_from_slash_date():
    assert normalize_report_period("2024/06/30") == "2024Q2"


def test_normalize_report_period_from_chinese_third_quarter_report():
    assert normalize_report_period("2024年三季报") == "2024Q3"


def test_normalize_report_period_from_chinese_annual_report():
    assert normalize_report_period("2024年报") == "2024Q4"
