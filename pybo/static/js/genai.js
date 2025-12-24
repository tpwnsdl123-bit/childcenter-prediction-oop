document.addEventListener("DOMContentLoaded", function () {

    // 모델별 실제 학습 이력 및 UI 제어 데이터 정의
    const modelHistory = {
        base:  { max_steps: 0,   readonly: true,  msg: "미학습 모델: 학습 파라미터가 존재하지 않습니다." },
        cp40:  { max_steps: 40,  readonly: true,  msg: "기초 학습 모델: Step 40 시점의 기록입니다. (수정 불가)" },
        cp80:  { max_steps: 80,  readonly: true,  msg: "중간 학습 모델: Step 80 시점의 기록입니다. (수정 불가)" },
        final: { max_steps: 300, readonly: false, msg: "최종 모델: 새로운 재학습 파라미터를 설정할 수 있습니다." }
    };

    // 선택된 모델에 따라 설정창 UI를 동적으로 업데이트하는 함수
    function updateModelSettingsUI() {
        const selected = document.querySelector('input[name="modelVersion"]:checked');
        const ver = selected ? selected.value : "final";
        const config = modelHistory[ver];

        // 제어할 입력창 ID 리스트 (HTML의 ID와 일치해야 함)
        const trainingInputs = [
            "max_steps", "evaluation_strategy", "save_strategy",
            "learning_rate", "optim", "weight_decay",
            "warmup_steps", "eval_steps", "save_steps", "logging_steps"
        ];

        trainingInputs.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                // 모델 단계에 따라 편집 가능/불가능 처리
                el.disabled = config.readonly;

                // max_steps의 경우 실제 해당 모델의 학습 수치로 강제 업데이트
                if (id === "max_steps") {
                    el.value = config.max_steps;
                }
            }
        });

        // 모달 내부에 현재 상태 메시지 출력 (Admin Only 배지 옆)
        const badge = document.querySelector(".badge-danger");
        if (badge) {
            let msgEl = document.getElementById("model-status-msg");
            if (!msgEl) {
                msgEl = document.createElement("span");
                msgEl.id = "model-status-msg";
                msgEl.className = "ml-3 small font-italic text-secondary";
                badge.parentNode.appendChild(msgEl);
            }
            msgEl.textContent = config.msg;
        }

        return ver;
    }

    // 상단 라디오 버튼 클릭 시 UI 업데이트 이벤트 연결
    document.querySelectorAll('input[name="modelVersion"]').forEach(radio => {
        radio.addEventListener('change', updateModelSettingsUI);
    });

    // 초기 로드 시 한 번 실행하여 상태 맞춤
    updateModelSettingsUI();

    function getModelVer() {
        const selected = document.querySelector('input[name="modelVersion"]:checked');
        return selected ? selected.value : "final";
    }

    // 연도 선택 스마트 로직
    const startSelect = document.getElementById('startYear');
    const endSelect = document.getElementById('endYear');
    const MAX_YEAR = 2030;

    if (startSelect && endSelect) {
        function updateEndYearOptions() {
            const startVal = parseInt(startSelect.value);
            const currentEndVal = parseInt(endSelect.value);
            endSelect.innerHTML = "";
            for (let y = startVal; y <= MAX_YEAR; y++) {
                const option = document.createElement("option");
                option.value = y;
                option.textContent = y + "년";
                endSelect.appendChild(option);
            }
            if (!isNaN(currentEndVal) && currentEndVal >= startVal) {
                endSelect.value = currentEndVal;
            } else {
                endSelect.value = startVal;
            }
        }
        startSelect.addEventListener('change', updateEndYearOptions);
        updateEndYearOptions();
    }

    // 보고서 생성 탭
    const reportForm = document.getElementById("reportForm");
    const resultSection = document.getElementById("resultSection");
    const loadingSpinner = document.getElementById("loadingSpinner");
    const aiTitle = document.getElementById("aiTitle");
    const aiSummary = document.getElementById("aiSummary");
    const aiContent = document.getElementById("aiContent");

    if (reportForm) {
        reportForm.addEventListener("submit", async function (e) {
            e.preventDefault();
            const modelVer = getModelVer();
            const region = document.getElementById("regionSelect").value;
            const startYearVal = document.getElementById("startYear").value;
            const endYearVal = document.getElementById("endYear").value;
            const reportBtn = reportForm.querySelector("button[type='submit']");

            if (parseInt(startYearVal) > parseInt(endYearVal)) {
                alert("시작 연도는 종료 연도보다 클 수 없습니다.");
                return;
            }

            if(resultSection) resultSection.style.display = "none";
            if(loadingSpinner) loadingSpinner.style.display = "block";
            if(reportBtn) {
                reportBtn.disabled = true;
                reportBtn.innerHTML = '<i class="bi bi-hourglass-split"></i> 생성 중...';
            }

            try {
                const resp = await fetch("/genai-api/report", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        district: region,
                        start_year: parseInt(startYearVal),
                        end_year: parseInt(endYearVal),
                        model_version: modelVer,
                        prompt: "report"
                    }),
                });
                const data = await resp.json();
                if (data.success) {
                    let parsedData = { title: "분석 결과", summary: "요약 정보 없음", content: data.result };
                    try {
                        let cleanJson = data.result.replace(/```json/g, "").replace(/```/g, "").trim();
                        parsedData = JSON.parse(cleanJson);
                    } catch (err) { parsedData.content = data.result; }
                    if(aiTitle) aiTitle.textContent = parsedData.title || "분석 보고서";
                    if(aiSummary) aiSummary.textContent = parsedData.summary || "요약된 내용이 없습니다.";
                    if(aiContent) aiContent.innerText = parsedData.content || "";
                    if(loadingSpinner) loadingSpinner.style.display = "none";
                    if(resultSection) resultSection.style.display = "block";
                } else {
                    alert(data.error || "오류 발생");
                    if(loadingSpinner) loadingSpinner.style.display = "none";
                }
            } catch (err) {
                alert("서버 통신 오류");
                if(loadingSpinner) loadingSpinner.style.display = "none";
            } finally {
                if(reportBtn) {
                    reportBtn.disabled = false;
                    reportBtn.innerHTML = '<i class="bi bi-magic"></i> 보고서 생성';
                }
            }
        });
    }

    // 정책 아이디어 탭
    const policyBtn = document.getElementById("policy-btn");
    const policyInput = document.getElementById("policy-input");
    const policyResultArea = document.getElementById("policyResultArea");

    if (policyBtn && policyInput && policyResultArea) {
        policyBtn.addEventListener("click", async function () {
            const modelVer = getModelVer();
            const text = (policyInput.value || "").trim();
            if (!text) { alert("요청 내용을 입력해 주세요."); policyInput.focus(); return; }
            policyBtn.disabled = true;
            policyResultArea.style.display = "block";
            policyResultArea.textContent = "정책 아이디어를 생성하고 있습니다...";
            try {
                const resp = await fetch("/genai-api/policy", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ prompt: text, model_version: modelVer }),
                });
                const data = await resp.json();
                policyResultArea.textContent = data.success ? data.result : data.error || "오류 발생";
            } catch (err) {
                policyResultArea.textContent = "서버 통신 오류";
            } finally {
                policyBtn.disabled = false;
                policyBtn.innerHTML = '<i class="bi bi-lightbulb mr-2"></i> 아이디어 생성';
            }
        });
    }

    // Q&A 탭
    const qaBtn = document.getElementById("qa-btn");
    const qaInput = document.getElementById("qa-input");
    const qaChatWindow = document.getElementById("qa-chat-window");

    if (qaBtn && qaInput && qaChatWindow) {
        qaBtn.addEventListener("click", async function () {
            const modelVer = getModelVer();
            const question = qaInput.value.trim();
            if (!question) return;
            const userDiv = document.createElement("div");
            userDiv.className = "chat-bubble user-bubble";
            userDiv.textContent = question;
            qaChatWindow.appendChild(userDiv);
            qaInput.value = "";
            try {
                const resp = await fetch("/genai-api/qa", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ question: question, model_version: modelVer }),
                });
                const data = await resp.json();
                const aiDiv = document.createElement("div");
                aiDiv.className = "chat-bubble ai-bubble";
                aiDiv.textContent = data.success ? data.result : "오류가 발생했습니다.";
                qaChatWindow.appendChild(aiDiv);
                qaChatWindow.scrollTop = qaChatWindow.scrollHeight;
            } catch (err) { console.error(err); }
        });
    }

    // 설정 저장 폼 (관리자 권한)
    const configForm = document.getElementById("configForm");
    if (configForm) {
        configForm.addEventListener("submit", async function (e) {
            e.preventDefault();
            // 최종 모델이 아닐 때는 저장을 막는 추가 안전장치
            if (getModelVer() !== "final") {
                alert("최종 모델 모드에서만 설정을 저장하거나 재학습을 시작할 수 있습니다.");
                return;
            }
            const payload = {
                temperature: parseFloat(document.getElementById("temperature").value) || 0.35,
                max_tokens: parseInt(document.getElementById("max_tokens").value) || 600,
                max_steps: parseInt(document.getElementById("max_steps").value),
                evaluation_strategy: document.getElementById("evaluation_strategy").value,
                save_strategy: document.getElementById("save_strategy").value,
                learning_rate: document.getElementById("learning_rate").value,
                optim: document.getElementById("optim").value,
                weight_decay: parseFloat(document.getElementById("weight_decay").value),
                warmup_steps: parseInt(document.getElementById("warmup_steps").value),
                eval_steps: parseInt(document.getElementById("eval_steps").value),
                save_steps: parseInt(document.getElementById("save_steps").value),
                logging_steps: parseInt(document.getElementById("logging_steps").value)
            };
            const btn = configForm.querySelector("button[type='submit']");
            btn.disabled = true;
            try {
                const resp = await fetch("/genai-api/config", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload),
                });
                const data = await resp.json();
                if (data.success) alert("설정 파일이 저장되었습니다!");
                else alert("오류: " + data.error);
            } catch (err) { alert("서버 통신 오류"); }
            finally { btn.disabled = false; }
        });
    }
});