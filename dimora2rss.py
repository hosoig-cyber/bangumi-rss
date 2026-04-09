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

# 新番組表記（OR 検索）
KEYWORDS = ["🈟", "[新]", "新"]

# 地デジ / BS（10件制限回避）
CHANNEL_TYPES = {
    "terrestrial": "2",
    "bs": "4",
}

# 有料BSチャンネル除外リスト
EXCLUDE_BS_STATIONS = [
    "BSアニマックス",
    "WOWOWプライム",
]

# ジャンル別設定
GENRES = {
    "anime": {
        "label": "アニメ",
        "genre": "7",
        "rss": "01_01new_anime.xml",
        "exclude_titles": [
            "総集編", "傑作選", "特別編", "劇場版", "OVA", "編集版","[無]","中国","韓国",
        ],
    },
    "drama": {
        "label": "ドラマ",
        "genre": "3",
        "rss": "01_02new_drama.xml",
        "exclude_titles": [
            "中国ドラマ", "韓", "華流","[無]","韓国ドラマ","中国","韓国",
        ],
    },
    "variety": {
        "label": "バラエティ",
        "genre": "5",
        "rss": "01_03new_variety.xml",
        "exclude_titles": [
            "中国ドラマ", "華流","韓国ドラマ","[無]",
        ],
    },
    "infom": {
        "genre": "2",
        "label": "情報／ワイドショー",
        "rss": "01_03new_variety.xml",
        "exclude_titles": [
            "中国ドラマ", "華流","韓国ドラマ","[無]",
        ],
    },
    "music": {
        "genre": "4",
        "label": "音楽",
        "rss": "01_03new_variety.xml",
        "exclude_titles": [
            "中国ドラマ", "華流","[再]","韓国ドラマ","[無]",
        ],
    },
    "docu": {
        "genre": "8",
        "label": "ドキュメンタリー／教養",
        "rss": "01_03new_variety.xml",
        "exclude_titles": [
            "中国ドラマ", "華流",
        ],
    },    
    "sports": {
        "genre": "1",
        "label": "スポーツ",
        "rss": "01_03new_variety.xml",
        "exclude_titles": [
            "中国ドラマ", "華流",
        ],
    },    
    
}

# ============================================================
# 共通関数
# ============================================================

def now_rfc2822():
    return datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0900")


def load_or_create_rss(path: str, title: str):
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
        "searchType": "1",   # 静的HTML
        "genre": genre,
        "areaId": AREA_ID,
    }
    res = requests.get(url, params=params, headers=HEADERS, timeout=30)
    res.raise_for_status()
    return BeautifulSoup(res.text, "lxml")


def is_excluded_title(title: str, exclude_list) -> bool:
    return any(word in title for word in exclude_list)


def is_excluded_station(station: str) -> bool:
    return any(name in station for name in EXCLUDE_BS_STATIONS)

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

                    # タイトル除外
                    if is_excluded_title(title, gconf["exclude_titles"]):
                        continue

                    datetime_txt = blk.select_one(".pgmTimeTxt").get_text(strip=True)
                    station = blk.select_one(".pgmBcsTxt").get_text(strip=True)

                    # 有料BSチャンネル除外
                    if ch_type == "4" and is_excluded_station(station):
                        continue

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

    # 同一実行内の重複除去
    uniq = {p["guid"]: p for p in collected}.values()

    added = 0
    for p in uniq:
        if p["guid"] in existing_guids:
            continue

        item = ET.SubElement(channel, "item")
        ET.SubElement(item, "title").text = p["title"]
        ET.SubElement(item, "link").text = p["link"]
        ET.SubElement(item, "description").text = (
            f"{p['station']} : "
            f"{p['datetime']}"
            f" 【{gconf['label']}】 \n"
#            f"詳細：{p['link']}"
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
    print("✅ GitHub に push しました")
else:
    print("✅ 更新なし（push不要）")