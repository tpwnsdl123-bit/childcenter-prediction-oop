import os
import sys

# 1. 경로 설정을 가장 먼저 수행 (ModuleNotFoundError 방지)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import time
import requests
import json
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

# 2. 이제 pybo 모듈 import 가능
from pybo.service.rag_service import RagService
from pybo import db
from pybo.models import RegionForecast
from sqlalchemy import func

mcp = FastMCP(
    "tAIke-tools",
    stateless_http=True,
    json_response=True,
    transport_security=TransportSecuritySettings(
        enable_dns_rebinding_protection=True,
        allowed_hosts=["localhost:*", "127.0.0.1:*", "host.docker.internal:*"],
        allowed_origins=["http://localhost:*", "http://127.0.0.1:*", "http://host.docker.internal:*"],
    ),
)

RUNPOD_URL = os.getenv("RUNPOD_API_URL")
RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")

session = requests.Session()
retry = Retry(
    total=3,  # 리트라이 횟수 증가
    backoff_factor=0.6,
    status_forcelist=(429, 500, 502, 503, 504, 524),  # 524 추가
    allowed_methods=frozenset(["POST"]),
    raise_on_status=False,
)
adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
session.mount("http://", adapter)
session.mount("https://", adapter)

DEFAULT_TEMP = 0.3
DEFAULT_MAX_NEW_TOKENS = 256

rag = RagService()


@mcp.tool()
def rag_search(question: str) -> str:
    return rag.get_relevant_context(question)


@mcp.tool()
def check_stats(district: str = "전체", start_year: int = 2023, end_year: int = 2030) -> str:
    try:
        if district == "전체":
            summary = (
                db.session.query(
                    RegionForecast.year,
                    func.sum(RegionForecast.predicted_child_user).label("total")
                )
                .filter(RegionForecast.year >= start_year, RegionForecast.year <= end_year)
                .group_by(RegionForecast.year)
                .order_by(RegionForecast.year.asc())
                .all()
            )
            if not summary:
                return f"{start_year}~{end_year} 기간의 전체 데이터가 없습니다."
            return "\n".join([f"{s.year}년 서울시 전체 합계: {s.total}명" for s in summary])

        rows = (
            RegionForecast.query
            .filter(
                RegionForecast.district == district,
                RegionForecast.year >= start_year,
                RegionForecast.year <= end_year
            )
            .order_by(RegionForecast.year.asc())
            .all()
        )
        if not rows:
            return f"{district}의 {start_year}~{end_year} 기간 데이터가 없습니다."

        result = [f"{district} 예측 데이터:"]
        result.extend([f"- {r.year}년: {r.predicted_child_user}명" for r in rows])
        return "\n".join(result)

    except Exception as e:
        return f"DB 조회 중 오류 발생: {str(e)}"



@mcp.tool()
def llama_generate(
    instruction: str,
    input_text: str,
    model_version: str = "final",
    temperature: float = DEFAULT_TEMP,
    max_new_tokens: int = DEFAULT_MAX_NEW_TOKENS,
    timeout_connect: float = 10.0,
    timeout_read: float = 180.0,
) -> str:
    if not RUNPOD_URL:
        return "RUNPOD_API_URL이 설정되지 않았습니다."

    payload = {
        "instruction": instruction,
        "input": input_text,
        "model_version": model_version,
        "max_new_tokens": max_new_tokens,
        "temperature": temperature,
        "stop": ["Observation:", "Observation", "###"],  # 중단 토큰 추가
    }

    headers = {"Content-Type": "application/json"}
    if RUNPOD_API_KEY and "proxy.runpod.net" not in RUNPOD_URL:
        headers["Authorization"] = f"Bearer {RUNPOD_API_KEY}"

    try:
        res = session.post(
            RUNPOD_URL,
            json=payload,
            headers=headers,
            timeout=(timeout_connect, timeout_read),
        )
        if not (200 <= res.status_code < 300):
            return f"AI 서버 오류(status={res.status_code})로 답변 생성에 실패했습니다. 잠시 후 재시도 해주세요."

        return (res.json().get("text", "") or "").strip()

    except requests.exceptions.Timeout:
        return "AI 서버 응답이 지연되고 있습니다. 잠시 후 다시 시도해주세요."
    except requests.exceptions.RequestException as e:
        return f"AI 서버 통신 중 오류가 발생했습니다: {str(e)}"
    except Exception:
        return "AI 서버 처리 중 알 수 없는 오류가 발생했습니다."


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
