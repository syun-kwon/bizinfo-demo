"""
BizInfo Web - FastAPI 백엔드
bizinfo_server.py의 함수를 직접 호출하여 REST API로 제공합니다.
"""

import os
from typing import Optional

import httpx
from fastapi import FastAPI, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# MCP 서버 함수 직접 임포트 (SSE 프로토콜 없이 직접 호출)
from bizinfo_server import (
    bizinfo_get_stats,
    bizinfo_search_programs,
    bizinfo_list_new_programs,
    bizinfo_generate_report,
    SearchProgramsInput,
    ListNewProgramsInput,
    GenerateReportInput,
    StatsInput,
    RealmType,
    RegionType,
    StatusType,
)

app = FastAPI(title="BizInfo Web API")

SUMMARIZER_URL = os.environ.get("SUMMARIZER_URL", "http://bizinfo-summarizer:4000")


class SummarizeRequest(BaseModel):
    url: str


# ── Health Check ────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ── 분야별 통계 ─────────────────────────────────────────

@app.get("/api/stats")
async def get_stats(region: str = Query("전국")):
    try:
        result = await bizinfo_get_stats(StatsInput(region=RegionType(region)))
        return {"markdown": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 지원사업 검색 ────────────────────────────────────────

@app.get("/api/search")
async def search_programs(
    keyword: Optional[str] = Query(None),
    realm: str = Query("전체"),
    region: str = Query("전국"),
    status: str = Query("진행중"),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    try:
        params = SearchProgramsInput(
            keyword=keyword or None,
            realm=RealmType(realm),
            region=RegionType(region),
            status=StatusType(status),
            page=page,
            page_size=page_size,
        )
        result = await bizinfo_search_programs(params)
        return {"markdown": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 신규 공고 조회 ───────────────────────────────────────

@app.get("/api/new")
async def list_new_programs(
    days: int = Query(7, ge=1, le=90),
    realm: str = Query("전체"),
    region: str = Query("전국"),
    max_pages: int = Query(3, ge=1, le=10),
):
    try:
        params = ListNewProgramsInput(
            days=days,
            realm=RealmType(realm),
            region=RegionType(region),
            max_pages=max_pages,
        )
        result = await bizinfo_list_new_programs(params)
        return {"markdown": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── 리포트 생성 ──────────────────────────────────────────

@app.get("/api/report")
async def generate_report(
    days: int = Query(7, ge=1, le=90),
    realm: str = Query("전체"),
    region: str = Query("전국"),
    max_items: int = Query(50, ge=1, le=200),
):
    try:
        params = GenerateReportInput(
            days=days,
            realm=RealmType(realm),
            region=RegionType(region),
            max_items=max_items,
        )
        result = await bizinfo_generate_report(params)
        return {"markdown": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── AI 요약 (bizinfo-summarizer 프록시) ─────────────────────

@app.post("/api/summarize")
async def proxy_summarize(req: SummarizeRequest):
    """bizinfo-summarizer 서비스로 요약 요청을 프록시합니다."""
    try:
        async with httpx.AsyncClient(timeout=130.0) as client:
            resp = await client.post(
                f"{SUMMARIZER_URL}/summarize",
                json={"url": req.url},
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="요약 서비스에 연결할 수 없습니다. bizinfo-summarizer가 실행 중인지 확인해주세요.",
        )
    except httpx.HTTPStatusError as e:
        detail = e.response.json().get("detail", e.response.text[:200]) if e.response.headers.get("content-type", "").startswith("application/json") else e.response.text[:200]
        raise HTTPException(status_code=e.response.status_code, detail=detail)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Static Files (프론트엔드) ─────────────────────────────

app.mount("/", StaticFiles(directory="static", html=True), name="static")
