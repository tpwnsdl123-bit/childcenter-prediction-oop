from flask import Blueprint, request, jsonify, current_app, g, render_template
from pybo.service.genai_service import GenAIService

# Blueprint 설정 (URL 프리픽스 확인: /genai-api)
bp = Blueprint("genai_api", __name__, url_prefix="/genai-api")

genai_service = GenAIService()


# 보고서 생성
@bp.route("/report", methods=["POST"])
def generate_report():
    data = request.get_json() or {}

    # UI의 드롭다운에서 보낸 값 받기
    district = (data.get("district") or "").strip()
    end_year = data.get("end_year")
    prompt = data.get("prompt")

    # 유효성 검사
    if not district or not end_year:
        return jsonify({"success": False, "error": "자치구와 연도를 모두 선택해주세요."}), 400

    try:
        # 서비스 호출 (JSON 포맷 강제 로직이 들어있는 함수)
        result_text = genai_service.generate_report_with_data(
            user_prompt=prompt,
            district=district,
            start_year=2023,  # 시작 연도는 고정하거나 UI에서 받아도 됨
            end_year=int(end_year)
        )
        return jsonify({"success": True, "result": result_text})
    except Exception as e:
        print(f"generate_report error: {e}", flush=True)
        return jsonify({"success": False, "error": "보고서 생성 중 오류가 발생했습니다."}), 500


# 정책 아이디어 생성
@bp.route("/policy", methods=["POST"])
def generate_policy():
    data = request.get_json() or {}
    prompt = (data.get("prompt") or "").strip()

    if not prompt:
        return jsonify({"success": False, "error": "요청 내용을 입력해 주세요."}), 400

    try:
        # 정책 제안은 연도/지역 정보가 필수는 아니지만, 있으면 더 좋음
        text = genai_service.generate_policy(prompt)
        return jsonify({"success": True, "result": text})
    except Exception as e:
        current_app.logger.error(f"policy error: {e}")
        return jsonify({"success": False, "error": "정책 제안 생성 중 오류가 발생했습니다."}), 500


# AI Q&A (지표 설명 + QA 통합)
@bp.route("/qa", methods=["POST"])
def qa():
    data = request.get_json() or {}
    question = (data.get("question") or "").strip()

    if not question:
        return jsonify({"success": False, "error": "질문을 입력해 주세요."}), 400

    # 로그인 사용자 ID 확인 (선택 사항)
    user_id = None
    if hasattr(g, "user_id") and getattr(g, "user", None):
        user_id = g.user.id

    try:
        answer = genai_service.answer_qa_with_log(
            question=question,
            user_id=user_id,
            page="genai"
        )
        return jsonify({"success": True, "result": answer})
    except Exception as e:
        current_app.logger.error(f"qa error: {e}")
        return jsonify({"success": False, "error": "답변 생성 중 오류가 발생했습니다."}), 500


# 설정 변경 API (JSON 반환으로 변경됨)
@bp.route("/config", methods=["POST"])
def config():
    data = request.get_json() or {}

    try:
        new_temp = float(data.get("temperature", 0.35))
        new_tokens = int(data.get("max_tokens", 600))

        # 서비스의 설정값 업데이트
        genai_service.update_settings({
            "temperature": new_temp,
            "max_tokens": new_tokens
        })

        return jsonify({"success": True, "message": "설정 변경 완료"})

    except ValueError:
        return jsonify({"success": False, "error": "잘못된 숫자 형식입니다."}), 400