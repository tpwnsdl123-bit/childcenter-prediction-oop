$(function () {
    console.log("predict script loaded");

    let predictChart = null;

    const svgIdToGu = {
        "Dobong-gu": "도봉구",
        "Dongdaemun-gu": "동대문구",
        "Dongjak-gu": "동작구",
        "Eunpyeong-gu": "은평구",
        "Gangbuk-gu": "강북구",
        "Gangdong-gu": "강동구",
        "Gangseo-gu": "강서구",
        "Geumcheon-gu": "금천구",
        "Guro-gu": "구로구",
        "Gwanak-gu": "관악구",
        "Gwangjin-gu": "광진구",
        "Gangnam-gu": "강남구",
        "Jongno-gu": "종로구",
        "Jung-gu": "중구",
        "Jungnang-gu": "중랑구",
        "Mapo-gu": "마포구",
        "Nowon-gu": "노원구",
        "Seocho-gu": "서초구",
        "Seodaemun-gu": "서대문구",
        "Seongbuk-gu": "성북구",
        "Seongdong-gu": "성동구",
        "Songpa-gu": "송파구",
        "Yangcheon-gu": "양천구",
        "Yeongdeungpo-gu_1_": "영등포구",
        "Yongsan-gu": "용산구"
    };

    const $mapInner = $('.map-inner');

    if ($mapInner.length) {
        $mapInner.find('.gu-region').each(function () {
            const $r = $(this);
            if (!$r.attr('data-gu')) {
                const mapped = svgIdToGu[this.id];
                if (mapped) $r.attr('data-gu', mapped);
            }
        });

        $mapInner.find('.gu-label').each(function () {
            const $l = $(this);
            if (!$l.attr('data-gu')) {
                $l.attr('data-gu', $.trim($l.text()));
            }
        });

        const $tooltip = $('<div class="map-tooltip"></div>').appendTo($mapInner);
        let tooltipVisible = false;

        function getGuNameFromRegion(el) {
            const $region = $(el);
            const svgId = el.id;
            let guName = $region.attr('data-gu');

            if (!guName && svgIdToGu[svgId]) {
                guName = svgIdToGu[svgId];
                $region.attr('data-gu', guName);
            }
            return guName || null;
        }

        function selectGuOnMap(guName) {
            $mapInner.find('.gu-region').removeClass('selected hovered');
            $mapInner.find('.gu-label').removeClass('selected hovered');

            if (!guName || guName === '전체') return;

            $mapInner.find(`.gu-region[data-gu="${guName}"]`).addClass('selected');
            $mapInner.find(`.gu-label[data-gu="${guName}"]`).addClass('selected');
        }

        $mapInner.on('mouseenter', '.gu-region', function (e) {
            const guName = getGuNameFromRegion(this);
            if (!guName) {
                console.log('매핑 안 된 SVG id:', this.id);
                return;
            }

            $(this).addClass('hovered');
            $mapInner.find('.gu-label').removeClass('hovered');
            $mapInner.find(`.gu-label[data-gu="${guName}"]`).addClass('hovered');

            $(this).css('cursor', 'pointer');
            $tooltip.text(guName).show();
            tooltipVisible = true;
        });

        $mapInner.on('mousemove', '.gu-region', function (e) {
            if (!tooltipVisible) return;
            const rect = $mapInner[0].getBoundingClientRect();
            const x = e.clientX - rect.left + 8;
            const y = e.clientY - rect.top + 8;
            $tooltip.css({ left: x + 'px', top: y + 'px' });
        });

        $mapInner.on('mouseleave', '.gu-region', function () {
            $(this).removeClass('hovered');
            $mapInner.find('.gu-label').removeClass('hovered');
            $tooltip.hide();
            tooltipVisible = false;
        });

        $mapInner.on('click', '.gu-region', function () {
            const guName = getGuNameFromRegion(this);
            if (!guName) return;

            selectGuOnMap(guName);
            $('#gu-select').val(guName);

            loadPredictData();
            loadPredictSeries();
        });

        $('#gu-select').on('change', function () {
            const guName = $(this).val() || '전체';
            selectGuOnMap(guName);
        });
    }

    function renderSummaryCards(data) {
        const $area = $('#predict-summary-area');
        const districtLabel =
            (data.district === '전체') ? '서울시 전체' : data.district;

        const cur = data.child_user || 0;
        const prev = data.prev_child_user;
        const seoulAvg = data.seoul_avg_child_user || 0;
        const seoulCnt = data.seoul_district_count || 1;

        const myValuePerGu = (data.district === '전체')
            ? (cur / seoulCnt)
            : cur;

        let yoyText = '전년 데이터 없음';
        if (prev !== null && prev !== undefined) {
            const diff = cur - prev;
            const rate = prev === 0 ? null : (diff / prev * 100);
            if (rate === null) {
                yoyText = `${diff.toLocaleString()} 명 (전년 0명 → 증감률 계산 불가)`;
            } else {
                const sign = diff >= 0 ? '+' : '';
                yoyText =
                    `${sign}${diff.toLocaleString()} 명 ` +
                    `(${sign}${rate.toFixed(1)}%)`;
            }
        }

        let avgText = '서울 평균 데이터 없음';
        if (seoulAvg) {
            const diffAvg = myValuePerGu - seoulAvg;
            const sign2 = diffAvg >= 0 ? '+' : '';
            avgText =
                `${sign2}${Math.round(diffAvg).toLocaleString()} 명<br> ` +
                `<small class="text-muted">(구당 평균 ${Math.round(seoulAvg).toLocaleString()}명 기준)</small>`;
        }

        const html = `
            <div class="row g-2">
                <div class="col-12 col-md-4">
                    <div class="card border-0 shadow-sm h-100">
                        <div class="card-body py-2">
                            <div class="text-muted small mb-1">예측 이용자 수</div>
                            <div class="fw-bold fs-5">
                                ${cur.toLocaleString()} <span class="small">명</span>
                            </div>
                            <div class="small text-muted mt-1">
                                ${data.year}년 ${districtLabel}
                            </div>
                        </div>
                    </div>
                </div>

                <div class="col-12 col-md-4">
                    <div class="card border-0 shadow-sm h-100">
                        <div class="card-body py-2">
                            <div class="text-muted small mb-1">전년 대비 증감</div>
                            <div class="fw-bold small">
                                ${yoyText}
                            </div>
                        </div>
                    </div>
                </div>

                <div class="col-12 col-md-4">
                    <div class="card border-0 shadow-sm h-100">
                        <div class="card-body py-2">
                            <div class="text-muted small mb-1">서울 평균 대비</div>
                            <div class="fw-bold small">
                                ${avgText}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        `;

        $area.html(html);
    }

    function renderPredictTable(data) {
        const $area = $('#predict-data-area');

        if (!data || !data.success) {
            $area.html('<p class="mb-0 text-muted">예측 데이터를 불러올 수 없습니다.</p>');
            return;
        }

        const districtLabel =
            (data.district === '전체') ? '서울시 전체' : data.district;
        const cur = data.child_user || 0;

        const f = data.features || {};

        const singleParent = (f.single_parent != null)
            ? `${Math.round(f.single_parent).toLocaleString()} 가구`
            : '-';

        const basicBeneficiaries = (f.basic_beneficiaries != null)
            ? `${Math.round(f.basic_beneficiaries).toLocaleString()} 명`
            : '-';

        const multiculturalHh = (f.multicultural_hh != null)
            ? `${Math.round(f.multicultural_hh).toLocaleString()} 가구`
            : '-';

        const academyCnt = (f.academy_cnt != null)
            ? `${Math.round(f.academy_cnt).toLocaleString()} 개`
            : '-';

        const grdpDisplay = (f.grdp != null)
            ? `${Math.round(f.grdp / 10000).toLocaleString()} 만원`
            : '-';

        const html = `
            <div class="w-100">
                <p class="mb-2 text-center small text-muted">
                    ${data.year}년 ${districtLabel} 기준 주요 지표 예측 결과입니다.
                </p>
                <table class="table table-sm mb-0 text-center predict-feature-table">
                    <thead>
                        <tr>
                            <th class="small">예측 이용자 수</th>
                            <th class="small">한부모 가구 수</th>
                            <th class="small">기초생활수급자 수</th>
                            <th class="small">다문화 가구 수</th>
                            <th class="small">사설 학원 수</th>
                            <th class="small">GRDP</th>
                        </tr>
                    </thead>
                    <tbody>
                        <tr>
                            <td>${cur.toLocaleString()} 명</td>
                            <td>${singleParent}</td>
                            <td>${basicBeneficiaries}</td>
                            <td>${multiculturalHh}</td>
                            <td>${academyCnt}</td>
                            <td>${grdpDisplay}</td>
                        </tr>
                    </tbody>
                </table>

                <p class="mt-2 mb-0 small text-muted text-center">
                    ※ 모델은 이 지표들의 변화 패턴을 종합적으로 학습하여 예측을 수행하므로,
                    <br>일부 값이 감소해도 전체 조합에 따라 예측 결과는 소폭 오르거나 내릴 수 있습니다.
                </p>
            </div>
        `;
        $area.html(html);
    }

    function renderPredictChart(series, districtLabel) {
        const canvas = document.getElementById('predictChart');
        if (!canvas) {
            console.warn("predictChart canvas not found");
            return;
        }

        const ctx = canvas.getContext('2d');

        const labels = series.map(r => r.year);
        const actual = series.map(r => r.is_pred ? null : r.child_user);
        const pred = series.map(r => r.is_pred ? r.child_user : null);

        if (predictChart) {
            predictChart.destroy();
        }

        predictChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: `${districtLabel} 실제 이용자 수 (2015~2022)`,
                        data: actual,
                        borderColor: 'rgba(37,99,235,1)',
                        backgroundColor: 'rgba(37,99,235,0.08)',
                        tension: 0.3,
                        spanGaps: true
                    },
                    {
                        label: `${districtLabel} 예측 이용자 수 (2023~2030)`,
                        data: pred,
                        borderColor: 'rgba(16,185,129,1)',
                        backgroundColor: 'rgba(16,185,129,0.08)',
                        borderDash: [5, 5],
                        tension: 0.3,
                        spanGaps: true
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            font: { size: 11 }
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: {
                            font: { size: 10 }
                        }
                    },
                    y: {
                        ticks: {
                            font: { size: 10 },
                            callback: function (value) {
                                return value.toLocaleString();
                            }
                        }
                    }
                }
            }
        });
    }

    function loadPredictData() {
        const year = $('#year-select').val();
        const gu = $('#gu-select').val() || '전체';

        if (!year) {
            alert('연도를 선택해주세요.');
            return;
        }

        const params = new URLSearchParams({
            year: year,
            district: gu
        });

        fetch('/data/predict-data?' + params.toString())
            .then(res => {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.json();
            })
            .then(data => {
                console.log("/data/predict-data response:", data);
                if (data.success) {
                    renderSummaryCards(data);
                    renderPredictTable(data);
                } else {
                    alert('예측 데이터 로드 실패: ' + (data.error || '알 수 없는 오류'));
                }
            })
            .catch(err => {
                console.error("loadPredictData error:", err);
                alert('예측 데이터를 불러오는 중 오류가 발생했습니다.');
            });
    }

    function loadPredictSeries() {
        const gu = $('#gu-select').val() || '전체';

        const params = new URLSearchParams({
            district: gu
        });

        fetch('/data/predict-series?' + params.toString())
            .then(res => {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.json();
            })
            .then(data => {
                console.log("/data/predict-series response:", data);
                if (data.success) {
                    const districtLabel =
                        (data.district === '전체') ? '서울시 전체' : data.district;
                    renderPredictChart(data.items, districtLabel);
                }
            })
            .catch(err => {
                console.error("loadPredictSeries error:", err);
            });
    }

    function loadDistrictsForPredict() {
        fetch('/data/districts')
            .then(res => {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.json();
            })
            .then(data => {
                console.log("/data/districts (predict) response:", data);
                if (!data.success) return;

                const $gu = $('#gu-select');
                $gu.empty();
                $gu.append(`<option value="전체" selected>자치구 전체</option>`);

                data.districts.forEach(d => {
                    $gu.append(`<option value="${d}">${d}</option>`);
                });

                loadPredictData();
                loadPredictSeries();
            })
            .catch(err => {
                console.error("loadDistrictsForPredict error:", err);
            });
    }

    $('#filter-submit').on('click', function () {
        loadPredictData();
        loadPredictSeries();
    });

    loadDistrictsForPredict();

    // 전역에서도 쓸 수 있게 window에 묶고 싶으면:
    window.loadPredictData = loadPredictData;
    window.loadPredictSeries = loadPredictSeries;
});
