$(function () {
    console.log("dashboard script loaded");
    let ALL_DISTRICTS = [];

    const ALL_YEARS = $('#dashboard-year-end option')
        .map(function () {
            return $(this).val();
        })
        .get()
        .filter(v => v)
        .map(v => Number(v));

    function updateEndYearOptions() {
        const startVal = $('#dashboard-year-start').val();
        const startYear = startVal ? Number(startVal) : null;
        const $end = $('#dashboard-year-end');
        const prevEndVal = $end.val();

        $end.empty();
        $end.append('<option value="">전체</option>');

        ALL_YEARS.forEach(y => {
            if (!startYear || y >= startYear) {
                $end.append(`<option value="${y}">${y}</option>`);
            }
        });

        if (prevEndVal && (!startYear || Number(prevEndVal) >= startYear)) {
            $end.val(prevEndVal);
        } else {
            $end.val('');
        }
    }

    function renderDashboardTable(items) {
        const $placeholder = $('#dashboard-table');

        const filtered = (items || []).filter(row => {
            const y = Number(row.year);
            return y >= 2015 && y <= 2022;
        });

        if (!filtered.length) {
            $placeholder.html(
                '<p class="text-muted small mb-0">해당 조건에 대한 2015~2022년 데이터가 없습니다.</p>'
            );
            return;
        }

        let html = `
            <table class="table table-sm mb-0">
                <thead>
                    <tr>
                        <th>연도</th>
                        <th>이용자 수</th>
                        <th>시설 수</th>
                    </tr>
                </thead>
                <tbody>
        `;

        filtered.forEach(row => {
            html += `
                <tr>
                    <td>${row.year}</td>
                    <td>${row.child_user}</td>
                    <td>${row.child_facility}</td>
                </tr>
            `;
        });

        html += `
                </tbody>
            </table>
        `;

        $placeholder.html(html);
    }

    function loadDashboardData() {
        const guInputRaw = $('#dashboard-gu-input').val().trim();
        const guInput = guInputRaw || '';

        let districtParam = '전체';
        let displayGu = '서울시';

        const norm = guInput.toLowerCase().replace(/\s/g, '');

        const isWholeSeoul =
            !guInput ||
            norm === '서울' ||
            norm === '서울시' ||
            norm === '서울시전체' ||
            norm === '전체';

        if (!isWholeSeoul) {
            districtParam = guInput;
            displayGu = guInput;
        }

        const startYear = $('#dashboard-year-start').val();
        const endYear = $('#dashboard-year-end').val();

        if (startYear && endYear && Number(startYear) > Number(endYear)) {
            alert('시작 연도는 종료 연도보다 작거나 같아야 합니다.');
            return;
        }

        const params = new URLSearchParams({ district: districtParam });
        if (startYear) params.append('start_year', startYear);
        if (endYear) params.append('end_year', endYear);

        fetch('/data/dashboard-data?' + params.toString())
            .then(res => {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.json();
            })
            .then(data => {
                console.log("/data/dashboard-data response:", data);

                let summary = displayGu + ', ';
                if (startYear && endYear) {
                    summary += `${startYear}년 ~ ${endYear}년 값입니다.`;
                } else if (startYear && !endYear) {
                    summary += `${startYear}년 이후 값입니다.`;
                } else if (!startYear && endYear) {
                    summary += `${endYear}년까지의 값입니다.`;
                } else {
                    summary += '전체 기간 값입니다.';
                }
                $('#dashboard-summary').text(summary);

                if (data.success) {
                    renderDashboardTable(data.items);
                } else {
                    alert('데이터 로드 실패: ' + (data.error || '알 수 없는 오류'));
                }
            })
            .catch(err => {
                console.error("dashboard load error:", err);
                alert('대시보드 데이터를 불러오는 중 오류가 발생했습니다.');
            });
    }

    function loadDistricts() {
        fetch('/data/districts')
            .then(res => {
                if (!res.ok) throw new Error('HTTP ' + res.status);
                return res.json();
            })
            .then(data => {
                console.log("/data/districts response:", data);
                if (!data.success) return;

                ALL_DISTRICTS = data.districts || [];

                const $list = $('#dashboard-gu-list');
                $list.empty();

                $list.append('<div class="autocomplete-item" data-value="전체">서울시</div>');

                ALL_DISTRICTS.forEach(d => {
                    $list.append(`<div class="autocomplete-item" data-value="${d}">${d}</div>`);
                });

                loadDashboardData();
            })
            .catch(err => {
                console.error("loadDistricts error:", err);
            });
    }

    const $guInput = $('#dashboard-gu-input');
    const $guList = $('#dashboard-gu-list');

    function showGuList() {
        $guList.show();
    }

    function hideGuList() {
        setTimeout(() => $guList.hide(), 150);
    }

    $guInput.on('focus click', function () {
        $guList.find('.autocomplete-item').show();
        showGuList();
    });

    $guInput.on('input', function () {
        const keywordRaw = $(this).val().trim().toLowerCase();
        const keyword = keywordRaw.replace(/\s/g, '');

        $guList.find('.autocomplete-item').each(function () {
            const textRaw = $(this).text().toLowerCase();
            const text = textRaw.replace(/\s/g, '');

            if (!keyword || text.indexOf(keyword) !== -1) {
                $(this).show();
            } else {
                $(this).hide();
            }
        });

        showGuList();
    });

    $guList.on('mousedown', '.autocomplete-item', function () {
        const value = $(this).data('value');
        const text = $(this).text();
        $guInput.val(value === '전체' ? '서울시 전체' : text);
        hideGuList();
    });

    $guInput.on('blur', hideGuList);

    $('#dashboard-year-start').on('change', updateEndYearOptions);
    $('#dashboard-refresh').on('click', loadDashboardData);

    loadDistricts();
});
