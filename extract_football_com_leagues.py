from bs4 import BeautifulSoup
import json

# ================== CONFIG ==================
HTML_FILE = "fb_region_leagues.html"          # ← Put your FULL file here
OUTPUT_JSON = "football_com_leagues_full.json"
# ===========================================

with open(HTML_FILE, "r", encoding="utf-8") as f:
    soup = BeautifulSoup(f, "html.parser")

leagues = []

# Each league block is inside <section data-v-8662d370="">
for league_section in soup.find_all("section", {"data-v-8662d370": True}):
    # League name
    title_wrapper = league_section.find("div", class_="league-title-wrapper")
    if not title_wrapper:
        continue
    
    name_tag = title_wrapper.find("h4")
    league_name = name_tag.get_text(strip=True) if name_tag else "Unknown"
    
    # League URL slug (from any match link inside this section)
    link_tag = league_section.find("a", href=True)
    url_slug = link_tag["href"] if link_tag else None
    
    # Number of matches (the h5 next to the title)
    match_count_tag = title_wrapper.find("h5", {"data-v-2c3f1176": True})
    match_count = match_count_tag.get_text(strip=True) if match_count_tag else "0"
    
    leagues.append({
        "league_id": f"football_com_{league_name.lower().replace(' ', '_').replace(',', '')}",
        "country_code": "unknown",                    # You can map this later if needed
        "continent": "unknown",
        "name": league_name,
        "url": url_slug,
        "match_count": int(match_count) if match_count.isdigit() else 0,
        "football_com_available": True,
        "last_seen": "2026-03-08"
    })

# Save as clean JSON
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(leagues, f, indent=2, ensure_ascii=False)

print(f"✅ Extraction complete!")
print(f"   Found {len(leagues)} leagues on football.com")
print(f"   Saved to: {OUTPUT_JSON}")