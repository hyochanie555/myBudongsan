import json
import time
import datetime
from datetime import timezone
import os
import sys
import re
import requests

# Fix Korean output on Windows terminals
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# --- Configuration ---
SCRAPERAPI_KEY = os.environ.get("SCRAPERAPI_KEY") 
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
    
    if not SCRAPERAPI_KEY:
        print("❌ SCRAPERAPI_KEY not found in environment variables.", flush=True)
        return current_listings

    for i, tgt in enumerate(TARGETS):
        apt_name = tgt["name"]
        complex_id = tgt["id"]
        print(f"\n[TARGET] {apt_name} ({complex_id})", flush=True)
        
        try:
            # 1. Definitive Bypass Strategy: Mobile Web Rendering with Custom Headers
            # Adding a real Mobile User-Agent and setting keep_headers: 'true'
            # makes our request indistinguishable from a legitimate mobile device.
            target_url = f"https://m.land.naver.com/complex/info/{complex_id}?tab=article"
            proxy_url = "http://api.scraperapi.com"
            
            # Use a robust mobile User-Agent (iPhone/iOS)
            custom_headers = {
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7'
            }
            
            params = {
                'api_key': SCRAPERAPI_KEY,
                'url': target_url,
                'render': 'true',         # Cloud-based browser rendering
                'premium': 'true',        # High-quality residential proxies
                'country_code': 'kr',     # South Korean targeting
                'keep_headers': 'true',   # CRITICAL: Forward our custom User-Agent to Naver
                'wait_for_selector': 'li[class*="ArticleCard_item__"]' 
            }
            
            print(f"  Requesting via ScraperAPI (Stealth Rendering Mode)...", flush=True)
            response = requests.get(proxy_url, params=params, headers=custom_headers, timeout=180)
            
            if response.status_code != 200:
                print(f"  Proxy error ({response.status_code}): {response.text[:200]}", flush=True)
                continue
                
            html = response.text
            
            # 2. Parse the rendered HTML DOM
            # The mobile UI uses deep components; we target the ArticleCard items
            items = re.findall(r'<li[^>]*class="[^"]*ArticleCard_item__[^"]*"[^>]*>(.*?)</li>', html, re.DOTALL)
            print(f"  Found {len(items)} items in rendered DOM.", flush=True)
            
            for item_html in items:
                try:
                    # Article ID
                    match_id = re.search(r'articles/(\d+)', item_html)
                    article_no = match_id.group(1) if match_id else ""
                    if not article_no: continue
                    
                    # Dong
                    match_dong = re.search(r'<span[^>]*class="[^"]*ArticleCard_name__[^"]*"[^>]*>(.*?)</span>', item_html)
                    full_name = match_dong.group(1) if match_dong else ""
                    dong = full_name.split(' ')[-1] if ' ' in full_name else full_name
                    
                    # Price
                    match_price = re.search(r'<span[^>]*class="[^"]*ArticleCard_price__[^"]*"[^>]*>(.*?)</span>', item_html)
                    price_text = match_price.group(1) if match_price else ""
                    if "매매" not in price_text: continue
                    
                    # Summary (Area, Floor) - Mobile structure
                    match_summaries = re.findall(r'<li[^>]*class="[^"]*ArticleCard_item-summary__[^"]*"[^>]*>(.*?)</li>', item_html)
                    if len(match_summaries) < 3: continue
                    area_text = match_summaries[1]
                    floor_text = match_summaries[2]
                    
                    areas = re.findall(r'(\d+(?:\.\d+)?)', area_text)
                    if not areas: continue
                    area1 = float(areas[0])
                    area2 = float(areas[1]) if len(areas) > 1 else area1
                    
                    if tgt["area_min"] <= area1 <= tgt["area_max"] or tgt["area_min"] <= area2 <= tgt["area_max"]:
                        # Reg Date from mobile confirm label
                        match_date = re.search(r'확인매물 (\d{4}\.\d{2}\.\d{2})', item_html)
                        reg_date = match_date.group(1)[2:] if match_date else ""
                        
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
                            'cp_name': "Naver Mobile",
                            'unit_hash': article_no 
                        }
                except Exception as e:
                    continue
                    
        except Exception as e:
            print(f"  Error processing {apt_name}: {e}", flush=True)
            continue
            
    return current_listings

def main():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    # 1. Load History & Determine Daily Reference
    history = {
        "last_day_listings": {}, 
        "historical_articles": [], 
        "historical_hashes": [],
        "last_ref_date": "",
        "reference_listings": {}
    }
    
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            history = json.load(f)
            
    prev_listings = history.get("last_day_listings", {}) # Final state of the last run
    hist_articles = set(history.get("historical_articles", []))
    hist_hashes = set(history.get("historical_hashes", []))
    
    # [Day-based Comparison Mode]
    now_kst_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)
    current_date = now_kst_dt.strftime("%Y-%m-%d")
    last_ref_date = history.get("last_ref_date", "")
    
    # If it's a new day, we set a new baseline for "Today's Changes"
    if current_date != last_ref_date:
        print(f"🌞 [SYSTEM] New Date detected ({current_date}). Setting morning baseline...", flush=True)
        # The baseline for today's comparison is what we saw at the end of yesterday
        reference_listings = prev_listings.copy()
        history["last_ref_date"] = current_date
        history["reference_listings"] = reference_listings
    else:
        # Throughout the day, we keep comparing against the same fixed morning baseline
        reference_listings = history.get("reference_listings", prev_listings)
        print(f"🕒 [SYSTEM] Day-based mode: Comparing to {current_date} baseline.", flush=True)

    # 2. Scrape Current
    today_listings = fetch_listings()
    if not today_listings:
        print("⚠️  No listings scraped. Safety check: Keeping existing results to avoid blanking out UI.", flush=True)
        return

    today_hashes = set(data['unit_hash'] for no, data in today_listings.items() if data.get('unit_hash'))
    results = []
    
    # 3. Compare with Morning Baseline (Cumulative Today's Changes)
    new_count = 0
    mod_count = 0
    del_count = 0
    
    for no, data in today_listings.items():
        status = "유지"
        # If it wasn't there this morning, it's New for today
        if no not in reference_listings:
            if no in hist_articles or (data['unit_hash'] and data['unit_hash'] in hist_hashes):
                status = "매물 재등록"
            else:
                status = "신규매물"
            new_count += 1
        elif data['price_val'] != reference_listings[no]['price_val']:
            status = "변동"
            mod_count += 1
        
        data['status'] = status
        results.append(data)
        
        # Archive
        hist_articles.add(no)
        if data.get('unit_hash'):
            hist_hashes.add(data['unit_hash'])
            
    # Check for removals since this morning (Completed at some point today)
    for no, data in reference_listings.items():
        if no not in today_listings:
            # Check for re-registration (to avoid double counting removals)
            unit_hash = data.get('unit_hash')
            if unit_hash and unit_hash in today_hashes:
                continue 
                
            data['status'] = "거래 완료"
            results.append(data)
            del_count += 1

    print(f"📊 Daily Summary: {new_count} New, {mod_count} Changed, {del_count} Completed since morning.", flush=True)

    # Sort results
    results.sort(key=lambda x: (
        x.get('status') != '거래 완료', 
        int(x.get('price_val', 0)), 
        str(x.get('dong', '')),
        str(x.get('floor', ''))
    ))
    
    # 4. Save results.json for Frontend
    now_kst_str = now_kst_dt.strftime("%Y-%m-%d %H:%M")
    
    summary = {}
    for apt in TARGETS:
        name = apt["name"]
        today_cnt = len([l for l in today_listings.values() if l["complex_name"] == name])
        ref_cnt = len([l for l in reference_listings.values() if l["complex_name"] == name])
        summary[name] = {"prev": ref_cnt, "today": today_cnt}

    output = {
        "last_update": now_kst_str,
        "summary": summary,
        "listings": results
    }
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # 5. Update History (Save current run as 'last seen' for next time)
    history["last_day_listings"] = today_listings
    history["historical_articles"] = list(hist_articles)
    history["historical_hashes"] = list(hist_hashes)
    
    with os.fdopen(os.open(HISTORY_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o666), 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
        
    print(f"Done! Updated {len(today_listings)} listings.")

if __name__ == "__main__":
    main()
