"""
bizinfo-summarizer: 기업마당 공고 상세 페이지 스크래핑 + Ollama 요약 서비스

POST /summarize  →  {"url": "...", "title": "...", "scraped_length": N, "summary": "...", "model": "..."}
GET  /health     →  {"status": "ok"}
"""

import os
import re

import httpx
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(title="BizInfo Summarizer")

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "gpt-oss-safeguard:20b")
SCRAPE_TIMEOUT = 20.0
OLLAMA_TIMEOUT = 120.0
MAX_TEXT_CHARS = 5000

# bizinfo.go.kr 상세 페이지 본문 영역 선택자 (우선순위 순)
CONTENT_SELECTORS = [
    "div.view_cont",           # bizinfo.go.kr 실제 구조
    "div.support_project_detail",
    "div.sub_cont",
    "div.view_content",
    "div.bbs_view",
    "div.cont_wrap",
    "div.detail_cont",
    "div#content",
    "div#sub_content",
    "table.write_table",
    "table.tbl_view",
    "div.board_view",
]

SCRAPE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    "Referer": "https://www.bizinfo.go.kr/",
}


class SummarizeRequest(BaseModel):
    url: str


class SummarizeResponse(BaseModel):
    url: str
    title: str
    scraped_length: int
    summary: str
    model: str


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/summarize", response_model=SummarizeResponse)
async def summarize(req: SummarizeRequest):
    # 1단계: 상세 페이지 스크래핑
    try:
        title, text = await _scrape(req.url)
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"페이지 요청 실패 (HTTP {e.response.status_code}): {req.url}",
        )
    except httpx.RequestError as e:
        raise HTTPException(
            status_code=502,
            detail=f"페이지 접속 오류: {e}",
        )

    if not text.strip():
        raise HTTPException(
            status_code=422,
            detail="페이지에서 텍스트를 추출할 수 없습니다.",
        )

    # 2단계: Ollama로 요약
    try:
        summary = await _call_ollama(text)
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail=f"Ollama 서버에 연결할 수 없습니다: {OLLAMA_HOST}",
        )
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Ollama 응답 시간 초과 (모델 로딩 중이거나 부하가 높습니다).",
        )
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=502,
            detail=f"Ollama API 오류 (HTTP {e.response.status_code}): {e.response.text[:200]}",
        )

    return SummarizeResponse(
        url=req.url,
        title=title,
        scraped_length=len(text),
        summary=summary,
        model=OLLAMA_MODEL,
    )


async def _scrape(url: str) -> tuple[str, str]:
    """URL의 HTML을 가져와 본문 텍스트를 추출합니다."""
    async with httpx.AsyncClient(
        timeout=SCRAPE_TIMEOUT,
        follow_redirects=True,
        headers=SCRAPE_HEADERS,
    ) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "lxml")

    # 페이지 제목 추출
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else "제목 없음"
    # "| 기업마당" 같은 접미사 제거
    title = re.sub(r"\s*[|\-–—]\s*기업마당.*$", "", title).strip()

    # 노이즈 태그 제거 (header는 제거하지 않음 — 내용이 포함될 수 있음)
    for tag in soup(["script", "style", "nav", "footer", "iframe", "noscript"]):
        tag.decompose()
    for el in soup.select(".gnb, .lnb, .snb, #footer, #header, .btn_area, .skip_navi"):
        el.decompose()

    # 본문 영역 탐색 (선택자 우선순위 순) — 가장 긴 텍스트를 우선 사용
    content_text = ""
    for selector in CONTENT_SELECTORS:
        el = soup.select_one(selector)
        if el:
            candidate = el.get_text(separator="\n", strip=True)
            if len(candidate) > len(content_text):
                content_text = candidate
            if len(content_text) > 500:  # 충분히 길면 중단
                break

    # 폴백: 선택자로 충분한 텍스트를 얻지 못한 경우 body 전체 사용
    if len(content_text) < 200:
        body = soup.find("body")
        if body:
            content_text = body.get_text(separator="\n", strip=True)

    # 공백 정리 및 길이 제한
    content_text = re.sub(r"\n{3,}", "\n\n", content_text)
    content_text = re.sub(r"[ \t]{2,}", " ", content_text)
    content_text = content_text[:MAX_TEXT_CHARS]

    return title, content_text


async def _call_ollama(text: str) -> str:
    """Ollama API를 호출하여 지원사업 공고를 요약합니다."""
    prompt = f"""당신은 대한민국 정부 지원사업 공고를 분석하는 전문가입니다.
아래 공고 본문을 읽고, 중소기업 대표가 알아야 할 핵심 내용을 5개 항목으로 요약해주세요.

[요약 형식]
1. 사업 목적: (한 문장으로)
2. 지원 대상: (자격 요건 핵심)
3. 지원 내용: (금액 또는 혜택)
4. 신청 방법 및 기간: (방법과 일정)
5. 주의사항 또는 특이사항: (중요 제약이나 우선순위)

공고 본문:
{text}

위 형식에 맞게 간결하고 명확하게 요약해주세요. 없는 정보는 "정보 없음"으로 표시하세요."""

    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.3,
            "num_predict": 512,
        },
    }

    async with httpx.AsyncClient(timeout=OLLAMA_TIMEOUT) as client:
        resp = await client.post(f"{OLLAMA_HOST}/api/generate", json=payload)
        resp.raise_for_status()
        data = resp.json()

    return data.get("response", "").strip()
