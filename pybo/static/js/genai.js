document.addEventListener("DOMContentLoaded", function () {

    // 모델 상태 표시용 데이터 (UI용)
    const modelHistory = {
        base: { max_steps: 0, readonly: true, msg: "미학습 모델: Llama-3 기본 상태입니다." },
        cp100: { max_steps: 100, readonly: true, msg: "초기 학습: 말투가 조금씩 변하기 시작합니다." },
        cp200: { max_steps: 200, readonly: true, msg: "중간 학습: 지시 이행 능력이 향상되었습니다." },
        final: { max_steps: 300, readonly: false, msg: "최종 모델: 300스텝 학습이 완료된 최적화 상태입니다." }
    };

    // UI 요소
    const reportForm = document.getElementById("reportForm");
    const resultSection = document.getElementById("resultSection");
    const loadingSpinner = document.getElementById("loadingSpinner");
    const aiTitle = document.getElementById("aiTitle");
    const aiSummary = document.getElementById("aiSummary");
    const aiContent = document.getElementById("aiContent");

    function getModelVer() {
        return document.querySelector('input[name="modelVersion"]:checked')?.value || "final";
    }

    function getSelectedDistrict() {
        return document.getElementById("regionSelect")?.value || "전체";
    }

    // 모델 교체 + UI 업데이트
    // ※ switch-model은 RunPod가 전역 모델 스위치를 지원할 때만 의미 있음.
    async function updateModelSettingsUI() {
        const selected = document.querySelector('input[name="modelVersion"]:checked');
        const ver = selected ? selected.value : "final";
        const config = modelHistory[ver] || modelHistory["final"];
        const reportBtn = reportForm ? reportForm.querySelector("button[type='submit']") : null;

        // 버튼 잠깐 비활성화(UX)
        if (reportBtn) {
            reportBtn.disabled = true;
            reportBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 모델 전환 중...';
        }

        // 전역 스위치 요청 (실패해도 각 API는 model_version으로 동작하니 치명적 아님)
        try {
            console.log(`서버 모델 교체 요청: ${ver}`);
            const switchResp = await fetch("/genai-api/switch-model", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ model_version: ver })
            });
            const switchData = await switchResp.json();
            if (switchData.success) {
                console.log(`모델 교체 성공: ${ver}`);
            } else {
                console.warn("모델 교체 실패(무시 가능):", switchData.error);
            }
        } catch (err) {
            console.warn("모델 교체 요청 실패(무시 가능):", err);
        } finally {
            if (reportBtn) {
                reportBtn.disabled = false;
                reportBtn.innerHTML = '<i class="bi bi-magic mr-2"></i> 보고서 생성';
            }
        }

        // UI 입력 제어(읽기전용 등)
        const trainingInputs = [
            "max_steps", "evaluation_strategy", "save_strategy",
            "learning_rate", "optim", "weight_decay",
            "warmup_steps", "eval_steps", "save_steps", "logging_steps"
        ];

        trainingInputs.forEach(id => {
            const el = document.getElementById(id);
            if (el) {
                el.disabled = config.readonly;
                if (id === "max_steps") el.value = config.max_steps;
            }
        });

        const badge = document.querySelector(".badge-danger");
        if (badge) {
            let msgEl = document.getElementById("model-status-msg") || document.createElement("span");
            if (!msgEl.id) {
                msgEl.id = "model-status-msg";
                msgEl.className = "ml-3 small font-italic text-secondary";
                badge.parentNode.appendChild(msgEl);
            }
            msgEl.textContent = config.msg;
        }
    }

    // 라디오 change 이벤트
    document.querySelectorAll('input[name="modelVersion"]').forEach(radio => {
        radio.addEventListener('change', updateModelSettingsUI);
    });

    // 초기 실행
    updateModelSettingsUI();

    // 연도 선택 로직
    const startSelect = document.getElementById('startYear');
    const endSelect = document.getElementById('endYear');
    if (startSelect && endSelect) {
        function updateEndYearOptions() {
            const startVal = parseInt(startSelect.value);
            const currentEndVal = parseInt(endSelect.value);
            endSelect.innerHTML = "";
            for (let y = startVal; y <= 2030; y++) {
                const option = document.createElement("option");
                option.value = y;
                option.textContent = y + "년";
                endSelect.appendChild(option);
            }
            endSelect.value = (currentEndVal >= startVal) ? currentEndVal : startVal;
        }
        startSelect.addEventListener('change', updateEndYearOptions);
        updateEndYearOptions();
    }

    // 보고서 생성
    if (reportForm) {
        reportForm.addEventListener("submit", async function (e) {
            e.preventDefault();

            const modelVer = getModelVer();
            const reportBtn = reportForm.querySelector("button[type='submit']");

            if (resultSection) resultSection.style.display = "none";
            if (loadingSpinner) loadingSpinner.style.display = "block";
            if (reportBtn) { reportBtn.disabled = true; reportBtn.innerHTML = "생성 중..."; }

            try {
                const resp = await fetch("/genai-api/report", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        district: getSelectedDistrict(),
                        start_year: parseInt(document.getElementById("startYear").value),
                        end_year: parseInt(document.getElementById("endYear").value),
                        model_version: modelVer,
                        prompt: "report"
                    }),
                });

                const data = await resp.json();
                if (data.success) {
                    let parsedData = { title: "분석 결과", summary: "정보 없음", content: data.result };
                    try {
                        const cleanJson = (data.result || "").replace(/```json/g, "").replace(/```/g, "").trim();
                        parsedData = JSON.parse(cleanJson);
                    } catch (err) {
                        parsedData.content = data.result;
                    }

                    if (aiTitle) aiTitle.textContent = parsedData.title || "분석 보고서";
                    if (aiSummary) aiSummary.textContent = parsedData.summary || "요약 없음";
                    if (aiContent) aiContent.innerText = parsedData.content || "";

                    if (resultSection) resultSection.style.display = "block";
                } else {
                    alert(data.error || "오류 발생");
                }
            } catch (err) {
                alert("서버 통신 오류");
            } finally {
                if (loadingSpinner) loadingSpinner.style.display = "none";
                if (reportBtn) { reportBtn.disabled = false; reportBtn.innerHTML = "보고서 생성"; }
            }
        });
    }

    // 정책 제안
    const policyBtn = document.getElementById("policy-btn");
    if (policyBtn) {
        policyBtn.addEventListener("click", async function () {
            const input = document.getElementById("policy-input");
            const resultArea = document.getElementById("policyResultArea");

            if (!input || !input.value.trim()) return;

            policyBtn.disabled = true;
            if (resultArea) {
                resultArea.style.display = "block";
                resultArea.textContent = "생성 중...";
            }

            try {
                const resp = await fetch("/genai-api/policy", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        prompt: input.value,
                        district: getSelectedDistrict(),
                        model_version: getModelVer()
                    }),
                });

                const data = await resp.json();
                if (resultArea) resultArea.textContent = data.success ? data.result : (data.error || "오류");
            } finally {
                policyBtn.disabled = false;
            }
        });
    }

    // Q&A
    const qaBtn = document.getElementById("qa-btn");
    const qaInput = document.getElementById("qa-input");

    if (qaBtn && qaInput) {
        // 엔터 전송 / Shift+Enter 줄바꿈
        qaInput.addEventListener("keydown", function (e) {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                qaBtn.click();
            }
        });

        qaBtn.addEventListener("click", async function () {
            const chat = document.getElementById("qa-chat-window");
            if (!qaInput.value.trim()) return;

            const q = qaInput.value;
            if (chat) chat.innerHTML += `<div class="chat-bubble user-bubble">${q}</div>`;
            qaInput.value = "";

            const tempLoadingId = "ai-loading-" + Date.now();
            if (chat) {
                chat.innerHTML += `
                    <div class="chat-bubble ai-bubble" id="${tempLoadingId}">
                        <div class="typing-indicator">
                            <span></span><span></span><span></span>
                        </div>
                    </div>`;
                chat.scrollTop = chat.scrollHeight;
            }

            try {
                const resp = await fetch("/genai-api/qa", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                        question: q,
                        model_version: getModelVer()
                    }),
                });

                const data = await resp.json();
                const loadingBubble = document.getElementById(tempLoadingId);
                if (loadingBubble) {
                    loadingBubble.innerHTML = data.success ? data.result : (data.error || "답변 생성 오류");
                }
            } catch (err) {
                const loadingBubble = document.getElementById(tempLoadingId);
                if (loadingBubble) loadingBubble.innerHTML = "서버 통신 오류가 발생했습니다.";
                console.error(err);
            } finally {
                if (chat) chat.scrollTop = chat.scrollHeight;
            }
        });
    }

    // 텍스트 요약
    const summaryBtn = document.getElementById("summary-btn");
    if (summaryBtn) {
        summaryBtn.addEventListener("click", async function () {
            const input = document.getElementById("summary-input");
            const resultArea = document.getElementById("summaryResultArea");
            const resultText = document.getElementById("summaryText");

            if (!input || !input.value.trim()) {
                alert("요약할 내용을 입력해주세요.");
                return;
            }

            summaryBtn.disabled = true;
            summaryBtn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> 요약 중...';

            if (resultArea) resultArea.style.display = "block";
            if (resultText) resultText.textContent = "문서를 분석하여 요약 중입니다. 잠시만 기다려 주세요...";

            try {
                const resp = await fetch("/genai-api/summarize", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ text: input.value }),
                });

                const data = await resp.json();
                if (resultText) resultText.textContent = data.success ? data.result : ("오류: " + (data.error || ""));
            } catch (err) {
                if (resultText) resultText.textContent = "서버 통신 오류가 발생했습니다.";
            } finally {
                summaryBtn.disabled = false;
                summaryBtn.innerHTML = '<i class="bi bi-scissors mr-2"></i> 핵심 요약하기';
            }
        });
    }

    // 탭 전환 시 모델 선택창 제어
    const modelSelector = document.querySelector('.model-compare-selector');
    const navLinks = document.querySelectorAll('#genaiTab .nav-link');

    function updateUIByTab(tabId) {
        if (!modelSelector) return;
        if (tabId === 'summary-tab') {
            modelSelector.style.display = 'none';
        } else {
            modelSelector.style.display = 'block';
        }
    }

    const currentActiveTab = document.querySelector('#genaiTab .nav-link.active');
    if (currentActiveTab) updateUIByTab(currentActiveTab.id);

    navLinks.forEach(link => {
        link.addEventListener('click', function () {
            updateUIByTab(this.id);
        });
    });
});
