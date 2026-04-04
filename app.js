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

            // Show Last Update Time with Stale Warning
            if (responseData.last_update) {
                const lastUpdateEl = document.getElementById('last-update');
                const updateTime = new Date(responseData.last_update.replace(/-/g, '/')); // Compatibility
                const now = new Date();
                const diffHours = (now - updateTime) / (1000 * 60 * 60);

                if (lastUpdateEl) {
                    lastUpdateEl.textContent = `최근 갱신: ${responseData.last_update}`;
                    if (diffHours > 24) {
                        lastUpdateEl.innerHTML += ` <span style="color: #f87171; font-weight: bold; margin-left: 10px;">⚠️ 데이터가 하루 이상 지났습니다. (크롤러 확인 필요)</span>`;
                    }
                }
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
            // 1. Status: '거래 완료' (Completed) to the top
            const statusA = (a.status || "").trim();
            const statusB = (b.status || "").trim();
            if (statusA === '거래 완료' && statusB !== '거래 완료') return -1;
            if (statusA !== '거래 완료' && statusB === '거래 완료') return 1;

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
                } else if (status === '매물 재등록') {
                    countRe++;
                    countActive++;
                } else if (status === '유지') {
                    countActive++;
                } else if (status === '거래 완료') {
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
            if (showChangesOnly && status === '유지') {
                return; // Hide unchanged if checked
            }

            const tr = document.createElement('tr');
            const badgeClass = `status-${status.replace(/\s+/g, '')}`;
            
            // Show grouped count if > 1
            const countSuffix = item.count > 1 ? ` <span style="color: #94a3b8; font-size: 0.85em; font-weight: normal;">(${item.count}건)</span>` : '';
            
            // Link to the first article if available
            const articleLink = item.article_no ? `https://m.land.naver.com/article/info/${item.article_no}` : '#';

            tr.innerHTML = `
                <td data-label="단지명"><strong>${item.complex_name}</strong></td>
                <td data-label="상태" class="mobile-status-container"><span class="status-badge ${badgeClass}">${status}</span></td>
                <td data-label="동" class="mobile-row-1-left">
                    <a href="${articleLink}" target="_blank" style="color: inherit; text-decoration: none;">
                        <strong>${item.dong}${countSuffix}</strong>
                    </a>
                </td>
                <td data-label="층" class="mobile-row-1-left">${item.floor || ''}</td>
                <td data-label="면적" class="mobile-row-1-left">${item.area || ''}</td>
                <td data-label="가격" class="mobile-row-2-right"><strong>${item.price}</strong></td>
                <td data-label="등록일" class="mobile-row-2-left">${item.reg_date || '-'}</td>
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

    const scrapeData = async () => {
        try {
            scrapeBtn.textContent = '확인 중...';
            scrapeBtn.disabled = true;
            
            const message = "데이터는 GitHub Actions를 통해 오전 11시, 오후 4시에 자동으로 갱신됩니다.\n\n" +
                            "지금 즉시 갱신하고 싶으시면 GitHub 저장소의 'Actions' 탭에서 'Scrape Real Estate Listings' 워크플로우를 수동으로 실행해 주세요.\n\n" +
                            "페이지 상단의 '새로고침' 버튼은 이미 저장된 최신 데이터를 다시 불러오는 기능입니다.";
            alert(message);
        } catch (error) {
            console.error('Scrape error:', error);
        } finally {
            scrapeBtn.textContent = '데이터 갱신 안내';
            scrapeBtn.disabled = false;
        }
    };

    // Setup listeners
    refreshBtn.addEventListener('click', loadData);
    scrapeBtn.addEventListener('click', scrapeData);
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
