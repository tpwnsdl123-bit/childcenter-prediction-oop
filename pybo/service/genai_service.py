from transformers import pipeline
import torch

from pybo import db
from pybo.models import GenAIChatLog

class GenAIService: # 생성형 AI 기능 모아둔 클래스

    def __init__(self) -> None:
        # GPU 있으면 0, 없으면 CPU(-1)
        device = 0 if torch.cuda.is_available() else -1

        # 한국어 텍스트 생성용 파이프라인 라마로 바꿀예정
        self.report_generator = pipeline(
            "text-generation",
            model="skt/kogpt2-base-v2",
            tokenizer="skt/kogpt2-base-v2",
            device=device,
        )

        # NER용 파이프라인 (다국어 BERT)
        self.ner_pipeline = pipeline(
            "ner",
            model="Davlan/bert-base-multilingual-cased-ner-hrl",
            tokenizer="Davlan/bert-base-multilingual-cased-ner-hrl",
            aggregation_strategy="simple",
            device=device,
        )

    # 질의/응답을 DB에 저장하는 함수.
    def _save_chat_log(self,
                       *,
                       user_id: int | None,
                       page: str | None,
                       task_type: str,
                       question: str,
                       answer: str,) -> None:
        log = GenAIChatLog(
            user_id=user_id,
            page=page,
            task_type=task_type,
            question=question,
            answer=answer,
        )
        db.session.add(log)
        db.session.commit()

    def generate_report(self, user_prompt: str) -> str: # 보고서 생성
        system_prefix = (
            "너는 서울시 지역아동센터 수요 예측 결과를 정책 담당자에게 설명하는 데이터 분석가야. "
            "공손한 존댓말을 사용하고, 핵심만 3~6문장 정도의 한국어 단락으로 정리해 줘."
        )

        full_prompt = f"{system_prefix}\n\n요청: {user_prompt}\n\n보고서:"

        outputs = self.report_generator(
            full_prompt,
            max_length=512,
            do_sample=True,
            top_p=0.95,
            temperature=0.7,
            num_return_sequences=1,
            pad_token_id=self.report_generator.tokenizer.eos_token_id,
        )

        generated = outputs[0]["generated_text"]

        # 앞부분 프롬프트 잘라내기 (프롬프트 그대로 복붙되는 부분 제거)
        if generated.startswith(full_prompt):
            generated = generated[len(full_prompt):]

        return generated.strip()

    def generate_policy(self,    prompt: str) -> str: # 정책 아이디어
        system_prefix = (
            "너는 서울시 지역아동센터 관련 정책을 기획하는 보조자야. "
            "입력 문장을 바탕으로 현실적인 돌봄·지원 정책 아이디어를 한국어로 제안해 줘. "
            "각 아이디어는 번호를 붙여서 3개 정도로 정리해 줘. "
            "입력 문장을 그대로 반복하지 말고, 새로운 문장으로만 아이디어를 작성해. "
            "정확한 통계 수치는 모르면 새로 지어내지 말고, "
            "'통계 수치는 별도 통계 참고 필요'라고 말해."
        )

        full_prompt = system_prefix + "\n\n요청:\n" + prompt + "\n\n정책 아이디어:\n"

        outputs = self.report_generator(
            full_prompt,
            max_length=256,
            do_sample=True,
            top_p=0.9,
            temperature=0.6,
            num_return_sequences=1,
            pad_token_id=self.report_generator.tokenizer.eos_token_id,
        )

        generated = outputs[0]["generated_text"]

        # 앞부분 프롬프트 잘라내기 (프롬프트 그대로 복붙되는 부분 제거)
        if generated.startswith(full_prompt):
            generated = generated[len(full_prompt):]

        return generated.strip()

    def explain_indicator(self, prompt: str) -> str: # 지표 설명
        user_prompt = (prompt or "").strip()

        system_prefix = (
            "너는 서울시 지역아동센터 수요 예측 모델에 들어가는 지표를 설명하는 데이터 분석가야. "
            "입력된 지표 이름이나 질문에 대해, "
            "지표의 의미와 해석 방법, 그리고 돌봄 수요와 어떤 관련이 있을 수 있는지를 "
            "3~6문장 정도의 한국어 단락으로 쉽게 설명해 줘. "
            "너무 어려운 통계 용어는 풀어서 설명해."
        )

        full_prompt = (
            f"{system_prefix}\n\n"
            f"질문:\n{user_prompt}\n\n"
            "설명:\n"
        )

        outputs = self.report_generator(
            full_prompt,
            max_length=512,
            do_sample=True,
            top_p=0.9,
            temperature=0.7,
            num_return_sequences=1,
            pad_token_id=self.report_generator.tokenizer.eos_token_id,
        )

        generated = outputs[0]["generated_text"]

        # 프롬프트 잘라내기
        if generated.startswith(full_prompt):
            generated = generated[len(full_prompt):]

        return generated.strip()

    def analyze_ner(self, text: str) -> list[dict]: # NER 분석

        sentence = (text or "").strip()
        if not sentence:
            return []

        raw_entities = self.ner_pipeline(sentence)

        results = []
        for ent in raw_entities:
            results.append(
                {
                    "word": ent.get("word"),
                    "type": ent.get("entity_group"),
                    "score": float(ent.get("score", 0.0)),
                    "start": int(ent.get("start", 0)),
                    "end": int(ent.get("end", 0)),
                }
            )
        return results

    def answer_qa(self, question: str) -> str: # AI Q&A
        user_q = (question or "").strip()

        system_prefix = (
            "너는 서울시 지역아동센터 수요 예측 결과와 관련된 질문에 답하는 "
            "데이터 분석 보조자야. "
            "입력된 질문에 대해, 예측 추세, 관련 지표, 정책적 시사점을 "
            "3~6문장 정도의 한국어 단락으로 설명해 줘. "
            "정확한 연도별 수치나 구체적인 숫자는 지금 알 수 없으니, "
            "숫자를 지어내지 말고 방향성 위주로 설명해."
        )

        full_prompt = (
            f"{system_prefix}\n\n"
            f"질문:\n{user_q}\n\n"
            "답변:\n"
        )

        outputs = self.report_generator(
            full_prompt,
            max_length=512,
            do_sample=True,
            top_p=0.9,
            temperature=0.7,
            num_return_sequences=1,
            pad_token_id=self.report_generator.tokenizer.eos_token_id,
        )

        generated = outputs[0]["generated_text"]

        # 프롬프트 잘라내기
        if generated.startswith(full_prompt):
            generated = generated[len(full_prompt):]

        return generated.strip()

    # Q&A 처리, 결과를 DB에 로그로 남기는 함수
    def answer_qa_with_log(
            self,
            question: str,
            *,
            user_id: int | None = None,
            page: str | None = None,
    ) -> str:

        user_q = (question or "").strip()

        answer = self.answer_qa(user_q)

        # DB에 로그 저장
        self._save_chat_log(
            user_id=user_id,
            page=page,
            task_type="qa",
            question=user_q,
            answer=answer,
        )

        return answer