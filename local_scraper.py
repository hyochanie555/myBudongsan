import asyncio
import json
import os
import sys
import datetime
from playwright.async_api import async_playwright
from playwright_stealth import Stealth
import random
import re

# Fix Korean output on Windows terminals
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# --- Configuration ---
TARGETS = [
    {
        "name": "더샵동천포레스트",
        "id": "110798",
        "area_min": 80.0,
        "area_max": 88.0,
        "target_pyeong_names": ["112A", "112B"],
        "target_desc": "84㎡ (34평형)"
    },
    {
        "name": "울산 힐스테이트 강동",
        "id": "109228",
        "area_min": 80.0,
        "area_max": 88.0,
        "target_pyeong_names": ["113A", "113B"],
        "target_desc": "84㎡ (34평형)"
    },
    {
        "name": "한강센트럴자이 1단지",
        "id": "108487",
        "area_min": 84.0,
        "area_max": 86.0,
        "target_pyeong_names": ["112A", "112B", "112C", "113D"],
        "target_desc": "84㎡ (34평형)"
    },
    {
        "name": "선암에코하이츠",
        "id": "106191",
        "area_min": 55.0,
        "area_max": 65.0,
        "target_pyeong_names": ["81A", "81B", "81C"],
        "target_desc": "59㎡ (24평형)"
    }
]

DATA_DIR = "data"
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
RESULTS_FILE = os.path.join(DATA_DIR, "results.json")

def parse_price(p_str):
    """Parses various Korean price strings to Won units."""
    if not p_str or "협의" in p_str: return 0
    try:
        if "~" in p_str:
            p_str = p_str.split("~")[0].strip()
            
        p_str = p_str.replace(",", "").replace(" ", "").replace("매매", "")
        if '억' in p_str:
            parts = p_str.split('억')
            total = int(parts[0] or 0) * 10000
            if len(parts) > 1 and parts[1]:
                rem_str = "".join(filter(str.isdigit, parts[1]))
                if rem_str: total += int(rem_str)
            return total * 10000
        else:
            num_str = "".join(filter(str.isdigit, p_str))
            if num_str: return int(num_str) * 10000 
            return 0
    except:
        return 0

async def minimize_chrome_window(page):
    """
    Chromium 계열에서만: 현재 페이지가 속한 브라우저 창을 '최소화'합니다.
    실패해도 크롤링은 계속 진행되도록 안전 처리합니다.
    """
    try:
        cdp = await page.context.new_cdp_session(page)
        try:
            win = await cdp.send("Browser.getWindowForTarget")
        except Exception:
            tinfo = await cdp.send("Target.getTargetInfo")
            target_id = tinfo["targetInfo"]["targetId"]
            win = await cdp.send("Browser.getWindowForTarget", {"targetId": target_id})

        window_id = win["windowId"]
        await cdp.send("Browser.setWindowBounds", {
            "windowId": window_id,
            "bounds": {"windowState": "minimized"}
        })
    except Exception:
        pass

async def fetch_complex_listings(page, tgt):
    apt_name = tgt["name"]
    complex_id = int(tgt["id"])
    target_desc = tgt.get("target_desc", "")
    target_pyeong_names = tgt.get("target_pyeong_names", [])
    area_min = tgt.get("area_min", 0)
    area_max = tgt.get("area_max", 9999)

    print(f"  📡 Fetching listings for {apt_name} (ID: {complex_id}, 타겟: {target_desc})...")

    # 브라우저 컨텍스트 내에서 단지 내 모든 평형 타입을 검색한 후 평형별로 전수 수집
    api_result = await page.evaluate("""
        async (args) => {
            const { complexId, tpnames, amin, amax } = args;

            // 1. 단지 내 등록된 평형 타입 목록 자동 감지
            let pyeongMeta = {};
            for (let pt = 1; pt <= 15; pt++) {
                try {
                    const resp = await fetch('/front-api/v1/complex/article/list', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            size: 1,
                            complexNumber: complexId,
                            tradeTypes: ['A1'],
                            pyeongTypes: [String(pt)],
                            dongNumbers: [],
                            userChannelType: 'PC',
                            articleSortType: 'RANKING_DESC',
                            lastInfo: []
                        })
                    });
                    const d = await resp.json();
                    if (d.isSuccess && d.result && d.result.totalCount > 0) {
                        const first = d.result.list?.[0];
                        const space = first?.representativeArticleInfo?.spaceInfo;
                        const sname = space?.supplySpaceName || '';
                        const excl = parseFloat(space?.exclusiveSpace || 0);
                        const supply = parseFloat(space?.supplySpace || 0);
                        
                        const isTarget = (tpnames.length > 0 && tpnames.includes(sname)) || (amin <= excl && excl <= amax);
                        pyeongMeta[String(pt)] = {
                            ptId: String(pt),
                            name: sname,
                            supply: supply,
                            exclusive: excl,
                            totalCount: d.result.totalCount,
                            isTarget: isTarget
                        };
                    }
                } catch(e) {}
            }

            // 2. 평형별로 페이지네이션을 순회하여 매물 누락 0건으로 수집
            let allItems = [];
            let seen = new Set();
            let pyeongStats = {};

            for (const [ptId, meta] of Object.entries(pyeongMeta)) {
                let lastInfo = [];
                let hasNext = true;
                let pageCount = 0;
                let ptItems = [];
                let karCount = 0;

                while (hasNext && pageCount < 20) {
                    pageCount++;
                    const payload = {
                        size: 30,
                        complexNumber: complexId,
                        tradeTypes: ['A1'],
                        pyeongTypes: [ptId],
                        dongNumbers: [],
                        userChannelType: 'PC',
                        articleSortType: 'RANKING_DESC',
                        lastInfo: lastInfo
                    };
                    const resp = await fetch('/front-api/v1/complex/article/list', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(payload)
                    });
                    const d = await resp.json();
                    if (!d.isSuccess || !d.result) break;
                    const list = d.result.list || [];
                    for (const it of list) {
                        const id = String(it.representativeArticleInfo?.articleNumber || '');
                        if (id && !seen.has(id)) {
                            seen.add(id);
                            ptItems.push(it);
                            allItems.push(it);

                            const info = it.representativeArticleInfo || {};
                            const v_info = info.verificationInfo || {};
                            const broker_info = info.brokerInfo || {};
                            const cp_name = info.cpName || '';
                            const brokerage_name = broker_info.brokerageName || '';
                            const cp_id = broker_info.cpId || '';
                            const is_assoc = v_info.isAssociationArticle === true;
                            if (cp_name.includes('공인중개사협회') || brokerage_name.includes('공인중개사협회') || cp_id === 'kar' || is_assoc) {
                                karCount++;
                            }
                        }
                    }
                    hasNext = d.result.hasNextPage === true;
                    lastInfo = d.result.lastInfo || [];
                    if (list.length === 0) break;
                }

                const pKey = `${meta.name} (공급 ${meta.supply}㎡ / 전용 ${meta.exclusive}㎡)`;
                pyeongStats[pKey] = {
                    ptId: ptId,
                    name: meta.name,
                    supply: meta.supply,
                    exclusive: meta.exclusive,
                    total: ptItems.length,
                    kar: karCount,
                    non_kar: ptItems.length - karCount,
                    isTarget: meta.isTarget
                };
            }

            return { success: true, count: allItems.length, items: allItems, pyeongStats: pyeongStats };
        }
    """, {'complexId': complex_id, 'tpnames': target_pyeong_names, 'amin': area_min, 'amax': area_max})

    if not api_result.get("success") and not api_result.get("items"):
        print(f"  ❌ Failed to fetch {apt_name}: {api_result.get('error')}")
        return {}

    captured_data = api_result.get("items", [])
    pyeong_stats = api_result.get("pyeongStats", {})
    print(f"    ✅ Captured {len(captured_data)} raw items from API.")

    listings = {}

    for item in captured_data:
        try:
            info = item.get("representativeArticleInfo", {})
            article_no = str(info.get("articleNumber"))
            if not article_no: continue
            
            dup_info = item.get("duplicatedArticleInfo", {})
            group_count = dup_info.get("realtorCount") or dup_info.get("articleCount") or len(dup_info.get("articleInfoList", [])) or 1
            
            dong = info.get("dongName") or ""
            if not dong.endswith("동") and dong: dong += "동"
            
            v_info = info.get("verificationInfo", {})
            price_info = info.get("priceInfo", {})
            dp = int(price_info.get("dealPrice") or 0)
            
            if dp > 0:
                if dp < 5000000: price_val = dp * 10000
                else: price_val = dp
            else: 
                price_val = parse_price(price_info.get("formattedPrice"))
            
            if price_val > 0:
                price_text = f"{price_val // 100000000}억"
                rem = (price_val % 100000000) // 10000
                if rem > 0: price_text += f" {rem:,}"
            else: 
                continue
            
            space = info.get("spaceInfo", {})
            area1 = float(space.get("supplySpace") or 0)
            area2 = float(space.get("exclusiveSpace") or 0)
            area_type = space.get("supplySpaceName") or ""
            
            floor = info.get("articleDetail", {}).get("floorInfo") or ""
            cp_name = info.get("cpName") or ""
            broker_info = info.get("brokerInfo", {})
            brokerage_name = broker_info.get("brokerageName") or ""
            cp_id = broker_info.get("cpId") or ""
            is_assoc = v_info.get("isAssociationArticle") == True
            
            # 🏢 [공인중개사협회 (KAR) 매물 식별]
            is_kar = ("공인중개사협회" in cp_name or "공인중개사협회" in brokerage_name or cp_id == "kar" or is_assoc)

            # 📏 [평수/면적 일치 판정]
            is_target_pyeong = False
            if target_pyeong_names:
                if area_type in target_pyeong_names or (area_min <= area2 <= area_max):
                    is_target_pyeong = True
            else:
                if area_min <= area2 <= area_max:
                    is_target_pyeong = True

            # 🎯 타겟 평수이고 공인중개사협회(KAR) 매물이 아닌 건만 수집
            if is_target_pyeong:
                if is_kar:
                    continue

                raw_date = v_info.get("articleConfirmDate") or info.get("confirmDate") or info.get("registerDate") or "최근"
                if "-" in raw_date:
                    raw_date = raw_date.replace("-", ".")

                unit_hash = f"NV_{article_no}" 
                
                listings[article_no] = {
                    'article_no': article_no,
                    'complex_name': apt_name,
                    'dong': dong,
                    'floor': floor,
                    'price': price_text,
                    'price_val': price_val, 
                    'area': f"{area_type} / {area2}㎡",
                    'reg_date': raw_date,
                    'cp_name': cp_name or broker_info.get("brokerName") or "",
                    'unit_hash': unit_hash,
                    'count': group_count
                }
        except: 
            continue
            
    print(f"    📐 [평형별 수집 및 필터 상세]:")
    for pk, pdata in sorted(pyeong_stats.items(), key=lambda x: x[1]["supply"]):
        tag = "✅ 타겟 포함" if pdata["isTarget"] else "❌ 비타겟 제외"
        adopted = f"-> {pdata['non_kar']}개 채택" if pdata["isTarget"] else ""
        print(f"       • {pk}: 원본 {pdata['total']}개 (일반 {pdata['non_kar']}, 협회KAR {pdata['kar']}) | {tag} {adopted}")

    print(f"    📊 최종 필터링: {apt_name} ({target_desc}) 총 {len(listings)}개 매물 수집 완료.")
    return listings

def get_prop_hash(data):
    """Generates a physical property hash based on core attributes to detect re-registered items."""
    return f"{data.get('complex_name', '')}_{data.get('dong', '')}_{data.get('floor', '')}_{data.get('price_val', 0)}_{data.get('area', '')}"

def group_listings(listings_dict):
    """Groups multiple article_nos into unique properties (trusting Naver's grouping)."""
    groups = {}
    for no, data in listings_dict.items():
        uh = data['unit_hash']
        if uh not in groups:
            groups[uh] = data.copy()
            groups[uh]['ids'] = [no]
            groups[uh]['count'] = data.get('count', 1)
        else:
            groups[uh]['ids'].append(no)
            groups[uh]['count'] += data.get('count', 1)
    return groups

async def _run_and_process_listings(page, TARGETS, reference_listings, now_kst, history):
    all_today_articles = {}
    for tgt in TARGETS:
        print(f"\n[TARGET] {tgt['name']} 크롤링 시작...")
        
        # 🔁 [RETRY LOOP] Try up to 3 times for each complex
        results = {}
        for attempt in range(1, 4):
            results = await fetch_complex_listings(page, tgt)
            if results and len(results) > 0:
                break
            
            if attempt < 3:
                wait_retry = attempt * 3
                print(f"  ⚠️ Attempt {attempt} failed (0 listings). Retrying in {wait_retry}s...")
                await asyncio.sleep(wait_retry)
            else:
                print(f"  ❌ Max retries reached for {tgt['name']}.")
        
        all_today_articles.update(results)
        
        wait_time = random.uniform(0.5, 1.2)
        await asyncio.sleep(wait_time)
        
    if not all_today_articles:
        print("\n⚠️ 수집된 데이터가 없습니다.")
        return {}, {}, {}, {}, {}

    # Grouping
    today_groups = group_listings(all_today_articles)
    ref_groups = group_listings(reference_listings)

    # Migration for list to dict if necessary
    hist_hashes_raw = history.get("historical_hashes", {})
    hist_props_raw = history.get("historical_props", {})
    hist_hashes = {h: now_kst.strftime("%Y-%m-%d") for h in hist_hashes_raw} if isinstance(hist_hashes_raw, list) else hist_hashes_raw
    hist_props = {p: now_kst.strftime("%Y-%m-%d") for p in hist_props_raw} if isinstance(hist_props_raw, list) else hist_props_raw

    return today_groups, all_today_articles, ref_groups, hist_hashes, hist_props

async def main():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    history = {"last_day_listings": {}, "historical_articles": [], "historical_hashes": {}, "historical_props": {}, "last_ref_date": "", "reference_listings": {}}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                history = json.load(f)
            except: pass
            
    prev_listings = history.get("last_day_listings", {})
    
    # Timezone handling (KST)
    now_kst = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)
    current_date = now_kst.strftime("%Y-%m-%d")

    last_ref_date = history.get("last_ref_date", "")
    
    if current_date != last_ref_date:
        print(f"🌞 [SYSTEM] New Date ({current_date}). Setting baseline...")
        reference_listings = prev_listings.copy()
        history["last_ref_date"] = current_date
        history["reference_listings"] = reference_listings
    else:
        reference_listings = history.get("reference_listings", prev_listings)

    max_overall_retries = 3
    overall_attempt = 0
    
    today_groups = {}
    all_today_articles = {}
    ref_groups = {}
    hist_hashes = {}
    hist_props = {}

    while overall_attempt < max_overall_retries:
        print(f"\n--- 전체 크롤링 시도 {overall_attempt + 1}/{max_overall_retries} ---")
        async with async_playwright() as p:
            print("🚀 Starting scraper... (Window will be automatically minimized)")
            browser = await p.chromium.launch(headless=False, args=["--start-minimized"])
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )
            page = await context.new_page()
            await Stealth().apply_stealth_async(page)
            await minimize_chrome_window(page)

            print("  🌐 Initializing session on https://fin.land.naver.com...")
            await page.goto("https://fin.land.naver.com", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2)
            
            today_groups, all_today_articles, ref_groups, hist_hashes, hist_props = await _run_and_process_listings(page, TARGETS, reference_listings, now_kst, history)
            
            await browser.close()

        prev_count = len(group_listings(reference_listings))
        today_count = len(today_groups)

        if prev_count > 0 and today_count < 0.7 * prev_count:
            print(f"  ⚠️ 오늘 수집된 매물({today_count}개)이 지난번({prev_count}개)의 70% 미만입니다. 재시도합니다...")
            overall_attempt += 1
            await asyncio.sleep(10)
        else:
            print(f"  ✅ 크롤링 성공 또는 재시도 조건 미달성. 매물 수: {today_count}개 (이전: {prev_count}개)")
            break
    
    if overall_attempt == max_overall_retries and (prev_count > 0 and today_count < 0.7 * prev_count):
        print("\n❌ 최대 재시도 횟수에 도달했습니다. 크롤링이 제대로 완료되지 않았을 수 있습니다.")
        return

    if not all_today_articles:
        print("\n⚠️ 수집된 데이터가 없습니다.")
        return

    # Grouping
    ref_groups = group_listings(reference_listings)
    
    results = []
    new_count, re_count, del_count = 0, 0, 0
    
    processed_today = set()
    replaced_ref_uhs = set()
    
    # Pass 1: exact matches (유지)
    for uh, data in today_groups.items():
        if uh in ref_groups:
            data['status'] = "유지"
            results.append(data)
            processed_today.add(uh)
            hist_hashes[uh] = current_date
            hist_props[get_prop_hash(data)] = current_date

    # Build maps for remaining ref_groups
    ref_leftovers = {uh: data for uh, data in ref_groups.items() if uh not in today_groups}
    ref_prop_map = {get_prop_hash(data): uh for uh, data in ref_leftovers.items()}
    
    # Pass 2: remaining in today_groups (신규 or 재등록)
    for uh, data in today_groups.items():
        if uh in processed_today: continue
        
        prop_hash = get_prop_hash(data)
        
        # Check if it physically replaces an item in ref_groups (Deleted then re-registered)
        if prop_hash in ref_prop_map:
            old_uh = ref_prop_map[prop_hash]
            replaced_ref_uhs.add(old_uh)
            data['status'] = "매물 재등록"
            re_count += 1
        else:
            # Check if it existed within the last 7 days
            is_re_reg = False
            for check_dict, key in [(hist_hashes, uh), (hist_props, prop_hash)]:
                if key in check_dict:
                    try:
                        old_date = datetime.datetime.strptime(check_dict[key], "%Y-%m-%d").date()
                        if (now_kst.date() - old_date).days <= 7:
                            is_re_reg = True
                            break
                    except: pass
            
            if is_re_reg:
                data['status'] = "매물 재등록"
                re_count += 1
            else:
                data['status'] = "신규매물"
                new_count += 1
            
        results.append(data)
        hist_hashes[uh] = current_date
        hist_props[prop_hash] = current_date
        
    # Pass 3: Process remaining ref_groups
    expire_count = 0
    for uh, data in ref_leftovers.items():
        if uh not in replaced_ref_uhs:
            status = "거래 완료"
            reg_date_str = data.get("reg_date", "")
            if reg_date_str and "." in reg_date_str:
                try:
                    r_date = datetime.datetime.strptime(reg_date_str, "%Y.%m.%d").date()
                    n_date = now_kst.date()
                    if (n_date - r_date).days >= 30:
                        status = "등록 만료"
                        expire_count += 1
                    else:
                        del_count += 1
                except:
                    del_count += 1
            else:
                del_count += 1
            
            data['status'] = status
            results.append(data)

    print(f"\n📊 Summary (Properties): New: {new_count}, Re-reg: {re_count}, Completed: {del_count}, Expired: {expire_count}")

    results.sort(key=lambda x: (x.get('status') not in ['거래 완료', '등록 만료'], int(x.get('price_val', 0)), str(x.get('dong', '')), str(x.get('floor', ''))))
    
    # Calculate Daily Stats
    daily_stats = history.get("daily_stats", {})
    today_str = now_kst.strftime("%Y-%m-%d")
    for apt in TARGETS:
        apt_name = apt["name"]
        t_count = len([l for l in today_groups.values() if l["complex_name"] == apt_name])
        d_count = len([r for r in results if r["complex_name"] == apt_name and r["status"] == "거래 완료"])
        if apt_name not in daily_stats:
            daily_stats[apt_name] = {}
        daily_stats[apt_name][today_str] = {"total": t_count, "done": d_count}

    output = {
        "last_update": now_kst.strftime("%Y-%m-%d %H:%M"),
        "summary": {apt["name"]: {"prev": len([l for l in ref_groups.values() if l["complex_name"] == apt["name"]]), "today": len([l for l in today_groups.values() if l["complex_name"] == apt["name"]])} for apt in TARGETS},
        "daily_stats": daily_stats,
        "listings": results
    }
    
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    history["daily_stats"] = daily_stats
    history["last_day_listings"] = all_today_articles
    history["historical_hashes"] = hist_hashes
    history["historical_props"] = hist_props
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
        
    print(f"✅ 완료! {len(today_groups)}개 고유 매물 저장됨.")

if __name__ == "__main__":
    asyncio.run(main())
