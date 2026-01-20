import asyncio
import nest_asyncio

# 전역에서 한 번만 설정
nest_asyncio.apply()

from typing import TypedDict

from langgraph.graph import StateGraph, END
from pybo.agent.tool_client import ToolClient

_tool_client = ToolClient()


class QAState(TypedDict):
    question: str
    pdf_context: str
    answer: str
    model_version: str


def _is_greeting(q: str) -> bool:
    greetings = ["안녕", "반가워", "하이", "hello", "hi", "누구"]
    q_low = (q or "").lower()
    return any(g in q_low for g in greetings) and len((q or "").strip()) < 15


async def node_rag(state: QAState) -> QAState:
    state["pdf_context"] = await _tool_client.call_tool_async(
        "rag_search",
        {"question": state["question"]},
    )
    return state


async def node_answer(state: QAState) -> QAState:
    q = state["question"]
    from pybo.agent.prompts import QA_GREETING_PROMPT, QA_NODE_PROMPT

    if _is_greeting(q):
        instruction = QA_GREETING_PROMPT
        input_text = f"사용자 질문: {q}"
    else:
        instruction = QA_NODE_PROMPT
        input_text = f"참조 자료:\n{state['pdf_context']}\n\n질문: {q}"

    state["answer"] = _tool_client.call_llm(
        instruction=instruction,
        input_text=input_text,
        model_version=state.get("model_version", "final"),
        temperature=0.3,
        max_new_tokens=256,
    )
    return state


def build_graph():
    g = StateGraph(QAState)
    g.add_node("rag", node_rag)
    g.add_node("answer", node_answer)
    g.set_entry_point("rag")
    g.add_edge("rag", "answer")
    g.add_edge("answer", END)
    return g.compile()


_graph = build_graph()


def run_qa(question: str, model_version: str = "final") -> str:
    state: QAState = {"question": question, "pdf_context": "", "answer": "", "model_version": model_version}
    try:
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        if loop.is_running():
            # nest_asyncio 덕분에 실행 중인 루프에서도 run_until_complete 가능
            return loop.run_until_complete(_graph.ainvoke(state))["answer"]
        else:
            return asyncio.run(_graph.ainvoke(state))["answer"]
    except Exception as e:
        print(f"[QA Graph Error] {e}")
        return f"QA 처리 중 오류가 발생했습니다: {str(e)}"
