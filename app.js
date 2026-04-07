document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard V1.6 Loaded (Enhanced Mode)');

    const refreshBtn = document.getElementById('refresh-btn');
    const filterBtns = document.querySelectorAll('.filter-btn');
    const showChangesCheckbox = document.getElementById('show-changes-only');

    let allData = [];
    let summaryData = {};

    const DATA_SOURCE = './data/results.json';

    /* =======================
        DATA LOAD
    ======================= */
    const loadData = async () => {
        try {
            refreshBtn.textContent = '불러오는 중...';
            refreshBtn.disabled = true;

            const res = await fetch(`${DATA_SOURCE}?t=${Date.now()}`);
            if (!res.ok) {
                if (res.status === 404) return showInitialScrapingMessage();
                throw new Error(`데이터 로딩 실패 (${res.status})`);
            }

            const data = await res.json();
            allData = data.listings || [];
            summaryData = data.summary || {};
            window.dailyStatsData = data.daily_stats || {};

            updateLastUpdate(data.last_update);
            updateFilterButtons();

            const activeBtn = document.querySelector('.filter-btn.active');
            renderDashboard(activeBtn ? activeBtn.dataset.apt : '더샵동천포레스트');
        } catch (e) {
            console.error(e);
            alert(e.message);
        } finally {
            refreshBtn.textContent = '새로고침';
            refreshBtn.disabled = false;
        }
    };

    const updateLastUpdate = (lastUpdate) => {
        if (!lastUpdate) return;
        const el = document.getElementById('last-update');
        if (!el) return;
        el.textContent = `최근 갱신: ${lastUpdate}`;
    };

    const updateFilterButtons = () => {
        filterBtns.forEach(btn => {
            const apt = btn.dataset.apt;
            const s = summaryData[apt];
            if (!s) return;
            btn.innerHTML = `${apt} <span style="color:#ffeb3b;">(${s.today}건)</span>`;
        });
    };

    /* =======================
        DASHBOARD RENDER
    ======================= */
    const renderDashboard = (aptFilter) => {
        const showChangesOnly = showChangesCheckbox.checked;
        const search =
            document.getElementById('search-input')?.value.toLowerCase() || '';

        let filtered = allData.filter(item => {
            if (item.complex_name !== aptFilter) return false;
            if (search) {
                const str = `${item.dong} ${item.floor} ${item.price}`.toLowerCase();
                if (!str.includes(search)) return false;
            }
            return true;
        });

        /* ---- sort ---- */
        const statusOrder = {
            '거래 완료': 1,
            '등록 만료': 2,
            '신규매물': 4,
            '매물 재등록': 4,
            '유지': 4
        };

        filtered.sort((a, b) => {
            const wA = statusOrder[(a.status || '').trim()] || 99;
            const wB = statusOrder[(b.status || '').trim()] || 99;
            if (wA !== wB) return wA - wB;
            return (a.price_val || 0) - (b.price_val || 0);
        });

        /* ---- table render ---- */
        const tbody = document.getElementById('listings-body');
        tbody.innerHTML = '';
        let renderedCount = 0;

        filtered.forEach(item => {
            const status = (item.status || '').trim();
            const hiddenStatuses = ['유지', '매물 재등록'];
            if (showChangesOnly && hiddenStatuses.includes(status)) return;

            const tr = document.createElement('tr');
            const badgeClass = `status-${status.replace(/\s+/g, '')}`;
            const link = item.article_no
                ? `https://m.land.naver.com/article/info/${item.article_no}`
                : '#';

            tr.innerHTML = `
                <td><strong>${item.complex_name}</strong></td>
                <td><span class="status-badge ${badgeClass}">${status}</span></td>
                <td><a href="${link}" target="_blank">${item.dong}</a></td>
                <td>${item.floor || ''}</td>
                <td>${item.area || ''}</td>
                <td><strong>${item.price}</strong></td>
                <td>${item.reg_date || '-'}</td>
            `;

            tbody.appendChild(tr);
            renderedCount++;
        });

        if (renderedCount === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" style="text-align:center; padding:3rem; color:#94a3b8;">
                        표시할 매물이 없습니다.
                    </td>
                </tr>
            `;
        }
    };

    /* =======================
        UI HELPERS
    ======================= */
    const showInitialScrapingMessage = () => {
        document.getElementById('listings-body').innerHTML =
            `<tr><td colspan="7" style="padding:4rem;text-align:center;">크롤링 중...</td></tr>`;
    };

    /* =======================
        EVENTS
    ======================= */
    refreshBtn.addEventListener('click', loadData);

    showChangesCheckbox.addEventListener('change', () => {
        const activeBtn = document.querySelector('.filter-btn.active');
        renderDashboard(activeBtn ? activeBtn.dataset.apt : '더샵동천포레스트');
    });

    document.getElementById('search-input')?.addEventListener('input', () => {
        const activeBtn = document.querySelector('.filter-btn.active');
        renderDashboard(activeBtn ? activeBtn.dataset.apt : '더샵동천포레스트');
    });

    filterBtns.forEach(btn => {
        btn.addEventListener('click', e => {
            filterBtns.forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');
            renderDashboard(e.currentTarget.dataset.apt);
        });
    });

    /* =======================
        INIT
    ======================= */
    loadData();
});