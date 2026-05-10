import pytest

from fundamental_pulse.ifind_adapter import (
    IfindMcpResponseError,
    parse_ifind_quarterly_response,
)


def test_parse_ifind_quarterly_response_maps_aliases_and_converts_units():
    raw = {
        "data": [
            {
                "证券代码": "300750.SZ",
                "报告期": "2024-03-31",
                "披露日期": "2024-04-15",
                "营业收入": 79770000,
                "营业成本": 59110000,
                "归母净利润": 10510000,
                "扣非归母净利润": 9247000,
                "经营活动现金流净额": 28360000,
                "单位": "万元",
                "数据来源": "iFinD MCP",
            }
        ]
    }

    records = parse_ifind_quarterly_response(raw, ticker="300750.SZ")

    assert len(records) == 1
    assert records[0].ticker == "300750.SZ"
    assert records[0].report_period == "2024Q1"
    assert records[0].period == "2024Q1"
    assert records[0].disclosure_date == "2024-04-15"
    assert records[0].source == "iFinD MCP"
    assert records[0].unit == "CNY"
    assert records[0].revenue == 79770000 * 10000
    assert records[0].operating_cash_flow == 28360000 * 10000


def test_parse_ifind_quarterly_response_accepts_common_container_keys():
    raw = {
        "result": {
            "rows": [
                {
                    "ticker": "300750.SZ",
                    "report_period": "2024Q2",
                    "revenue": 1,
                }
            ]
        }
    }

    records = parse_ifind_quarterly_response(raw, ticker="300750.SZ")

    assert records[0].report_period == "2024Q2"
    assert records[0].revenue == 1


def test_parse_ifind_quarterly_response_sorts_and_deduplicates_by_period():
    raw = [
        {"ticker": "300750.SZ", "report_period": "2024Q2", "revenue": 2},
        {"ticker": "300750.SZ", "report_period": "2024Q1", "revenue": 1},
        {
            "ticker": "300750.SZ",
            "report_period": "2024Q2",
            "revenue": 3,
            "net_profit_parent": 1,
        },
    ]

    records = parse_ifind_quarterly_response(raw, ticker="300750.SZ")

    assert [record.report_period for record in records] == ["2024Q1", "2024Q2"]
    assert records[1].revenue == 3


def test_parse_ifind_quarterly_response_requires_financial_fields():
    raw = [{"ticker": "300750.SZ", "report_period": "2024Q1"}]

    with pytest.raises(IfindMcpResponseError, match="no revenue or profit"):
        parse_ifind_quarterly_response(raw, ticker="300750.SZ")
