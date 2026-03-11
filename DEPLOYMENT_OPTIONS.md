# 배포 옵션 분석 — BizInfo Demo

> 작성일: 2026-03-10
> 현재 환경: 로컬 Docker Compose (macOS, 32GB RAM)

---

## 1. 현재 아키텍처 요약

```
bizinfo-web        FastAPI + HTML    포트 3000   Python 3.11
bizinfo-mcp        FastMCP SSE       포트 8000   Python 3.11
bizinfo-summarizer FastAPI + BS4     포트 4000   Python 3.11
ollama             LLM 런타임        포트 11434  gpt-oss-safeguard:20b (13.8 GB)
```

로컬에서는 Docker Compose 하나로 4개 서비스가 동작하지만, 클라우드 배포 시 각 서비스의 리소스 요구사항이 제약이 된다.

---

## 2. Supabase 배포 가능 여부

### 결론: 현재 구조 그대로 Supabase 이전 불가

Supabase는 **BaaS(Backend-as-a-Service)** 플랫폼으로, 제공하는 기능은 다음과 같다.

| 기능 | 제공 여부 |
|------|:---:|
| PostgreSQL 데이터베이스 | ✅ |
| 인증 (Auth) | ✅ |
| 파일 스토리지 | ✅ |
| Edge Functions (Deno, 메모리 512MB) | ✅ |
| Python 서버 상시 실행 | ❌ |
| Docker 컨테이너 실행 | ❌ |
| 대용량 ML 모델 실행 | ❌ |

### 서비스별 호환성

| 서비스 | Supabase 호환 | 이유 |
|--------|:---:|------|
| `bizinfo-web` (FastAPI) | ❌ | Python 서버 호스팅 불가 |
| `bizinfo-mcp` (FastMCP SSE) | ❌ | Deno 기반 Edge Functions만 지원 |
| `bizinfo-summarizer` (FastAPI + BS4) | ❌ | Python 런타임 없음 |
| `ollama` (20B LLM) | ❌ | 13.1 GB 메모리 요구 → Edge Functions 512MB 한도의 26배 초과 |

### Supabase를 부분 활용하는 방안

전면 이전은 불가하지만, **DB/Auth 레이어로만** 활용하는 혼합 구성은 가능하다.

```
브라우저
   ├── 정적 파일 ──────────── Supabase Storage 또는 Vercel
   ├── API 서버 ────────────── Railway / Render / Fly.io
   ├── 요약 서비스 ─────────── Railway / Render
   ├── LLM ─────────────────── 외부 AI API (Claude, Groq, Gemini)
   └── 데이터 캐싱/저장 ────── Supabase PostgreSQL  ← 여기만 Supabase
```

활용 시나리오:
- 공고 검색 결과를 DB에 캐싱하여 API 호출 횟수 절감
- AI 요약 결과를 DB에 저장하여 동일 URL 재요약 방지
- 사용자 인증이 필요한 경우 Supabase Auth 사용

### Supabase 풀 활용 시 재설계 필요 사항

Edge Functions(Deno/TypeScript)으로 전면 재작성이 필요하다.

```
Supabase Edge Function ─── 기업마당 API 호출 ─── PostgreSQL 저장
Supabase Edge Function ─── 외부 LLM API 호출 ─── 요약 결과 캐싱
Vercel / Netlify       ─── 정적 HTML 서빙
```

| 장점 | 단점 |
|------|------|
| 운영 비용 최소화 | Python → TypeScript 전면 재작성 필요 |
| Supabase 무료 티어 활용 가능 | 작업 공수 큼 |
| 확장성 우수 | |

---

## 3. 무료/저비용 배포 서비스 비교

### 3-1. Docker/컨테이너 지원 (현재 프로젝트와 호환성 높음)

| 서비스 | 무료 한도 | 특징 | 단점 |
|--------|-----------|------|------|
| **Railway** | $5 크레딧/월 | docker-compose 지원, 배포 간단 | 무료 한도 작음 |
| **Render** | 750시간/월 (1개 서비스) | Docker 지원, GitHub 자동 배포 | 무료는 슬립 모드 (15분 미사용 시 중단, 첫 요청 30초 지연) |
| **Fly.io** | 3개 VM 무료 (각 256MB) | Docker 지원, 글로벌 엣지 | CLI 기반, 설정 다소 복잡 |
| **Koyeb** | 2개 서비스 무료 | Docker/GitHub 배포 | 메모리 512MB 제한 |

### 3-2. 정적 사이트 / 프론트엔드 전용

| 서비스 | 무료 한도 | 특징 |
|--------|-----------|------|
| **Vercel** | 무제한 (개인) | GitHub 연동 자동 배포 |
| **Netlify** | 무제한 (개인) | 정적 사이트, Functions 지원 |
| **Cloudflare Pages** | 무제한 | CDN 포함, Workers 연동 |
| **GitHub Pages** | 무제한 | 정적 HTML만 가능 |

### 3-3. 서버리스 함수 (경량 API)

| 서비스 | 무료 한도 | 특징 |
|--------|-----------|------|
| **Supabase Edge Functions** | 500,000건/월 | Deno 기반 |
| **Cloudflare Workers** | 100,000건/일 | 매우 빠름, 전세계 엣지 |
| **Vercel Functions** | 무제한 호출 | Node.js/Python 지원 |

### 3-4. AI/LLM 특화 (ollama 대체 후보)

| 서비스 | 무료 한도 | 특징 | 한국어 품질 |
|--------|-----------|------|:---:|
| **Groq** | 무료 티어 (분당 30건) | 초고속 추론, LLaMA/Mistral 등 | 보통 |
| **Google AI Studio** | 분당 15건, 일 1,500건 | Gemini Flash 무료 | 우수 |
| **Claude API** | 없음 (유료) | 한국어 최우수 | 최우수 |
| **OpenRouter** | 일부 모델 무료 | 여러 모델 통합 API | 모델마다 다름 |
| **Hugging Face Spaces** | CPU 무료 | 모델 직접 실행 가능 | 모델마다 다름 |

---

## 4. ollama 무료 배포의 현실적 한계

**20B 모델은 무료 티어에서 사실상 실행 불가능하다.**

| 항목 | 수치 |
|------|------|
| `gpt-oss-safeguard:20b` 메모리 요구량 | 13.1 GB |
| Render 무료 메모리 | 512 MB |
| Fly.io 무료 메모리 | 256 MB |
| Railway 무료 메모리 | 512 MB |
| 부족 배율 | 25~50배 |

GPU 인스턴스가 필요한 경우 비용:

| 서비스 | 스펙 | 월 비용 |
|--------|------|--------|
| RunPod | RTX 3090 (24GB VRAM) | $0.44/시간 (~$30~50/월) |
| Lambda Labs | A10 (24GB VRAM) | $0.75/시간 |
| Modal | 사용량 기반 | 첫 $30 무료 크레딧 |

---

## 5. 권장 배포 구성

### 옵션 A: 빠른 배포 + 무료 운영 (권장)

**ollama → Groq API 또는 Google Gemini Flash API 교체**

```
[변경 사항]
bizinfo_summarizer/main.py 에서
  _call_ollama() → _call_groq() 또는 _call_gemini() 로 교체
  (수십 줄 수정)

[배포 구성]
정적 HTML      → Vercel 또는 Netlify       (완전 무료)
bizinfo-web    → Render 무료 티어           (슬립 모드 주의)
bizinfo-mcp    → Render 무료 티어           (슬립 모드 주의)
bizinfo-summarizer → Render 무료 티어      (슬립 모드 주의)
ollama         → 제거 (외부 API로 대체)
```

| 항목 | 내용 |
|------|------|
| 예상 월 비용 | $0 (Groq/Gemini 무료 한도 내) |
| 요약 속도 | 3~10초 (로컬 30~90초 대비 대폭 향상) |
| 코드 변경량 | 소 (bizinfo-summarizer/main.py만 수정) |
| 한계 | 무료 한도 초과 시 과금, 외부로 데이터 전송 |

### 옵션 B: 현재 코드 유지 + 유료 서버

```
[배포 구성]
bizinfo-web + bizinfo-mcp + bizinfo-summarizer
  → Railway 또는 Render (메모리 2GB 인스턴스)
ollama (20B 모델)
  → GPU 클라우드 (RunPod, Modal) 또는 별도 VPS
```

| 항목 | 내용 |
|------|------|
| 예상 월 비용 | $30~80 |
| 코드 변경량 | 없음 (docker-compose.yml 환경변수 조정만 필요) |
| 한계 | 비용 발생, GPU 인스턴스 관리 필요 |

### 옵션 C: Supabase 풀 활용 (장기 재설계)

```
[배포 구성]
프론트엔드     → Vercel (정적)
API 로직       → Supabase Edge Functions (TypeScript 재작성)
AI 요약        → Supabase Edge Functions + 외부 LLM API
데이터 캐싱    → Supabase PostgreSQL
```

| 항목 | 내용 |
|------|------|
| 예상 월 비용 | $0 (무료 티어 내) |
| 코드 변경량 | 대 (Python → TypeScript 전면 재작성) |
| 장점 | 확장성, 유지비 최소화 |

---

## 6. 결정 기준

```
빠른 배포 + 무료 원함    → 옵션 A (Groq/Gemini + Render)
현재 코드 유지 원함      → 옵션 B (유료 서버)
장기 운영 + 비용 최소화  → 옵션 C (Supabase 재설계)
로컬 LLM 유지 필수       → 옵션 B (GPU 클라우드)
```

---

## 7. 다음 단계 (미결)

- [ ] ollama → Groq 또는 Gemini API 교체 작업
- [ ] Render / Fly.io 배포 테스트
- [ ] Supabase PostgreSQL 연동 (공고 캐싱) 설계
