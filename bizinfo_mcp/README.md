# 🏢 BizInfo MCP Server

중소벤처기업부 **기업마당(bizinfo.go.kr)** Open API를 Claude에 연결하는 MCP 서버입니다.
Claude에서 직접 정부 지원사업을 검색하고, 신규 공고 리포트를 자동 생성할 수 있습니다.

---

## 🛠️ 제공 기능 (Tools)

| 도구명 | 설명 |
|--------|------|
| `bizinfo_search_programs` | 분야/지역/키워드로 지원사업 검색 |
| `bizinfo_list_new_programs` | 최근 N일 신규 공고 목록 조회 |
| `bizinfo_generate_report` | 신규 공고 마크다운 리포트 자동 생성 |
| `bizinfo_get_stats` | 분야별 진행 중 공고 통계 조회 |

---

## ⚙️ 설치 방법

### 1단계: Python 의존성 설치

```bash
cd bizinfo_mcp
pip install -r requirements.txt
```

### 2단계: API 키 확인

기업마당(https://www.bizinfo.go.kr) 에서 발급받은 API 키를 준비합니다.

### 3단계: Claude Desktop 연동 설정

Claude Desktop의 설정 파일(`claude_desktop_config.json`)에 아래 내용을 추가합니다.

**macOS 경로**: `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows 경로**: `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "bizinfo": {
      "command": "python",
      "args": ["/절대경로/bizinfo_mcp/server.py"],
      "env": {
        "BIZINFO_API_KEY": "여기에_발급받은_API_키_입력"
      }
    }
  }
}
```

> ⚠️ `/절대경로/` 부분을 실제 server.py 파일의 절대 경로로 바꿔주세요.

### 4단계: Claude Desktop 재시작

설정 저장 후 Claude Desktop을 완전히 종료했다가 다시 실행합니다.

---

## 💬 사용 예시

Claude에서 아래와 같이 요청하면 됩니다:

```
최근 7일간 신규 지원사업 리포트를 만들어줘.
```

```
창업 분야 진행 중인 지원사업을 서울 지역으로 검색해줘.
```

```
R&D 관련 지원사업 목록을 보여줘.
```

```
분야별 진행 중인 지원사업 통계를 알려줘.
```

---

## 🔄 자동 스케줄링 (선택)

Claude의 스케줄 기능을 활용하면 매일 또는 매주 자동으로 신규 공고 리포트를 생성하고 저장할 수 있습니다.

---

## 📋 API 출처

- **기업마당 Open API**: https://www.bizinfo.go.kr
- **API 문서**: https://www.bizinfo.go.kr/apiDetail.do?id=bizinfoApi
- **엔드포인트**: `https://www.bizinfo.go.kr/uss/rss/bizinfoApi.do`
