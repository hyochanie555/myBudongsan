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

# Local .env support for environments that don't share terminal session variables
if not SCRAPERAPI_KEY and os.path.exists(".env"):
    try:
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("SCRAPERAPI_KEY="):
                    SCRAPERAPI_KEY = line.strip().split("=")[1].strip().strip("'").strip('"')
                    break
    except Exception:
        pass

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
    if not p_str: return 0
    try:
        if '~' in p_str:
            p_str = p_str.split('~')[0].strip()
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
        return total * 10000 
    except Exception:
        return 0

def fetch_listings():
    """Fetches real estate listings for all targets via ScraperAPI (Stealth Rendering)."""
    current_listings = {}
    
    if not SCRAPERAPI_KEY:
        print("❌ SCRAPERAPI_KEY not found in environment variables.", flush=True)
        return current_listings

    for tgt in TARGETS:
        apt_id = tgt["id"]
        apt_name = tgt["name"]
        print(f"\n[TARGET] {apt_name} ({apt_id}) Scraping start...", flush=True)
        
        # 🔁 [RETRY LOOP] Try up to 3 times per complex
        for attempt in range(1, 4):
            try:
                # 1. ScraperAPI Stealth Rendering Setup
                target_url = f"https://m.land.naver.com/complex/info/{apt_id}?tab=article"
                proxy_url = "http://api.scraperapi.com"
                
                custom_headers = {
                    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7'
                }
                
                params = {
                    'api_key': SCRAPERAPI_KEY,
                    'url': target_url,
                    'render': 'true',
                    'premium': 'true',
                    'country_code': 'kr',
                    'keep_headers': 'true',
                    'wait_for_selector': 'li[class*="ArticleCard_item__"]' 
                }
                
                print(f"  Requesting via ScraperAPI (Attempt {attempt})...", flush=True)
                response = requests.get(proxy_url, params=params, headers=custom_headers, timeout=180)
                
                if response.status_code != 200:
                    print(f"  Proxy error ({response.status_code}): {response.text[:100]}", flush=True)
                    continue
                    
                html = response.text
                items = re.findall(r'<li[^>]*class="[^"]*ArticleCard_item__[^"]*"[^>]*>(.*?)</li>', html, re.DOTALL)
                
                if not items:
                    print(f"  ⚠️ No items found in DOM (Attempt {attempt}).", flush=True)
                    if attempt < 3: 
                        time.sleep(attempt * 5)
                    continue
                    
                print(f"  Found {len(items)} items in rendered DOM.", flush=True)
                
                complex_success = False
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
                        
                        # Summary (Area, Floor)
                        match_summaries = re.findall(r'<li[^>]*class="[^"]*ArticleCard_item-summary__[^"]*"[^>]*>(.*?)</li>', item_html)
                        if len(match_summaries) < 3: continue
                        area_text = match_summaries[1] 
                        floor_text = match_summaries[2]
                        
                        area_clean = area_text.replace('㎡', '').replace(' ', '')
                        if '/' in area_clean:
                            area_parts = area_clean.split('/')
                            area_type = area_parts[0]
                            area_val = area_parts[1]
                        else:
                            area_type = area_clean
                            area_val = area_clean
                        
                        areas = re.findall(r'(\d+(?:\.\d+)?)', area_val)
                        if not areas: continue
                        area_num = float(areas[0])
                        
                        if tgt["area_min"] <= area_num <= tgt["area_max"]:
                            match_date = re.search(r'확인매물 (\d{4}\.\d{2}\.\d{2})', item_html)
                            reg_date = match_date.group(1)[2:] if match_date else ""
                            
                            price_val = parse_price(price_text)
                            
                            match_count = re.search(r'중개사\s*(\d+)곳에서\s*등록했어요', item_html)
                            group_count = int(match_count.group(1)) if match_count else 1
                            
                            match_cp = re.search(r'<(?:span|li)[^>]*class="[^"]*ArticleBrokerInfo_item-source__[^"]*"[^>]*>(.*?)</(?:span|li)>', item_html)
                            cp_name = match_cp.group(1).strip() if match_cp else "Naver Mobile"
                            
                            # 🚫 [Filter] Association pattern check
                            if "공인중개사협회" in cp_name or "협회" in cp_name:
                                continue

                            unit_hash = f"NV_{article_no}" 
                            
                            current_listings[article_no] = {
                                'article_no': article_no,
                                'complex_name': apt_name,
                                'dong': dong,
                                'floor': floor_text,
                                'price': price_text,
                                'price_val': price_val,
                                'area': f"{area_type} / {area_num}㎡",
                                'reg_date': reg_date,
                                'cp_name': cp_name,
                                'unit_hash': unit_hash,
                                'count': group_count
                            }
                            complex_success = True
                    except:
                        continue
                
                if complex_success:
                    break # Success for this complex
            except Exception as e:
                print(f"  Error on attempt {attempt}: {e}", flush=True)
                
    return current_listings

def group_listings(listings_dict):
    """Groups multiple article_nos into unique properties."""
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

def main():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        
    history = {
        "last_day_listings": {}, 
        "historical_articles": [], 
        "historical_hashes": [],
        "last_ref_date": "",
        "reference_listings": {}
    }
    
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            try:
                history = json.load(f)
            except: pass
            
    prev_listings = history.get("last_day_listings", {})
    hist_hashes = set(history.get("historical_hashes", []))
    
    now_kst_dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=9)
    current_date = now_kst_dt.strftime("%Y-%m-%d")
    last_ref_date = history.get("last_ref_date", "")
    
    if current_date != last_ref_date:
        print(f"🌞 [SYSTEM] New Date detected ({current_date}). Setting morning baseline...", flush=True)
        reference_listings = prev_listings.copy()
        history["last_ref_date"] = current_date
        history["reference_listings"] = reference_listings
    else:
        reference_listings = history.get("reference_listings", prev_listings)
        print(f"🕒 [SYSTEM] Day-based mode: Comparing to {current_date} baseline.", flush=True)

    # 2. Scrape Current
    today_articles = fetch_listings()
    if not today_articles:
        print("⚠️ No listings scraped. Safety check: Keeping existing results.", flush=True)
        return

    # 3. Grouping
    today_groups = group_listings(today_articles)
    ref_groups = group_listings(reference_listings)
    
    results = []
    new_count = 0
    re_count = 0
    del_count = 0
    
    # 4. Compare Groups
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

    print(f"📊 Property Summary: {new_count} New, {re_count} Re-reg, {del_count} Completed since morning.", flush=True)

    results.sort(key=lambda x: (
        x.get('status') != '거래 완료', 
        int(x.get('price_val', 0)), 
        str(x.get('dong', '')),
        str(x.get('floor', ''))
    ))
    
    now_kst_str = now_kst_dt.strftime("%Y-%m-%d %H:%M")
    
    summary = {}
    for apt in TARGETS:
        name = apt["name"]
        today_cnt = len([l for l in today_groups.values() if l["complex_name"] == name])
        ref_cnt = len([l for l in ref_groups.values() if l["complex_name"] == name])
        summary[name] = {"prev": ref_cnt, "today": today_cnt}

    output = {
        "last_update": now_kst_str,
        "summary": summary,
        "listings": results
    }
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    history["last_day_listings"] = today_articles 
    history["historical_hashes"] = list(hist_hashes)
    
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
        
    print(f"Done! Saved {len(today_groups)} unique properties.")

if __name__ == "__main__":
    main()
