from fundamental_pulse.highfreq import (
    normalize_direction,
    normalize_signal_type,
    parse_highfreq_response,
)


def test_parse_json_highfreq_response():
    raw = [
        {
            "date": "2024-04-10",
            "type": "订单",
            "name": "海外储能订单增加",
            "direction": "正面",
            "evidence": "订单披露增加",
        }
    ]

    signals = parse_highfreq_response(raw, ticker="300750.SZ")

    assert len(signals) == 1
    assert signals[0].ticker == "300750.SZ"
    assert signals[0].signal_type == "revenue"
    assert signals[0].signal_name == "海外储能订单增加"
    assert signals[0].direction == "positive"


def test_parse_unknown_signal_does_not_crash():
    raw = [{"foo": "bar"}]

    signals = parse_highfreq_response(raw, ticker="300750.SZ")

    assert len(signals) == 1
    assert signals[0].signal_type == "unknown"
    assert signals[0].direction == "unknown"


def test_parse_ifind_empty_datas_returns_empty_list():
    raw = {
        "content": [
            {
                "type": "text",
                "text": '{"code":1,"msg":"success","data":{"answer":"","datas":[]}}',
            }
        ]
    }

    signals = parse_highfreq_response(raw, ticker="300750.SZ")

    assert signals == []


def test_parse_ifind_plain_text_answer_degrades_to_unknown_signal():
    raw = {
        "content": [
            {
                "type": "text",
                "text": (
                    '{"code":1,"msg":"success",'
                    '"data":{"answer":"近90天暂无可结构化高频表格。"}}'
                ),
            }
        ]
    }

    signals = parse_highfreq_response(raw, ticker="300750.SZ")

    assert len(signals) == 1
    assert signals[0].signal_type == "unknown"
    assert signals[0].direction == "unknown"
    assert signals[0].evidence == "近90天暂无可结构化高频表格。"


def test_parse_plain_text_highfreq_response_does_not_raise():
    signals = parse_highfreq_response("近90天动力电池装机量增长。", ticker="300750.SZ")

    assert len(signals) == 1
    assert signals[0].signal_type == "revenue"
    assert signals[0].direction == "positive"


def test_parse_wide_markdown_table_infers_signal_name_and_value():
    raw = (
        "|日期|新能源汽车销量（单位：辆）|\n"
        "|---|---|\n"
        "|2026-03-31|125.2万|\n"
    )

    signals = parse_highfreq_response(raw, ticker="300750.SZ")

    assert len(signals) == 1
    assert signals[0].date.isoformat() == "2026-03-31"
    assert signals[0].signal_name == "新能源汽车销量"
    assert signals[0].signal_type == "revenue"
    assert signals[0].value == "125.2万"


def test_parse_ifind_skill_text_extracts_multiple_markdown_tables():
    raw = {
        "content": [
            {
                "type": "text",
                "text": (
                    '{"code":1,"msg":"success","data":{"text":"'
                    "# 利润表\\n\\n"
                    "| 证券代码 | 证券简称 | 日期 | 营业总收入(TTM) | 营业总成本(TTM) |\\n"
                    "|---|---|---:|---:|---:|\\n"
                    "| 300750.SZ | 宁德时代 | 20260331 | 423701834000.00 | 353902945000.00 |\\n"
                    "\\n# 现金流量表\\n\\n"
                    "| 证券代码 | 证券简称 | 日期 | 经营活动现金净流量(TTM) |\\n"
                    "|---|---|---:|---:|\\n"
                    "| 300750.SZ | 宁德时代 | 20260331 | 133219982000.00 |\\n"
                    '"}}'
                ),
            }
        ]
    }

    signals = parse_highfreq_response(raw, ticker="300750.SZ")

    assert [(signal.signal_name, signal.signal_type) for signal in signals] == [
        ("营业总收入(TTM)", "revenue"),
        ("营业总成本(TTM)", "cost"),
        ("经营活动现金净流量(TTM)", "cashflow"),
    ]
    assert {signal.direction for signal in signals} == {"unknown"}


def test_normalize_signal_type_uses_signal_name_keywords():
    assert normalize_signal_type(None, "碳酸锂原材料价格下降") == "cost"
    assert normalize_signal_type(None, "渠道库存增加") == "cashflow"
    assert normalize_signal_type(None, "产业政策延续支持") == "policy"


def test_normalize_direction_handles_chinese_and_evidence_text():
    assert normalize_direction("利好") == "positive"
    assert normalize_direction("恶化") == "negative"
    assert normalize_direction(None, "主要原材料价格下降，对成本端形成支持") == "positive"
    assert normalize_direction(None, "产品价格下降，盈利能力承压") == "negative"
