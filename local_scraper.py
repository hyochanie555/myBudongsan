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
    {"name": "더샵동천포레스트", "id": "110798", "area_min": 80, "area_max": 88}, 
    {"name": "울산 힐스테이트 강동", "id": "109228", "area_min": 80, "area_max": 88}, 
    {"name": "한강센트럴자이 1단지", "id": "108487", "area_min": 84.0, "area_max": 85.5}, # 290건 타겟 정교화
    {"name": "선암에코하이츠", "id": "106191", "area_min": 55, "area_max": 65} 
]

DATA_DIR = "data"
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
RESULTS_FILE = os.path.join(DATA_DIR, "results.json")

def parse_price(p_str):
    """Parses various Korean price strings to Won units."""
    if not p_str or "협의" in p_str: return 0
    try:
        # Handle range format "4억 8,000 ~ 4억 9,000" by taking the lower bound
        if "~" in p_str:
            p_str = p_str.split("~")[0].strip()
            
        p_str = p_str.replace(",", "").replace(" ", "").replace("매매", "")
        # If the string contains '억'
        if '억' in p_str:
            parts = p_str.split('억')
            total = int(parts[0] or 0) * 10000
            if len(parts) > 1 and parts[1]:
                rem_str = "".join(filter(str.isdigit, parts[1]))
                if rem_str: total += int(rem_str)
            return total * 10000
        else:
            # Just numbers likely
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

        # 1) 보통은 인자 없이도 창 ID를 얻을 수 있습니다(세션이 target에 붙어있음).
        try:
            win = await cdp.send("Browser.getWindowForTarget")
        except Exception:
            # 2) 혹시 실패하면 targetId를 명시해서 재시도
            tinfo = await cdp.send("Target.getTargetInfo")
            target_id = tinfo["targetInfo"]["targetId"]
            win = await cdp.send("Browser.getWindowForTarget", {"targetId": target_id})

        window_id = win["windowId"]

        # 창 최소화
        await cdp.send("Browser.setWindowBounds", {
            "windowId": window_id,
            "bounds": {"windowState": "minimized"}
        })

    except Exception:
        # Chromium이 아니거나(webkit/firefox) 회사 정책/환경에 따라 실패할 수 있어요.
        # 실패해도 동작은 계속되게 조용히 무시합니다.
        pass
async def fetch_complex_listings(page, tgt):
    apt_name = tgt["name"]
    complex_id = str(tgt["id"])
    print(f"\n[TARGET] {apt_name} (ID: {complex_id}) 수집 시작...", flush=True)

    all_raw_items = []
    last_info = []
    seed = None
    page_num = 1

    while True:
        payload = {
            "size": 30,
            "complexNumber": complex_id,
            "tradeTypes": ["A1"],  # 매매 전용 필터
            "pyeongTypes": [],
            "dongNumbers": [],
            "userChannelType": "PC",
            "articleSortType": "RANKING_DESC",
            "lastInfo": last_info
        }
        if seed:
            payload["seed"] = seed

        res_data = await page.evaluate("""async (p) => {
            try {
                const res = await fetch('https://fin.land.naver.com/front-api/v1/complex/article/list', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'Accept': 'application/json, text/plain, */*'
                    },
                    body: JSON.stringify(p)
                });
                return await res.json();
            } catch (err) {
                return { error: err.toString() };
            }
        }""", payload)

        if not res_data or not res_data.get("isSuccess"):
            print(f"  ⚠️ API 응답 실패 또는 종료: {res_data}", flush=True)
            break

        result = res_data.get("result", {})
        page_list = result.get("list", [])
        if not page_list:
            break

        all_raw_items.extend(page_list)
        total_cnt = result.get("totalCount", 0)
        print(f"  📥 페이지 {page_num}: +{len(page_list)}건 수집 (누적: {len(all_raw_items)} / 전체 {total_cnt}건)", flush=True)

        last_info = result.get("lastInfo")
        seed = result.get("seed")
        is_more = result.get("isMore")
        has_next = result.get("hasNext")

        page_num += 1

        # 페이지네이션 종료 조건 체크
        if not last_info or len(page_list) < 30 or (is_more is False) or (has_next is False):
            break

        await asyncio.sleep(0.2)

    print(f"  ✅ 원시 데이터 {len(all_raw_items)}개 수집 완료. 필터링 및 파싱 진행 중...", flush=True)

    listings = {}
    for item in all_raw_items:
        try:
            info = item.get("representativeArticleInfo", item)
            article_no = str(info.get("articleNumber", ""))
            if not article_no: continue

            # 중개사 중복 수 (네이버 클러스터링 카운트)
            group_count = item.get("duplicatedArticleInfo", {}).get("articleCount") or 1

            dong = info.get("dongName") or ""
            if not dong.endswith("동") and dong: dong += "동"

            # 가격 파싱 (dealPrice 우선, fallback: formattedPrice)
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

            # 공인중개사협회 매물 필터링
            v_info = info.get("verificationInfo", {})
            is_assoc = v_info.get("isAssociationArticle") == True

            if "공인중개사협회" in cp_name or "공인중개사협회" in brokerage_name or cp_id.lower() == "kar" or is_assoc:
                continue

            # 전용면적 기준 필터링
            if tgt["area_min"] <= area2 <= tgt["area_max"]:
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
                    'cp_name': cp_name or brokerage_name,
                    'unit_hash': unit_hash,
                    'count': group_count
                }
        except Exception:
            continue

    print(f"  🎯 타겟 면적 필터 적용 후 {len(listings)}개 매물 확정.", flush=True)
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
            # [Grouping] Use Naver's defined count if available
            groups[uh]['count'] = data.get('count', 1)
        else:
            groups[uh]['ids'].append(no)
            # Sum counts if somehow they match
            groups[uh]['count'] += data.get('count', 1)
    return groups

async def main():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    history = {"last_day_listings": {}, "historical_articles": [], "historical_hashes": [], "last_ref_date": "", "reference_listings": {}}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                history = json.load(f)
            except: pass
            
    prev_listings = history.get("last_day_listings", {})
    hist_hashes_raw = history.get("historical_hashes", {})
    hist_props_raw = history.get("historical_props", {})
    
    # Timezone handling (KST)
    now_kst = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)
    current_date = now_kst.strftime("%Y-%m-%d")

    # Migration for list to dict if necessary
    hist_hashes = {h: current_date for h in hist_hashes_raw} if isinstance(hist_hashes_raw, list) else hist_hashes_raw
    hist_props = {p: current_date for p in hist_props_raw} if isinstance(hist_props_raw, list) else hist_props_raw
    
    last_ref_date = history.get("last_ref_date", "")
    
    if current_date != last_ref_date:
        print(f"🌞 [SYSTEM] New Date ({current_date}). Setting baseline...", flush=True)
        reference_listings = prev_listings.copy()
        history["last_ref_date"] = current_date
        history["reference_listings"] = reference_listings
    else:
        reference_listings = history.get("reference_listings", prev_listings)

    launch_args = ["--no-sandbox", "--disable-setuid-sandbox", "--disable-dev-shm-usage", "--disable-gpu"]
    is_windows = sys.platform == "win32"
    if is_windows:
        launch_args.append("--start-minimized")

    async with async_playwright() as p:
        print("🚀 Starting scraper...", flush=True)
        browser = await p.chromium.launch(headless=not is_windows, args=launch_args)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = await context.new_page()
        await Stealth().apply_stealth_async(page)

        # 브라우저 창 최소화 (Windows 로컬 실행 시)
        if is_windows:
            await minimize_chrome_window(page)

        # 세션/쿠키 초기화를 위한 네이버 부동산 페이지 접속
        init_url = f"https://fin.land.naver.com/complexes/{TARGETS[0]['id']}?propertyType=APT&tradeType=SALE"
        print(f"🌐 세션 초기화 접속: {init_url}", flush=True)
        try:
            await page.goto(init_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
        except Exception as e:
            print(f"  ⚠️ 세션 초기화 접속 경고: {e}", flush=True)

        all_today_articles = {}
        for tgt in TARGETS:
            results = {}
            for attempt in range(1, 4):
                try:
                    results = await fetch_complex_listings(page, tgt)
                    if results and len(results) > 0:
                        break # Success!
                except Exception as e:
                    print(f"  ⚠️ Attempt {attempt} error: {e}", flush=True)
                
                if attempt < 3:
                    wait_retry = attempt * 3
                    print(f"  ⚠️ Attempt {attempt} failed. Retrying in {wait_retry}s...", flush=True)
                    await asyncio.sleep(wait_retry)
                else:
                    print(f"  ❌ Max retries reached for {tgt['name']}.", flush=True)
            
            all_today_articles.update(results)
            await asyncio.sleep(random.uniform(0.5, 1.0))
            
        await browser.close()

    if not all_today_articles:
        print("\n❌ 수집된 데이터가 없습니다. 스크래퍼 비정상 종료.", flush=True)
        sys.exit(1)

    # Grouping
    today_groups = group_listings(all_today_articles)
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
                except: pass
            
            data['status'] = status
            results.append(data)
            if status == "거래 완료":
                del_count += 1

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

