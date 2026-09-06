document.addEventListener('DOMContentLoaded', () => {
    console.log('Dashboard V1.6 Loaded (Enhanced Mode)');
    const refreshBtn = document.getElementById('refresh-btn');
    const filterBtns = document.querySelectorAll('.filter-btn');
    const showChangesCheckbox = document.getElementById('show-changes-only');
    const scrapeBtn = document.getElementById('scrape-btn');

    let allData = [];
    let summaryData = {};
    let listingsHistory = { new: [], re: [], done: [] };

    // JSON Data Source
    const DATA_SOURCE = './data/results.json';
    const HISTORY_SOURCE = './data/listings_history.json';

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

            // Fetch Unified Listings History Data
            try {
                const histRes = await fetch(`${HISTORY_SOURCE}?t=${new Date().getTime()}`);
                if (histRes.ok) {
                    listingsHistory = await histRes.json();
                }
            } catch (he) {
                console.warn("Listings history fetch error:", he);
            }


            // Show Last Update Time
            const lastUpdateEl = document.getElementById('last-update');
            if (responseData.last_update && lastUpdateEl) {
                lastUpdateEl.textContent = `최근 갱신: ${responseData.last_update}`;
            }

            // Show Battery Status
            const batteryEl = document.getElementById('battery-status');
            if (responseData.battery && batteryEl && typeof responseData.battery.percent === 'number') {
                const b = responseData.battery;
                const pct = b.percent;
                const isCharging = b.is_charging;
                
                let icon = '🔋';
                if (isCharging) icon = '⚡';
                else if (pct <= 20) icon = '🪫';

                batteryEl.textContent = `${icon} ${pct}%${isCharging ? ' (충전중)' : ''}`;
                batteryEl.style.display = 'inline-flex';
                
                batteryEl.className = 'battery-badge';
                if (isCharging || pct > 50) {
                    batteryEl.classList.add('battery-good');
                } else if (pct > 20) {
                    batteryEl.classList.add('battery-mid');
                } else {
                    batteryEl.classList.add('battery-low');
                }
            } else if (batteryEl) {
                batteryEl.style.display = 'none';
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
            const statusA = (a.status || "").trim();
            const statusB = (b.status || "").trim();

            if (showChangesOnly) {
                // [체크박스 켜짐 - 변동 매물 집중 보기]
                // 신규매물 > 가격 인하 > 가격 인상 > 거래 완료 > 등록 만료
                const changeStatusOrder = {
                    '신규매물': 1,
                    '가격 인하': 2,
                    '가격 인상': 3,
                    '거래 완료': 4,
                    '등록 만료': 5,
                    '매물 재등록': 6,
                    '유지': 6
                };
                const weightA = changeStatusOrder[statusA] || 99;
                const weightB = changeStatusOrder[statusB] || 99;

                if (weightA !== weightB) {
                    return weightA - weightB;
                }
            } else {
                // [체크박스 해제 - 전체 매물 시세순 보기]
                // 1순위: 거래 완료/등록 만료 매물만 최상단에 배치
                // 2순위: 나머지 모든 활성 매물은 신규 여부 무관하게 동일 순위로 묶어 가격순 정렬
                const isDoneA = (statusA === '거래 완료' || statusA === '등록 만료') ? 1 : 2;
                const isDoneB = (statusB === '거래 완료' || statusB === '등록 만료') ? 1 : 2;

                if (isDoneA !== isDoneB) {
                    return isDoneA - isDoneB;
                }
            }

            // 공통 정렬 1순위: 가격 낮은 순 (price_val)
            if ((a.price_val || 0) !== (b.price_val || 0)) {
                return (a.price_val || 0) - (b.price_val || 0);
            }

            // 공통 정렬 2순위: 동 번호 순
            if (a.dong !== b.dong) {
                return (a.dong || "").localeCompare(b.dong || "");
            }

            // 공통 정렬 3순위: 층수 순
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
                        <strong style="color:#60a5fa;">${item.price}</strong>
                        <span style="color:#38bdf8; font-size:0.82em; font-weight:bold;">(-${diffMan}만 🔻)</span>
                    </div>
                `;
            } else if (item.prev_price && status === '가격 인상') {
                const diffMan = item.price_diff ? Math.round(item.price_diff / 10000).toLocaleString() : '';
                priceHtml = `
                    <div style="font-size:0.82em; color:#94a3b8; text-decoration:line-through;">${item.prev_price}</div>
                    <div style="display:flex; align-items:center; gap:4px;">
                        <strong style="color:#f87171;">${item.price}</strong>
                        <span style="color:#ef4444; font-size:0.82em; font-weight:bold;">(+${diffMan}만 🔺)</span>
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

    // --- Toast Notification ---
    let toastTimeout = null;
    const showToast = (message) => {
        let toast = document.getElementById('app-toast');
        if (!toast) {
            toast = document.createElement('div');
            toast.id = 'app-toast';
            toast.className = 'toast-msg';
            document.body.appendChild(toast);
        }
        toast.textContent = message;
        toast.classList.add('show');
        if (toastTimeout) clearTimeout(toastTimeout);
        toastTimeout = setTimeout(() => {
            toast.classList.remove('show');
        }, 2000);
    };

    // --- History Navigation Guard (Back button support for modals & main screen) ---
    let isProgrammaticBack = false;

    const initHistoryGuard = () => {
        if (!window.history.state || window.history.state.page !== 'home_active') {
            window.history.replaceState({ page: 'home_base' }, '');
            window.history.pushState({ page: 'home_active' }, '');
        }

        window.addEventListener('popstate', () => {
            if (isProgrammaticBack) {
                isProgrammaticBack = false;
                return;
            }

            const historyModalEl = document.getElementById('history-modal');
            const chartModalEl = document.getElementById('chart-modal');

            const isHistoryOpen = historyModalEl && historyModalEl.style.display !== 'none';
            const isChartOpen = chartModalEl && chartModalEl.style.display !== 'none';

            if (isHistoryOpen) {
                historyModalEl.style.display = 'none';
                return;
            }
            if (isChartOpen) {
                chartModalEl.style.display = 'none';
                return;
            }

            // User pressed Back on main dashboard: prevent exit and show toast
            window.history.pushState({ page: 'home_active' }, '');
            showToast('마지막 화면입니다.');
        });
    };

    const pushModalHistory = (modalName) => {
        window.history.pushState({ modal: modalName }, '');
    };

    const closeModalSafely = (modalEl) => {
        if (!modalEl || modalEl.style.display === 'none') return;
        modalEl.style.display = 'none';
        if (window.history.state && window.history.state.modal) {
            isProgrammaticBack = true;
            window.history.back();
        }
    };

    initHistoryGuard();

    trendBtn?.addEventListener('click', () => {
        chartModal.style.display = 'flex';
        pushModalHistory('chart');
        // Select currently active filter if possible
        const activeBtn = document.querySelector('.filter-btn.active');
        if(activeBtn) {
            chartAptSelect.value = activeBtn.dataset.apt;
        }
        renderChart(chartAptSelect.value);
    });

    closeChartBtn?.addEventListener('click', () => {
        closeModalSafely(chartModal);
    });

    chartModal?.addEventListener('click', (e) => {
        if(e.target === chartModal) closeModalSafely(chartModal);
    });

    chartAptSelect?.addEventListener('change', (e) => {
        renderChart(e.target.value);
    });

    // --- Unified History Modal Logic (New, Re, Done) ---
    const historyModal = document.getElementById('history-modal');
    const closeHistoryBtn = document.getElementById('close-history-btn');
    const historyTitleText = document.getElementById('history-title-text');
    const historyTotalBadge = document.getElementById('history-total-badge');
    const historyModalSubtitle = document.getElementById('history-modal-subtitle');
    const historyColDate = document.getElementById('history-col-date');
    const historyColPrice = document.getElementById('history-col-price');
    const historyAptFilters = document.querySelectorAll('#history-apt-filters .comp-filter-btn');
    const historySearchInput = document.getElementById('history-search-input');
    const historyTableBody = document.getElementById('history-table-body');

    const cardNewBtn = document.getElementById('card-new-btn');
    const cardReBtn = document.getElementById('card-re-btn');
    const cardDoneBtn = document.getElementById('card-done-btn');

    let currentHistoryType = 'done'; // 'new' | 're' | 'done'
    let activeHistoryApt = 'ALL';

    const formatDateCompact = (d) => {
        if (!d || d === '-') return '-';
        let clean = String(d).replace(/-/g, '.').trim();
        if (clean.startsWith('20')) {
            clean = clean.substring(2);
        }
        return clean;
    };

    const renderHistoryModal = () => {
        if (!historyTableBody) return;
        const rawList = listingsHistory[currentHistoryType] || [];
        const searchTerm = (historySearchInput?.value || '').trim().toLowerCase();
        
        let filtered = rawList.filter(item => {
            if (activeHistoryApt !== 'ALL' && item.complex_name !== activeHistoryApt) return false;
            if (searchTerm) {
                const str = `${item.event_date || item.done_date || ''} ${item.complex_name || ''} ${item.dong || ''} ${item.floor || ''} ${item.price || ''} ${item.area || ''} ${item.reg_date || ''}`.toLowerCase();
                if (!str.includes(searchTerm)) return false;
            }
            return true;
        });

        // Sort: event_date descending (newest first), then price descending
        filtered.sort((a, b) => {
            const dateA = a.event_date || a.done_date || '';
            const dateB = b.event_date || b.done_date || '';
            if (dateA !== dateB) return dateB.localeCompare(dateA);
            return (b.price_val || 0) - (a.price_val || 0);
        });

        if (historyTotalBadge) {
            historyTotalBadge.textContent = `${filtered.length}건`;
        }

        historyTableBody.innerHTML = '';
        if (filtered.length === 0) {
            historyTableBody.innerHTML = `
                <tr>
                    <td colspan="5" style="text-align: center; padding: 3rem 1rem; color: #94a3b8; font-size: 1rem;">
                        선택된 단지 또는 검색 조건에 일치하는 이력이 없습니다.
                    </td>
                </tr>
            `;
            return;
        }

        const priceColor = currentHistoryType === 'new' ? '#34d399' : (currentHistoryType === 're' ? '#fbbf24' : '#c084fc');

        filtered.forEach(item => {
            const tr = document.createElement('tr');
            const articleLink = item.article_no ? `https://m.land.naver.com/article/info/${item.article_no}` : '#';
            const eventDate = formatDateCompact(item.event_date || item.done_date || '-');
            const regDate = formatDateCompact(item.reg_date || '-');
            
            let priceHtml = `<span class="history-price-val" style="color: ${priceColor};">${item.price}</span>`;
            if (item.prev_price && currentHistoryType === 're') {
                const isDown = item.price_diff < 0;
                const diffMan = Math.abs(item.price_diff) / 10000;
                const diffBadge = isDown
                    ? `<span style="font-size: 0.7rem; color: #38bdf8; background: rgba(56, 189, 248, 0.15); padding: 1px 3px; border-radius: 3px; margin-left: 3px; font-weight: 600;">▼${diffMan}만</span>`
                    : `<span style="font-size: 0.7rem; color: #f87171; background: rgba(248, 113, 113, 0.15); padding: 1px 3px; border-radius: 3px; margin-left: 3px; font-weight: 600;">▲${diffMan}만</span>`;
                priceHtml = `<span style="display: inline-flex; align-items: center; justify-content: flex-end; white-space: nowrap;">${priceHtml}${diffBadge}</span>`;
            }

            tr.innerHTML = `
                <td style="text-align: center; padding: 0.6rem 0.25rem;"><span class="done-date-badge">${eventDate}</span></td>
                <td style="text-align: left; padding: 0.6rem 0.25rem; font-weight: 600;">
                    <a href="${articleLink}" target="_blank" rel="noopener" style="color: #60a5fa; text-decoration: none; white-space: nowrap;">
                        ${item.dong || '-'} ↗
                    </a>
                </td>
                <td style="text-align: center; padding: 0.6rem 0.25rem; color: #cbd5e1;">${item.floor || '-'}</td>
                <td style="text-align: right; padding: 0.6rem 0.25rem;">${priceHtml}</td>
                <td style="text-align: center; padding: 0.6rem 0.25rem; color: #64748b; font-size: 0.78rem;">${regDate}</td>
            `;
            historyTableBody.appendChild(tr);
        });

    };

    const openHistoryModal = (type) => {
        currentHistoryType = type;
        if (!historyModal) return;

        // Match current active apartment filter on main screen if selected
        const activeMainBtn = document.querySelector('.filter-btn.active');
        activeHistoryApt = (activeMainBtn && activeMainBtn.dataset.apt) ? activeMainBtn.dataset.apt : 'ALL';

        historyAptFilters.forEach(btn => {
            if (btn.dataset.apt === activeHistoryApt) {
                btn.classList.add('active');
            } else {
                btn.classList.remove('active');
            }
        });

        if (historySearchInput) historySearchInput.value = '';

        // Dynamic header setup
        if (type === 'new') {
            if (historyTitleText) historyTitleText.textContent = '✨ 신규 매물 등록 이력';
            if (historyModalSubtitle) historyModalSubtitle.textContent = '과거에 새롭게 등록되었던 매물의 등록일자와 최초 등록 가격을 최신순으로 표시합니다.';
            if (historyTotalBadge) historyTotalBadge.className = 'history-count-badge badge-new';
            if (historyColDate) historyColDate.textContent = '등록일자';
            if (historyColPrice) historyColPrice.textContent = '최초 등록 금액';
        } else if (type === 're') {
            if (historyTitleText) historyTitleText.textContent = '🔄 매물 재등록 및 변동 이력';
            if (historyModalSubtitle) historyModalSubtitle.textContent = '과거 매물 재등록 및 가격 변동(인하/인상) 내역을 최신순으로 표시합니다.';
            if (historyTotalBadge) historyTotalBadge.className = 'history-count-badge badge-re';
            if (historyColDate) historyColDate.textContent = '변동일자';
            if (historyColPrice) historyColPrice.textContent = '변동 금액';
        } else {
            if (historyTitleText) historyTitleText.textContent = '📋 거래 완료 내역';
            if (historyModalSubtitle) historyModalSubtitle.textContent = '어제부터 시작하여 이전에 거래 완료된 매물의 날짜와 금액을 최신순으로 표시합니다.';
            if (historyTotalBadge) historyTotalBadge.className = 'history-count-badge badge-done';
            if (historyColDate) historyColDate.textContent = '완료일자';
            if (historyColPrice) historyColPrice.textContent = '거래 완료 금액';
        }

        historyModal.style.display = 'flex';
        pushModalHistory('history');
        renderHistoryModal();
    };

    // Click & Touch listeners for summary cards
    cardNewBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        openHistoryModal('new');
    });
    cardReBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        openHistoryModal('re');
    });
    cardDoneBtn?.addEventListener('click', (e) => {
        e.stopPropagation();
        openHistoryModal('done');
    });

    [cardNewBtn, cardReBtn, cardDoneBtn].forEach(card => {
        card?.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                card.click();
            }
        });
    });

    closeHistoryBtn?.addEventListener('click', () => {
        closeModalSafely(historyModal);
    });

    historyModal?.addEventListener('click', (e) => {
        if (e.target === historyModal) closeModalSafely(historyModal);
    });

    historyAptFilters.forEach(btn => {
        btn.addEventListener('click', (e) => {
            historyAptFilters.forEach(b => b.classList.remove('active'));
            e.currentTarget.classList.add('active');
            activeHistoryApt = e.currentTarget.dataset.apt;
            renderHistoryModal();
        });
    });

    historySearchInput?.addEventListener('input', () => {
        renderHistoryModal();
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
