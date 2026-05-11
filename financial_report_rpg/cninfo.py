from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import Request, urlopen

DEFAULT_CNINFO_REPORT_DIR = Path(".local/cninfo_reports")
CNINFO_STOCK_LIST_URL = "https://www.cninfo.com.cn/new/data/szse_stock.json"
CNINFO_QUERY_URL = "https://www.cninfo.com.cn/new/hisAnnouncement/query"
CNINFO_STATIC_BASE_URL = "https://static.cninfo.com.cn"
DEFAULT_FROM_YEAR = 2022

FINANCIAL_REPORT_CATEGORIES = (
    "category_ndbg_szsh",
    "category_bndbg_szsh",
    "category_yjdbg_szsh",
    "category_sjdbg_szsh",
)
REPORT_TITLE_KEYWORDS = (
    "年度报告",
    "半年度报告",
    "一季度报告",
    "第一季度报告",
    "三季度报告",
    "第三季度报告",
)
REPORT_EXCLUDED_KEYWORDS = (
    "摘要",
    "英文",
    "取消",
    "提示性公告",
    "更正公告",
    "审计报告",
)
PROSPECTUS_EXCLUDED_KEYWORDS = (
    "确认意见",
    "关于",
    "提示性公告",
    "核查意见",
    "声明",
)

Fetch = Callable[..., bytes]


class CninfoError(RuntimeError):
    pass


@dataclass(frozen=True)
class CninfoSecurity:
    code: str
    org_id: str
    name: str


@dataclass(frozen=True)
class CninfoAnnouncement:
    announcement_id: str
    title: str
    adjunct_url: str
    announcement_time: int
    kind: str


@dataclass(frozen=True)
class CninfoSavedFile:
    announcement: CninfoAnnouncement
    path: Path
    status: str


@dataclass(frozen=True)
class CninfoFailure:
    announcement: CninfoAnnouncement
    error: str


@dataclass(frozen=True)
class CninfoDocumentEntry:
    company_code: str
    company_name: str
    announcement_id: str
    title: str
    report_year: int | None
    report_type: str
    file_name: str
    status: str


@dataclass(frozen=True)
class CninfoDocumentManifest:
    security: CninfoSecurity
    from_year: int
    to_date: str
    documents: list[CninfoDocumentEntry]

    @property
    def prospectus_count(self) -> int:
        return sum(1 for document in self.documents if document.report_type == "招股说明书")

    @property
    def financial_report_count(self) -> int:
        return len(self.documents) - self.prospectus_count


@dataclass(frozen=True)
class CninfoDownloadSummary:
    security: CninfoSecurity
    from_year: int
    to_date: str
    prospectuses: list[CninfoAnnouncement]
    financial_reports: list[CninfoAnnouncement]
    saved_files: list[CninfoSavedFile]
    failures: list[CninfoFailure]

    @property
    def prospectus_count(self) -> int:
        return len(self.prospectuses)

    @property
    def financial_report_count(self) -> int:
        return len(self.financial_reports)

    @property
    def downloaded_count(self) -> int:
        return sum(1 for item in self.saved_files if item.status == "downloaded")

    @property
    def skipped_count(self) -> int:
        return sum(1 for item in self.saved_files if item.status == "exists")

    @property
    def failed_count(self) -> int:
        return len(self.failures)


class CninfoClient:
    def __init__(self, *, fetch: Fetch | None = None):
        self._fetch = fetch or _default_fetch

    def ping(self) -> None:
        payload = self._fetch_json(CNINFO_STOCK_LIST_URL)
        if not isinstance(payload.get("stockList"), list):
            raise CninfoError("巨潮网证券列表返回格式异常")

    def download_company_documents(
        self,
        company: str,
        *,
        from_year: int = DEFAULT_FROM_YEAR,
        output_dir: str | Path = DEFAULT_CNINFO_REPORT_DIR,
        today: str | date | None = None,
    ) -> CninfoDownloadSummary:
        if from_year < 1990:
            raise CninfoError("起始年份过早，请使用 1990 年之后的年份")

        to_date = _date_label(today)
        security = self.resolve_security(company)
        prospectuses = self.find_prospectuses(security, to_date=to_date)
        financial_reports = self.find_financial_reports(
            security,
            from_year=from_year,
            to_date=to_date,
        )
        announcements = _dedupe_announcements([*prospectuses, *financial_reports])
        if not announcements:
            raise CninfoError(f"未在巨潮网找到 {security.name}（{security.code}）的可下载财报资料")

        company_dir = Path(output_dir) / f"{security.code}_{_safe_filename(security.name)}"
        company_dir.mkdir(parents=True, exist_ok=True)
        existing_documents = {
            document.announcement_id: document
            for document in _load_manifest_from_path(_manifest_path(company_dir)).documents
        }

        saved_files: list[CninfoSavedFile] = []
        failures: list[CninfoFailure] = []
        manifest_documents: dict[str, CninfoDocumentEntry] = dict(existing_documents)
        for announcement in announcements:
            existing_document = existing_documents.get(announcement.announcement_id)
            file_name = (
                existing_document.file_name
                if existing_document
                else _announcement_filename(announcement)
            )
            target = company_dir / file_name
            if target.exists() and target.stat().st_size > 0:
                saved_files.append(CninfoSavedFile(announcement, target, "exists"))
                manifest_documents[announcement.announcement_id] = _document_entry(
                    security, announcement, file_name=file_name, status="exists"
                )
                continue
            try:
                content = self._fetch(
                    _download_url(announcement.adjunct_url),
                    headers=_download_headers(),
                )
                if b"%PDF" not in content[:32]:
                    raise CninfoError("下载内容不是 PDF")
                target.write_bytes(content)
                saved_files.append(CninfoSavedFile(announcement, target, "downloaded"))
                manifest_documents[announcement.announcement_id] = _document_entry(
                    security, announcement, file_name=file_name, status="downloaded"
                )
            except Exception as exc:  # noqa: BLE001
                failures.append(CninfoFailure(announcement, str(exc)))
                manifest_documents[announcement.announcement_id] = _document_entry(
                    security, announcement, file_name=file_name, status="failed"
                )

        _save_manifest(
            company_dir,
            CninfoDocumentManifest(
                security=security,
                from_year=from_year,
                to_date=to_date,
                documents=sorted(
                    manifest_documents.values(),
                    key=lambda document: (
                        document.report_year or 0,
                        document.report_type,
                        document.title,
                    ),
                ),
            ),
        )

        return CninfoDownloadSummary(
            security=security,
            from_year=from_year,
            to_date=to_date,
            prospectuses=prospectuses,
            financial_reports=financial_reports,
            saved_files=saved_files,
            failures=failures,
        )

    def resolve_security(self, company: str) -> CninfoSecurity:
        query = company.strip()
        if not query:
            raise CninfoError("上市公司代码或简称不能为空")

        payload = self._fetch_json(CNINFO_STOCK_LIST_URL)
        securities = payload.get("stockList")
        if not isinstance(securities, list):
            raise CninfoError("巨潮网证券列表返回格式异常")

        exact_matches = [
            item for item in securities if item.get("code") == query or item.get("zwjc") == query
        ]
        matches = exact_matches or [
            item
            for item in securities
            if query.lower() == str(item.get("pinyin", "")).lower()
            or query in str(item.get("zwjc", ""))
        ]
        if not matches:
            raise CninfoError(f"未找到上市公司：{query}")
        if len(matches) > 1:
            candidates = "、".join(
                f"{item.get('zwjc')}({item.get('code')})" for item in matches[:5]
            )
            raise CninfoError(f"上市公司匹配不唯一：{candidates}")

        item = matches[0]
        code = str(item.get("code") or "").strip()
        org_id = str(item.get("orgId") or "").strip()
        name = str(item.get("zwjc") or "").strip()
        if not code or not org_id or not name:
            raise CninfoError("巨潮网证券列表缺少代码、机构 ID 或简称")
        return CninfoSecurity(code=code, org_id=org_id, name=name)

    def find_prospectuses(
        self,
        security: CninfoSecurity,
        *,
        to_date: str,
    ) -> list[CninfoAnnouncement]:
        announcements = self._query_announcements(
            security,
            searchkey="招股说明书",
            se_date=f"1990-01-01~{to_date}",
            kind="prospectus",
        )
        return [item for item in announcements if _is_prospectus(item.title)]

    def find_financial_reports(
        self,
        security: CninfoSecurity,
        *,
        from_year: int,
        to_date: str,
    ) -> list[CninfoAnnouncement]:
        reports: list[CninfoAnnouncement] = []
        se_date = f"{from_year}-01-01~{to_date}"
        for category in FINANCIAL_REPORT_CATEGORIES:
            reports.extend(
                self._query_announcements(
                    security,
                    category=category,
                    se_date=se_date,
                    kind="financial_report",
                )
            )
        return [
            item
            for item in _dedupe_announcements(reports)
            if _is_financial_report(item.title, from_year=from_year)
        ]

    def _query_announcements(
        self,
        security: CninfoSecurity,
        *,
        se_date: str,
        kind: str,
        category: str = "",
        searchkey: str = "",
    ) -> list[CninfoAnnouncement]:
        announcements: list[CninfoAnnouncement] = []
        for page_num in range(1, 51):
            payload = self._fetch_json(
                CNINFO_QUERY_URL,
                data={
                    "pageNum": str(page_num),
                    "pageSize": "30",
                    "column": "szse",
                    "tabName": "fulltext",
                    "plate": "",
                    "stock": f"{security.code},{security.org_id}",
                    "searchkey": searchkey,
                    "secid": "",
                    "category": category,
                    "trade": "",
                    "seDate": se_date,
                    "sortName": "",
                    "sortType": "",
                    "isHLtitle": "true",
                },
            )
            raw_items = payload.get("announcements") or []
            if not isinstance(raw_items, list):
                raise CninfoError("巨潮网公告列表返回格式异常")
            announcements.extend(_announcement_from_payload(item, kind) for item in raw_items)

            total_pages = int(payload.get("totalpages") or 0)
            has_more = bool(payload.get("hasMore"))
            if not has_more and (not total_pages or page_num >= total_pages):
                break
            if total_pages and page_num >= total_pages:
                break
        return announcements

    def _fetch_json(self, url: str, *, data: dict[str, str] | None = None) -> dict[str, Any]:
        body = urlencode(data).encode() if data is not None else None
        try:
            raw = self._fetch(url, data=body, headers=_query_headers())
            payload = json.loads(raw.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise CninfoError(f"巨潮网请求失败：{url}") from exc
        if not isinstance(payload, dict):
            raise CninfoError("巨潮网返回格式异常")
        return payload


def load_document_manifest(
    company: str,
    *,
    output_dir: str | Path = DEFAULT_CNINFO_REPORT_DIR,
) -> CninfoDocumentManifest:
    query = company.strip()
    if not query:
        raise CninfoError("上市公司代码或简称不能为空")
    matches: list[CninfoDocumentManifest] = []
    for manifest_path in Path(output_dir).glob("*/manifest.json"):
        manifest = _load_manifest_from_path(manifest_path)
        if manifest.security.code == query or manifest.security.name == query:
            matches.append(manifest)
    if not matches:
        raise CninfoError(f"本地资料背包未找到：{query}")
    if len(matches) > 1:
        candidates = "、".join(f"{item.security.name}({item.security.code})" for item in matches)
        raise CninfoError(f"本地资料背包匹配不唯一：{candidates}")
    return matches[0]


def _save_manifest(company_dir: Path, manifest: CninfoDocumentManifest) -> None:
    payload = {
        "company_code": manifest.security.code,
        "company_name": manifest.security.name,
        "org_id": manifest.security.org_id,
        "from_year": manifest.from_year,
        "to_date": manifest.to_date,
        "documents": [
            {
                "company_code": document.company_code,
                "company_name": document.company_name,
                "announcement_id": document.announcement_id,
                "title": document.title,
                "report_year": document.report_year,
                "report_type": document.report_type,
                "file_name": document.file_name,
                "status": document.status,
            }
            for document in manifest.documents
        ],
    }
    _manifest_path(company_dir).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _load_manifest_from_path(path: Path) -> CninfoDocumentManifest:
    if not path.exists():
        return CninfoDocumentManifest(
            security=CninfoSecurity(code="", org_id="", name=""),
            from_year=DEFAULT_FROM_YEAR,
            to_date="",
            documents=[],
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CninfoError("资料清单格式异常") from exc
    if not isinstance(payload, dict):
        raise CninfoError("资料清单格式异常")
    security = CninfoSecurity(
        code=_manifest_string(payload.get("company_code"), "company_code"),
        org_id=_manifest_string(payload.get("org_id"), "org_id"),
        name=_manifest_string(payload.get("company_name"), "company_name"),
    )
    documents_payload = payload.get("documents") or []
    if not isinstance(documents_payload, list):
        raise CninfoError("资料清单格式异常")
    documents = [_document_entry_from_payload(item) for item in documents_payload]
    return CninfoDocumentManifest(
        security=security,
        from_year=_manifest_int(payload.get("from_year"), "from_year"),
        to_date=_manifest_string(payload.get("to_date"), "to_date"),
        documents=documents,
    )


def _document_entry_from_payload(payload: Any) -> CninfoDocumentEntry:
    if not isinstance(payload, dict):
        raise CninfoError("资料清单格式异常")
    report_year = payload.get("report_year")
    if report_year is not None and not isinstance(report_year, int):
        raise CninfoError("资料清单格式异常")
    return CninfoDocumentEntry(
        company_code=_manifest_string(payload.get("company_code"), "documents.company_code"),
        company_name=_manifest_string(payload.get("company_name"), "documents.company_name"),
        announcement_id=_manifest_string(
            payload.get("announcement_id"), "documents.announcement_id"
        ),
        title=_manifest_string(payload.get("title"), "documents.title"),
        report_year=report_year,
        report_type=_manifest_string(payload.get("report_type"), "documents.report_type"),
        file_name=_manifest_string(payload.get("file_name"), "documents.file_name"),
        status=_manifest_string(payload.get("status"), "documents.status"),
    )


def _manifest_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str):
        raise CninfoError(f"资料清单字段异常：{field_name}")
    return value


def _manifest_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int):
        raise CninfoError(f"资料清单字段异常：{field_name}")
    return value


def _manifest_path(company_dir: Path) -> Path:
    return company_dir / "manifest.json"


def _default_fetch(url: str, *, data: bytes | None = None, headers=None) -> bytes:
    request = Request(url, data=data, headers=headers or {})
    with urlopen(request, timeout=30) as response:
        return response.read()


def _query_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search",
        "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    }


def _download_headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.cninfo.com.cn/",
    }


def _announcement_from_payload(payload: dict[str, Any], kind: str) -> CninfoAnnouncement:
    adjunct_url = str(payload.get("adjunctUrl") or "").strip()
    announcement_id = str(payload.get("announcementId") or "").strip()
    title = _clean_title(str(payload.get("announcementTitle") or "").strip())
    if not adjunct_url or not announcement_id or not title:
        raise CninfoError("巨潮网公告缺少标题、公告 ID 或附件地址")
    return CninfoAnnouncement(
        announcement_id=announcement_id,
        title=title,
        adjunct_url=adjunct_url,
        announcement_time=int(payload.get("announcementTime") or 0),
        kind=kind,
    )


def _document_entry(
    security: CninfoSecurity,
    announcement: CninfoAnnouncement,
    *,
    file_name: str,
    status: str,
) -> CninfoDocumentEntry:
    return CninfoDocumentEntry(
        company_code=security.code,
        company_name=security.name,
        announcement_id=announcement.announcement_id,
        title=announcement.title,
        report_year=_report_year(announcement.title),
        report_type=_report_type(announcement),
        file_name=file_name,
        status=status,
    )


def _clean_title(title: str) -> str:
    return unescape(re.sub(r"<[^>]+>", "", title)).strip()


def _is_prospectus(title: str) -> bool:
    return "招股说明书" in title and not any(
        keyword in title for keyword in PROSPECTUS_EXCLUDED_KEYWORDS
    )


def _is_financial_report(title: str, *, from_year: int) -> bool:
    if title.startswith("关于"):
        return False
    if any(keyword in title for keyword in REPORT_EXCLUDED_KEYWORDS):
        return False
    if not any(keyword in title for keyword in REPORT_TITLE_KEYWORDS):
        return False
    year_match = re.search(r"(20\d{2})年", title)
    return bool(year_match and int(year_match.group(1)) >= from_year)


def _report_year(title: str) -> int | None:
    year_match = re.search(r"(20\d{2})年", title)
    if not year_match:
        return None
    return int(year_match.group(1))


def _report_type(announcement: CninfoAnnouncement) -> str:
    if announcement.kind == "prospectus":
        return "招股说明书"
    title = announcement.title
    if "半年度报告" in title:
        return "半年度报告"
    if "一季度报告" in title or "第一季度报告" in title:
        return "一季度报告"
    if "三季度报告" in title or "第三季度报告" in title:
        return "三季度报告"
    if "年度报告" in title:
        return "年度报告"
    return "财报"


def _dedupe_announcements(items: list[CninfoAnnouncement]) -> list[CninfoAnnouncement]:
    seen: set[str] = set()
    deduped: list[CninfoAnnouncement] = []
    for item in sorted(items, key=lambda current: (current.announcement_time, current.title)):
        if item.announcement_id in seen:
            continue
        seen.add(item.announcement_id)
        deduped.append(item)
    return deduped


def _download_url(adjunct_url: str) -> str:
    if adjunct_url.startswith("http://") or adjunct_url.startswith("https://"):
        return adjunct_url
    return f"{CNINFO_STATIC_BASE_URL}/{adjunct_url.lstrip('/')}"


def _announcement_filename(announcement: CninfoAnnouncement) -> str:
    date_prefix = _date_from_millis(announcement.announcement_time)
    title = _safe_filename(announcement.title)
    return f"{date_prefix}_{announcement.announcement_id}_{title}.pdf"


def _safe_filename(value: str) -> str:
    cleaned = re.sub(r'[\\/:*?"<>|\s]+', "_", value).strip("._")
    return cleaned[:120] or "untitled"


def _date_from_millis(value: int) -> str:
    if value <= 0:
        return "00000000"
    return date.fromtimestamp(value / 1000).strftime("%Y%m%d")


def _date_label(value: str | date | None) -> str:
    if value is None:
        return date.today().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    return value
