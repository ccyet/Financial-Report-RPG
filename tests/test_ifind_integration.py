import os

import pytest

from fundamental_pulse.ifind_adapter import IfindMcpClient, IfindMcpConfig


@pytest.mark.skipif(
    os.getenv("RUN_IFIND_INTEGRATION") != "1",
    reason="requires real iFinD MCP credentials",
)
def test_ifind_integration_quarterly():
    client = IfindMcpClient(config=IfindMcpConfig.from_sources())

    records = client.query_quarterly_financials("300750.SZ", "2024Q1", "2024Q2")

    assert records
    assert records[0].report_period
    assert any(
        record.revenue is not None
        or record.net_profit_parent is not None
        or record.net_profit_deducted is not None
        for record in records
    )
