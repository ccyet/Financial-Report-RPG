from fundamental_pulse.analysis import normalize_to_single_quarter
from fundamental_pulse.models import QuarterRecord


def test_cumulative_to_single_quarter_keeps_balance_sheet_items():
    records = [
        QuarterRecord(
            ticker="300750.SZ",
            period="2025Q1",
            is_cumulative=True,
            revenue=100,
            operating_cost=60,
            operating_cash_flow=20,
            accounts_receivable=50,
            inventory=30,
        ),
        QuarterRecord(
            ticker="300750.SZ",
            period="2025Q2",
            is_cumulative=True,
            revenue=230,
            operating_cost=150,
            operating_cash_flow=30,
            accounts_receivable=55,
            inventory=35,
        ),
    ]

    normalized = normalize_to_single_quarter(records)
    q2 = normalized[1]

    assert q2.revenue == 130
    assert q2.operating_cost == 90
    assert q2.operating_cash_flow == 10
    assert q2.accounts_receivable == 55
    assert q2.inventory == 35
    assert q2.is_cumulative is False


def test_non_cumulative_records_are_returned_as_single_quarter():
    records = [
        QuarterRecord(
            ticker="300750.SZ",
            period="2025Q1",
            revenue=100,
            operating_cash_flow=20,
            accounts_receivable=50,
        )
    ]

    normalized = normalize_to_single_quarter(records)

    assert normalized[0].revenue == 100
    assert normalized[0].operating_cash_flow == 20
    assert normalized[0].accounts_receivable == 50
    assert normalized[0].is_cumulative is False
