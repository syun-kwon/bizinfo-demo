FROM python:3.11-slim

WORKDIR /app

# 웹 앱 의존성 설치
COPY bizinfo_web/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# MCP 서버 코드 (함수 직접 호출용)
COPY bizinfo_mcp/requirements.txt mcp_requirements.txt
RUN pip install --no-cache-dir -r mcp_requirements.txt

COPY bizinfo_mcp/server.py ./bizinfo_server.py
COPY bizinfo_web/ .

EXPOSE 3000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3000"]
