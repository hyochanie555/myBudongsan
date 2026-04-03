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
        print("Please add it to GitHub Secrets: https://github.com/settings/secrets/actions", flush=True)
        return current_listings

    for i, tgt in enumerate(TARGETS):
        apt_name = tgt["name"]
        complex_id = tgt["id"]
        print(f"\n[TARGET] {apt_name} ({complex_id})", flush=True)
        
        try:
            # 1. High-Efficiency API Call (render=false)
            # This calls Naver's internal API directly via ScraperAPI's South Korean proxy.
            # Speed: Instant (<1s) | Cost: 1 credit (saves 90% vs rendering)
            target_url = f"https://fin.land.naver.com/front-api/v1/article/list?complexNo={complex_id}&tradeType=A1&priceOrder=ASC"
            proxy_url = "http://api.scraperapi.com"
            params = {
                'api_key': SCRAPERAPI_KEY,
                'url': target_url,
                'render': 'false', # No headless browser needed for JSON, saving time/money
                'country_code': 'kr'
            }
            
            print(f"  Requesting via ScraperAPI (Direct API High Speed)...", flush=True)
            response = requests.get(proxy_url, params=params, timeout=60)
            
            if response.status_code != 200:
                print(f"  Proxy error ({response.status_code}): {response.text[:200]}", flush=True)
                continue
                
            data = response.json()
            items = data.get('result', {}).get('list', [])
            print(f"  Found {len(items)} items in JSON response.", flush=True)
            
            for item in items:
                try:
                    article_no = str(item.get('articleNo', ''))
                    if not article_no: continue
                    
                    rep_info = item.get('representativeArticleInfo', {})
                    dong = rep_info.get('dongName', '')
                    
                    price_info = item.get('priceInfo', {})
                    price_text = price_info.get('dealPriceName', '')
                    price_val = price_info.get('dealPrice', 0)
                    
                    if "매매" not in price_text: continue
                    
                    space_info = item.get('spaceInfo', {})
                    area1 = space_info.get('exclusiveSpace', 0)
                    area2 = space_info.get('supplySpace', area1)
                    
                    if tgt["area_min"] <= area1 <= tgt["area_max"] or tgt["area_min"] <= area2 <= tgt["area_max"]:
                        detail = item.get('articleDetail', {})
                        floor_text = detail.get('floorInfo', '')
                        
                        verif_info = item.get('verificationInfo', {})
                        reg_date = verif_info.get('articleConfirmDate', '')
                        if reg_date: reg_date = reg_date[2:].replace('-', '.') # "2026-04-03" -> "26.04.03"
                        
                        current_listings[article_no] = {
                            'article_no': article_no,
                            'complex_name': apt_name,
                            'dong': dong,
                            'floor': floor_text,
                            'price': price_text,
                            'price_val': price_val,
                            'area': f"{area1}㎡ / {area2}㎡",
                            'reg_date': reg_date,
                            'cp_name': "Naver API",
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
                "message": "⚠️ SCRAPERAPI_KEY가 설정되지 않았거나 프록시 오류가 발생했습니다. 저장소의 Settings > Secrets에 키를 등록했는지 확인해 주세요."
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
