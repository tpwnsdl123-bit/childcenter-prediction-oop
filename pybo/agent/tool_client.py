import os
import asyncio
import nest_asyncio

# 전역에서 한 번만 설정하여 오버헤드 감소
nest_asyncio.apply()

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


import requests

class ToolClient:
    """MCP 서버와 통신하며 도구를 호출하거나 직접 LLM을 호출하는 전담 클라이언트"""

    def __init__(self, mcp_url: str = None):
        self.mcp_url = mcp_url or os.getenv("MCP_URL", "http://127.0.0.1:8000/mcp")
        self.runpod_url = os.getenv("RUNPOD_API_URL")
        self.runpod_api_key = os.getenv("RUNPOD_API_KEY")

    def call_llm(self, instruction: str, input_text: str, **kwargs) -> str:
        """MCP를 거치지 않고 직접 런포드 LLM을 호출 (안정성 확보)"""
        if not self.runpod_url:
            return "AI 서버 URL이 설정되지 않았습니다."
        
        payload = {
            "instruction": instruction,
            "input": input_text,
            "model_version": kwargs.get("model_version", "final"),
            "max_new_tokens": kwargs.get("max_new_tokens", 256),
            "temperature": kwargs.get("temperature", 0.3),
            "stop": ["Observation:", "Observation", "###"],
        }
        
        headers = {"Content-Type": "application/json"}
        if self.runpod_api_key and "proxy.runpod.net" not in self.runpod_url:
            headers["Authorization"] = f"Bearer {self.runpod_api_key}"

        try:
            # 30초 대신 충분한 타임아웃 부여 (180초)
            response = requests.post(self.runpod_url, json=payload, headers=headers, timeout=180.0)
            if response.status_code == 200:
                return response.json().get("text", "").strip()
            return f"AI 서버 오류 (Status: {response.status_code})"
        except Exception as e:
            return f"AI 서버 통신 오류: {str(e)}"

    async def call_tool_async(self, tool_name: str, arguments: dict) -> str:
        try:
            async with streamable_http_client(self.mcp_url) as (read, write, _):
                async with ClientSession(read, write) as session:
                    # 서버 초기화 및 호출에 타임아웃 적용
                    await asyncio.wait_for(session.initialize(), timeout=10.0)
                    result = await asyncio.wait_for(
                        session.call_tool(tool_name, arguments=arguments),
                        timeout=30.0
                    )
                    return result.content[0].text if result.content else "결과 없음"
        except asyncio.TimeoutError:
            return f"MCP 도구 호출 시간 초과 ({tool_name})"
        except BaseException as e:
            # TaskGroup errors are often BaseException or derived from its structure
            return f"MCP 도구 호출 오류 ({tool_name}): {str(e)}"

    def call_tool(self, tool_name: str, arguments: dict) -> str:
        try:
            # nest_asyncio.apply()는 이미 전역에서 호출됨
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

            if loop.is_running():
                # 이미 실행 중인 루프에서는 nest_asyncio 덕분에 run_until_complete 가능
                return loop.run_until_complete(self.call_tool_async(tool_name, arguments))
            else:
                return asyncio.run(self.call_tool_async(tool_name, arguments))
        except Exception as e:
            print(f"[Tool Client Error] {tool_name}: {str(e)}")
            return f"도구 호출 오류 ({tool_name}): {str(e)}"
