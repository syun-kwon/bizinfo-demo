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
