# 🏢 BizInfo Demo

> 중소벤처기업부 **기업마당(bizinfo.go.kr)** Open API를 활용한 정부 지원사업 조회 시스템

두 가지 방법으로 지원사업을 조회하고, AI로 공고 내용을 자동 요약할 수 있습니다.

| 방법 | 설명 | 대상 |
|------|------|------|
| **웹 UI** | 브라우저에서 바로 사용하는 대시보드 + AI 요약 | 일반 사용자 |
| **MCP 서버** | Claude Desktop AI에서 자연어로 조회 | Claude 사용자 |

---

## 📋 목차

1. [주요 기능](#-주요-기능)
2. [시스템 아키텍처](#-시스템-아키텍처)
3. [사전 준비](#-사전-준비)
4. [빠른 시작 (Docker)](#-빠른-시작-docker)
5. [Claude Desktop 연동](#-claude-desktop-연동)
6. [MCP 단독 실행 (Docker 없이)](#-mcp-단독-실행-docker-없이)
7. [웹 UI 사용법](#-웹-ui-사용법)
8. [MCP 도구 레퍼런스](#-mcp-도구-레퍼런스)
9. [API 엔드포인트](#-api-엔드포인트)
10. [파일 구조](#-파일-구조)
11. [트러블슈팅](#-트러블슈팅)

---

## ✨ 주요 기능

### 웹 대시보드 (http://localhost:3000)

- **📊 분야별 통계** — 금융·기술·인력·수출·내수·창업·경영·기타 8개 분야의 진행 중 공고 건수를 지역별로 조회
- **🔍 지원사업 검색** — 분야·지역·상태·키워드 조합 검색, 페이지 이동
- **🆕 신규 공고** — 최근 N일 이내 등록된 신규 공고 목록
- **📋 리포트 생성** — 분야별로 정리된 마크다운 리포트 생성 및 `.md` 파일 다운로드
- **🤖 AI 요약** — 공고 링크 옆 `AI 요약` 버튼으로 해당 페이지를 스크래핑하고 로컬 LLM(Ollama)으로 5개 항목 자동 요약

### Claude Desktop MCP 도구

Claude Desktop에서 자연어로 지원사업을 조회할 수 있습니다.

```
"최근 일주일 창업 분야 신규 공고 알려줘"
"경기도 기술 분야 진행 중인 지원사업 검색해줘"
"이번 달 수출 지원사업 리포트 만들어줘"
"서울 지역 분야별 지원사업 통계 보여줘"
```

---

## 🏗 시스템 아키텍처

```
브라우저 ──────────── http://localhost:3000
                              │
                    ┌─────────▼──────────┐
                    │   bizinfo-web       │  Docker 컨테이너
                    │  (FastAPI + HTML)   │  포트 3000
                    │                     │
                    │  bizinfo_server.py  │  ← server.py 직접 임포트
                    └──────┬─────┬───────┘
                           │     │ POST /api/summarize
         SSE ──── :8000    │     │
Claude Desktop             │     ▼
                    ┌──────▼──   ┌──────────────────────┐
                    │bizinfo-mcp │  bizinfo-summarizer   │  Docker 컨테이너
                    │(FastMCP)  │  (FastAPI, 스크래핑)  │  포트 4000
                    └──────┬─── └──────────┬────────────┘
                           │               │ /api/generate
                           │    ┌──────────▼────────────┐
                           │    │  ollama               │  Docker 컨테이너
                           │    │  gpt-oss-safeguard:20b│  포트 11434
                           │    └───────────────────────┘
                           │
                    ┌──────▼────────────┐
                    │ 기업마당 Open API  │  외부 인터넷
                    │ bizinfo.go.kr      │  XML/RSS 응답
                    └───────────────────┘
```

> **설계 포인트**: `bizinfo-web` 컨테이너는 `server.py`를 직접 임포트하여 MCP 프로토콜 없이 Python 함수를 호출합니다. AI 요약은 별도 `bizinfo-summarizer` 마이크로서비스로 분리하여 LLM 타임아웃이 웹 서비스에 영향을 주지 않습니다.

---

## 🔧 사전 준비

### 1. 기업마당 API 키 발급

1. [기업마당 Open API 신청 페이지](https://www.bizinfo.go.kr/apiDetail.do?id=bizinfoApi) 접속
2. 서비스 이용 신청 (기관명, 담당자명, 이메일, 전화번호, 시스템 IP 등 입력)
3. 승인 후 이메일로 `crtfcKey` (인증키) 수령

### 2. Docker Desktop 설치

- [Docker Desktop 다운로드](https://www.docker.com/products/docker-desktop/)
- 설치 후 Docker Desktop 실행 확인

> **⚠️ 메모리 설정 (AI 요약 기능 사용 시)**
> AI 요약에 사용하는 `gpt-oss-safeguard:20b` 모델은 실행 시 약 13.1 GiB RAM이 필요합니다.
> Docker Desktop → Settings → Resources → Memory를 **16 GiB 이상**으로 설정하세요.
> (호스트 시스템에 32 GiB RAM 권장. AI 요약 기능 미사용 시 이 설정은 불필요합니다.)

### 3. 소스 코드 클론

```bash
git clone https://github.com/syun-kwon/bizinfo-demo.git
cd bizinfo-demo
```

---

## 🚀 빠른 시작 (Docker)

### 1단계: 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어 발급받은 API 키를 입력합니다.

```bash
# .env
BIZINFO_API_KEY=여기에_발급받은_API_키_입력
```

### 2단계: 컨테이너 빌드 및 실행

```bash
docker compose up -d
```

최초 실행 시 이미지 빌드 및 Ollama 모델 다운로드에 상당 시간이 소요됩니다.

> **최초 실행 소요 시간 안내**
> - Docker 이미지 빌드: 1~2분
> - `gpt-oss-safeguard:20b` 모델 다운로드: **약 13.8 GB** (네트워크 속도에 따라 10분~1시간)
> - 모델 다운로드 진행 상황: `docker compose logs -f ollama-model-init`
> - 모델 다운로드 완료 전에는 AI 요약 기능이 동작하지 않습니다.

### 3단계: 접속 확인

| 서비스 | URL |
|--------|-----|
| 웹 UI | http://localhost:3000 |
| REST API 문서 (Swagger) | http://localhost:3000/docs |
| MCP SSE (Claude Desktop용) | http://localhost:8000/sse |

```bash
# 정상 동작 확인
curl http://localhost:3000/api/health
# {"status":"ok"}
```

### 운영 명령어

```bash
# 컨테이너 상태 확인
docker compose ps

# 로그 확인 (전체)
docker compose logs -f

# 로그 확인 (서비스별)
docker compose logs -f bizinfo-web
docker compose logs -f bizinfo-mcp
docker compose logs -f bizinfo-summarizer
docker compose logs -f ollama
docker compose logs -f ollama-model-init  # 모델 다운로드 진행 상황

# 중지
docker compose down

# 코드 수정 후 재빌드
docker compose build
docker compose up -d
```

---

## 🤖 Claude Desktop 연동

### MCP 서버를 통해 Claude에서 자연어로 지원사업을 조회할 수 있습니다.

> **전제 조건**: Docker 컨테이너가 실행 중이어야 합니다. (`docker compose up -d`)

### 설정 방법

Claude Desktop의 설정 파일을 수정합니다.

**macOS**
```bash
open ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

**Windows**
```
%APPDATA%\Claude\claude_desktop_config.json
```

아래 내용을 추가합니다.

```json
{
  "mcpServers": {
    "bizinfo": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

### Claude Desktop 재시작

설정 파일 저장 후 Claude Desktop을 재시작합니다.
좌측 사이드바 또는 도구 목록에 `bizinfo` MCP 도구가 표시되면 연동 완료입니다.

### 사용 예시

Claude Desktop 채팅창에 다음과 같이 입력합니다.

```
지원사업 분야별 통계 보여줘

최근 7일 신규 창업 지원사업 뭐 있어?

경기도 기술 분야 지원사업 검색해줘

이번 달 수출 분야 지원사업 마크다운 리포트 작성해줘
```

---

## 🖥 MCP 단독 실행 (Docker 없이)

Claude Desktop에서 로컬 Python으로 직접 MCP 서버를 실행하는 방법입니다.

### 1. Python 3.11 이상 준비

```bash
# macOS (Homebrew)
brew install python@3.11

# 버전 확인
python3.11 --version
```

### 2. 패키지 설치

```bash
cd bizinfo_mcp
pip3.11 install -r requirements.txt
```

### 3. 환경변수 설정

```bash
cp .env.example .env
# .env 파일에 API 키 입력
```

### 4. Claude Desktop 설정 (stdio 방식)

```json
{
  "mcpServers": {
    "bizinfo": {
      "command": "/opt/homebrew/bin/python3.11",
      "args": ["/절대경로/bizinfo_demo/bizinfo_mcp/server.py"],
      "env": {
        "BIZINFO_API_KEY": "여기에_API_키_입력"
      }
    }
  }
}
```

> `command` 경로는 `which python3.11` 명령으로 확인하세요.

### 5. 동작 테스트 (CLI)

```bash
cd bizinfo_mcp
BIZINFO_API_KEY=your_key python3.11 -c "
import asyncio
from server import bizinfo_get_stats, StatsInput, RegionType

async def test():
    result = await bizinfo_get_stats(StatsInput(region=RegionType.전국))
    print(result)

asyncio.run(test())
"
```

---

## 🌐 웹 UI 사용법

### 📊 분야별 통계 탭

지역을 선택하고 **조회** 버튼을 클릭합니다.
8개 분야(금융·기술·인력·수출·내수·창업·경영·기타)의 진행 중 공고 건수를 표로 표시합니다.

![통계 예시]

| 분야 | 전국 | 서울 |
|------|------|------|
| 금융 | 166건 | 26건 |
| 기술 | 211건 | 120건 |
| 창업 | 55건 | 36건 |
| 합계 | 1,037건 | 473건 |

### 🔍 지원사업 검색 탭

| 필터 | 선택지 | 동작 방식 |
|------|--------|----------|
| 키워드 | 자유 입력 | 공고 제목에 포함된 단어 검색 |
| 분야 | 전체/금융/기술/인력/수출/내수/창업/경영/기타 | API 레벨 필터 |
| 지역 | 전국/서울/부산 등 17개 시도 | API 레벨 필터 (`hashtags`) |
| 상태 | 진행중/마감/전체 | 신청 마감일 기준 클라이언트 필터 |
| 페이지당 건수 | 10/20/50건 | - |

검색 후 **← 이전 / 다음 →** 버튼으로 페이지를 이동합니다.
키워드 입력 후 **Enter** 키로도 검색할 수 있습니다.

### 🆕 신규 공고 탭

| 필터 | 선택지 |
|------|--------|
| 조회 기간 | 최근 3/7/14/30일 |
| 분야 | 전체 또는 특정 분야 |
| 지역 | 전국 또는 특정 시도 |
| 최대 페이지 | 2/3/5/10페이지 |

등록일 기준으로 최신 공고를 시간 역순으로 표시합니다.

### 📋 리포트 탭

| 필터 | 선택지 |
|------|--------|
| 기간 | 최근 7/14/30/60일 |
| 분야 | 전체 또는 특정 분야 |
| 지역 | 전국 또는 특정 시도 |
| 최대 건수 | 20/50/100건 |

**생성** 버튼 클릭 후 분야별로 분류된 마크다운 리포트가 화면에 표시됩니다.
**⬇ 다운로드** 버튼으로 `.md` 파일을 저장할 수 있습니다.

### 🤖 AI 요약 버튼

검색 결과, 신규 공고, 리포트 등 어느 탭에서든 **bizinfo.go.kr 링크 옆에 보라색 `AI 요약` 버튼**이 자동으로 표시됩니다.

| 단계 | 설명 |
|------|------|
| 1 | 공고 링크 옆 **`AI 요약`** 버튼 클릭 |
| 2 | "요약 중…" 표시와 함께 해당 공고 페이지를 스크래핑 |
| 3 | 로컬 Ollama LLM(`gpt-oss-safeguard:20b`)으로 분석 |
| 4 | 공고 링크 아래에 5개 항목 요약 결과 표시 |

**요약 출력 형식**
```
1. 사업 목적: (한 문장)
2. 지원 대상: (자격 요건 핵심)
3. 지원 내용: (금액 또는 혜택)
4. 신청 방법 및 기간: (방법과 일정)
5. 주의사항 또는 특이사항: (중요 제약)
```

> **소요 시간**: 첫 번째 요약은 모델 로딩으로 2~3분, 이후 요청은 30~90초 소요됩니다.
> **한계**: 공고의 상세 본문(PDF 첨부 파일)은 분석 대상에서 제외되며, 상세 페이지 HTML 텍스트만 요약합니다.

---

## 📚 MCP 도구 레퍼런스

### `bizinfo_search_programs` — 지원사업 검색

분야·지역·키워드·상태 조건으로 지원사업 공고를 검색합니다.

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `keyword` | string (선택) | — | 공고 제목 검색어 (1~100자) |
| `realm` | enum | `전체` | 금융/기술/인력/수출/내수/창업/경영/기타/전체 |
| `region` | enum | `전국` | 서울/부산/대구/인천/광주/대전/울산/세종/경기/강원/충북/충남/전북/전남/경북/경남/제주/전국 |
| `status` | enum | `진행중` | 진행중/마감/전체 |
| `page` | int | `1` | 페이지 번호 |
| `page_size` | int | `20` | 페이지당 건수 (최대 100) |

**Claude 사용 예시**
```
창업 분야 서울 지역 진행 중인 지원사업 찾아줘
R&D 키워드로 기술 분야 지원사업 검색해줘
마감된 수출 지원사업 목록 보여줘
```

---

### `bizinfo_list_new_programs` — 신규 공고 조회

최근 N일 이내 등록된 신규 지원사업 공고를 조회합니다.

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `days` | int | `7` | 최근 N일 이내 (1~90) |
| `realm` | enum | `전체` | 분야 필터 |
| `region` | enum | `전국` | 지역 필터 |
| `page_size` | int | `30` | 페이지당 건수 |
| `max_pages` | int | `3` | 최대 조회 페이지 수 (1~10) |

**Claude 사용 예시**
```
이번 주 새로 올라온 지원사업 알려줘
최근 30일 경기도 창업 분야 신규 공고 보여줘
```

---

### `bizinfo_generate_report` — 리포트 생성

최근 신규 공고를 수집하여 분야별로 정리한 마크다운 리포트를 생성합니다.

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `days` | int | `7` | 최근 N일 이내 공고 수집 (1~90) |
| `realm` | enum | `전체` | 분야 필터 |
| `region` | enum | `전국` | 지역 필터 |
| `max_items` | int | `50` | 최대 공고 수 (1~200) |
| `title` | string (선택) | 자동 생성 | 리포트 제목 |

**Claude 사용 예시**
```
주간 지원사업 리포트 만들어줘
이번 달 수출 분야 신규 공고 리포트 작성해줘
"2026년 3월 창업 지원사업 현황"이라는 제목으로 리포트 만들어줘
```

---

### `bizinfo_get_stats` — 분야별 통계

현재 진행 중인 지원사업의 분야별 건수를 조회합니다.

| 파라미터 | 타입 | 기본값 | 설명 |
|----------|------|--------|------|
| `region` | enum | `전국` | 지역 필터 |

**Claude 사용 예시**
```
지원사업 분야별 현황 보여줘
서울 지역 지원사업 통계 알려줘
```

---

## 🔌 API 엔드포인트

웹 컨테이너(`http://localhost:3000`)가 제공하는 REST API입니다.
Swagger 문서: http://localhost:3000/docs

### `GET /api/stats`

분야별 통계 조회

| 파라미터 | 필수 | 예시 |
|----------|------|------|
| `region` | 선택 | `서울` (기본: `전국`) |

```bash
curl "http://localhost:3000/api/stats?region=서울"
```

---

### `GET /api/search`

지원사업 검색

| 파라미터 | 필수 | 예시 |
|----------|------|------|
| `keyword` | 선택 | `R%26D` |
| `realm` | 선택 | `창업` (기본: `전체`) |
| `region` | 선택 | `경기` (기본: `전국`) |
| `status` | 선택 | `진행중` (기본: `진행중`) |
| `page` | 선택 | `1` (기본: `1`) |
| `page_size` | 선택 | `20` (기본: `10`, 최대: `100`) |

```bash
curl "http://localhost:3000/api/search?realm=창업&region=서울&page=1&page_size=10"
```

---

### `GET /api/new`

신규 공고 조회

| 파라미터 | 필수 | 예시 |
|----------|------|------|
| `days` | 선택 | `7` (기본: `7`, 최대: `90`) |
| `realm` | 선택 | `기술` (기본: `전체`) |
| `region` | 선택 | `전국` (기본: `전국`) |
| `max_pages` | 선택 | `3` (기본: `3`, 최대: `10`) |

```bash
curl "http://localhost:3000/api/new?days=14&realm=기술"
```

---

### `GET /api/report`

마크다운 리포트 생성

| 파라미터 | 필수 | 예시 |
|----------|------|------|
| `days` | 선택 | `30` (기본: `7`) |
| `realm` | 선택 | `수출` (기본: `전체`) |
| `region` | 선택 | `전국` (기본: `전국`) |
| `max_items` | 선택 | `50` (기본: `50`, 최대: `200`) |

```bash
curl "http://localhost:3000/api/report?days=30&realm=수출" | python3 -c "
import sys, json
print(json.load(sys.stdin)['markdown'])
"
```

---

### `POST /api/summarize`

공고 페이지 스크래핑 후 AI 요약 (bizinfo-summarizer 프록시)

| 필드 | 필수 | 설명 |
|------|------|------|
| `url` | **필수** | 요약할 bizinfo.go.kr 상세 페이지 URL |

```bash
curl -X POST "http://localhost:3000/api/summarize" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://www.bizinfo.go.kr/web/lay1/bbs/S1T122C128/AS/74/view.do?pblancId=PBLN000000000082601"}'
```

응답:
```json
{
  "url": "https://www.bizinfo.go.kr/...",
  "title": "공고 제목",
  "scraped_length": 914,
  "summary": "1. 사업 목적: ...\n2. 지원 대상: ...\n...",
  "model": "gpt-oss-safeguard:20b"
}
```

> 타임아웃: 330초 (모델 첫 로딩 시 2~3분 소요)

---

### 공통 응답 형식

모든 엔드포인트는 마크다운 문자열을 포함한 JSON을 반환합니다.

```json
{
  "markdown": "# 🏢 기업마당 지원사업 검색 결과\n\n..."
}
```

오류 시:

```json
{
  "detail": "오류 메시지"
}
```

---

## 📁 파일 구조

```
bizinfo_demo/
├── .env                          ← API 키 (로컬 전용, git 제외)
├── .env.example                  ← API 키 템플릿 (git 포함)
├── .gitignore
├── docker-compose.yml            ← 통합 실행 (mcp + web + summarizer + ollama)
├── ARCHITECTURE.md               ← 상세 아키텍처 문서
├── WORK_LOG.md                   ← 개발 작업 로그
├── README.md                     ← 이 파일
│
├── bizinfo_mcp/                  ← MCP 서버
│   ├── server.py                 ← 핵심 로직 (MCP 도구 4개 정의)
│   ├── requirements.txt          ← mcp, httpx, pydantic
│   ├── Dockerfile
│   ├── docker-compose.yml        ← MCP 서버 단독 실행용
│   ├── .env.example
│   └── claude_desktop_config_example.json
│
├── bizinfo_web/                  ← 웹 프론트엔드
│   ├── main.py                   ← FastAPI 백엔드 + /api/summarize 프록시
│   ├── requirements.txt          ← fastapi, uvicorn, httpx
│   ├── Dockerfile
│   └── static/
│       └── index.html            ← SPA (Tailwind CSS + marked.js + AI 요약 UI)
│
└── bizinfo_summarizer/           ← AI 요약 마이크로서비스
    ├── main.py                   ← FastAPI (스크래핑 + Ollama 호출)
    ├── requirements.txt          ← fastapi, httpx, beautifulsoup4, lxml
    └── Dockerfile
```

---

## ⚙️ 환경변수

| 변수명 | 필수 | 설명 |
|--------|------|------|
| `BIZINFO_API_KEY` | **필수** | 기업마당에서 발급받은 API 인증키 |
| `MCP_TRANSPORT` | 선택 | `sse` 또는 `stdio` (기본: `stdio`) |
| `MCP_HOST` | 선택 | SSE 바인딩 주소 (기본: `0.0.0.0`) |
| `MCP_PORT` | 선택 | SSE 포트 (기본: `8000`) |
| `SUMMARIZER_URL` | 선택 | bizinfo-summarizer 주소 (기본: `http://bizinfo-summarizer:4000`) |
| `OLLAMA_HOST` | 선택 | Ollama 서버 주소 (기본: `http://ollama:11434`) |
| `OLLAMA_MODEL` | 선택 | 요약에 사용할 Ollama 모델 (기본: `gpt-oss-safeguard:20b`) |

---

## 🔍 트러블슈팅

### Docker 컨테이너가 시작되지 않을 때

```bash
# 로그 확인
docker compose logs bizinfo-web
docker compose logs bizinfo-mcp

# 컨테이너 재시작
docker compose down && docker compose up -d
```

### API 키 오류 (`BIZINFO_API_KEY 환경변수가 설정되지 않았습니다`)

`.env` 파일이 프로젝트 루트에 있는지, API 키가 올바르게 입력되었는지 확인합니다.

```bash
cat .env
# BIZINFO_API_KEY=실제키값  ← 이렇게 되어 있어야 함
```

### Claude Desktop에서 MCP 도구가 보이지 않을 때

1. Docker 컨테이너가 실행 중인지 확인합니다.

   ```bash
   docker compose ps
   # bizinfo-mcp가 Up 상태여야 함
   ```

2. MCP SSE 엔드포인트에 접근 가능한지 확인합니다.

   ```bash
   curl http://localhost:8000/sse
   # 연결이 열려 있어야 함
   ```

3. `claude_desktop_config.json` 파일의 URL을 확인합니다.

   ```json
   { "mcpServers": { "bizinfo": { "url": "http://localhost:8000/sse" } } }
   ```

4. Claude Desktop을 완전히 종료 후 재시작합니다.

### 검색 결과가 없을 때

- 분야·지역 필터를 `전체` / `전국`으로 초기화하고 재검색합니다.
- 키워드가 너무 구체적이면 결과가 없을 수 있습니다. 짧은 키워드를 사용해보세요.
- 상태를 `진행중`에서 `전체`로 변경해보세요.

### AI 요약이 동작하지 않을 때

```bash
# 요약 서비스 상태 확인
curl http://localhost:4000/health

# Ollama 모델 다운로드 완료 여부 확인
docker exec bizinfo_demo-ollama-1 ollama list

# 모델이 없으면 수동으로 다운로드
docker exec bizinfo_demo-ollama-1 ollama pull gpt-oss-safeguard:20b

# 서비스 로그 확인
docker compose logs bizinfo-summarizer
docker compose logs ollama
```

### Docker Desktop 메모리 부족 (`model requires 13.1 GiB, available X GiB`)

Docker Desktop → Settings → Resources → Memory 슬라이더를 **16 GiB 이상**으로 조정 후 Apply & Restart.

### 응답이 느릴 때

통계 조회는 8개 분야를 병렬로 API 호출하므로 첫 조회 시 5~10초 소요될 수 있습니다.
리포트 생성은 여러 페이지를 수집하므로 조건에 따라 10~30초 소요될 수 있습니다.
AI 요약은 첫 번째 요청 시 모델 로딩으로 2~3분, 이후 30~90초 소요됩니다.

---

## 📌 기술 스택

| 구분 | 기술 |
|------|------|
| MCP 서버 | Python 3.11, FastMCP, httpx, Pydantic v2 |
| 웹 백엔드 | Python 3.11, FastAPI, Uvicorn |
| 웹 프론트엔드 | HTML/JS (Vanilla), Tailwind CSS (CDN), marked.js |
| AI 요약 | Python 3.11, FastAPI, BeautifulSoup4, lxml, httpx |
| 로컬 LLM | Ollama, gpt-oss-safeguard:20b (13.8 GB) |
| 컨테이너 | Docker, Docker Compose |
| 외부 API | 기업마당 Open API (`/uss/rss/bizinfoApi.do`, XML/RSS) |

---

## 📄 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다.
기업마당 Open API 데이터는 공공데이터포털 이용약관을 따릅니다.

---

## 🔗 관련 링크

- [기업마당 Open API 문서](https://www.bizinfo.go.kr/apiDetail.do?id=bizinfoApi)
- [기업마당 지원사업 포털](https://www.bizinfo.go.kr)
- [FastMCP 문서](https://github.com/jlowin/fastmcp)
- [Claude Desktop MCP 설정 가이드](https://modelcontextprotocol.io/quickstart/user)
