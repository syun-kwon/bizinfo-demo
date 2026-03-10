# BizInfo Demo — 아키텍처 문서

> 중소벤처기업부 기업마당(bizinfo.go.kr) 지원사업 조회 시스템

---

## 1. 시스템 개요

이 프로젝트는 기업마당 Open API를 두 가지 방법으로 활용할 수 있도록 구성된 시스템입니다.

1. **Claude Desktop MCP 연동** — AI 어시스턴트가 직접 지원사업을 조회
2. **웹 UI** — 브라우저에서 접근 가능한 독립형 대시보드

두 서비스 모두 Docker 컨테이너로 패키징되어 단일 `docker compose` 명령으로 실행됩니다.

---

## 2. 전체 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                          사용자 접근 경로                          │
├─────────────────────────────┬───────────────────────────────────┤
│    브라우저                   │    Claude Desktop                 │
│    http://localhost:3000    │    MCP 설정 (SSE)                 │
└─────────────┬───────────────┴──────────┬────────────────────────┘
              │                           │
              ▼                           ▼
┌─────────────────────────┐   ┌──────────────────────────┐
│   bizinfo-web (3000)    │   │   bizinfo-mcp (8000)      │
│                         │   │                           │
│  FastAPI + HTML/JS      │   │  FastMCP (SSE 전송)       │
│  REST API 제공          │   │  MCP 프로토콜 처리        │
│  /api/summarize (프록시) │   │                           │
│  bizinfo_server.py 임포트│   │  server.py (동일 코드)    │
└──────┬──────────────────┘   └────────────┬──────────────┘
       │           │                        │
       │           │ AI 요약 요청            │
       │           ▼                        │
       │  ┌─────────────────────────┐       │
       │  │ bizinfo-summarizer (4000)│       │
       │  │                         │       │
       │  │  스크래핑 (BeautifulSoup) │       │
       │  │  + Ollama 요약 호출      │       │
       │  └─────────┬───────────────┘       │
       │            │                        │
       │            ▼                        │
       │  ┌─────────────────────────┐       │
       │  │   ollama (11434)         │       │
       │  │  gpt-oss-safeguard:20b  │       │
       │  │  (로컬 LLM 추론)         │       │
       │  └─────────────────────────┘       │
       │                                    │
       └──────────────┬─────────────────────┘
                      │
                      ▼
        ┌─────────────────────────────┐
        │   기업마당 Open API          │
        │   https://www.bizinfo.go.kr │
        │   /uss/rss/bizinfoApi.do    │
        │   (XML/RSS 응답)            │
        └─────────────────────────────┘
```

### 핵심 설계 결정

**1. 코드 공유 방식**
`bizinfo-web` 컨테이너는 MCP 서버의 `server.py`를 `bizinfo_server.py`로 복사한 뒤 Python 모듈로 직접 임포트합니다. MCP 프로토콜 오버헤드 없이 API 함수를 바로 호출합니다.

> **배경**: Docker 내부 네트워크에서 MCP SSE 접속 시 FastMCP의 DNS 리바인딩 보호 기능이 `bizinfo-mcp:8000` Host 헤더를 차단하는 문제(`421 Invalid Host header`)가 발생하여, SSE 클라이언트 방식 대신 직접 임포트 방식을 채택했습니다.

**2. AI 요약 마이크로서비스 분리**
요약 기능은 별도 `bizinfo-summarizer` 컨테이너로 분리합니다. LLM 추론 시간이 30~90초 이상 소요되어 웹 서버와 같은 컨테이너에 두면 다른 API 응답에 영향을 줄 수 있기 때문입니다. `bizinfo-web`은 `/api/summarize`를 단순 프록시로만 처리합니다.

**3. 로컬 LLM (Ollama)**
외부 LLM API 비용 없이 `gpt-oss-safeguard:20b` 모델을 로컬에서 실행합니다. CPU 기반 추론이므로 속도는 느리지만 데이터가 외부로 전송되지 않습니다.

---

## 3. 컴포넌트 상세

### 3.1 bizinfo-mcp 컨테이너

| 항목 | 내용 |
|------|------|
| 이미지 | `python:3.11-slim` |
| 포트 | 8000 (내부 전용, 외부 미노출) |
| 전송 방식 | SSE (Server-Sent Events) |
| 용도 | Claude Desktop MCP 연동 전용 |

**제공 MCP 도구 (4개)**

| 도구명 | 기능 | 주요 파라미터 |
|--------|------|--------------|
| `bizinfo_search_programs` | 키워드/분야/지역/상태로 지원사업 검색 | keyword, realm, region, status, page |
| `bizinfo_list_new_programs` | 최근 N일 신규 공고 목록 조회 | days, realm, region, max_pages |
| `bizinfo_generate_report` | 분야별 마크다운 리포트 자동 생성 | days, realm, region, max_items |
| `bizinfo_get_stats` | 8개 분야 병렬 통계 조회 | region |

**실행 방식**

```bash
# MCP_TRANSPORT=sse 시 SSE 서버로 기동
# MCP_TRANSPORT 미설정 시 stdio 모드 (Claude Desktop 로컬 직접 실행)
python server.py
```

### 3.2 bizinfo-web 컨테이너

| 항목 | 내용 |
|------|------|
| 이미지 | `python:3.11-slim` |
| 포트 | 3000 (외부 공개) |
| 프레임워크 | FastAPI + Uvicorn |
| 프론트엔드 | 정적 HTML/JS (Tailwind CSS, marked.js) |

**REST API 엔드포인트**

| 엔드포인트 | MCP 도구 매핑 | 설명 |
|-----------|--------------|------|
| `GET /api/stats` | `bizinfo_get_stats` | 분야별 통계 |
| `GET /api/search` | `bizinfo_search_programs` | 지원사업 검색 |
| `GET /api/new` | `bizinfo_list_new_programs` | 신규 공고 조회 |
| `GET /api/report` | `bizinfo_generate_report` | 리포트 생성 |
| `POST /api/summarize` | — | AI 요약 (bizinfo-summarizer 프록시) |
| `GET /api/health` | — | 헬스 체크 |
| `GET /docs` | — | FastAPI 자동 API 문서 |

### 3.3 bizinfo-summarizer 컨테이너

| 항목 | 내용 |
|------|------|
| 이미지 | `python:3.11-slim` |
| 포트 | 4000 (외부 공개, 직접 접근 가능) |
| 주요 의존성 | `httpx`, `beautifulsoup4`, `lxml`, `fastapi` |

**동작 흐름**

```
POST /summarize {"url": "https://www.bizinfo.go.kr/..."}
    │
    ├─ 1. HTTP GET → bizinfo.go.kr 상세 페이지 스크래핑
    │   선택자 우선순위: div.view_cont → div.support_project_detail
    │   → div.sub_cont → ... → body 전체 (폴백)
    │   최대 5,000자 추출
    │
    └─ 2. POST → ollama:11434/api/generate
        모델: gpt-oss-safeguard:20b
        프롬프트: 5항목 구조화 한국어 요약
        (사업목적/지원대상/지원내용/신청방법/주의사항)
```

**엔드포인트**

| 엔드포인트 | 설명 |
|-----------|------|
| `POST /summarize` | URL 스크래핑 + AI 요약 |
| `GET /health` | 헬스 체크 |

### 3.4 ollama 컨테이너

| 항목 | 내용 |
|------|------|
| 이미지 | `ollama/ollama:latest` |
| 포트 | 11434 (내부 전용) |
| 모델 | `gpt-oss-safeguard:20b` (13.8GB) |
| 볼륨 | `ollama_data` (모델 영구 저장) |
| 헬스체크 | `ollama list` 명령 |

> **메모리 요구사항**: 20B 모델 로딩에 13.1 GiB 필요. Docker Desktop 메모리를 **16 GiB 이상**으로 설정해야 합니다 (Settings → Resources → Memory).

---

## 4. 핵심 모듈: server.py 및 summarizer/main.py

```
bizinfo_mcp/server.py
├── 상수 정의
│   ├── API_BASE_URL, API_TIMEOUT, MAX_PAGES_PER_REQUEST
│   ├── REALM_CODES   (분야명 → API 코드, 8개)
│   ├── REGION_CODES  (지역명 → API 코드, 17개)
│   └── STATUS_CODES  (상태명 → API 코드)
│
├── Enum 정의
│   ├── RealmType   (금융/기술/인력/수출/내수/창업/경영/기타/전체)
│   ├── RegionType  (전국 + 17개 시도)
│   └── StatusType  (진행중/마감/전체)
│
├── Pydantic 입력 모델 (v2)
│   ├── SearchProgramsInput
│   ├── ListNewProgramsInput
│   ├── GenerateReportInput
│   └── StatsInput
│
├── 공통 유틸리티
│   ├── _get_auth_key()          환경변수에서 API 키 읽기
│   ├── _xml_text()              XML 요소 텍스트 추출
│   ├── _parse_xml_response()    XML RSS → 내부 dict 변환
│   ├── _call_api()              httpx 비동기 API 호출
│   ├── _handle_api_error()      에러 타입별 메시지 처리
│   ├── _parse_program()         API 응답 항목 정제
│   ├── _format_date()           날짜 문자열 포맷 변환
│   ├── _is_within_days()        N일 이내 여부 판단
│   └── _build_search_params()   API 파라미터 구성
│
└── MCP 도구 (4개)
    ├── bizinfo_search_programs()
    ├── bizinfo_list_new_programs()
    ├── bizinfo_generate_report()
    └── bizinfo_get_stats()       ← asyncio.gather로 병렬 조회
```

### 4.2 bizinfo_summarizer/main.py

```
bizinfo_summarizer/main.py
├── 설정 상수
│   ├── OLLAMA_HOST, OLLAMA_MODEL
│   ├── SCRAPE_TIMEOUT=20s, OLLAMA_TIMEOUT=300s
│   └── MAX_TEXT_CHARS=5000
│
├── CONTENT_SELECTORS (우선순위 선택자 목록)
│   ├── div.view_cont             ← bizinfo.go.kr 실제 구조
│   ├── div.support_project_detail
│   ├── div.sub_cont
│   └── ... (8개 폴백)
│
├── _scrape(url) → (title, text)
│   ├── httpx GET (follow_redirects, bot-friendly headers)
│   ├── BeautifulSoup lxml 파싱
│   ├── 노이즈 제거 (script/style/nav/footer 등)
│   ├── 선택자 순서대로 최적 콘텐츠 탐색
│   └── 미달 시 body 전체 폴백
│
├── _call_ollama(text) → summary
│   ├── 5항목 구조화 프롬프트 구성
│   └── POST ollama:11434/api/generate (stream=False)
│
└── POST /summarize
    ├── _scrape() 호출
    └── _call_ollama() 호출 → SummarizeResponse 반환
```

### XML 파싱 처리

기업마당 API는 JSON이 아닌 XML/RSS 형식으로 응답합니다. `_parse_xml_response()`가 이를 내부 dict 구조로 변환합니다.

```
XML 필드               →   내부 dict 키
─────────────────────────────────────────
pblancId               →   pblancId
pblancNm               →   pblancNm
pldirSportRealmLclas.. →   pldirSportRealmLclasCodeNm
creatPnttm             →   pblancRegistDt (날짜 정규화)
reqstBeginEndDe        →   reqstBeginEndDe / reqstCloseEndDe (분리)
bsnsSumryCn            →   bsnsSumryCn (HTML 태그 제거)
```

**날짜 정규화**
- 등록일: `"2026-03-06 14:51:46"` → `"20260306"`
- 신청기간: `"2026-03-03 ~ 2026-04-05"` → start=`"20260303"`, end=`"20260405"`

---

## 5. Docker 구성

### 파일 구조

```
bizinfo_demo/
├── docker-compose.yml             ← 통합 실행 (4개 서비스)
├── .env                           ← BIZINFO_API_KEY (gitignore)
├── .env.example                   ← API 키 템플릿 (커밋됨)
├── bizinfo_mcp/
│   ├── Dockerfile                 ← MCP 서버 이미지
│   ├── docker-compose.yml         ← MCP 단독 실행용
│   ├── server.py                  ← 핵심 로직
│   └── requirements.txt
├── bizinfo_web/
│   ├── Dockerfile                 ← 웹 서버 이미지 (루트 컨텍스트)
│   ├── main.py                    ← FastAPI 백엔드
│   ├── requirements.txt
│   └── static/
│       └── index.html             ← SPA 프론트엔드
└── bizinfo_summarizer/
    ├── Dockerfile                 ← 요약 서버 이미지
    ├── main.py                    ← 스크래핑 + Ollama 연동
    └── requirements.txt
```

### Docker 이미지 빌드 방식

**bizinfo-mcp** (단순 빌드)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY server.py .
EXPOSE 8000
CMD ["python", "server.py"]
```

**bizinfo-web** (루트 컨텍스트, 코드 공유)
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY bizinfo_web/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY bizinfo_mcp/requirements.txt mcp_requirements.txt
RUN pip install --no-cache-dir -r mcp_requirements.txt
COPY bizinfo_mcp/server.py ./bizinfo_server.py   # ← 핵심: MCP 코드 공유
COPY bizinfo_web/ .
EXPOSE 3000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
```

> `bizinfo-web`의 build context가 루트(`.`)인 이유: `bizinfo_mcp/server.py`를 `bizinfo_web/` 컨테이너에 복사하려면 두 디렉토리에 모두 접근할 수 있는 공통 상위 디렉토리를 컨텍스트로 지정해야 하기 때문입니다.

### 네트워크 구성

```
외부 인터넷
    │
    ├── 포트 3000 (공개) → bizinfo-web
    ├── 포트 4000 (공개) → bizinfo-summarizer
    ├── 포트 8000 (내부 전용) → bizinfo-mcp ← Claude Desktop만 접근
    └── 포트 11434 (공개) → ollama (LLM API)

Docker 내부 네트워크
    bizinfo-web    → bizinfo-summarizer:4000 (요약 프록시)
    bizinfo-summarizer → ollama:11434         (LLM 추론)
```

### ollama-model-init 서비스

```yaml
# 1회성 초기화 컨테이너 — ollama healthy 후 모델 pull
ollama-model-init:
  image: curlimages/curl:latest
  depends_on:
    ollama: { condition: service_healthy }
  command: curl -X POST http://ollama:11434/api/pull -d '{"name":"gpt-oss-safeguard:20b"}'
  restart: on-failure

# bizinfo-summarizer는 init 완료 후 시작
bizinfo-summarizer:
  depends_on:
    ollama-model-init: { condition: service_completed_successfully }
```

모델은 `ollama_data` 볼륨에 영구 저장되어 재시작 시 재다운로드 없이 바로 사용됩니다.

---

## 6. 데이터 흐름

### 6.1 웹 UI 경로

```
사용자 (브라우저)
    │  HTTP GET /api/stats?region=서울
    ▼
bizinfo-web (FastAPI, :3000)
    │  await bizinfo_get_stats(StatsInput(region="서울"))
    │  ← bizinfo_server.py 직접 호출
    ▼
기업마당 API
    │  GET /uss/rss/bizinfoApi.do
    │  ?crtfcKey=...&pageIndex=1&pageUnit=1&pldirSportRealmLclasCode=010&pbancSttus=ing
    ▼  (× 8개 분야, asyncio.gather 병렬)
XML/RSS 응답
    │  _parse_xml_response() → dict
    ▼
마크다운 문자열 반환
    │  {"markdown": "# 📊 지원사업 분야별 통계..."}
    ▼
브라우저 (marked.js로 렌더링)
```

### 6.2 Claude Desktop 경로

```
Claude Desktop
    │  MCP 도구 호출: bizinfo_get_stats(region="서울")
    │  SSE 연결: http://localhost:8000/sse
    ▼
bizinfo-mcp (FastMCP, :8000)
    │  MCP 프로토콜 처리
    ▼
기업마당 API (동일한 로직)
    ▼
마크다운 문자열
    ▼
Claude Desktop (AI 응답에 포함)
```

---

## 7. 환경변수 및 보안

| 변수명 | 설명 | 설정 위치 |
|--------|------|----------|
| `BIZINFO_API_KEY` | 기업마당 API 인증 키 | `.env` (gitignore) |
| `MCP_TRANSPORT` | `sse` 또는 `stdio` | docker-compose.yml |
| `MCP_HOST` | SSE 바인딩 주소 | docker-compose.yml |
| `MCP_PORT` | SSE 포트 | docker-compose.yml |
| `FASTMCP_TRANSPORT_SECURITY__ENABLE_DNS_REBINDING_PROTECTION` | DNS 리바인딩 보호 비활성화 | docker-compose.yml |
| `SUMMARIZER_URL` | 요약 서비스 URL | docker-compose.yml |
| `OLLAMA_HOST` | Ollama 서버 URL | docker-compose.yml |
| `OLLAMA_MODEL` | 사용할 Ollama 모델명 | docker-compose.yml |

**API 키 관리 원칙**
- `.env` 파일에 실제 키 보관 (`.gitignore`로 커밋 제외)
- `.env.example`에 템플릿 제공 (커밋됨)
- `server.py`에서 매 API 호출 시 `os.environ.get("BIZINFO_API_KEY")`로 읽음 (전역 변수 없음)

---

## 8. 의존성

### Python 패키지

| 패키지 | 용도 | 서비스 |
|--------|------|--------|
| `mcp` | MCP 프로토콜 서버 프레임워크 (FastMCP) | mcp, web |
| `httpx` | 비동기 HTTP 클라이언트 | mcp, web, summarizer |
| `pydantic` | 입력 유효성 검사 (v2) | mcp, web, summarizer |
| `fastapi` | REST API 웹 프레임워크 | web, summarizer |
| `uvicorn` | ASGI 서버 | web, summarizer |
| `beautifulsoup4` | HTML 파싱 (스크래핑) | summarizer |
| `lxml` | 고속 HTML 파서 | summarizer |

### 프론트엔드 (CDN)

| 라이브러리 | 용도 |
|------------|------|
| Tailwind CSS | UI 스타일링 |
| marked.js | 마크다운 → HTML 렌더링 |

---

## 9. 로컬 실행 방법

### 사전 준비

1. Docker Desktop 설치 및 실행
2. 기업마당(bizinfo.go.kr)에서 API 키 발급

### 환경변수 설정

```bash
cd bizinfo_demo
cp .env.example .env
# .env 파일을 열어 BIZINFO_API_KEY에 실제 키 입력
```

### 실행

```bash
# 전체 시작
docker compose up -d

# 로그 확인
docker compose logs -f

# 특정 서비스 로그
docker compose logs -f bizinfo-web
docker compose logs -f bizinfo-mcp

# 재빌드 (코드 변경 후)
docker compose build && docker compose up -d

# 중지
docker compose down
```

### 접속 URL

| 서비스 | URL |
|--------|-----|
| 웹 UI | http://localhost:3000 |
| REST API 문서 | http://localhost:3000/docs |
| MCP SSE (Claude Desktop) | http://localhost:8000/sse |
| AI 요약 서비스 직접 접근 | http://localhost:4000/summarize |
| Ollama API | http://localhost:11434 |

### Docker Desktop 메모리 설정

`gpt-oss-safeguard:20b` 모델은 13.1 GiB의 메모리가 필요합니다.

```
Docker Desktop → Settings → Resources → Memory → 16 GiB 이상
→ Apply & Restart
```

호스트 시스템에 16 GiB 이상의 RAM이 있어야 합니다.

### Claude Desktop 설정

`~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "bizinfo": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

---

## 10. 클라우드 배포 시 변경 사항

| 항목 | 로컬 | 클라우드 배포 |
|------|------|--------------|
| 접속 URL | http://localhost:3000 | https://your-domain.com |
| SSL/TLS | 불필요 | Nginx + Let's Encrypt |
| API 키 관리 | `.env` 파일 | AWS Secrets Manager 등 |
| 포트 노출 | 로컬 포트 포워딩 | 로드밸런서/리버스 프록시 |
| `server.py` / `main.py` | 변경 없음 | 변경 없음 |
| `docker-compose.yml` | 현재 그대로 | Nginx 서비스 추가 |

---

*최초 작성일: 2026-03-09 | 최종 수정일: 2026-03-10 (AI 요약 서비스 추가)*
*GitHub: https://github.com/syun-kwon/bizinfo-demo*
