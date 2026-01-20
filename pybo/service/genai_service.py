import os
import json
import time
import requests
from dotenv import load_dotenv
from typing import Optional, Tuple

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from pybo.agent.tool_agent import ToolAgent
from pybo.agent.qa_graph import run_qa
from pybo.agent.prompts import (
    QA_SYSTEM_PROMPT, REPORT_SYSTEM_PROMPT, POLICY_SYSTEM_PROMPT
)

load_dotenv()


class GenAIService:
    def __init__(self) -> None:
        self.api_url = os.getenv("RUNPOD_API_URL")
        self.api_key = os.getenv("RUNPOD_API_KEY")

        self.session = requests.Session()
        retry = Retry(
            total=3,  # 리트라이 횟수 약간 증가
            backoff_factor=0.6,
            status_forcelist=(429, 500, 502, 503, 504, 524),  # 524(Proxy Timeout) 추가
            allowed_methods=frozenset(["POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        self.default_settings = {"temperature": 0.3, "max_new_tokens": 256}

        self._agent_instance = None

    @property
    def agent(self) -> ToolAgent:
        if self._agent_instance is None:
            self._agent_instance = ToolAgent(llm_callback=self._call_llama3)
        return self._agent_instance

    def _call_llama3(
        self,
        instruction: str,
        input_text: str,
        max_new_tokens: Optional[int] = None,
        model_version: str = "final",
        temperature: Optional[float] = None,
        timeout: Tuple[float, float] = (10.0, 180.0), # 300s -> 180s (3분)으로 조정
    ) -> str:
        if not self.api_url:
            return "RUNPOD_API_URL이 설정되지 않았습니다."

        payload = {
            "instruction": instruction,
            "input": input_text,
            "model_version": model_version,
            "max_new_tokens": max_new_tokens or self.default_settings["max_new_tokens"],
            "temperature": temperature if temperature is not None else self.default_settings["temperature"],
            "stop": ["Observation:", "Observation", "###"],  # 중단 토큰 추가
        }

        headers = {"Content-Type": "application/json"}
        # Proxy URL(8000번 포트 등)인 경우 보통 인증 헤더가 필요 없으므로 구분하여 처리
        if self.api_key and "proxy.runpod.net" not in self.api_url:
            headers["Authorization"] = f"Bearer {self.api_key}"
            print(f">>> [LLM Request] Using API Key for {self.api_url}")
        else:
            print(f">>> [LLM Request] Standard Proxy Request (No Auth Header) to {self.api_url}")

        start = time.time()
        print(f">>> [LLM Request] Starting request to {self.api_url} (timeout={timeout})")
        try:
            response = self.session.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=timeout,
            )
            print(f">>> [LLM Response] Received response with status {response.status_code}")

            if not (200 <= response.status_code < 300):
                print(f"[LLM ERROR] status={response.status_code}, body={response.text[:300]}")
                return f"AI 서버 오류(status={response.status_code})로 답변 생성에 실패했습니다. 잠시 후 다시 시도해주세요."

            elapsed = time.time() - start
            print(f"--- AI 추론 완료 (소요시간: {elapsed:.2f}초) ---")

            return (response.json().get("text", "") or "").strip()

        except requests.exceptions.Timeout:
            print("[LLM TIMEOUT] AI 서버 응답 지연")
            return "AI 서버 응답이 지연되고 있습니다. 잠시 후 다시 시도해주세요."
        except requests.exceptions.RequestException as e:
            print(f"[LLM REQUEST ERROR] {e}")
            return "AI 서버 통신 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
        except Exception as e:
            print(f"[LLM UNKNOWN ERROR] {e}")
            return "AI 서버 처리 중 알 수 없는 오류가 발생했습니다."

    def generate_report_with_data(self, user_prompt: str, **kwargs) -> str:
        district = kwargs.get("district", "전체")
        start_year = int(kwargs.get("start_year", 2023))
        end_year = int(kwargs.get("end_year", 2030))
        model_version = kwargs.get("model_version", "final")

        # 서비스단에서 데이터 선조회 (도구 호출 오버헤드 최소화)
        stats_data = self.agent.tool_client.call_tool(
            "check_stats",
            {"district": district, "start_year": start_year, "end_year": end_year}
        )

        input_text = f"[참조 데이터: {stats_data}]\n대상 지역: {district}"

        # 에이전트 루프 우회: 직접 LLM 호출 (속도 극대화)
        raw_response = self._call_llama3(
            instruction=REPORT_SYSTEM_PROMPT,
            input_text=input_text,
            model_version=model_version,
            max_new_tokens=256,
            temperature=0.3
        )

        report_data = {
            "title": f"{district} 아동복지 데이터 분석 보고서",
            "summary": "AI 데이터 분석 결과",
            "content": raw_response,
        }
        return json.dumps(report_data, ensure_ascii=False)

    def generate_policy(self, user_prompt: str, **kwargs) -> str:
        district = kwargs.get("district", "전체")
        model_version = kwargs.get("model_version", "final")

        stats_data = self.agent.tool_client.call_tool(
            "check_stats",
            {"district": district, "start_year": 2023, "end_year": 2030}
        )

        input_text = f"[참조 데이터: {stats_data}]\n지역: {district}"

        return self._call_llama3(
            instruction=POLICY_SYSTEM_PROMPT,
            input_text=input_text,
            model_version=model_version,
            max_new_tokens=256,
            temperature=0.3
        )

    def answer_qa_with_log(self, question: str, **kwargs) -> str:
        model_version = kwargs.get("model_version", "final")
        return run_qa(question, model_version=model_version)

    def summarize_text(self, text: str, model_version: str = "final") -> str:
        instruction = (
            "너는 한국어 문서 요약기다. 반드시 한국어로만 답해라.\n"
            "아래 본문을 핵심만 5줄 이내로 요약해라.\n"
            "없는 내용은 만들지 말고, 너무 길면 더 압축해라."
        )

        return self._call_llama3(
            instruction=instruction,
            input_text=text,
            model_version=model_version,
            temperature=0.1,
            max_new_tokens=256,
        )


_genai_service_instance = None


def get_genai_service() -> "GenAIService":
    global _genai_service_instance
    if _genai_service_instance is None:
        _genai_service_instance = GenAIService()
    return _genai_service_instance
