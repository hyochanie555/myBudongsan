document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard V1.6 Loaded (Enhanced Mode)');
    const refreshBtn = document.getElementById('refresh-btn');
    const filterBtns = document.querySelectorAll('.filter-btn');
    const showChangesCheckbox = document.getElementById('show-changes-only');
    const scrapeBtn = document.getElementById('scrape-btn');

    let allData = [];
    let summaryData = {};

    // JSON Data Source
    const DATA_SOURCE = './data/results.json';

    // Fetch data with improved error handling for "Scraping in progress"
    const loadData = async () => {
        try {
            refreshBtn.textContent = '불러오는 중...';
            refreshBtn.disabled = true;

            const res = await fetch(`${DATA_SOURCE}?t=${new Date().getTime()}`); // Cache busting
            
            if (!res.ok) {
                if (res.status === 404) {
                    showInitialScrapingMessage();
                    return;
                }
                throw new Error(`데이터 파일을 불러올 수 없습니다 (${res.status})`);
            }

            const responseData = await res.json();
            allData = responseData.listings || [];
            summaryData = responseData.summary || {};
            window.dailyStatsData = responseData.daily_stats || {};

            // Show Last Update Time
            const lastUpdateEl = document.getElementById('last-update');
            if (responseData.last_update && lastUpdateEl) {
                lastUpdateEl.textContent = `최근 갱신: ${responseData.last_update}`;
            }

            // Update Filter Button Texts (Aesthetics Restoration)
            filterBtns.forEach(btn => {
                const apt = btn.dataset.apt;
                const s = summaryData[apt];
                if (s) {
                    if (s.prev > 0) {
                        btn.innerHTML = `${apt} <span style="font-size:1.2rem; font-weight: 700; color: #ffeb3b; margin-left: 8px;">(${s.prev} ➔ ${s.today})</span>`;
                    } else {
                        btn.innerHTML = `${apt} <span style="font-size:1.2rem; font-weight: 700; color: #ffeb3b; margin-left: 8px;">(${s.today}건)</span>`;
                    }
                }
            });

            const activeBtn = document.querySelector('.filter-btn.active');
            renderDashboard(activeBtn ? activeBtn.dataset.apt : '더샵동천포레스트');
        } catch (error) {
            console.error('Error loading data:', error);
            // If it's a CORS error (file://), show a specific hint
            if (window.location.protocol === 'file:') {
                showCORSErrorMessage();
            } else {
                alert(`데이터 로딩 실패: ${error.message}`);
            }
        } finally {
            refreshBtn.textContent = '새로고침';
            refreshBtn.disabled = false;
        }
    };

    const showInitialScrapingMessage = () => {
        const tbody = document.getElementById('listings-body');
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" style="text-align: center; padding: 4rem; color: #94a3b8;">
                        <div style="font-size: 1.5rem; margin-bottom: 1rem;">🛰️ 크롤링이 진행 중입니다...</div>
                        <div style="font-size: 1rem;">처음 실행 시 데이터 생성까지 약 1~2분이 소요됩니다.<br>잠시 후 '새로고침' 버튼을 눌러주세요.</div>
                    </td>
                </tr>
            `;
        }
        document.getElementById('last-update').textContent = '데이터 생성 대기 중...';
    };

    const showCORSErrorMessage = () => {
        const tbody = document.getElementById('listings-body');
        if (tbody) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="7" style="text-align: center; padding: 4rem; color: #f87171;">
                        <div style="font-size: 1.5rem; margin-bottom: 1rem;">❌ 로컬 파일 실행 제한 (CORS)</div>
                        <div style="font-size: 1rem; color: #94a3b8;">웹 브라우저의 보안 정책으로 인해 로컬 파일을 직접 열면 데이터를 불러올 수 없습니다.<br>
                        <strong>VS Code의 'Live Server'</strong> 등을 사용하거나 <strong>GitHub</strong>에 업로드하여 확인해 주세요.</div>
                    </td>
                </tr>
            `;
        }
    };

    // Render Dashboard (Cards + Table)
    const renderDashboard = (aptFilter) => {
        const showChangesOnly = showChangesCheckbox.checked;
        const searchTerm = document.getElementById('search-input')?.value.toLowerCase() || "";
        
        // Comprehensive Filtering
        const filtered = allData.filter(item => {
            // 1. Apartment Filter
            if (item.complex_name !== aptFilter) return false;
            
            // 2. Search Term Filter (Multi-column)
            if (searchTerm) {
                const searchStr = `${item.complex_name} ${item.dong} ${item.floor} ${item.price} ${item.area} ${item.reg_date}`.toLowerCase();
                if (!searchStr.includes(searchTerm)) return false;
            }
            
            return true;
        });

        // Multi-level Sorting Logic
        filtered.sort((a, b) => {
            const statusOrder = {
                '신규매물': 1,
                '가격 인하': 2,
                '거래 완료': 3,
                '가격 인상': 4,
                '매물 재등록': 5,
                '유지': 6,
                '등록 만료': 7
            };
            const statusA = (a.status || "").trim();
            const statusB = (b.status || "").trim();
            
            const weightA = statusOrder[statusA] || 99;
            const weightB = statusOrder[statusB] || 99;

            // 1. Status Priority
            if (weightA !== weightB) {
                return weightA - weightB;
            }

            // 2. Price: Lowest price first (price_val)
            if ((a.price_val || 0) !== (b.price_val || 0)) {
                return (a.price_val || 0) - (b.price_val || 0);
            }

            // 3. Dong: Alphabetical order
            if (a.dong !== b.dong) {
                return (a.dong || "").localeCompare(b.dong || "");
            }

            // 4. Floor: String comparison (deals with '고/21', '중/21', etc.)
            return (a.floor || "").localeCompare(b.floor || "");
        });

        // Update cards with safety
        try {
            let countNew = 0, countRe = 0, countActive = 0, countDone = 0;

            filtered.forEach(item => {
                const status = (item.status || "").trim();
                if (status === '신규매물') {
                    countNew++;
                    countActive++;
                } else if (status === '매물 재등록' || status === '가격 인하' || status === '가격 인상') {
                    countRe++;
                    countActive++;
                } else if (status === '유지') {
                    countActive++;
                } else if (status === '거래 완료' || status === '등록 만료') {
                    countDone++;
                }
            });

            if (document.getElementById('count-new')) document.getElementById('count-new').textContent = countNew;
            if (document.getElementById('count-re')) document.getElementById('count-re').textContent = countRe;
            if (document.getElementById('count-done')) document.getElementById('count-done').textContent = countDone;
            if (document.getElementById('count-active')) document.getElementById('count-active').textContent = countActive;
        } catch (e) {
            console.warn("Card update failed:", e);
        }

        // Render Table
        const tbody = document.getElementById('listings-body');
        if (!tbody) return;
        tbody.innerHTML = '';

        let renderedCount = 0;
        filtered.forEach(item => {
            const status = (item.status || "").trim();
            if (showChangesOnly && (status === '유지' || status === '매물 재등록')) {
                return; // Hide unchanged and re-registered if checked
            }

            const tr = document.createElement('tr');
            const badgeClass = `status-${status.replace(/\s+/g, '')}`;
            
            // Show grouped count if > 1
            const countSuffix = item.count > 1 ? ` <span style="color: #94a3b8; font-size: 0.85em; font-weight: normal;">(${item.count}건)</span>` : '';
            
            // Link to the first article if available
            const articleLink = item.article_no ? `https://m.land.naver.com/article/info/${item.article_no}` : '#';

            // Price display logic (handles price drops/raises)
            let priceHtml = `<strong>${item.price}</strong>`;
            if (item.prev_price && status === '가격 인하') {
                const diffMan = item.price_diff ? Math.abs(Math.round(item.price_diff / 10000)).toLocaleString() : '';
                priceHtml = `
                    <div style="font-size:0.82em; color:#94a3b8; text-decoration:line-through;">${item.prev_price}</div>
                    <div style="display:flex; align-items:center; gap:4px;">
                        <strong style="color:#fb7185;">${item.price}</strong>
                        <span style="color:#f43f5e; font-size:0.8em; font-weight:bold;">(-${diffMan}만 🔻)</span>
                    </div>
                `;
            } else if (item.prev_price && status === '가격 인상') {
                const diffMan = item.price_diff ? Math.round(item.price_diff / 10000).toLocaleString() : '';
                priceHtml = `
                    <div style="font-size:0.82em; color:#94a3b8; text-decoration:line-through;">${item.prev_price}</div>
                    <div style="display:flex; align-items:center; gap:4px;">
                        <strong style="color:#a78bfa;">${item.price}</strong>
                        <span style="color:#8b5cf6; font-size:0.8em; font-weight:bold;">(+${diffMan}만 🔺)</span>
                    </div>
                `;
            }

            tr.innerHTML = `
                <td data-label="단지명"><strong>${item.complex_name}</strong></td>
                <td data-label="상태"><span class="status-badge ${badgeClass}">${status}</span></td>
                <td class="dong-cell">
                    <a href="${articleLink}" target="_blank" style="color: inherit; text-decoration: none;">
                        <strong>${item.dong}${countSuffix}</strong>
                    </a>
                </td>
                <td class="floor-cell">${item.floor || ''}</td>
                <td class="area-cell">${item.area || ''}</td>
                <td data-label="가격" class="price-cell">${priceHtml}</td>
                <td data-label="등록일" class="reg-date-cell">${item.reg_date || '-'}</td>
            `;
            tbody.appendChild(tr);
            renderedCount++;
        });

        // Show empty message if no rows
        if (renderedCount === 0) {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td colspan="7" style="text-align: center; padding: 3rem; color: #94a3b8; font-size: 1.2rem;">
                    표시할 매물이 없습니다. (변동 사항이 없거나 검색 결과가 없습니다.)
                </td>
            `;
            tbody.appendChild(tr);
        }
    };

    // --- Trend Chart Logic ---
    let trendChartInstance = null;
    const chartModal = document.getElementById('chart-modal');
    const trendBtn = document.getElementById('trend-btn');
    const closeChartBtn = document.getElementById('close-chart-btn');
    const chartAptSelect = document.getElementById('chart-apt-select');

    const renderChart = (aptName) => {
        const ctx = document.getElementById('trendChart').getContext('2d');
        const stats = window.dailyStatsData || {};
        const aptData = stats[aptName] || {};
        
        const labels = Object.keys(aptData).sort();
        const totalListings = labels.map(date => aptData[date].total);
        const doneListings = labels.map(date => aptData[date].done);

        if (trendChartInstance) {
            trendChartInstance.destroy();
        }

        Chart.defaults.color = '#94a3b8';
        Chart.defaults.font.family = "'Pretendard', sans-serif";

        trendChartInstance = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: '전체 매물 (활성)',
                        data: totalListings,
                        borderColor: '#3b82f6',
                        backgroundColor: 'rgba(59, 130, 246, 0.2)',
                        tension: 0.3,
                        fill: true,
                    },
                    {
                        label: '찐 거래 완료',
                        data: doneListings,
                        borderColor: '#10b981',
                        backgroundColor: 'rgba(16, 185, 129, 0.2)',
                        tension: 0.3,
                        fill: true,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        position: 'top',
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    };

    trendBtn?.addEventListener('click', () => {
        chartModal.style.display = 'flex';
        // Select currently active filter if possible
        const activeBtn = document.querySelector('.filter-btn.active');
        if(activeBtn) {
            chartAptSelect.value = activeBtn.dataset.apt;
        }
        renderChart(chartAptSelect.value);
    });

    closeChartBtn?.addEventListener('click', () => {
        chartModal.style.display = 'none';
    });

    chartModal?.addEventListener('click', (e) => {
        if(e.target === chartModal) chartModal.style.display = 'none';
    });

    chartAptSelect?.addEventListener('change', (e) => {
        renderChart(e.target.value);
    });

    // Setup listeners
    refreshBtn.addEventListener('click', loadData);
    showChangesCheckbox.addEventListener('change', () => {
        const activeBtn = document.querySelector('.filter-btn.active');
        renderDashboard(activeBtn ? activeBtn.dataset.apt : '더샵동천포레스트');
    });
    
    // 🔍 Real-time Search Listener
    document.getElementById('search-input')?.addEventListener('input', () => {
        const activeBtn = document.querySelector('.filter-btn.active');
        renderDashboard(activeBtn ? activeBtn.dataset.apt : '더샵동천포레스트');
    });

    filterBtns.forEach(btn => {
        btn.addEventListener('click', (e) => {
            filterBtns.forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');
            renderDashboard(e.currentTarget.dataset.apt);
        });
    });

    // Initial load
    loadData();
});
