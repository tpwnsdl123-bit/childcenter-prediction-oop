import requests
import json
import re
import os
from dotenv import load_dotenv
from dataclasses import dataclass
from typing import Optional

from transformers import pipeline

from pybo import db
from pybo.models import GenAIChatLog, RegionForecast

# .env 파일 로드
load_dotenv()

DISTRICTS = [
    "종로구", "중구", "용산구", "성동구", "광진구", "동대문구", "중랑구", "성북구", "강북구", "도봉구",
    "노원구", "은평구", "서대문구", "마포구", "양천구", "강서구", "구로구", "금천구", "영등포구", "동작구",
    "관악구", "서초구", "강남구", "송파구", "강동구",
]

INDICATOR_MAP = {
    "한부모": ("single_parent", "한부모 가구 수"),
    "기초생활": ("basic_beneficiaries", "기초생활수급자 수"),
    "다문화": ("multicultural_hh", "다문화 가구 수"),
    "학원": ("academy_cnt", "학원 수"),
    "grdp": ("grdp", "1인당 GRDP"),
    "인구": ("population", "자치구 인구수"),
}


@dataclass
class QueryMeta:
    district: str = "전체"
    start_year: Optional[int] = None
    end_year: Optional[int] = None


class GenAIService:
    # 서버 메모리에 저장되는 기본 하이퍼파라미터
    settings = {
        "temperature": 0.35,
        "max_tokens": 600,  # JSON 잘림 방지용 여유분
        "system_prompt_report": (
            "너는 서울시 아동 돌봄 정책 전문 데이터 분석가야. "
            "주어진 [데이터 요약]을 바탕으로 정책 담당자용 보고서를 작성해.\n"
            "**반드시 아래 JSON 형식으로만 답변해야 해.** 설명이나 사족을 붙이지 마.\n\n"
            "{\n"
            '  "title": "보고서 제목",\n'
            '  "summary": "핵심 내용 3줄 요약",\n'
            '  "content": "상세 분석 내용 (평서문으로 작성)"\n'
            "}"
        )
    }

    def __init__(self) -> None:
        # API URL 로드
        self.api_url = os.getenv("RUNPOD_API_URL")
        self.timeout = 60

        if not self.api_url:
            print("경고: .env 파일에서 RUNPOD_API_URL을 찾을 수 없습니다.")

        # NER 모델 로딩 (UI에 적용안함)
        print("NER(개체명 인식) 모델을 로딩 중입니다...")
        try:
            self.ner_pipeline = pipeline("ner", model="Leo97/KoELECTRA-small-v3-modu-ner")
            print("NER 모델 로딩 완료!")
        except Exception as e:
            print(f"NER 모델 로딩 실패: {e}")
            self.ner_pipeline = None

    # 파라미터 값 업데이트
    def update_settings(self, new_settings: dict):
        # Inference 실시간 서비스 설정 적용
        if "temperature" in new_settings:
            self.settings["temperature"] = new_settings["temperature"]
        if "max_tokens" in new_settings:
            self.settings["max_tokens"] = new_settings["max_tokens"]

        print(f"추론 설정 변경됨: Temp={self.settings['temperature']}")

        # Training 학습 설정 파일 생성
        # UI에서 받은 10개 값 + UI에서 뺀 고정값(batch 등)을 합쳐서 저장
        training_args_config = {
            # UI에서 온 값들
            "max_steps": new_settings.get("max_steps", 300),
            "evaluation_strategy": new_settings.get("evaluation_strategy", "steps"),
            "save_strategy": new_settings.get("save_strategy", "steps"),
            "learning_rate": new_settings.get("learning_rate", "1e-4"),
            "optim": new_settings.get("optim", "paged_adamw_8bit"),
            "weight_decay": new_settings.get("weight_decay", 0.01),
            "warmup_steps": new_settings.get("warmup_steps", 20),
            "eval_steps": new_settings.get("eval_steps", 20),
            "save_steps": new_settings.get("save_steps", 40),
            "logging_steps": new_settings.get("logging_steps", 1),

            # UI에서 뺐지만 학습엔 꼭 필요한 고정값 (성공 스크립트 기준)
            "per_device_train_batch_size": 1,  # 고정
            "gradient_accumulation_steps": 8,  # 고정
            "output_dir": "/workspace/finetune/outputs_llama3_c2",
            "load_best_model_at_end": True,
            "metric_for_best_model": "eval_loss",
            "greater_is_better": False,
            "bf16": True,
            "report_to": "none"
        }

        # JSON 파일로 저장
        try:
            with open("training_config.json", "w", encoding="utf-8") as f:
                json.dump(training_args_config, f, indent=4)
            print("training_config.json 파일 생성 완료 (고정값 포함)")
        except Exception as e:
            print(f"파일 저장 실패: {e}")

    # RunPod 통신 함수
    def _call_llama3(self, instruction: str, input_text: str, max_tokens: int = None) -> str:
        final_max_tokens = max_tokens if max_tokens else self.settings["max_tokens"]

        headers = {'Content-Type': 'application/json'}
        payload = {
            "instruction": instruction,
            "input": input_text,
            "max_new_tokens": final_max_tokens,
            "temperature": self.settings["temperature"],
            "do_sample": True
        }

        try:
            response = requests.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()

            # 텍스트 정제 (JSON 파싱을 위해 특수문자 보존, 줄바꿈만 정리)
            raw_text = result.get("text", "").strip()
            clean_text = raw_text.replace('\r', '')

            return clean_text

        except Exception as e:
            print(f"RunPod Error: {e}")
            return "죄송합니다. AI 서버와 연결할 수 없습니다."

    # 메타 데이터 추출 및 유틸리티
    def _extract_query_meta(self, text: str) -> QueryMeta:
        q = (text or "").strip()
        meta = QueryMeta()
        for gu in DISTRICTS:
            if gu in q:
                meta.district = gu
                break

        # 연도 범위 추출
        range_pattern = r"(20\d{2})\s*[-~]\s*(20\d{2})"
        m = re.search(range_pattern, q)
        if m:
            y1, y2 = int(m.group(1)), int(m.group(2))
            meta.start_year = min(y1, y2)
            meta.end_year = max(y1, y2)
        else:
            single_pattern = r"(20\d{2})"
            m2 = re.search(single_pattern, q)
            if m2:
                y = int(m2.group(1))
                meta.start_year = y
                meta.end_year = y
            else:
                meta.start_year = 2023
                meta.end_year = 2030

        # 범위 보정
        if meta.start_year and meta.start_year < 2015: meta.start_year = 2015
        if meta.end_year and meta.end_year > 2035: meta.end_year = 2035

        return meta

    def _build_meta_with_overrides(self, text: str, *, district: str | None, start_year: int | None,
                                   end_year: int | None) -> QueryMeta:
        meta = self._extract_query_meta(text)
        if district and district != "전체": meta.district = district.strip()
        if start_year is not None: meta.start_year = int(start_year)
        if end_year is not None: meta.end_year = int(end_year)
        return meta

    def _detect_indicator(self, text: str) -> tuple[Optional[str], Optional[str]]:
        q = (text or "").strip().lower()
        for keyword, (col, label) in INDICATOR_MAP.items():
            if keyword in q: return col, label
        return None, None

    def _format_change(self, start, end) -> str:
        if start is None or end is None: return "데이터 없음"
        try:
            s, e = float(start), float(end)
        except:
            return f"{start} -> {end}"
        base = f"{int(round(s)):,} -> {int(round(e)):,}"
        if s == 0: return base
        try:
            diff = (e - s) / s * 100.0
        except:
            return base
        sign = "+" if diff >= 0 else ""
        return f"{base} ({sign}{diff:.1f}%)"

    def _save_chat_log(self, *, user_id, page, task_type, question, answer) -> None:
        try:
            log = GenAIChatLog(user_id=user_id, page=page, task_type=task_type, question=question, answer=answer)
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            print(f"로그 저장 실패: {e}")
            db.session.rollback()

    def _query_forecast_rows(self, district: str, start_year: int, end_year: int) -> list[RegionForecast]:
        return RegionForecast.query.filter(
            RegionForecast.district == district,
            RegionForecast.year >= start_year,
            RegionForecast.year <= end_year
        ).order_by(RegionForecast.year.asc()).all()

    # 보고서 생성 (JSON 출력)
    def generate_report_with_data(self, user_prompt: str, *, district: str | None = None, start_year: int | None = None,
                                  end_year: int | None = None) -> str:
        meta = self._build_meta_with_overrides(user_prompt, district=district, start_year=start_year, end_year=end_year)
        context = self._build_forecast_context(meta)

        # 설정값에 저장된 JSON 전용 프롬프트 사용
        instruction = self.settings["system_prompt_report"]
        input_text = f"{context}\n\n[사용자 요청]: {meta.district}의 {meta.start_year}~{meta.end_year}년 예측 데이터를 분석해줘."

        return self._call_llama3(instruction, input_text)

    # 정책 제안
    def generate_policy(self, prompt: str, *, district: str | None = None, start_year: int | None = None,
                        end_year: int | None = None) -> str:
        meta = self._build_meta_with_overrides(prompt, district=district, start_year=start_year, end_year=end_year)
        context = self._build_forecast_context(meta)

        instruction = (
            "너는 서울시 지역아동센터 관련 정책을 기획하는 보조자야. "
            "제공된 데이터를 바탕으로 현실적인 돌봄·지원 정책 아이디어를 3개 제안해 줘. "
            "JSON 형식이 아니라, 줄글로 편하게 작성해."
        )
        input_text = f"{context}\n\n[사용자 요청]: {prompt}"

        return self._call_llama3(instruction, input_text, max_tokens=500)

    # 지표 설명
    def explain_indicator(self, prompt: str, **kwargs) -> str:
        return self._call_llama3("지표의 통계적 의미를 설명해줘.", prompt)

    # QA (질의응답)
    def answer_qa(self, question: str, *, district: str | None = None, start_year: int | None = None,
                  end_year: int | None = None) -> str:
        user_q = (question or "").strip()
        meta = self._build_meta_with_overrides(user_q, district=district, start_year=start_year, end_year=end_year)
        context = self._build_forecast_context(meta)

        instruction = "너는 서울시 아동 정책 Q&A 봇이야. 데이터를 근거로 답변해 줘."
        input_text = f"{context}\n\n질문: {user_q}"

        return self._call_llama3(instruction, input_text, max_tokens=400)

    def answer_qa_with_log(self, question: str, *, user_id: int | None = None, page: str | None = None,
                           district: str | None = None, start_year: int | None = None,
                           end_year: int | None = None) -> str:
        answer = self.answer_qa(question, district=district, start_year=start_year, end_year=end_year)
        self._save_chat_log(user_id=user_id, page=page, task_type="qa", question=question, answer=answer)
        return answer

    # NER (개체명 인식)
    def analyze_ner(self, text: str) -> list[dict]:
        """
        Hugging Face 파이프라인을 사용해 텍스트에서 개체명(인물, 기관, 장소 등)을 추출
        """
        if not self.ner_pipeline or not text:
            return []

        try:
            # 파이프라인 실행
            results = self.ner_pipeline(text)

            # 결과 정리 (중복 제거 및 점수 변환)
            unique_entities = []
            seen = set()

            for r in results:
                word = r['word'].replace("##", "")  # 토크나이저의 ## 제거
                label = r['entity']
                score = float(r['score'])

                # 중복되지 않고, 2글자 이상인 의미 있는 단어만 추출
                if word not in seen and len(word) > 1:
                    seen.add(word)
                    unique_entities.append({"word": word, "type": label, "score": score})

            return unique_entities

        except Exception as e:
            print(f"NER 분석 중 오류: {e}")
            return []

    # Context Builders (Prompt Engineering)
    def _build_forecast_context(self, meta: QueryMeta) -> str:
        district = (meta.district or "").strip()
        if not district or district == "전체": return ""

        s_year = meta.start_year if meta.start_year else 2023
        e_year = meta.end_year if meta.end_year else 2030

        rows = self._query_forecast_rows(district, s_year, e_year)
        if not rows: return ""

        first, last = rows[0], rows[-1]

        def get_val(obj, key):
            return getattr(obj, key, 0)

        feature_summaries = [
            f"예측 이용자 수: {self._format_change(first.predicted_child_user, last.predicted_child_user)}",
            f"한부모 가구: {self._format_change(get_val(first, 'single_parent'), get_val(last, 'single_parent'))}",
            f"기초생활수급: {self._format_change(get_val(first, 'basic_beneficiaries'), get_val(last, 'basic_beneficiaries'))}",
            f"다문화 가구: {self._format_change(get_val(first, 'multicultural_hh'), get_val(last, 'multicultural_hh'))}",
            f"학원 수: {self._format_change(get_val(first, 'academy_cnt'), get_val(last, 'academy_cnt'))}",
            f"1인당 GRDP: {self._format_change(get_val(first, 'grdp'), get_val(last, 'grdp'))}",
            f"인구수: {self._format_change(get_val(first, 'population'), get_val(last, 'population'))}"
        ]

        context_lines = [
            "[데이터 요약]",
            f"자치구: {district}, 기간: {s_year}~{e_year}",
            "주요 지표 변화:", *[f"- {fs}" for fs in feature_summaries]
        ]
        return "\n".join(context_lines)

    def _build_indicator_context(self, meta: QueryMeta, col: str, label: str) -> str:
        return ""