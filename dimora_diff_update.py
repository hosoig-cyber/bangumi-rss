import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
import subprocess

# =========================
# 共通設定
# =========================

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "ja",
}

BASE_URL = "https://www.dimora.jp/freeword-search/"
AREA_ID = "027"

KEYWORDS = ["🈟", "[新]", "新"]

CHANNEL_TYPES = {
    "terrestrial": "2",  # 地デジ
    "bs": "4",           # BS
}

GENRES = {
    "anime": {
        "genre": "7",
        "rss": "01_01new_anime.xml",
    },
    "drama": {
        "genre": "3",
        "rss": "01_02new_drama.xml",
    },
    "variety": {
        "genre": "5",
        "rss": "01_03new_variety.xml",
    },
}

# =========================
# ユーティリティ
# =========================

def now_rfc2822():
    return datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0900")


def load_rss(path):
    tree = ET.parse(path)
    channel = tree.getroot().find("channel")
    guids = {
        item.findtext("guid")
        for item in channel.findall("item")
        if item.find("guid") is not None
    }
    return tree, channel, guids


def fetch_dimora(keyword, ch_type, genre):
    url = BASE_URL + requests.utils.quote(keyword)
    params = {
        "chType": ch_type,
        "searchType": "1",  # ★重要
        "genre": genre,
        "areaId": AREA_ID,
    }

    r = requests.get(url, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


def extract_programs(soup):
    programs = []
    for blk in soup.select("div.pgmInnArea"):
        try:
            time_txt = blk.select_one(".pgmTimeTxt").get_text(strip=True)
            title_el = blk.select_one(".pgmLinkTtl")
            title = title_el.get_text(strip=True)
            station = blk.select_one(".pgmBcsTxt").get_text(strip=True)
            link = "https://www.dimora.jp" + title_el["href"]

            guid = f"{title}|{time_txt}|{station}"

            programs.append({
                "guid": guid,
                "title": title,
                "datetime": time_txt,
                "station": station,
                "link": link,
            })
        except Exception:
            continue
    return programs


def append_diff(channel, existing_guids, programs):
    added = 0
    for p in programs:
        if p["guid"] in existing_guids:
            continue

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = p["title"]
        ET.SubElement(item, "link").text = p["link"]

        description = (
            f"{p['station']} : "
            f"{p['datetime']}\n"
#            f"情報源：DiMORA（補助検知）\n"
#            f"詳細：{p['link']}"
        )

        ET.SubElement(item, "description").text = description
        ET.SubElement(item, "pubDate").text = now_rfc2822()
        ET.SubElement(item, "guid").text = p["guid"]

        existing_guids.add(p["guid"])
        added += 1
    return added


def git_push_if_changed():
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(
        ["git", "commit", "-m", "update rss (add dimora diff)"],
        check=False
    )
    subprocess.run(["git", "push"], check=True)

# =========================
# メイン処理
# =========================

total_added = 0

for gname, gconf in GENRES.items():
    rss_path = gconf["rss"]
    if not Path(rss_path).exists():
        print(f"❌ {rss_path} が見つかりません")
        continue

    print(f"\n=== {gname.upper()} ===")

    tree, channel, existing_guids = load_rss(rss_path)

    diff_programs = []

    for ct_name, ch_type in CHANNEL_TYPES.items():
        for kw in KEYWORDS:
            print(f"検索: {kw} / {ct_name}")
            soup = fetch_dimora(kw, ch_type, gconf["genre"])
            programs = extract_programs(soup)
            diff_programs.extend(programs)

    # 重複排除
    uniq = {p["guid"]: p for p in diff_programs}.values()

    added = append_diff(channel, existing_guids, uniq)

    if added > 0:
        tree.write(rss_path, encoding="utf-8", xml_declaration=True)
        print(f"✅ {rss_path} に {added} 件追記")
        total_added += added
    else:
        print("差分なし")

# =========================
# GitHub push
# =========================

if total_added > 0:
    git_push_if_changed()
    print("✅ GitHub に push 完了")
else:
    print("✅ 追加なし（push不要）")
