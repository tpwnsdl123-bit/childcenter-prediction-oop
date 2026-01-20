from flask import Blueprint, request, jsonify, current_app, g
import requests
import os

from pybo.service.genai_service import get_genai_service

bp = Blueprint("genai_api", __name__, url_prefix="/genai-api")
genai_service = get_genai_service()


@bp.route("/switch-model", methods=["POST"])
def switch_model():
    data = request.get_json() or {}
    try:
        runpod_generate = os.getenv("RUNPOD_API_URL") or ""
        if not runpod_generate:
            return jsonify({"success": False, "error": "RUNPOD_API_URL이 설정되지 않았습니다."}), 500

        runpod_url = runpod_generate.replace("/generate", "/switch_model")
        res = requests.post(runpod_url, json=data, timeout=60)

        if not (200 <= res.status_code < 300):
            return jsonify({"success": False, "error": f"모델 전환 실패 (status={res.status_code})"}), 500

        return jsonify({"success": True, "result": res.json()})
    except Exception as e:
        current_app.logger.exception("switch-model error")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/report", methods=["POST"])
def generate_report():
    data = request.get_json() or {}
    district = (data.get("district") or "").strip()
    start_year = data.get("start_year", 2023)
    end_year = data.get("end_year")
    model_ver = data.get("model_version", "final")

    if not district or end_year is None:
        return jsonify({"success": False, "error": "자치구와 연도를 모두 선택해주세요."}), 400

    try:
        result_text = genai_service.generate_report_with_data(
            user_prompt="report",
            district=district,
            start_year=int(start_year),
            end_year=int(end_year),
            model_version=model_ver,
        )
        return jsonify({"success": True, "result": result_text})
    except Exception as e:
        current_app.logger.exception("report error")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/policy", methods=["POST"])
def generate_policy():
    data = request.get_json() or {}
    prompt = (data.get("prompt") or "").strip()
    district = (data.get("district") or "전체").strip()
    model_ver = data.get("model_version", "final")

    if not prompt:
        return jsonify({"success": False, "error": "정책 생성 프롬프트를 입력해주세요."}), 400

    try:
        text = genai_service.generate_policy(
            prompt,
            district=district,
            model_version=model_ver,
        )
        return jsonify({"success": True, "result": text})
    except Exception as e:
        current_app.logger.exception("policy error")
        return jsonify({"success": False, "error": str(e)}), 500


@bp.route("/qa", methods=["POST"])
def qa():
    data = request.get_json() or {}
    question = (data.get("question") or "").strip()
    model_ver = data.get("model_version", "final")

    if not question:
        return jsonify({"success": False, "error": "질문을 입력해 주세요."}), 400

    user_id = None
    if hasattr(g, "user") and getattr(g, "user", None):
        user_id = getattr(g.user, "id", None)

    try:
        answer = genai_service.answer_qa_with_log(question, model_version=model_ver)
        return jsonify({"success": True, "result": answer})
    except Exception:
        current_app.logger.exception("qa error")
        return jsonify({"success": False, "error": "답변 생성 중 오류가 발생했습니다."}), 500


@bp.route("/summarize", methods=["POST"])
def summarize():
    data = request.get_json() or {}
    text = (data.get("text") or "").strip()
    model_ver = data.get("model_version", "final")

    if not text:
        return jsonify({"success": False, "error": "요약할 본문을 입력해 주세요."}), 400

    try:
        summary = genai_service.summarize_text(text, model_version=model_ver)
        return jsonify({"success": True, "result": summary})
    except Exception:
        current_app.logger.exception("summarize error")
        return jsonify({"success": False, "error": "요약 생성 중 오류가 발생했습니다."}), 500


@bp.route("/qa_v2", methods=["POST"])
def qa_v2():
    data = request.get_json() or {}
    question = (data.get("question") or "").strip()
    model_ver = data.get("model_version", "final")

    if not question:
        return jsonify({"success": False, "error": "질문을 입력해 주세요."}), 400

    try:
        answer = genai_service.answer_qa_with_log(question, model_version=model_ver)
        return jsonify({"success": True, "result": answer})
    except Exception:
        current_app.logger.exception("qa_v2 error")
        return jsonify({"success": False, "error": "qa_v2 error (check server log)"}), 500
