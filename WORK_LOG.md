# BizInfo Demo 작업 로그

**작업일**: 2026-03-09
**프로젝트**: 중소벤처기업부 기업마당 지원사업 조회 시스템

---

## 1. 프로젝트 분석

### 초기 상태
- `bizinfo_mcp/server.py` — 기업마당 Open API 연동 MCP 서버 (사전 작성됨)
- FastMCP 기반, 4개 도구 정의
- Python 3.10+ 및 `mcp`, `httpx`, `pydantic` 의존

### 제공 MCP 도구

| 도구명 | 기능 |
|--------|------|
| `bizinfo_search_programs` | 분야/지역/키워드/상태로 지원사업 검색 |
| `bizinfo_list_new_programs` | 최근 N일 신규 공고 목록 조회 |
| `bizinfo_generate_report` | 분야별 마크다운 리포트 자동 생성 |
| `bizinfo_get_stats` | 8개 분야 병렬 통계 조회 |

---

## 2. API 키 설정 및 Claude Desktop 연동

### 작업 내용
- API 키를 `claude_desktop_config.json`에 반영 (키 값은 `.env` 파일로 관리)
- 설정 파일 경로: `~/Library/Application Support/Claude/claude_desktop_config.json`

### 초기 설정 (로컬 프로세스 방식)
```json
{
  "mcpServers": {
    "bizinfo": {
      "command": "/opt/homebrew/bin/python3.11",
      "args": [".../bizinfo_mcp/server.py"],
      "env": { "BIZINFO_API_KEY": "YOUR_API_KEY" }
    }
  }
}
```

---

## 3. MCP 서버 오류 수정

### 문제 1: `python` 명령어 없음
- **원인**: 시스템 Python(3.9)만 존재, `python` 명령 없음
- **해결**: Homebrew로 Python 3.11 설치 (`/opt/homebrew/bin/python3.11`)
- **패키지 설치**: `mcp`, `httpx`, `pydantic` 및 의존성

### 문제 2: API 인증 실패 + JSON 파싱 오류
- **원인 1**: `server.py`가 `authKey` 파라미터 사용 → 실제 API는 `crtfcKey` 사용
- **원인 2**: API가 JSON이 아닌 XML(RSS) 형식으로만 응답
- **해결**: `server.py` 수정

#### 수정 내용 (`server.py`)
```python
# 추가 import
import re
import xml.etree.ElementTree as ET

# XML 파서 함수 추가
def _xml_text(el, tag): ...
def _parse_xml_response(xml_text): ...
  # XML → {"jsonArray": [...], "totalCount": N} 변환
  # 필드 매핑: pblancId, pblancNm, pldirSportRealmLclasCodeNm 등
  # 날짜 변환: "2026-03-06 14:51:46" → "20260306"
  # 신청기간 파싱: "2026-03-03 ~ 2026-04-05" → start/end 분리
  # HTML 태그 제거 (사업개요)

# _call_api 수정
# authKey → crtfcKey
# returnType=JSON 제거
# response.json() → _parse_xml_response(response.text)
```

### 테스트 결과 (4개 도구 모두 정상)
- `bizinfo_get_stats`: 8개 분야 병렬 조회 성공
- `bizinfo_search_programs`: 검색 결과 + 페이지네이션 정상
- `bizinfo_list_new_programs`: 최근 7일 신규 공고 30건 수집
- `bizinfo_generate_report`: 분야별 마크다운 리포트 생성

---

## 4. Docker 로컬 배포 (MCP 서버)

### 생성 파일
- `bizinfo_mcp/Dockerfile`
- `bizinfo_mcp/docker-compose.yml`
- `bizinfo_mcp/.env`
- `bizinfo_mcp/.gitignore`

### MCP 서버 SSE 전환 (`server.py` 하단 수정)
```python
if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport == "sse":
        mcp.settings.host = os.environ.get("MCP_HOST", "0.0.0.0")
        mcp.settings.port = int(os.environ.get("MCP_PORT", "8000"))
        mcp.run(transport="sse")
    else:
        mcp.run()
```

### Claude Desktop 설정 변경 (URL 방식)
```json
{
  "mcpServers": {
    "bizinfo": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

### Docker 명령어
```bash
cd bizinfo_mcp
docker compose build
docker compose up -d
docker compose logs -f
```

---

## 5. 웹 프론트엔드 추가 (통합 Docker Compose)

### 최종 아키텍처
```
브라우저 (http://localhost:3000)
        ↓
bizinfo-web 컨테이너 (FastAPI + HTML/JS)
  - REST API 제공: /api/stats, /api/search, /api/new, /api/report
  - bizinfo_server.py 함수 직접 임포트 호출
        ↓
bizinfo.go.kr Open API (외부 인터넷)

Claude Desktop → bizinfo-mcp 컨테이너 (포트 8000, SSE)
```

### 생성 파일
| 파일 | 설명 |
|------|------|
| `bizinfo_web/main.py` | FastAPI 백엔드 (REST API) |
| `bizinfo_web/requirements.txt` | fastapi, uvicorn, mcp, httpx |
| `bizinfo_web/Dockerfile` | 빌드 설정 |
| `bizinfo_web/static/index.html` | 탭 기반 SPA 프론트엔드 |
| `docker-compose.yml` (루트) | 통합 실행 설정 |
| `.env` (루트) | 공통 환경변수 |

### 웹 프론트엔드 기능
- **📊 분야별 통계**: 지역 선택 → 8개 분야 현황 표
- **🔍 지원사업 검색**: 키워드/분야/지역/상태 필터 + 페이지 이동
- **🆕 신규 공고**: 기간/분야/지역 선택 → 최신 공고 목록
- **📋 리포트**: 마크다운 리포트 생성 + `.md` 파일 다운로드

### 트러블슈팅: MCP SSE 내부 통신 문제
- **문제**: Docker 내부 네트워크에서 MCP SSE 접속 시 `421 Invalid Host header`
- **원인**: FastMCP DNS 리바인딩 보호 기능이 `bizinfo-mcp:8000` Host 헤더 차단
- **해결**: SSE 클라이언트 방식 포기 → `bizinfo_server.py` 함수 직접 임포트 호출

#### `bizinfo_web/Dockerfile` 핵심
```dockerfile
# MCP 서버 코드를 웹 컨테이너에 복사하여 직접 임포트
COPY bizinfo_mcp/server.py ./bizinfo_server.py
```

#### `bizinfo_web/main.py` 핵심
```python
from bizinfo_server import (
    bizinfo_get_stats, bizinfo_search_programs, ...
)
# MCP 프로토콜 없이 함수 직접 호출
result = await bizinfo_get_stats(StatsInput(region=RegionType(region)))
```

---

## 6. 최종 파일 구조

```
bizinfo_demo/
├── .env                              ← BIZINFO_API_KEY=YOUR_API_KEY (gitignore 처리)
├── docker-compose.yml                ← 통합 실행 (mcp + web)
├── WORK_LOG.md                       ← 이 파일
├── bizinfo_mcp/
│   ├── server.py                     ← MCP 서버 (수정됨)
│   ├── Dockerfile
│   ├── docker-compose.yml            ← MCP 단독 실행용
│   ├── requirements.txt
│   ├── .env
│   ├── .gitignore
│   ├── README.md
│   └── claude_desktop_config_example.json
└── bizinfo_web/
    ├── main.py                       ← FastAPI 백엔드
    ├── requirements.txt
    ├── Dockerfile
    └── static/
        └── index.html                ← SPA 프론트엔드
```

---

## 7. 실행 중인 컨테이너

| 컨테이너 | 이미지 | 포트 | 용도 |
|----------|--------|------|------|
| `bizinfo_demo-bizinfo-web-1` | bizinfo_demo-bizinfo-web (282MB) | 3000 → 외부 공개 | 웹 UI + REST API |
| `bizinfo_demo-bizinfo-mcp-1` | bizinfo_demo-bizinfo-mcp (280MB) | 8000 → 내부 전용 | Claude Desktop MCP |

---

## 8. 운영 명령어

```bash
# 전체 시작 (루트 디렉토리에서)
cd bizinfo_demo
docker compose up -d

# 로그 확인
docker compose logs -f

# 특정 서비스 로그
docker compose logs -f bizinfo-web
docker compose logs -f bizinfo-mcp

# 전체 중지
docker compose down

# 코드 변경 후 재빌드
docker compose build
docker compose up -d
```

## 9. 접속 정보

| 항목 | URL |
|------|-----|
| 웹 UI | http://localhost:3000 |
| REST API 문서 | http://localhost:3000/docs |
| MCP SSE (Claude Desktop) | http://localhost:8000/sse |

---

## 10. 향후 배포 확장 계획

로컬 Docker → 클라우드 배포 시 변경 사항:

| 항목 | 로컬 | 배포 |
|------|------|------|
| 접속 URL | http://localhost:3000 | https://your-domain.com |
| SSL | 불필요 | Nginx + Let's Encrypt |
| API 키 관리 | .env 파일 | Secrets Manager 등 |
| docker-compose.yml | 현재 그대로 | Nginx 서비스 추가 |
| server.py / main.py | 변경 없음 | 변경 없음 |

---

---

# 추가 작업 로그

**작업일**: 2026-03-10

---

## 11. 아키텍처 문서 작성

- `ARCHITECTURE.md` 파일 신규 생성
- 시스템 전체 구조, 컴포넌트 상세, 데이터 흐름, Docker 구성, 배포 가이드 포함

---

## 12. 웹 UI 필터 동작 불량 원인 분석 및 수정

### 문제 상황

`http://localhost:3000` 웹 UI에서 분야·지역·상태·키워드 필터를 선택/입력해도 결과가 변하지 않음.

### 원인 규명 (1단계): 잘못된 API 파라미터

실제 API 응답을 직접 호출해 확인한 결과, 기존 코드가 사용하던 파라미터가 모두 기업마당 RSS API에서 지원되지 않는 파라미터였음.

| 기능 | 기존 (미동작) 파라미터 | 올바른 파라미터 |
|------|----------------------|----------------|
| 분야 필터 | `pldirSportRealmLclasCode=060` | `searchLclasId=06` |
| 지역 필터 | `bizSprptLclasCode=11` | `hashtags=서울` |
| 상태 필터 | `pbancSttus=ing` | API 미지원 → 클라이언트 사이드 |
| 키워드 필터 | `pblancNm=창업` | API 미지원 → 클라이언트 사이드 |

어떤 필터 조합을 사용해도 항상 totCnt=1005(동일)가 반환되는 것을 실증적으로 확인.

### 원인 규명 (2단계): API 문서 확인

`https://www.bizinfo.go.kr/apiDetail.do?id=bizinfoApi` 공식 API 문서 확인.

**올바른 파라미터 명세**
- `searchLclasId`: 분야 코드 (01=금융, 02=기술, 03=인력, 04=수출, 05=내수, 06=창업, 07=경영, 09=기타)
- `hashtags`: 지역명을 한국어로 직접 입력 (예: `hashtags=서울`, 복수 시 쉼표 구분)
- `pageIndex` / `pageUnit`: 페이지네이션 (정상 동작)
- 상태·키워드: API에서 미지원 → Python 클라이언트 사이드 처리 유지

### 수정 내용 (`bizinfo_mcp/server.py`)

#### 1. `REALM_CODES` 코드 수정
```python
# 수정 전 (미동작)
REALM_CODES = {"금융": "010", "기술": "020", ...}

# 수정 후 (정상)
REALM_CODES = {"금융": "01", "기술": "02", ..., "기타": "09"}
```

#### 2. `_build_search_params()` 파라미터 수정
```python
# 수정 전
params["pldirSportRealmLclasCode"] = REALM_CODES.get(realm.value, "")
params["bizSprptLclasCode"] = REGION_CODES.get(region.value, "")

# 수정 후
params["searchLclasId"] = REALM_CODES.get(realm.value, "")  # 분야
params["hashtags"] = region.value                            # 지역 (한국어 이름)
```

#### 3. `_fetch_all_programs()` 추가 — 병렬 전체 데이터 조회

API 레벨 필터(분야·지역)를 적용한 뒤 남은 상태·키워드 필터를 처리하기 위해,
조건에 맞는 데이터를 병렬로 일괄 수집하는 헬퍼 추가.

```python
async def _fetch_all_programs(max_pages=12, extra_params=None) -> list[dict]:
    # searchLclasId, hashtags 등 API 필터 파라미터 전달 가능
    # 첫 페이지로 total 파악 → 나머지 페이지 asyncio.gather 병렬 조회
```

#### 4. `_apply_filters()` 추가 — Python 클라이언트 사이드 필터

```python
def _apply_filters(items, realm, keyword, status, days) -> list[dict]:
    # 상태: reqstCloseEndDe 마감일과 오늘 비교
    # 키워드: pblancNm 제목에 포함 여부 (대소문자 무시)
    # 날짜: pblancRegistDt 기준 N일 이내
```

#### 5. `bizinfo_get_stats()` — searchLclasId 병렬 조회로 복원

```python
# 8개 분야를 searchLclasId로 각각 조회 → totCnt 집계
async def _fetch_realm_count(realm):
    params = {"searchLclasId": REALM_CODES[realm.value], "pageUnit": 1, ...}
    if region != 전국: params["hashtags"] = region.value
    ...
results = await asyncio.gather(*[_fetch_realm_count(r) for r in realms])
```

#### 6. `bizinfo_search_programs()` — API + 클라이언트 사이드 혼합

```python
# API 레벨: searchLclasId(분야) + hashtags(지역)
api_params = {"searchLclasId": ..., "hashtags": ...}
all_items = await _fetch_all_programs(max_pages=6, extra_params=api_params)

# 클라이언트 사이드: 상태·키워드 필터
filtered = _apply_filters(all_items, keyword=..., status=...)
```

#### 7. `bizinfo_list_new_programs()` / `bizinfo_generate_report()` 동일 방식 적용

### 수정 내용 (`bizinfo_web/static/index.html`)

- **Enter 키 버그 수정**: 키워드 입력 후 Enter 시 `loadSearch()` → `loadSearch(1)` (페이지 리셋)
- **지역 필터 복원**: API 파라미터 수정으로 지역 필터가 동작하게 되어 disabled 상태 해제

### 검증 결과

| 테스트 | 결과 |
|--------|------|
| 창업 분야 검색 | 45건 (모두 창업 분야 공고) |
| 창업 + 서울 검색 | 36건 (창업 분야, 서울 관련 공고) |
| AI 키워드 검색 | 19건 (제목에 AI 포함) |
| 통계 전국 | 합계 1,037건 (분야별 상이한 건수) |
| 통계 서울 | 합계 473건 (전국과 명확히 구분됨) |

분야·지역·키워드·상태 필터 모두 정상 동작 확인.

---

## 13. AI 요약 서비스 추가 (bizinfo-summarizer)

**작업일**: 2026-03-10

### 배경 및 목적

기존 시스템은 기업마당 API가 제공하는 `bsnsSumryCn`(사업개요) 필드만 표시했으나, 이 필드는 대부분 비어 있거나 수십 자 수준의 단편 정보에 불과함. 상세 공고 링크를 클릭해야 내용을 확인할 수 있는 불편함 해소를 위해 AI 요약 기능 추가.

### 아키텍처 설계

```
bizinfo-web (3000)
    ↓ POST /api/summarize (프록시)
bizinfo-summarizer (4000)   ← 신규 컨테이너
    ├── 스크래핑: bizinfo.go.kr 상세 페이지 HTML 파싱
    └── 요약: Ollama API 호출
ollama (11434)              ← 신규 컨테이너
    └── gpt-oss-safeguard:20b 모델
```

### 신규 생성 파일

| 파일 | 내용 |
|------|------|
| `bizinfo_summarizer/main.py` | FastAPI 앱 (`/summarize` POST, `/health` GET) |
| `bizinfo_summarizer/requirements.txt` | fastapi, uvicorn, httpx, beautifulsoup4, lxml, pydantic |
| `bizinfo_summarizer/Dockerfile` | python:3.11-slim, port 4000 |

### 수정 파일

| 파일 | 변경 내용 |
|------|----------|
| `docker-compose.yml` | `bizinfo-summarizer`, `ollama`, `ollama-model-init` 서비스 및 `ollama_data` 볼륨 추가 |
| `bizinfo_web/main.py` | `POST /api/summarize` 프록시 엔드포인트 추가, `SUMMARIZER_URL` 환경변수 |
| `bizinfo_web/static/index.html` | `.ai-summary-btn`/`.ai-summary-box` CSS, `injectSummarizeButtons()`, `requestSummary()` JS 함수 추가 |

### 스크래핑 로직 (`bizinfo_summarizer/main.py`)

```python
CONTENT_SELECTORS = [
    "div.view_cont",           # bizinfo.go.kr 실제 구조 (최우선)
    "div.support_project_detail",
    "div.sub_cont",
    ... (8개 폴백 선택자)
]
```

- `User-Agent` + `Referer` 헤더로 봇 차단 우회
- `header` 태그 제거 제외 (콘텐츠가 내부에 위치함)
- 최적 선택자 불일치 시 `body` 전체 텍스트로 자동 폴백
- 5,000자 상한으로 Ollama 프롬프트 길이 제어

### Ollama 요약 프롬프트

5개 항목 구조화 프롬프트 (한국어):
1. 사업 목적 / 2. 지원 대상 / 3. 지원 내용 / 4. 신청 방법 및 기간 / 5. 주의사항

설정값: `temperature=0.3` (사실 추출 집중), `num_predict=1024`, `timeout=300s`

### docker-compose.yml 서비스 구성

```yaml
ollama:            # ollama/ollama:latest, 포트 11434, ollama_data 볼륨
ollama-model-init: # curlimages/curl, 모델 pull 1회성 실행
bizinfo-summarizer: # 자체 빌드, 포트 4000, ollama-model-init 완료 후 시작
```

**Ollama 헬스체크**: `CMD ["ollama", "list"]` (curl 미포함 이미지)

### 웹 UI 변경

검색·신규공고·리포트 탭 결과의 `bizinfo.go.kr` 링크 옆에 보라색 `AI 요약` 버튼 자동 삽입.

클릭 흐름:
1. 버튼 클릭 → "요약 중…" 표시
2. `POST /api/summarize` 호출 → bizinfo-web → bizinfo-summarizer → Ollama
3. 완료 시 버튼 아래에 보라색 테두리 박스로 5항목 요약 인라인 표시
4. 재클릭 가능 ("다시 요약")

---

## 14. 테스트 및 버그 수정

**작업일**: 2026-03-10

### 발견 및 수정된 버그

#### Bug 1: Ollama 헬스체크 실패
- **원인**: `docker-compose.yml`의 헬스체크 명령이 `curl -sf http://localhost:11434/`이었으나 Ollama 이미지에 `curl` 미포함
- **수정**: `CMD ["ollama", "list"]` 으로 변경

#### Bug 2: 스크래퍼 선택자 미일치
- **원인**: bizinfo.go.kr 실제 HTML 구조는 `div.view_cont` 사용. 기존 선택자 목록에 없어 101자 단편 텍스트만 추출됨
- **수정**: `div.view_cont`, `div.support_project_detail`, `div.sub_cont` 을 최우선 선택자로 추가

#### Bug 3: 선택자 폴백 미작동
- **원인**: 선택자가 매칭되어 `content_text`에 짧은 텍스트가 할당되면, `if not content_text:` 조건이 False가 되어 body 폴백이 실행되지 않음
- **수정**: `if len(content_text) < 200:` 조건으로 변경

#### Bug 4: `header` 태그 제거로 콘텐츠 손실
- **원인**: `soup(["script","style","nav","header","footer"])` 에서 `header` 제거 시 실제 콘텐츠 영역도 함께 제거됨
- **수정**: 노이즈 제거 목록에서 `header` 제외

#### Bug 5: Ollama 타임아웃 (첫 로딩)
- **원인**: 20B 모델 첫 메모리 로딩에 120초 이상 소요. `OLLAMA_TIMEOUT=120.0` 초과
- **수정**: `OLLAMA_TIMEOUT=300.0`, 웹 프록시 `timeout=330.0`

#### Bug 6: 요약 내용 잘림
- **원인**: `num_predict=512` 설정으로 5항목 완성 전에 생성 중단
- **수정**: `num_predict=1024` 로 증가

#### Bug 7: Docker Desktop 메모리 부족
- **현상**: `model requires more system memory (13.1 GiB) than is available (2.4 GiB)` 오류
- **원인**: Docker Desktop 기본 메모리 7.6 GiB로는 20B 모델(13.1 GiB 필요) 로딩 불가
- **해결**: Docker Desktop Settings → Resources → Memory를 16 GiB 이상으로 증가 (시스템 RAM 32 GB 여유분 활용)

### 최종 테스트 결과

| 테스트 항목 | 결과 |
|------------|------|
| 4개 컨테이너 정상 기동 | ✅ |
| `gpt-oss-safeguard:20b` 모델 로딩 | ✅ (13.8GB) |
| 스크래핑 (`div.view_cont`) | ✅ 800~914자 추출 |
| Ollama 요약 직접 호출 (`/summarize`) | ✅ 5항목 한국어 요약 |
| 웹 프록시 경유 (`/api/summarize`) | ✅ 동일 정상 동작 |
| 웹 UI `AI 요약` 버튼 주입 | ✅ 전 탭 공통 적용 |

**요약 소요 시간**: 첫 요청 약 2~3분 (모델 메모리 로딩), 이후 요청 30~90초

### 한계 및 향후 개선 방향

현재 요약은 상세 페이지의 개요(메타데이터) 기반이며, 실제 공고문 전체 내용은 첨부 PDF에 포함되어 있음.

| 구분 | 현재 | 향후 개선 시 |
|------|------|-------------|
| 데이터 소스 | 상세 페이지 개요 (~900자) | 첨부 PDF 전문 (5,000~20,000자) |
| 요약 품질 | 기본 메타데이터 수준 | 지원 자격·금액·심사 기준 포함 |
| 처리 방식 | 동기 (버튼 클릭 → 대기) | 비동기 큐 + SSE 결과 전달 필요 |
| 모델 | Ollama 로컬 20B CPU | 상용 LLM API 대비 속도/품질 낮음 |

PDF 추출은 이미지 스캔 PDF·HWP 파일 처리 난이도, 컨텍스트 길이 한계(4096 토큰), 추론 시간(5~10분) 문제로 현 아키텍처에서는 사용자 경험 저하가 우려되어 현재 구현에서 제외함.

---

## Section 15: Docker 환경 정리 (2026-03-11)

### 작업 내용

불필요한 Docker 컨테이너 및 이미지 정리.

| 삭제 항목 | 종류 | 이유 |
|-----------|------|------|
| `bizinfo_demo-ollama-model-init-1` | 컨테이너 (Exited) | 모델 초기화 완료 후 종료된 일회성 컨테이너 |
| `bizinfo_mcp-bizinfo-mcp:latest` | 이미지 (280MB) | `bizinfo_mcp/` 내 별도 docker-compose로 빌드된 중복 이미지 |

### 정리 후 상태

**컨테이너 (4개 Running)**
```
bizinfo_demo-bizinfo-summarizer-1   Up   포트 4000
bizinfo_demo-bizinfo-web-1          Up   포트 3000
bizinfo_demo-ollama-1               Up   포트 11434 (healthy)
bizinfo_demo-bizinfo-mcp-1          Up   포트 8000
```

**이미지 (5개)**
```
bizinfo_demo-bizinfo-mcp:latest          280MB
bizinfo_demo-bizinfo-summarizer:latest   272MB
bizinfo_demo-bizinfo-web:latest          283MB
curlimages/curl:latest                    38MB  (ollama-model-init 재실행용)
ollama/ollama:latest                     8.71GB
```

---

## Section 16: 클라우드 배포 옵션 분석 (2026-03-11)

### 배경

현재 로컬 Docker Compose 환경에서 운영 중인 서비스를 클라우드로 이전하는 방안 검토.

### Supabase 이전 가능 여부 분석

**결론: 현재 구조 그대로 Supabase 이전 불가**

Supabase는 BaaS 플랫폼으로 Python 서버 실행 및 대용량 ML 모델 실행을 지원하지 않음.

| 서비스 | Supabase 호환 | 이유 |
|--------|:---:|------|
| `bizinfo-web` (FastAPI) | ❌ | Python 서버 호스팅 불가 |
| `bizinfo-mcp` (FastMCP SSE) | ❌ | Deno 기반 Edge Functions만 지원 |
| `bizinfo-summarizer` | ❌ | Python 런타임 없음 |
| `ollama` (20B LLM) | ❌ | 13.1 GiB 요구 → Edge Functions 512MB 한도의 26배 초과 |

**부분 활용 가능한 시나리오**: Supabase PostgreSQL을 공고 캐싱 DB로, Supabase Auth를 사용자 인증으로 활용하고 나머지는 별도 호스팅.

### 무료 배포 서비스 비교

#### Docker/컨테이너 지원

| 서비스 | 무료 한도 | 특징 |
|--------|-----------|------|
| Railway | $5 크레딧/월 | docker-compose 지원, 배포 간단 |
| Render | 750시간/월 | Docker 지원, 슬립 모드 (15분 미사용 시 중단) |
| Fly.io | VM 3개 (각 256MB) | Docker 지원, 글로벌 엣지, CLI 기반 |
| Koyeb | 2개 서비스 | 메모리 512MB 제한 |

#### AI/LLM 특화 (ollama 대체 후보)

| 서비스 | 무료 한도 | 한국어 품질 |
|--------|-----------|:---:|
| Groq | 분당 30건 | 보통 |
| Google AI Studio (Gemini Flash) | 분당 15건, 일 1,500건 | 우수 |
| Claude API | 없음 (유료) | 최우수 |
| OpenRouter | 일부 모델 무료 | 모델마다 다름 |

### ollama 무료 배포의 현실적 한계

| 항목 | 수치 |
|------|------|
| `gpt-oss-safeguard:20b` 메모리 요구량 | 13.1 GB |
| Render / Railway / Fly.io 무료 메모리 | 256~512 MB |
| 부족 배율 | 25~50배 |

→ **무료 티어에서 ollama 20B 모델 실행 불가**

### 권장 배포 구성 3가지

#### 옵션 A: 빠른 배포 + 무료 운영 (권장)

ollama → Groq 또는 Gemini Flash API로 교체, Python 서버는 Render 무료 티어 배포.

- 예상 월 비용: $0 (무료 한도 내)
- 요약 속도: 3~10초 (현재 30~90초 대비 대폭 향상)
- 코드 변경량: 소 (`bizinfo-summarizer/main.py` `_call_ollama()` 함수만 수정)

#### 옵션 B: 현재 코드 유지 + 유료 서버

Python 서버는 Railway/Render 유료 인스턴스, ollama는 GPU 클라우드(RunPod, Modal).

- 예상 월 비용: $30~80
- 코드 변경량: 없음

#### 옵션 C: Supabase 풀 활용 (장기 재설계)

Python → TypeScript(Deno) 전면 재작성, Edge Functions + Supabase PostgreSQL 구성.

- 예상 월 비용: $0
- 코드 변경량: 대 (전면 재작성)

### 산출물

- `DEPLOYMENT_OPTIONS.md` 신규 작성 — 전체 분석 내용 상세 문서화

### 미결 사항

- [ ] ollama → Groq 또는 Gemini API 교체 작업
- [ ] Render / Fly.io 배포 테스트
- [ ] Supabase PostgreSQL 연동 (공고 캐싱) 설계
