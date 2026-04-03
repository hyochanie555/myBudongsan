import json
import time
import datetime
from datetime import timezone
import os
import sys
import re
from playwright.sync_api import sync_playwright

# Fix Korean output on Windows terminals
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# --- Configuration ---
TARGETS = [
    {"name": "더샵동천포레스트", "id": "110798", "area_min": 108, "area_max": 115},
    {"name": "울산 힐스테이트 강동", "id": "109228", "area_min": 108, "area_max": 115},
    {"name": "한강센트럴자이 1단지", "id": "108487", "area_min": 108, "area_max": 115},
    {"name": "선암에코하이츠", "id": "106191", "area_min": 75, "area_max": 83}
]

DATA_DIR = "data"
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")
RESULTS_FILE = os.path.join(DATA_DIR, "results.json")

def parse_price(p_str):
    if not p_str: return 0
    try:
        # "매매 9억 3,000" -> "9억3000"
        p_str = p_str.replace(",", "").replace(" ", "").replace("매매", "")
        
        total = 0
        if '억' in p_str:
            parts = p_str.split('억')
            if parts[0]:
                total += int(parts[0]) * 10000
            if len(parts) > 1 and parts[1]:
                digits_only = "".join(filter(str.isdigit, parts[1]))
                if digits_only:
                    total += int(digits_only)
        else:
            digits_only = "".join(filter(str.isdigit, p_str))
            if digits_only:
                total = int(digits_only)
        return total * 10000 # Convert to actual value if needed, but here we just need relative price
    except Exception as e:
        return 0

def fetch_listings():
    current_listings = {}
    
    with sync_playwright() as p:
        # Use a real browser with a realistic user agent
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
            viewport={"width": 1280, "height": 800}
        )
        page = context.new_page()
        
        for i, tgt in enumerate(TARGETS):
            apt_name = tgt["name"]
            complex_id = tgt["id"]
            print(f"\n[TARGET] {apt_name} ({complex_id})", flush=True)
            
            try:
                # 1. Navigate to the complex page
                url = f"https://fin.land.naver.com/complexes/{complex_id}"
                page.goto(url, wait_until="networkidle", timeout=60000)
                time.sleep(3) # Extra wait for lazy loading
                
                # 2. Click the '매물' (Listings) tab if it's not active
                # The page usually defaults to some overview or map. We need the list.
                # Actually, /complexes/{id} often shows the list directly in the sidebar on recent Naver Land.
                
                # Wait for any ArticleCard items to appear
                page.wait_for_selector('li[class*="ArticleCard_item"]', timeout=10000)
                
                # 3. Scrape the DOM
                cards = page.query_selector_all('li[class*="ArticleCard_item"]')
                print(f"  Found {len(cards)} items in DOM.", flush=True)
                
                for card in cards:
                    try:
                        # Article Number (ID)
                        thumb_link = card.query_selector('a[class*="ArticleCard_area-thumbnail"]')
                        if not thumb_link: continue
                        href = thumb_link.get_attribute('href') or ""
                        match = re.search(r'/articles/(\d+)', href)
                        article_no = match.group(1) if match else ""
                        if not article_no: continue
                        
                        # Dong (e.g., "더샵동천포레스트 102동")
                        name_el = card.query_selector('span[class*="ArticleCard_name"]')
                        full_name = name_el.inner_text() if name_el else ""
                        dong = full_name.split(' ')[-1] if ' ' in full_name else full_name
                        
                        # Price (e.g., "매매 9억 3,000")
                        price_el = card.query_selector('span[class*="ArticleCard_price"]')
                        price_text = price_el.inner_text() if price_el else ""
                        if "매매" not in price_text: continue # Skip if not Sale
                        
                        # Area & Floor
                        # In the summary list: li:nth-child(2) is Area, li:nth-child(3) is Floor
                        summary_items = card.query_selector_all('li[class*="ArticleCard_item-summary"]')
                        if len(summary_items) < 3: continue
                        
                        area_text = summary_items[1].inner_text() # e.g., "112A㎡ (전용84A)"
                        floor_text = summary_items[2].inner_text() # e.g., "7/21층"
                        
                        # Extract area numbers for filtering
                        # e.g., "112A㎡ (전용84A)" -> 112, 84
                        areas = re.findall(r'(\d+(?:\.\d+)?)', area_text)
                        if not areas: continue
                        area1 = float(areas[0])
                        area2 = float(areas[1]) if len(areas) > 1 else area1
                        
                        # Filter by area
                        if tgt["area_min"] <= area1 <= tgt["area_max"] or tgt["area_min"] <= area2 <= tgt["area_max"]:
                            # Reg Date (e.g., "확인매물 2026.04.03")
                            date_el = card.query_selector('li[class*="PropertyBadgeList_type-confirmed"]')
                            reg_date = ""
                            if date_el:
                                date_match = re.search(r'(\d{4}\.\d{2}\.\d{2})', date_el.inner_text())
                                if date_match:
                                    reg_date = date_match.group(1)[2:] # "26.04.03"
                            
                            # Price value for sorting
                            price_val = parse_price(price_text)
                            
                            current_listings[article_no] = {
                                'article_no': article_no,
                                'complex_name': apt_name,
                                'dong': dong,
                                'floor': floor_text,
                                'price': price_text,
                                'price_val': price_val,
                                'area': f"{area1}㎡ / {area2}㎡",
                                'reg_date': reg_date,
                                'cp_name': "Naver Land",
                                'unit_hash': article_no 
                            }
                    except Exception as e:
                        continue # Skip individual item error
                        
            except Exception as e:
                print(f"  Error processing {apt_name}: {e}", flush=True)
                continue
                
            # Random wait between targets
            if i < len(TARGETS) - 1:
                time.sleep(5 + (time.time() * 1000 % 5000) / 1000.0)
                
        browser.close()
                
    return current_listings

def main():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    # 1. Load History
    history = {"last_day_listings": {}, "historical_articles": [], "historical_hashes": []}
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
            
    prev_listings = history.get("last_day_listings", {})
    hist_articles = set(history.get("historical_articles", []))
    hist_hashes = set(history.get("historical_hashes", []))
    
    # 2. Scrape Current
    today_listings = fetch_listings()
    today_hashes = set(data['unit_hash'] for no, data in today_listings.items() if data.get('unit_hash'))
    
    results = []
    
    # 3. Compare: Today's listings
    for no, data in today_listings.items():
        status = "유지"
        if no not in prev_listings:
            if no in hist_articles or (data['unit_hash'] and data['unit_hash'] in hist_hashes):
                status = "매물 재등록"
            else:
                status = "신규매물"
        
        data['status'] = status
        results.append(data)
        
    # 4. Compare: Previous listings (to find Completed/Deleted)
    for no, data in prev_listings.items():
        if no not in today_listings:
            # Check if it was replaced (re-registered) in today's set
            unit_hash = data.get('unit_hash')
            if unit_hash and unit_hash in today_hashes:
                continue # Replaced by another article, don't count as complete
                
            data['status'] = "거래 완료"
            results.append(data)
            
    # Safety Check: If results are zero, do not overwrite to avoid blanking out data due to IP blocks
    if not today_listings:
        print("⚠️ Safety check triggered: No listings found.")
        
        # If results.json doesn't exist at all (e.g. after accidental deletion), create a placeholder
        if not os.path.exists(RESULTS_FILE):
            now_kst = (datetime.datetime.now(timezone.utc) + datetime.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
            placeholder = {
                "last_update": now_kst,
                "summary": {tgt["name"]: {"prev": 0, "today": 0} for tgt in TARGETS},
                "listings": [],
                "message": "네이버 차단으로 인해 데이터를 가져오지 못했습니다. 잠시 후 상단 Actions에서 다시 실행해 주세요."
            }
            with open(RESULTS_FILE, "w", encoding="utf-8") as f:
                json.dump(placeholder, f, ensure_ascii=False, indent=2)
            print(f"Created a placeholder {RESULTS_FILE} to prevent UI error.")
            
        print("Not overwriting existing data if it exists.")
        return
            
    # Sort results
    results.sort(key=lambda x: (
        x.get('status') != '거래 완료', 
        int(x.get('price_val', 0)), 
        str(x.get('dong', '')),
        str(x.get('floor', ''))
    ))
    
    # 5. Save Results for Frontend
    now_kst = (datetime.datetime.now(timezone.utc) + datetime.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
    
    summary = {}
    for apt in TARGETS:
        name = apt["name"]
        today_count = len([l for l in today_listings.values() if l["complex_name"] == name])
        prev_count = len([l for l in prev_listings.values() if l["complex_name"] == name])
        summary[name] = {"prev": prev_count, "today": today_count}

    output = {
        "last_update": now_kst,
        "summary": summary,
        "listings": results
    }
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
        
    # 6. Update History
    new_hist_articles = list(hist_articles.union(prev_listings.keys()))
    new_hist_hashes = list(hist_hashes.union(set(d.get('unit_hash') for d in prev_listings.values() if d.get('unit_hash'))))
    
    new_history = {
        "last_day_listings": today_listings,
        "historical_articles": new_hist_articles,
        "historical_hashes": new_hist_hashes
    }
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(new_history, f, ensure_ascii=False, indent=2)
        
    print(f"Done! Updated {len(today_listings)} listings.")

if __name__ == "__main__":
    main()
