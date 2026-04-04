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

async def fetch_complex_listings(context, tgt):
    apt_name = tgt["name"]
    complex_id = tgt["id"]
    # 🌍 브라우저 수사관(Subagent) 성공 환경 복제
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
    page = await context.new_page()
    await page.set_viewport_size({"width": 1920, "height": 1080})
    await Stealth().apply_stealth_async(page)
    
    url = f"https://fin.land.naver.com/complexes/{complex_id}?propertyType=APT&tradeType=SALE"
    
    captured_data = []

    # 🛡️ 응답 가로채기 핸들러
    async def handle_response(response):
        if "/front-api/v1/complex/article/list" in response.url:
            if response.status == 200:
                try:
                    json_data = await response.json()
                    items = json_data.get("result", {}).get("list", [])
                    if items:
                        captured_data.extend(items)
                        print(f"    ✅ Captured {len(items)} items from API.")
                except: pass

    page.on("response", handle_response)
    
    listings = {}
    try:
        print(f"  🌐 Navigating to {url}...")
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # 📶 [STABILITY FIX] Wait for network/UI initialization (important for slow/wireless)
        print("  ⏳ Waiting for page stabilization (5s)...")
        await asyncio.sleep(5)
        
        # Human-like scrolling
        print("  🖱️ Scrolling to mimic human behavior...")
        for _ in range(random.randint(2, 4)):
            await page.mouse.wheel(0, random.randint(300, 600))
            await asyncio.sleep(random.uniform(0.5, 1.5))
        
        await asyncio.sleep(2)
        
        # '매물' 탭 클릭 (JS 강제 클릭 포함)
        tab_selector = 'button[class*="LineTab-module_link"]:has-text("매물")'
        try:
            # 1. 일반 클릭 시도
            await page.wait_for_selector(tab_selector, timeout=8000)
            await asyncio.sleep(random.uniform(1, 2))
            await page.click(tab_selector)
            print("  ✅ Clicked '매물' tab.")
        except:
            # 2. 자바스크립트 강제 클릭 (더 강력함)
            print("  ⚠️ Standard click failed, attempting JS click...")
            await page.evaluate("""
                const btn = Array.from(document.querySelectorAll('button')).find(b => b.innerText.includes('매물'));
                if (btn) btn.click();
            """)
            print("  ✅ Executed JS click on '매물' tab.")

        # ⏳ [ADD] Wait for the first API response before starting scroll
        print("  ⏳ Waiting for initial API response (up to 15s)...")
        for _ in range(15):
            if captured_data: break
            await asyncio.sleep(1)
        
        # [Fallback] If nothing captured, try Tab-Toggling (click another tab, then back to '매물')
        if not captured_data:
            print("  🔄 No API response yet. Attempting Tab-Toggle...")
            await page.evaluate("""
                const tabs = Array.from(document.querySelectorAll('a[role="tab"]'));
                const otherTab = tabs.find(t => !t.innerText.includes('매물'));
                if (otherTab) otherTab.click();
            """)
            await asyncio.sleep(2)
            await page.evaluate("""
                const tabs = Array.from(document.querySelectorAll('a[role="tab"]'));
                const salesTab = tabs.find(t => t.innerText.includes('매물'));
                if (salesTab) salesTab.click();
            """)
            await asyncio.sleep(5)

        # Speed-optimized Deep Scrolling
        print("  🖱️ Scrolling to load articles...")
        last_count = 0
        scroll_attempts = 0
        max_scrolls = 20 # Deeper scroll
        
        while scroll_attempts < max_scrolls:
            await page.keyboard.press("End")
            await asyncio.sleep(0.6) # Extreme speed scroll
            
            current_count = len(captured_data)
            if current_count == last_count:
                # If we already found some items and it's been 3 attempts with no new items, we're likely done
                if current_count > 0 and scroll_attempts >= 3:
                    break
                
                await page.mouse.move(250, 400)
                await page.mouse.wheel(0, 800)
                await asyncio.sleep(0.4)
                scroll_attempts += 1
            else:
                print(f"    📊 Articles: {current_count}...")
                last_count = current_count
                scroll_attempts = 0 
            
            if current_count >= 500: break 

        if not captured_data:
            # Final attempt: Check if we can wait 5 more seconds
            print("  ⏳ Final wait for API (5s)...")
            await asyncio.sleep(5)
            current_count = len(captured_data)

        if not captured_data:
            print(f"  ❌ No API response for {apt_name}.")
            await page.close()
            return {}

        for item in captured_data:
            try:
                info = item.get("representativeArticleInfo", {})
                article_no = str(info.get("articleNumber"))
                if not article_no: continue
                
                # [Grouping] Use Naver's native count (duplicatedArticleInfo.articleCount)
                # This is the most accurate source for the "중개사 X곳" number.
                group_count = item.get("duplicatedArticleInfo", {}).get("articleCount") or 1
                
                dong = info.get("dongName") or ""
                if not dong.endswith("동") and dong: dong += "동"
                
                # 🏷️ [ROBUST PRICE] Use raw numeric dealPrice for 100% accuracy
                v_info = info.get("verificationInfo", {})
                price_info = info.get("priceInfo", {})
                dp = int(price_info.get("dealPrice") or 0)
                
                # Use raw numeric dealPrice if available (standard for Naver)
                if dp > 0:
                    # Naver dealPrice is 10000 based in some versions, or raw Won in others.
                    # Heuristic: If it's like 93000, it's 9억 3000 (Man-won). If it's like 930,000,000 it's Won.
                    if dp < 5000000: price_val = dp * 10000
                    else: price_val = dp
                else: 
                    # Fallback to string parsing if dealPrice is 0
                    price_val = parse_price(price_info.get("formattedPrice"))
                
                # 🏷️ [DISPLAY] Format to "X억 Y,ZZZ"
                if price_val > 0:
                    price_text = f"{price_val // 100000000}억"
                    rem = (price_val % 100000000) // 10000
                    if rem > 0: price_text += f" {rem:,}"
                else:
                    # 🚫 [UPDATE] Skip items with no price (solves 0-price and count mismatch issues)
                    continue
                
                space = info.get("spaceInfo", {})
                area1, area2 = float(space.get("supplySpace") or 0), float(space.get("exclusiveSpace") or 0)
                # 🏷️ [TYPE FIX] Get supplySpaceName (e.g., 112A)
                area_type = space.get("supplySpaceName") or ""
                
                floor = info.get("articleDetail", {}).get("floorInfo") or ""

                cp_name = info.get("cpName") or ""
                broker_info = info.get("brokerInfo", {})
                brokerage_name = broker_info.get("brokerageName") or ""
                cp_id = broker_info.get("cpId") or ""
                
                # 🏷️ [EXTRA FILTER] Check for Association (KAR) via cpId or verification flag
                v_info = info.get("verificationInfo", {})
                is_assoc = v_info.get("isAssociationArticle") == True
                
                # 🚫 [UPDATE] 공인중개사협회 (cpId: "kar") 매물 제외 
                # These are often duplicates that Naver fails to cluster properly.
                if "공인중개사협회" in cp_name or "공인중개사협회" in brokerage_name or cp_id == "kar" or is_assoc:
                    continue

                # 📏 [STRICT FILTER] Use Exclusive Area (area2) as the anchor (Standard 84㎡ or 59㎡)
                if tgt["area_min"] <= area2 <= tgt["area_max"]:
                    # 🗓️ [DATE FIX] Use articleConfirmDate for precise registration (YYYY.MM.DD)
                    # This is the "확인매물 2026.04.04" date user requested.
                    raw_date = v_info.get("articleConfirmDate") or info.get("confirmDate") or info.get("registerDate") or "최근"
                    if "-" in raw_date:
                        # Convert YYYY-MM-DD to YYYY.MM.DD
                        raw_date = raw_date.replace("-", ".")

                    # [Hash] Use Naver's clustering logic (Article No is unique for the card/group)
                    # This fulfills "Don't organize it yourself" requirement.
                    unit_hash = f"NV_{article_no}" 
                    
                    listings[article_no] = {
                        'article_no': article_no,
                        'complex_name': apt_name,
                        'dong': dong,
                        'floor': floor,
                        'price': price_text, # (매매) 텍스트 삭제
                        'price_val': price_val, 
                        'area': f"{area_type} / {area2}㎡",
                        'reg_date': raw_date,
                        'cp_name': cp_name,
                        'unit_hash': unit_hash,
                        'count': group_count
                    }
            except: continue
                
    except Exception as e:
        print(f"  Error: {e}")
    finally:
        await page.close()
        
    return listings

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
    hist_hashes = set(history.get("historical_hashes", []))
    
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

    async with async_playwright() as p:
        print("🚀 Starting scraper... (Window will be automatically minimized)")
        browser = await p.chromium.launch(headless=False, args=["--start-minimized"])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        
        all_today_articles = {}
        for tgt in TARGETS:
            print(f"\n[TARGET] {tgt['name']} 크롤링 시작...")
            
            # 🔁 [RETRY LOOP] Try up to 3 times for each complex
            results = {}
            for attempt in range(1, 4):
                results = await fetch_complex_listings(context, tgt)
                if results and len(results) > 0:
                    break # Success!
                
                if attempt < 3:
                    wait_retry = attempt * 5
                    print(f"  ⚠️ Attempt {attempt} failed (0 listings). Retrying in {wait_retry}s...")
                    await asyncio.sleep(wait_retry)
                else:
                    print(f"  ❌ Max retries reached for {tgt['name']}.")
            
            all_today_articles.update(results)
            
            wait_time = random.randint(1, 2)
            print(f"  ☕ {wait_time}s wait...")
            await asyncio.sleep(wait_time)
            
        await browser.close()

    if not all_today_articles:
        print("\n⚠️ 수집된 데이터가 없습니다.")
        return

    # Grouping
    today_groups = group_listings(all_today_articles)
    ref_groups = group_listings(reference_listings)
    
    results = []
    new_count, re_count, del_count = 0, 0, 0
    
    for uh, data in today_groups.items():
        status = "유지"
        if uh not in ref_groups:
            if uh in hist_hashes:
                status = "매물 재등록"
                re_count += 1
            else:
                status = "신규매물"
                new_count += 1
        
        data['status'] = status
        results.append(data)
        hist_hashes.add(uh)
            
    for uh, data in ref_groups.items():
        if uh not in today_groups:
            data['status'] = "거래 완료"
            results.append(data)
            del_count += 1

    print(f"\n📊 Summary (Properties): New: {new_count}, Re-reg: {re_count}, Completed: {del_count}")

    results.sort(key=lambda x: (x.get('status') != '거래 완료', int(x.get('price_val', 0)), str(x.get('dong', '')), str(x.get('floor', ''))))
    
    output = {
        "last_update": now_kst.strftime("%Y-%m-%d %H:%M"),
        "summary": {apt["name"]: {"prev": len([l for l in ref_groups.values() if l["complex_name"] == apt["name"]]), "today": len([l for l in today_groups.values() if l["complex_name"] == apt["name"]])} for apt in TARGETS},
        "listings": results
    }
    
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    history["last_day_listings"] = all_today_articles
    history["historical_hashes"] = list(hist_hashes)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
        
    print(f"✅ 완료! {len(today_groups)}개 고유 매물 저장됨.")

if __name__ == "__main__":
    asyncio.run(main())
