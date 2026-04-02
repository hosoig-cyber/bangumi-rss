import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
import subprocess

# ============================================================
# 基本設定
# ============================================================

BASE_URL = "https://www.dimora.jp/freeword-search/"
AREA_ID = "027"   # 群馬

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "ja",
}

# 検索語（OR）
KEYWORDS = ["🈟", "[新]", "新"]

# 地デジ / BS（10件制限対策）
CHANNEL_TYPES = {
    "terrestrial": "2",
    "bs": "4",
}

# ジャンル別設定
GENRES = {
    "anime": {
        "genre": "7",
        "rss": "01_01new_anime.xml",
        "exclude_titles": [
            "総集編", "傑作選", "特別編", "劇場版", "OVA", "編集版",
        ],
    },
    "drama": {
        "genre": "3",
        "rss": "01_02new_drama.xml",
        "exclude_titles": [
            "中国ドラマ", "韓", "華流",
        ],
    },
    "variety": {
        "genre": "5",
        "rss": "01_03new_variety.xml",
        "exclude_titles": [
            "再放送",
        ],
    },
}

# ============================================================
# 共通関数
# ============================================================

def now_rfc2822():
    return datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0900")


def load_or_create_rss(path, title):
    if Path(path).exists():
        tree = ET.parse(path)
        channel = tree.getroot().find("channel")
        guids = {
            item.findtext("guid")
            for item in channel.findall("item")
            if item.find("guid") is not None
        }
        return tree, channel, guids

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = title
    ET.SubElement(channel, "link").text = "https://www.dimora.jp/"
    ET.SubElement(channel, "description").text = title
    ET.SubElement(channel, "lastBuildDate").text = now_rfc2822()
    return ET.ElementTree(rss), channel, set()


def fetch_dimora(keyword, ch_type, genre):
    url = BASE_URL + requests.utils.quote(keyword)
    params = {
        "chType": ch_type,
        "searchType": "1",   # 静的HTML版
        "genre": genre,
        "areaId": AREA_ID,
    }
    r = requests.get(url, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "lxml")


def is_excluded(title, exclude_list):
    return any(word in title for word in exclude_list)


# ============================================================
# メイン処理
# ============================================================

total_added = 0

for gname, gconf in GENRES.items():
    print(f"\n=== {gname.upper()} ===")

    tree, channel, existing_guids = load_or_create_rss(
        gconf["rss"],
        f"DiMORA 新番組 RSS ({gname})"
    )

    collected = []

    for ch_name, ch_type in CHANNEL_TYPES.items():
        for kw in KEYWORDS:
            print(f"検索: {kw} / {ch_name}")
            soup = fetch_dimora(kw, ch_type, gconf["genre"])

            for blk in soup.select("div.pgmInnArea"):
                try:
                    title = blk.select_one(".pgmLinkTtl").get_text(strip=True)

                    # 除外語チェック（生タイトル）
                    if is_excluded(title, gconf["exclude_titles"]):
                        continue

                    datetime_txt = blk.select_one(".pgmTimeTxt").get_text(strip=True)
                    station = blk.select_one(".pgmBcsTxt").get_text(strip=True)
                    link = "https://www.dimora.jp" + blk.select_one(".pgmLinkTtl")["href"]

                    guid = f"{title}|{datetime_txt}|{station}"

                    collected.append({
                        "guid": guid,
                        "title": title,
                        "datetime": datetime_txt,
                        "station": station,
                        "link": link,
                    })
                except Exception:
                    continue

    # GUIDで重複排除（同一スクリプト内）
    uniq = {p["guid"]: p for p in collected}.values()

    added = 0
    for p in uniq:
        if p["guid"] in existing_guids:
            continue

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = p["title"]
        ET.SubElement(item, "link").text = p["link"]
        ET.SubElement(item, "description").text = (
            f"放送日時：{p['datetime']}\n"
            f"放送局：{p['station']}\n"
            f"情報源：DiMORA\n"
            f"詳細：{p['link']}"
        )
        ET.SubElement(item, "pubDate").text = now_rfc2822()
        ET.SubElement(item, "guid").text = p["guid"]

        existing_guids.add(p["guid"])
        added += 1

    if added > 0:
        tree.write(gconf["rss"], encoding="utf-8", xml_declaration=True)
        print(f"✅ {gconf['rss']} に {added} 件追加")
        total_added += added
    else:
        print("差分なし")

# ============================================================
# GitHub push
# ============================================================

if total_added > 0:
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(
        ["git", "commit", "-m", "update dimora new programs"],
        check=False
    )
    subprocess.run(["git", "push"], check=True)
    print("✅ GitHubにpushしました")
else:
    print("✅ 更新なし（push不要）")