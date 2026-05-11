import json
from pathlib import Path
from urllib.parse import parse_qs

from financial_report_rpg.cninfo import CninfoClient, load_document_manifest


class FakeCninfoFetch:
    def __init__(self):
        self.downloaded_urls: list[str] = []

    def __call__(self, url: str, *, data: bytes | None = None, headers=None) -> bytes:
        if url.endswith("/new/data/szse_stock.json"):
            return json.dumps(
                {
                    "stockList": [
                        {
                            "code": "300750",
                            "orgId": "GD165627",
                            "zwjc": "宁德时代",
                            "pinyin": "ndsd",
                            "category": "A股",
                        }
                    ]
                },
                ensure_ascii=False,
            ).encode()

        if url.endswith("/new/hisAnnouncement/query"):
            params = parse_qs((data or b"").decode())
            category = params.get("category", [""])[0]
            searchkey = params.get("searchkey", [""])[0]
            if searchkey == "招股说明书":
                return _announcement_payload(
                    [
                        _announcement(
                            "1205010303",
                            "首次公开发行股票并在创业板上市<em>招股说明书</em>",
                        ),
                        _announcement("1204979996", "控股股东、实际控制人对招股说明书的确认意见"),
                    ]
                )
            if category == "category_ndbg_szsh":
                return _announcement_payload(
                    [
                        _announcement("1213000000", "2021年年度报告"),
                        _announcement("1225002214", "2025年年度报告"),
                        _announcement("1225002213", "2025年年度报告摘要"),
                    ]
                )
            if category == "category_bndbg_szsh":
                return _announcement_payload([_announcement("1224342874", "2025年半年度报告")])
            if category == "category_yjdbg_szsh":
                return _announcement_payload([_announcement("1225107946", "2026年一季度报告")])
            if category == "category_sjdbg_szsh":
                return _announcement_payload([_announcement("1224721971", "2025年三季度报告")])
            return _announcement_payload([])

        if url.startswith("https://static.cninfo.com.cn/"):
            self.downloaded_urls.append(url)
            return b"%PDF-1.7\nfake pdf\n"

        raise AssertionError(f"unexpected url: {url}")


def test_cninfo_downloads_prospectus_and_financial_reports(tmp_path: Path):
    fetch = FakeCninfoFetch()
    client = CninfoClient(fetch=fetch)

    summary = client.download_company_documents(
        "300750",
        from_year=2022,
        output_dir=tmp_path,
        today="2026-05-11",
    )

    assert summary.security.code == "300750"
    assert summary.security.name == "宁德时代"
    assert summary.prospectus_count == 1
    assert summary.financial_report_count == 4
    assert summary.failed_count == 0
    assert len(fetch.downloaded_urls) == 5

    files = sorted(path.name for path in tmp_path.rglob("*.pdf"))
    assert any("招股说明书" in name for name in files)
    assert any("2025年年度报告" in name for name in files)
    assert all("2021年年度报告" not in name for name in files)
    assert all("摘要" not in name for name in files)
    assert all("<em>" not in name for name in files)


def test_cninfo_writes_manifest_and_skips_existing_downloads(tmp_path: Path):
    first_fetch = FakeCninfoFetch()
    client = CninfoClient(fetch=first_fetch)

    first_summary = client.download_company_documents(
        "300750",
        from_year=2022,
        output_dir=tmp_path,
        today="2026-05-11",
    )
    manifest = load_document_manifest("300750", output_dir=tmp_path)

    assert first_summary.downloaded_count == 5
    assert manifest.security.code == "300750"
    assert manifest.security.name == "宁德时代"
    assert len(manifest.documents) == 5
    assert {doc.report_type for doc in manifest.documents} == {
        "招股说明书",
        "年度报告",
        "半年度报告",
        "一季度报告",
        "三季度报告",
    }
    assert any(
        doc.report_year == 2025 and doc.file_name.endswith(".pdf") for doc in manifest.documents
    )

    second_fetch = FakeCninfoFetch()
    second_client = CninfoClient(fetch=second_fetch)
    second_summary = second_client.download_company_documents(
        "300750",
        from_year=2022,
        output_dir=tmp_path,
        today="2026-05-11",
    )

    assert second_summary.downloaded_count == 0
    assert second_summary.skipped_count == 5
    assert second_fetch.downloaded_urls == []


def _announcement_payload(items: list[dict]) -> bytes:
    return json.dumps(
        {
            "announcements": items,
            "hasMore": False,
            "totalpages": 1,
            "totalAnnouncement": len(items),
        },
        ensure_ascii=False,
    ).encode()


def _announcement(announcement_id: str, title: str) -> dict:
    return {
        "secCode": "300750",
        "secName": "宁德时代",
        "orgId": "GD165627",
        "announcementId": announcement_id,
        "announcementTitle": title,
        "announcementTime": 1747008926000,
        "adjunctUrl": f"finalpage/2025-05-12/{announcement_id}.PDF",
        "adjunctType": "PDF",
    }
