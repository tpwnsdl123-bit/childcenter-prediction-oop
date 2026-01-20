import json
import re
from typing import Optional, Tuple, Dict, Any
from pybo.agent.tool_client import ToolClient


class ToolAgent:
    """도구를 사용하여 자율적으로 사고하고 답변하는 에이전트 엔진"""

    def __init__(self, llm_callback, max_iterations: int = 2):
        self.tool_client = ToolClient()
        self.llm_callback = llm_callback
        self.max_iterations = max_iterations

    def run(
        self,
        query: str,
        instruction: str,
        mode: str = "qa",
        model_version: str = "final",
        **kwargs,
    ) -> str:
        current_chain = f"사용자 질문: {query}\n"
        executed_action = False

        for i in range(self.max_iterations):
            llm_input = f"{current_chain}\nThought: "

            try:
                raw = (self.llm_callback(instruction, llm_input, model_version=model_version, **kwargs) or "").strip()
            except TypeError:
                raw = (self.llm_callback(instruction, llm_input, **kwargs) or "").strip()

            if not raw:
                current_chain += (
                    "\n시스템: 출력이 비었습니다. 반드시 아래 중 하나로만 답하세요.\n"
                    "1) Action: <tool>\nAction Input: {...JSON...}\n"
                    "2) Final Answer: <한국어 답변>\n"
                )
                continue

            print(f">>> [Turn {i+1}] LLM Raw Response:\n{raw}\n---")

            response = raw if raw.lstrip().startswith("Thought:") else ("Thought: " + raw)

            action_block = self._extract_action_block(response)
            if action_block:
                try:
                    tool_name, tool_input = self._parse_action(action_block)
                    tool_input = self._inject_model_version(tool_name, tool_input, model_version)

                    print(f">>> [Turn {i+1}] Calling Tool: {tool_name} with {tool_input}")
                    observation = self.tool_client.call_tool(tool_name, tool_input)
                    executed_action = True

                    current_chain += (
                        f"\nAction: {tool_name}\n"
                        f"Action Input: {json.dumps(tool_input, ensure_ascii=False)}\n"
                        f"Observation: {observation}\n"
                    )
                    continue

                except Exception as e:
                    print(f">>> [Turn {i+1}] Tool Call Error: {str(e)}")
                    current_chain += (
                        f"\nObservation: 오류 발생({str(e)}).\n"
                        "시스템: Action Input은 반드시 JSON 하나만, 키/값은 큰따옴표로 작성하세요.\n"
                        "예) Action: rag_search\nAction Input: {\"question\": \"...\"}\n"
                    )
                    continue

            final_ans = self._extract_final_answer(response)
            if final_ans:
                final_ans = final_ans.strip()
                print(f">>> [Turn {i+1}] Found Final Answer: {final_ans[:100]}...")

                return final_ans

            # QA 모드에서 형식을 못 지켰을 때의 보완책 (암시적 답변 허용)
            if mode == "qa":
                clean_ans = response.replace("Thought:", "").strip()
                # 시스템 메시지가 섞이지 않았고 실질적인 내용이 있으면 그냥 리턴
                if len(clean_ans) > 5 and "시스템:" not in clean_ans:
                    print(f">>> [Turn {i+1}] Implicit QA Answer Accepted.")
                    return clean_ans

            if i == self.max_iterations - 1:
                return "AI 서버 응답 지연/오류로 도구 호출을 완료하지 못했습니다. 잠시 후 다시 시도해주세요."

            current_chain += (
                "\n시스템: 다음 형식을 정확히 지켜주세요.\n"
                "Action: <도구명>\nAction Input: { ...JSON... }\n"
                "또는\nFinal Answer: <한국어 최종 답변>\n"
            )

        return "미안해, 답변을 생성하는 데 실패했어. 다시 한번 물어봐 줄래?"

    def _inject_model_version(self, tool_name: str, tool_input: Dict[str, Any], model_version: str) -> Dict[str, Any]:
        if tool_name in ("llama_generate",):
            if isinstance(tool_input, dict) and "model_version" not in tool_input:
                tool_input["model_version"] = model_version
        return tool_input

    def _extract_action_block(self, text: str) -> Optional[str]:
        # 'Action:'부터 시작해서 텍스트 끝까지를 가져옵니다. (내부의 _parse_action이 실제 JSON을 찾음)
        m = re.search(r"Action:.*?\s*Action Input:.*", text, re.DOTALL | re.IGNORECASE)
        if m:
            return m.group(0).strip()
        return None

    def _extract_final_answer(self, text: str) -> Optional[str]:
        # 'Final Answer:' 인식을 더 유연하게 (따옴표 포함 등)
        m = re.search(r"['\"]?Final Answer:['\"]?\s*(.*)", text, re.DOTALL | re.IGNORECASE)
        if not m:
            return None
        ans = m.group(1).strip()
        # 앞뒤에 남은 따옴표 제거 (따옴표로 전체를 감싸는 경우가 있음)
        ans = re.sub(r"^['\"]|['\"]$", "", ans).strip()
        if "Action:" in ans:
            ans = ans.split("Action:")[0].strip()
        return ans

    def _needs_evidence(self, q: str) -> bool:
        keywords = [
            "법", "법령", "지침", "근거", "조항", "규정", "자료", "통계", "수치", "증가", "감소", "추세",
            "원인", "이유", "정책", "지원금", "예산", "사업", "제도", "기준", "대상", "조건"
        ]
        q = (q or "").strip()
        return any(k in q for k in keywords) and len(q) >= 6

    def _parse_action(self, response: str) -> Tuple[str, dict]:
        action_match = re.search(r"Action:\s*(\w+)", response, re.IGNORECASE)
        if not action_match:
            raise ValueError("응답에서 Action 도구명을 찾을 수 없습니다.")
        tool_name = action_match.group(1).strip()

        if "Action Input:" not in response:
            raise ValueError("Action Input 항목을 찾을 수 없습니다.")

        content_after_action = response.split("Action Input:", 1)[1]

        brace_count = 0
        json_start = -1
        json_end = -1

        for i, ch in enumerate(content_after_action):
            if ch == "{":
                if brace_count == 0:
                    json_start = i
                brace_count += 1
            elif ch == "}":
                if brace_count > 0:
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break

        if json_start == -1 or json_end == -1:
            raise ValueError("Action Input에서 유효한 JSON 중괄호 블록을 찾을 수 없습니다.")

        json_str = content_after_action[json_start:json_end].strip()

        # 기본적인 전처리 (중첩 중괄호 {{...}} -> {...} 보정, 작은따옴표 -> 큰따옴표 등)
        pre_cleaned = json_str
        if pre_cleaned.startswith("{{") and pre_cleaned.endswith("}}"):
            pre_cleaned = pre_cleaned[1:-1]
            
        if "'" in pre_cleaned and '"' not in pre_cleaned:
            pre_cleaned = pre_cleaned.replace("'", '"')

        try:
            return tool_name, json.loads(pre_cleaned)
        except json.JSONDecodeError:
            try:
                # 후행 쉼표 제거 ( ,} -> } )
                fixed = re.sub(r",\s*}", "}", pre_cleaned)
                return tool_name, json.loads(fixed)
            except Exception:
                raise ValueError(f"JSON 파싱 실패: {json_str}")
