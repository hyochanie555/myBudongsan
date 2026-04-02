import requests
import json
import time
import datetime
import os
import sys

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
        # "3억 1,800" -> "3억1800"
        p_str = p_str.replace(",", "").replace(" ", "")
        
        # Split by non-digit or '억'
        total = 0
        if '억' in p_str:
            parts = p_str.split('억')
            if parts[0]:
                total += int(parts[0]) * 10000
            if len(parts) > 1 and parts[1]:
                # Remove any leftover non-digits (like '만')
                digits_only = "".join(filter(str.isdigit, parts[1]))
                if digits_only:
                    total += int(digits_only)
        else:
            digits_only = "".join(filter(str.isdigit, p_str))
            if digits_only:
                total = int(digits_only)
        return total
    except Exception as e:
        print(f"Price parsing error for '{p_str}': {e}", file=sys.stderr)
        return 0

def fetch_listings():
    # List of common mobile browser User-Agents
    UAS = [
        'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Mobile/15E148 Safari/604.1',
        'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Mobile Safari/537.36'
    ]
    
    session = requests.Session()
    current_listings = {} 
    
    for i, tgt in enumerate(TARGETS):
        apt_name = tgt["name"]
        complex_id = tgt["id"]
        print(f"\n[TARGET] {apt_name} ({complex_id})")
        
        # 0. Mobile Specific Headers
        import random
        ua = random.choice(UAS)
        session.headers.update({
            'User-Agent': ua,
            'Accept': 'application/json, text/plain, */*',
            'Referer': f'https://m.land.naver.com/complex/info/{complex_id}?tradTpCd=A1',
            'Connection': 'keep-alive'
        })
            
        page = 1
        while True:
            # ‼️ MOBILE API ENDPOINT (Often has different WAF rules)
            # hscpNo: Complex ID, tradTpCd: A1 (Deal), rletTpCd: A01 (APT)
            url = f"https://m.land.naver.com/api/article/list?hscpNo={complex_id}&tradTpCd=A1&rletTpCd=A01&showNoPrice=false&page={page}"
            
            try:
                # Randomized sleep
                time.sleep(2 + random.random() * 3) 
                
                res = session.get(url, timeout=20)
                
                if res.status_code != 200: 
                    print(f"  HTTP error {res.status_code} (Mobile API)")
                    print(f"  Response: {res.text[:150]}")
                    break
                
                data = res.json()
                # Mobile API structure: result.list
                result_obj = data.get("result", {})
                if not result_obj:
                    print(f"  No 'result' found in Mobile API (Block or Empty)")
                    break
                    
                items = result_obj.get("list", [])
                if not items: 
                    print(f"  End of list (Page {page})")
                    break
                
                print(f"  Found {len(items)} items on Page {page} (Mobile).")
                
                new_on_page = 0
                for item in items:
                    article_no = str(item.get("atclNo", "")) # Mobile use atclNo
                    if not article_no: continue
                    
                    # Mobile uses spc1 (Supply), spc2 (Net)
                    area1 = float(item.get("spc1", 0))
                    area2 = float(item.get("spc2", 0))
                    
                    # Filter (10-300 for debug)
                    if 10 <= area1 <= 300 or 10 <= area2 <= 300:
                        raw_date = str(item.get("atclCfmYmd", "")) # Mobile use atclCfmYmd
                        
                        current_listings[article_no] = {
                            'article_no': article_no,
                            'complex_name': apt_name,
                            'dong': item.get("bildNm", ""), # Mobile use bildNm
                            'floor': item.get("flrInfo", ""), # Mobile use flrInfo
                            'price': item.get("prc", "") + " (매매)", # Mobile use prc
                            'price_val': parse_price(item.get("prc", "")),
                            'area': f"{area1}㎡ / {area2}㎡",
                            'reg_date': raw_date, # Format: YY.MM.DD
                            'cp_name': item.get("cpNm", ""), # Mobile use cpNm
                            'unit_hash': article_no
                        }
                        new_on_page += 1
                
                if len(items) < 20: break
                page += 1
                if page > 10: break
            except Exception as e:
                print(f"  Error: {e}")
                break
        
        # Long randomized delay between complexes
        if i < len(TARGETS) - 1:
            wait_between = 40 + random.randint(0, 40)
            print(f"  ✅ Finished {apt_name}. Waiting {wait_between} seconds...")
            time.sleep(wait_between)
                
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
            now_kst = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
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
    now_kst = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d %H:%M")
    
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
