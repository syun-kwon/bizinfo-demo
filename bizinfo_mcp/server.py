#!/usr/bin/env python3
"""
BizInfo MCP Server - 중소벤처기업부 기업마당 지원사업 조회 서버

이 서버는 기업마당(bizinfo.go.kr) Open API를 통해 정부 지원사업 정보를
조회하고 마크다운 리포트를 생성하는 도구를 제공합니다.
"""

import os
import re
import asyncio
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Optional, List
from enum import Enum

import httpx
from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP

# ──────────────────────────────────────────────
# 서버 초기화
# ──────────────────────────────────────────────
mcp = FastMCP("bizinfo_mcp")

# ──────────────────────────────────────────────
# 상수
# ──────────────────────────────────────────────
API_BASE_URL = "https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do"
MAX_PAGES_PER_REQUEST = 10   # generate_report while 루프 최대 페이지 수 (🔴 수정)
API_TIMEOUT = 30.0

REALM_CODES = {
    "금융": "010",
    "기술": "020",
    "인력": "030",
    "수출": "040",
    "내수": "050",
    "창업": "060",
    "경영": "070",
    "기타": "080",
}

REGION_CODES = {
    "전국": "",
    "서울": "11",
    "부산": "26",
    "대구": "27",
    "인천": "28",
    "광주": "29",
    "대전": "30",
    "울산": "31",
    "세종": "36",
    "경기": "41",
    "강원": "42",
    "충북": "43",
    "충남": "44",
    "전북": "45",
    "전남": "46",
    "경북": "47",
    "경남": "48",
    "제주": "50",
}

STATUS_CODES = {
    "진행중": "ing",
    "마감": "close",
    "전체": "",
}


# ──────────────────────────────────────────────
# Enums
# ──────────────────────────────────────────────
class RealmType(str, Enum):
    금융 = "금융"
    기술 = "기술"
    인력 = "인력"
    수출 = "수출"
    내수 = "내수"
    창업 = "창업"
    경영 = "경영"
    기타 = "기타"
    전체 = "전체"


class RegionType(str, Enum):
    전국 = "전국"
    서울 = "서울"
    부산 = "부산"
    대구 = "대구"
    인천 = "인천"
    광주 = "광주"
    대전 = "대전"
    울산 = "울산"
    세종 = "세종"
    경기 = "경기"
    강원 = "강원"
    충북 = "충북"
    충남 = "충남"
    전북 = "전북"
    전남 = "전남"
    경북 = "경북"
    경남 = "경남"
    제주 = "제주"


class StatusType(str, Enum):
    진행중 = "진행중"
    마감 = "마감"
    전체 = "전체"


# ──────────────────────────────────────────────
# Pydantic 입력 모델
# ──────────────────────────────────────────────
class SearchProgramsInput(BaseModel):
    """지원사업 목록 검색 입력 모델."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    keyword: Optional[str] = Field(
        default=None,
        description="검색 키워드 (사업명 포함 검색, 예: 'R&D', '창업', '수출')",
        min_length=1,     # 🟡 수정: 빈 문자열 입력 방지
        max_length=100,
    )
    realm: RealmType = Field(
        default=RealmType.전체,
        description="지원사업 분야: 금융/기술/인력/수출/내수/창업/경영/기타/전체",
    )
    region: RegionType = Field(
        default=RegionType.전국,
        description="지역 필터: 서울/부산/대구/인천/광주/대전/울산/세종/경기/강원/충북/충남/전북/전남/경북/경남/제주/전국",
    )
    status: StatusType = Field(
        default=StatusType.진행중,
        description="공고 상태: 진행중/마감/전체",
    )
    page: int = Field(default=1, description="페이지 번호 (1부터 시작)", ge=1)
    page_size: int = Field(default=20, description="페이지당 결과 수 (최대 100)", ge=1, le=100)


class GenerateReportInput(BaseModel):
    """신규 지원사업 리포트 생성 입력 모델."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    days: int = Field(
        default=7,
        description="최근 N일 이내 등록된 신규 공고 수집 (기본 7일)",
        ge=1,
        le=90,
    )
    realm: RealmType = Field(
        default=RealmType.전체,
        description="분야 필터 (전체 또는 특정 분야)",
    )
    region: RegionType = Field(
        default=RegionType.전국,
        description="지역 필터",
    )
    max_items: int = Field(
        default=50,
        description="리포트에 포함할 최대 공고 수",
        ge=1,
        le=200,
    )
    title: Optional[str] = Field(
        default=None,
        description="리포트 제목 (없으면 자동 생성)",
        min_length=1,     # 🟡 수정: 빈 문자열 입력 방지
        max_length=100,
    )


class ListNewProgramsInput(BaseModel):
    """신규 지원사업 목록 조회 입력 모델."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    days: int = Field(
        default=7,
        description="최근 N일 이내 등록된 공고 조회",
        ge=1,
        le=90,
    )
    realm: RealmType = Field(
        default=RealmType.전체,
        description="분야 필터",
    )
    region: RegionType = Field(
        default=RegionType.전국,
        description="지역 필터",
    )
    page_size: int = Field(
        default=30,
        description="한 페이지당 조회 건수 (여러 페이지를 순회하며 신규 공고를 수집합니다)",
        ge=1,
        le=100,
    )
    max_pages: int = Field(       # ⚪ 추가: 다중 페이지 지원
        default=3,
        description="최대 조회 페이지 수 (기본 3페이지). 신규 공고가 적을 경우 늘려보세요.",
        ge=1,
        le=10,
    )


class StatsInput(BaseModel):
    """분야별 통계 조회 입력 모델."""
    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    region: RegionType = Field(
        default=RegionType.전국,
        description="지역 필터 (기본: 전국)",
    )


# ──────────────────────────────────────────────
# 공통 유틸리티 함수
# ──────────────────────────────────────────────
def _get_auth_key() -> str:
    """환경변수에서 API 키를 가져옵니다. (🟡 수정: AUTH_KEY 전역 변수 제거)"""
    key = os.environ.get("BIZINFO_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "BIZINFO_API_KEY 환경변수가 설정되지 않았습니다. "
            "기업마당(bizinfo.go.kr)에서 API 키를 발급받아 설정해주세요."
        )
    return key


def _xml_text(el: ET.Element, tag: str) -> str:
    """XML 요소에서 태그 텍스트를 추출합니다."""
    child = el.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _parse_xml_response(xml_text: str) -> dict:
    """기업마당 XML RSS 응답을 내부 dict 구조로 변환합니다."""
    root = ET.fromstring(xml_text.strip())
    channel = root.find("channel")
    if channel is None:
        return {"jsonArray": [], "totalCount": 0}

    items = []
    total_count = 0

    for item in channel.findall("item"):
        # 신청기간 파싱: "2026-03-03 ~ 2026-04-05" → "20260303", "20260405"
        reqst_dt = _xml_text(item, "reqstBeginEndDe") or _xml_text(item, "reqstDt")
        start_de = end_de = ""
        if "~" in reqst_dt:
            parts = reqst_dt.split("~")
            start_de = parts[0].strip().replace("-", "")
            end_de = parts[1].strip().replace("-", "")

        # 등록일 파싱: "2026-03-06 14:51:46" → "20260306"
        regist_dt = _xml_text(item, "creatPnttm") or _xml_text(item, "pubDate")
        regist_de = regist_dt[:10].replace("-", "") if regist_dt else ""

        # 전체건수
        tot_cnt = _xml_text(item, "totCnt")
        if tot_cnt:
            try:
                total_count = int(tot_cnt)
            except ValueError:
                pass

        # 사업개요 HTML 태그 제거
        summary = _xml_text(item, "bsnsSumryCn") or _xml_text(item, "description")
        summary = re.sub(r"<[^>]+>", "", summary).replace("&nbsp;", " ").strip()

        items.append({
            "pblancId": _xml_text(item, "pblancId") or _xml_text(item, "seq"),
            "pblancNm": _xml_text(item, "pblancNm") or _xml_text(item, "title"),
            "pldirSportRealmLclasCodeNm": _xml_text(item, "pldirSportRealmLclasCodeNm") or _xml_text(item, "lcategory"),
            "jrsdInsttNm": _xml_text(item, "jrsdInsttNm") or _xml_text(item, "author"),
            "excInsttNm": _xml_text(item, "excInsttNm"),
            "bizSprptLclasCodeNm": "전국",
            "reqstBeginEndDe": start_de,
            "reqstCloseEndDe": end_de,
            "pblancRegistDt": regist_de,
            "pbancSttus": "",
            "detailUrl": _xml_text(item, "pblancUrl") or _xml_text(item, "link"),
            "bsnsSumryCn": summary,
        })

    return {"jsonArray": items, "totalCount": total_count}


async def _call_api(params: dict) -> dict:
    """기업마당 API를 호출하고 XML을 파싱하여 반환합니다."""
    request_params = dict(params)   # 원본 dict 변형 방지
    request_params["crtfcKey"] = _get_auth_key()

    async with httpx.AsyncClient(timeout=API_TIMEOUT) as client:
        response = await client.get(API_BASE_URL, params=request_params)
        response.raise_for_status()
        try:
            return _parse_xml_response(response.text)
        except Exception:
            raise ValueError(
                f"API 응답을 파싱할 수 없습니다. "
                f"응답 내용: {response.text[:200]}"
            )


def _handle_api_error(e: Exception) -> str:
    """API 오류를 일관된 형식으로 처리합니다."""
    if isinstance(e, ValueError):
        return f"설정/파싱 오류: {str(e)}"
    if isinstance(e, httpx.ConnectError):           # 🔴 수정: 연결 오류 명시 처리
        return "연결 오류: 기업마당 API 서버에 연결할 수 없습니다. 네트워크 상태를 확인해주세요."
    if isinstance(e, httpx.HTTPStatusError):
        status = e.response.status_code
        if status == 401:
            return "인증 오류: API 키가 유효하지 않습니다. BIZINFO_API_KEY를 확인해주세요."
        if status == 429:
            return "요청 한도 초과: 잠시 후 다시 시도해주세요."
        if status == 500:
            return "서버 오류: 기업마당 API 서버에 문제가 발생했습니다. 잠시 후 다시 시도해주세요."
        return f"API 오류 (HTTP {status}): {e.response.text[:200]}"
    if isinstance(e, httpx.TimeoutException):
        return "연결 시간 초과: 기업마당 API 서버 응답이 없습니다. 잠시 후 다시 시도해주세요."
    return f"예기치 못한 오류 ({type(e).__name__}): {str(e)}"


def _parse_program(item: dict) -> dict:
    """API 응답 항목을 정제된 딕셔너리로 변환합니다."""
    return {
        "id": item.get("pblancId", ""),
        "title": item.get("pblancNm", "제목 없음"),
        "realm": item.get("pldirSportRealmLclasCodeNm", ""),
        "agency": item.get("jrsdInsttNm", ""),
        "executing_agency": item.get("excInsttNm", ""),
        "region": item.get("bizSprptLclasCodeNm", "전국"),
        "start_date": item.get("reqstBeginEndDe", ""),
        "end_date": item.get("reqstCloseEndDe", ""),
        "registered_date": item.get("pblancRegistDt", ""),
        "status": item.get("pbancSttus", ""),
        "detail_url": item.get("detailUrl", ""),
        "summary": item.get("bsnsSumryCn", ""),
    }


def _format_date(date_str: str) -> str:
    """날짜 문자열을 읽기 좋은 형식으로 변환합니다."""
    if not date_str or len(date_str) < 8:
        return date_str or "-"
    try:
        d = datetime.strptime(date_str[:8], "%Y%m%d")
        return d.strftime("%Y년 %m월 %d일")
    except ValueError:
        return date_str


def _is_within_days(date_str: str, days: int) -> bool:
    """등록일이 최근 N일 이내인지 확인합니다."""
    if not date_str or len(date_str) < 8:
        return False
    try:
        registered = datetime.strptime(date_str[:8], "%Y%m%d")
        cutoff = datetime.now() - timedelta(days=days)
        return registered >= cutoff
    except ValueError:
        return False


def _build_search_params(
    realm: RealmType,
    region: RegionType,
    status: StatusType,
    keyword: Optional[str],
    page: int,
    page_size: int,
) -> dict:
    """API 검색 파라미터를 구성합니다."""
    params: dict = {
        "pageIndex": page,
        "pageUnit": page_size,
    }
    if realm != RealmType.전체:
        params["pldirSportRealmLclasCode"] = REALM_CODES.get(realm.value, "")
    if region != RegionType.전국:
        params["bizSprptLclasCode"] = REGION_CODES.get(region.value, "")
    if status != StatusType.전체:
        params["pbancSttus"] = STATUS_CODES.get(status.value, "")
    if keyword:
        params["pblancNm"] = keyword
    return params


# ──────────────────────────────────────────────
# MCP 도구 정의
# ──────────────────────────────────────────────

@mcp.tool(
    name="bizinfo_search_programs",
    annotations={
        "title": "기업마당 지원사업 검색",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def bizinfo_search_programs(params: SearchProgramsInput) -> str:
    """기업마당 API에서 정부 지원사업 공고를 검색합니다.

    분야(금융/기술/인력/수출/내수/창업/경영/기타), 지역, 공고 상태(진행중/마감),
    키워드를 조합하여 원하는 지원사업 목록을 조회합니다.
    페이지네이션을 지원하므로 대량의 결과도 순차적으로 조회할 수 있습니다.

    Args:
        params (SearchProgramsInput): 검색 조건
            - keyword (Optional[str]): 사업명 검색 키워드, 1~100자 (선택)
            - realm (RealmType): 지원 분야 (기본: 전체)
            - region (RegionType): 지역 (기본: 전국)
            - status (StatusType): 공고 상태 (기본: 진행중)
            - page (int): 페이지 번호, 1 이상 (기본: 1)
            - page_size (int): 페이지당 건수, 1~100 (기본: 20)

    Returns:
        str: 마크다운 형식의 지원사업 목록

        성공 시:
        - 검색 조건 요약
        - 각 공고의 제목/분야/소관기관/지역/신청기간/등록일/상세링크
        - 다음 페이지 안내 (추가 결과가 있을 때)

        오류 시: "설정/파싱/연결/인증 오류: ..." 형식의 메시지

    Examples:
        - "창업 분야 서울 지원사업 검색" → realm="창업", region="서울"
        - "R&D 키워드 검색" → keyword="R&D"
        - "마감된 수출 지원사업" → realm="수출", status="마감"
    """
    try:
        api_params = _build_search_params(
            params.realm, params.region, params.status,
            params.keyword, params.page, params.page_size,
        )
        data = await _call_api(api_params)

        items = data.get("jsonArray", [])
        total = int(data.get("totalCount", 0))

        if not items:
            return "검색 결과가 없습니다. 검색 조건을 변경해 보세요."

        lines = ["# 🏢 기업마당 지원사업 검색 결과", ""]

        conditions = []
        if params.keyword:
            conditions.append(f"키워드: **{params.keyword}**")
        if params.realm != RealmType.전체:
            conditions.append(f"분야: **{params.realm.value}**")
        if params.region != RegionType.전국:
            conditions.append(f"지역: **{params.region.value}**")
        conditions.append(f"상태: **{params.status.value}**")

        lines.append("**검색 조건**: " + " | ".join(conditions))
        lines.append(f"**총 {total}건** 중 {len(items)}건 표시 (페이지 {params.page})")
        lines.append("")
        lines.append("---")
        lines.append("")

        for i, raw in enumerate(items, 1):
            prog = _parse_program(raw)
            lines.append(f"## {i}. {prog['title']}")
            lines.append(f"- **ID**: `{prog['id']}`")
            lines.append(f"- **분야**: {prog['realm']}")
            lines.append(f"- **소관기관**: {prog['agency']}")
            if prog["executing_agency"] and prog["executing_agency"] != prog["agency"]:
                lines.append(f"- **수행기관**: {prog['executing_agency']}")
            lines.append(f"- **지역**: {prog['region']}")
            lines.append(f"- **신청기간**: {_format_date(prog['start_date'])} ~ {_format_date(prog['end_date'])}")
            lines.append(f"- **등록일**: {_format_date(prog['registered_date'])}")
            lines.append(f"- **상태**: {prog['status']}")
            if prog["detail_url"]:
                lines.append(f"- **상세보기**: [{prog['title']}]({prog['detail_url']})")
            lines.append("")

        has_more = total > params.page * params.page_size
        if has_more:
            lines.append("---")
            lines.append(f"*다음 페이지 조회: page={params.page + 1} 으로 재호출하세요.*")

        return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="bizinfo_list_new_programs",
    annotations={
        "title": "신규 지원사업 목록 조회",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def bizinfo_list_new_programs(params: ListNewProgramsInput) -> str:
    """최근 N일 이내에 등록된 신규 지원사업 공고를 조회합니다.

    기업마당 API에서 여러 페이지를 순회하며 최신 공고를 가져온 뒤
    등록일 기준으로 필터링합니다. 매일 또는 매주 신규 공고를 파악하는 데 유용합니다.

    Args:
        params (ListNewProgramsInput): 조회 조건
            - days (int): 최근 N일 이내, 1~90 (기본: 7)
            - realm (RealmType): 분야 필터 (기본: 전체)
            - region (RegionType): 지역 필터 (기본: 전국)
            - page_size (int): 페이지당 건수, 1~100 (기본: 30)
            - max_pages (int): 최대 조회 페이지 수, 1~10 (기본: 3)

    Returns:
        str: 신규 공고 목록 (마크다운)

        성공 시:
        - 수집 기간 및 신규 공고 건수 요약
        - 각 공고의 분야/소관기관/지역/신청기간/등록일/상세링크 표

        오류 시: "설정/파싱/연결/인증 오류: ..." 형식의 메시지

    Examples:
        - "이번 주 신규 공고" → days=7
        - "이번 달 창업 분야 신규 공고" → days=30, realm="창업"
        - "최근 3일 경기도 신규 공고" → days=3, region="경기"
    """
    try:
        all_new: List[dict] = []

        # ⚪ 수정: 여러 페이지 순회하여 신규 공고 누락 방지
        for page_num in range(1, params.max_pages + 1):
            api_params = _build_search_params(
                params.realm, params.region, StatusType.전체,
                None, page_num, params.page_size,
            )
            data = await _call_api(api_params)
            items = data.get("jsonArray", [])
            if not items:
                break

            for raw in items:
                if _is_within_days(raw.get("pblancRegistDt", ""), params.days):
                    all_new.append(_parse_program(raw))

            # 전체 건수 대비 더 가져올 필요 없으면 중단
            total = int(data.get("totalCount", 0))
            if page_num * params.page_size >= total:
                break

        cutoff_str = (datetime.now() - timedelta(days=params.days)).strftime("%Y년 %m월 %d일")
        today_str = datetime.now().strftime("%Y년 %m월 %d일")

        lines = [f"# 🆕 신규 지원사업 ({cutoff_str} ~ {today_str})", ""]
        lines.append(f"최근 **{params.days}일** 이내 신규 등록 공고: **총 {len(all_new)}건**")
        lines.append("")

        if not all_new:
            lines.append("> 해당 기간 내 신규 공고가 없습니다.")
            lines.append(f"> max_pages({params.max_pages})를 늘리거나 days를 확대해 보세요.")
            return "\n".join(lines)

        lines.append("---")
        lines.append("")

        for i, prog in enumerate(all_new, 1):
            lines.append(f"### {i}. {prog['title']}")
            lines.append("| 항목 | 내용 |")
            lines.append("|------|------|")
            lines.append(f"| 분야 | {prog['realm']} |")
            lines.append(f"| 소관기관 | {prog['agency']} |")
            lines.append(f"| 지역 | {prog['region']} |")
            lines.append(f"| 신청기간 | {_format_date(prog['start_date'])} ~ {_format_date(prog['end_date'])} |")
            lines.append(f"| 등록일 | {_format_date(prog['registered_date'])} |")
            if prog["detail_url"]:
                lines.append(f"| 링크 | [{prog['title']}]({prog['detail_url']}) |")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="bizinfo_generate_report",
    annotations={
        "title": "지원사업 마크다운 리포트 생성",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def bizinfo_generate_report(params: GenerateReportInput) -> str:
    """최근 신규 지원사업을 수집하여 분야별로 정리된 마크다운 리포트를 생성합니다.

    기업마당 API에서 최근 N일 이내 등록된 공고를 수집하고,
    분야별로 분류하여 보고용 마크다운 리포트를 생성합니다.
    생성된 리포트는 파일로 저장하거나 이메일/슬랙으로 공유하기에 적합합니다.

    Args:
        params (GenerateReportInput): 리포트 생성 조건
            - days (int): 최근 N일 이내 공고 수집, 1~90 (기본: 7)
            - realm (RealmType): 분야 필터 (기본: 전체)
            - region (RegionType): 지역 필터 (기본: 전국)
            - max_items (int): 최대 수집 건수, 1~200 (기본: 50)
            - title (Optional[str]): 리포트 제목, 1~100자 (없으면 자동 생성)

    Returns:
        str: 분야별로 정리된 마크다운 형식의 지원사업 리포트

        성공 시:
        - 수집 기간·총 건수·분야/지역 필터 요약 헤더
        - 분야별 건수 요약 표
        - 분야별 상세 목록 (소관기관/신청기간/등록일/사업개요/링크)

        오류 시: "설정/파싱/연결/인증 오류: ..." 형식의 메시지

    Examples:
        - "주간 지원사업 리포트" → days=7, max_items=50
        - "이번 달 창업 리포트 만들어줘" → days=30, realm="창업"
        - "경기도 신규 공고 월간 리포트" → days=30, region="경기"
    """
    try:
        all_programs: List[dict] = []
        page = 1
        page_size = min(params.max_items, 100)

        # 🔴 수정: while 루프에 MAX_PAGES_PER_REQUEST 상한 적용
        while len(all_programs) < params.max_items and page <= MAX_PAGES_PER_REQUEST:
            api_params = _build_search_params(
                params.realm, params.region, StatusType.진행중,
                None, page, page_size,
            )
            data = await _call_api(api_params)
            items = data.get("jsonArray", [])
            if not items:
                break

            for raw in items:
                if _is_within_days(raw.get("pblancRegistDt", ""), params.days):
                    all_programs.append(_parse_program(raw))

            total = int(data.get("totalCount", 0))
            if page * page_size >= total:
                break
            page += 1

        all_programs = all_programs[: params.max_items]

        # 분야별 그룹핑
        by_realm: dict[str, List[dict]] = {}
        for prog in all_programs:
            realm_name = prog["realm"] or "기타"
            by_realm.setdefault(realm_name, []).append(prog)

        today_str = datetime.now().strftime("%Y년 %m월 %d일")
        cutoff_str = (datetime.now() - timedelta(days=params.days)).strftime("%Y년 %m월 %d일")

        if params.title:
            report_title = params.title
        else:
            realm_label = f"{params.realm.value} 분야 " if params.realm != RealmType.전체 else ""
            region_label = f"{params.region.value} " if params.region != RegionType.전국 else ""
            report_title = f"정부 지원사업 신규 공고 리포트 ({region_label}{realm_label}{today_str})"

        lines = [
            f"# 📋 {report_title}",
            "",
            f"> **수집 기간**: {cutoff_str} ~ {today_str} (최근 {params.days}일)",
            f"> **총 신규 공고**: {len(all_programs)}건",
            f"> **분야 필터**: {params.realm.value}",
            f"> **지역 필터**: {params.region.value}",
            f"> **생성일시**: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "---",
            "",
        ]

        if not all_programs:
            lines.append("해당 기간 내 신규 등록된 지원사업 공고가 없습니다.")
            return "\n".join(lines)

        lines.append("## 📊 분야별 요약")
        lines.append("")
        lines.append("| 분야 | 건수 |")
        lines.append("|------|------|")
        for realm_name, programs in sorted(by_realm.items(), key=lambda x: -len(x[1])):
            lines.append(f"| {realm_name} | {len(programs)}건 |")
        lines.append("")
        lines.append("---")
        lines.append("")

        lines.append("## 📌 분야별 상세 목록")
        lines.append("")

        for realm_name, programs in sorted(by_realm.items(), key=lambda x: -len(x[1])):
            lines.append(f"### 🔹 {realm_name} ({len(programs)}건)")
            lines.append("")

            for prog in programs:
                lines.append(f"#### {prog['title']}")
                lines.append(f"- **소관기관**: {prog['agency']}")
                lines.append(f"- **지역**: {prog['region']}")
                lines.append(f"- **신청기간**: {_format_date(prog['start_date'])} ~ {_format_date(prog['end_date'])}")
                lines.append(f"- **등록일**: {_format_date(prog['registered_date'])}")
                if prog["summary"]:
                    summary = prog["summary"][:150] + "..." if len(prog["summary"]) > 150 else prog["summary"]
                    lines.append(f"- **사업 개요**: {summary}")
                if prog["detail_url"]:
                    lines.append(f"- **상세보기**: [공고 링크]({prog['detail_url']})")
                lines.append("")

        lines.append("---")
        lines.append(f"*본 리포트는 기업마당(bizinfo.go.kr) Open API를 통해 자동 생성되었습니다. ({today_str})*")

        return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e)


@mcp.tool(
    name="bizinfo_get_stats",
    annotations={
        "title": "지원사업 분야별 통계 조회",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def bizinfo_get_stats(params: StatsInput) -> str:
    """현재 진행 중인 지원사업의 분야별 통계를 조회합니다.

    각 분야(금융/기술/인력/수출/내수/창업/경영/기타)별로 진행 중인
    지원사업 건수를 병렬로 조회하여 한눈에 볼 수 있는 요약을 제공합니다.

    Args:
        params (StatsInput): 조회 조건
            - region (RegionType): 지역 필터 (기본: 전국)

    Returns:
        str: 분야별 통계 마크다운 요약

        성공 시:
        - 기준일 및 지역 정보
        - 분야별 진행 중 공고 건수 표
        - 합계

        오류 시: "설정/파싱/연결/인증 오류: ..." 형식의 메시지

    Examples:
        - "지원사업 분야별 현황" → region="전국"
        - "서울 지원사업 통계" → region="서울"
    """
    try:
        realms_to_check = [r for r in RealmType if r != RealmType.전체]

        # 🔴 수정: asyncio.gather로 8개 분야를 병렬 조회 (순차 240초 → 병렬 30초)
        async def _fetch_realm_count(realm: RealmType) -> tuple[str, int]:
            api_params = _build_search_params(realm, params.region, StatusType.진행중, None, 1, 1)
            data = await _call_api(api_params)
            return realm.value, int(data.get("totalCount", 0))

        results = await asyncio.gather(
            *[_fetch_realm_count(realm) for realm in realms_to_check],
            return_exceptions=True,
        )

        today_str = datetime.now().strftime("%Y년 %m월 %d일 기준")
        lines = ["# 📊 지원사업 분야별 통계 (진행 중)", ""]
        lines.append(f"**기준일**: {today_str}")
        if params.region != RegionType.전국:
            lines.append(f"**지역**: {params.region.value}")
        lines.append("")
        lines.append("| 분야 | 진행 중 건수 |")
        lines.append("|------|-------------|")

        total_count = 0
        for result in results:
            if isinstance(result, Exception):
                lines.append(f"| (조회 실패) | - |")
                continue
            realm_name, count = result
            total_count += count
            lines.append(f"| {realm_name} | {count:,}건 |")

        lines.append(f"| **합계** | **{total_count:,}건** |")
        lines.append("")
        lines.append("---")
        lines.append(f"*출처: 기업마당(bizinfo.go.kr) | {today_str}*")

        return "\n".join(lines)

    except Exception as e:
        return _handle_api_error(e)


# ──────────────────────────────────────────────
# 서버 실행
# ──────────────────────────────────────────────
if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        mcp.settings.host = os.environ.get("MCP_HOST", "0.0.0.0")
        mcp.settings.port = int(os.environ.get("MCP_PORT", "8000"))
        mcp.run(transport="sse")
    else:
        mcp.run()
