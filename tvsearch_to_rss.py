import requests
from bs4 import BeautifulSoup
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
import os
import json
import re
import subprocess

# ============================================================
# 基本設定
# ============================================================

API_URL = "https://bangumi.org/fetch_search_content/"
OUTPUT_DIR = "."
RETENTION_DAYS = 30

os.makedirs(OUTPUT_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ja,en-US;q=0.9",
    "Referer": "https://bangumi.org/search",
}

# ============================================================
# スカパー除外（地上波＋BS）
# ============================================================

SKY_PERFECT_KEYWORDS = [
    "AT-X",
    "ナショジオ",
    "スーパー!ドラマ",
    "キッズステーション",
    "BS釣りビジョン",
    "J SPORTS",
    "ディスカバリー",
    "スカパー",
    "BS11イレブン",
#    "TBS1",
    "ＢＳフジ４Ｋ",
    "TBSチャンネル2",
    "TOKYO MX1",
    "tvk1",
    "フジテレビONE",
    "ＢＳ朝日　４Ｋ",
    "フジテレビTWO",
    "ＢＳ日テレ　４Ｋ",
    "ＮＨＫ　ＢＳＰ４Ｋ",
    "TBSチャンネル1",
    "チャンネル銀河",
    "WOWOWプラス",
    "WOWOWシネマ",
    "日本映画専門ch",
    "WOWOWプライム",
    "ディズニーch",
    "映画・chNECO",
    "衛星劇場",
    "ムービープラス",
    "ディズニージュニア",
    "エムオン!",
    "スペースシャワーTV",
    "ゴルフネットワーク",
    "テレ玉1",
    "チバテレ1",
    "ホームドラマCH",
    "東映チャンネル",
    "ＢＳテレ東４Ｋ",
    "フジテレビNEXT",
    "WOWOWライブ",
    "CNNj",
    "スポーツライブ＋",
    "スカチャン1",
    "日テレジータス",
    "ファミリー劇場",
    "ザ・シネマ",
]

def is_skyperfect(station: str) -> bool:
    return any(k in station for k in SKY_PERFECT_KEYWORDS)

# ============================================================
# RSSルール（ここを編集）
# ============================================================

RSS_RULES = {
    "new_anime": {
        "queries": ["🈟"],          # OR条件
        "genres": {"アニメ／特撮"},
        "exclude_titles": ["総集編"],
        "rss_file": "01_01new_anime.xml",
    },
    "new_drama": {
        "queries": ["🈟"],          # OR条件
        "genres": {"ドラマ"},
        "exclude_titles": [],
        "rss_file": "01_02new_drama.xml",
    },
    "new_variety": {
        "queries": ["🈟"],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": ["再放送"],
        "rss_file": "01_03new_variety.xml",
    },
    "tv_movie": {
        "queries": ["🈙","映画"],          # OR条件
        "genres": {"映画"},
        "exclude_titles": ["🈞"],
        "rss_file": "01_04tv_movie.xml",
    },
    ## 番組指定
    "tv_life": {
        "queries": ["これ、かっこイイぜ","人と暮らしと台所","タサン志麻"],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": [],
        "rss_file": "02_01tv_life.xml",
    },
    "tv_nhk": {
        "queries": ["魔改造の夜","バス乗り継ぎ旅W","バス乗り継ぎ旅Ｗ","素っ頓狂な夜","糸井重里","みうらじゅん","バックパッカー世界さすらいメシ"],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": ["新TV見仏記"],
        "rss_file": "02_02tv_nhk.xml",
    },
    
    ## スポーツ
    "tv_suports": {
        "queries": ["バスケットボール","女子バレー","ラグビー","Bリーグ","女子マラソン","女子駅伝","バレー女子",],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": [],
        "rss_file": "03_01tv_suports.xml",
    },
    
    
    ## 個別人物
    
    "tv_ariyoshi": {
        "queries": ["有吉弘行"],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": ["再放送","櫻井・有吉THE夜会","有吉のお金発見","ぶらサタ・タカトシ","有吉ゼミ","有吉の壁"],
        "rss_file": "04_01tv_ari.xml",
    },
    "tv_westland": {
        "queries": ["ウエストランド"],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": ["再放送","KAWAIIってして","耳の穴かっぽじって"],
        "rss_file": "04_02tv_westland.xml",
    },
    "tv_kudokan": {
        "queries": ["宮藤官九郎"],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": [],
        "rss_file": "04_03tv_kudokan.xml",
    },
    "tv_arita": {
        "queries": ["有田哲平"],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": ["ナゾトレ","コスられない街","くりぃむ雑学","ミラクル9"],
        "rss_file": "04_05tv_arita.xml",
    },
    "tv_sansiro": {
        "queries": ["三四郎"],          # OR条件
        "genres": {"バラエティ""情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育"},
        "exclude_titles": [],
        "rss_file": "04_05tv_sansiro.xml",
    },
     "tv_nights": {
        "queries": ["ナイツ"],          # OR条件
        "genres": {"バラエティ"},
        "exclude_titles": ["カイモノラボ",],
        "rss_file": "04_06tv_nights.xml",
    },
     "tv_audry": {
        "queries": ["オードリー"],          # OR条件
        "genres": {"バラエティ","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": ["ソレダメ","スクール革命","ベスコングルメ"],
        "rss_file": "04_07tv_audry.xml",
    },
     "tv_tokyo03": {
        "queries": ["東京03","東京０３"],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": ["ノンストップ"],
        "rss_file": "04_08tv_tokyo03.xml",
    },
     "tv_sakuma": {
        "queries": ["佐久間宣行"],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": ["テレ東批評"],
        "rss_file": "04_09tv_sakuma.xml",
    },
     "tv_oota": {
        "queries": ["太田光"],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": ["サンデー・ジャポン","バズ英語",],
        "rss_file": "04_10tv_oota.xml",
    },
      "tv_kisitakano": {
        "queries": ["きしたかの"],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": [],
        "rss_file": "04_11tv_kisitakano.xml",
    },
      "tv_hinata": {
        "queries": ["日向坂46","日向坂４６"],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": ["日向坂で会いましょう"],
        "rss_file": "04_12tv_hinata.xml",
    },
    "tv_hinata_og": {
        "queries": ["佐々木久美","加藤史帆","斉藤京子","佐々木美鈴","影山優佳",],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": [],
        "rss_file": "04_13tv_hinataog.xml",
    },
      "tv_evas": {
        "queries": ["エバース"],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": [],
        "rss_file": "04_14tv_evas.xml",
    },
      "tv_kato": {
        "queries": ["加藤浩次"],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": ["がっちりマンデー"],
        "rss_file": "04_15tv_kato.xml",
    },
      "tv_timo": {
        "queries": ["ティモンディ"],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": ["ヴィクトリーグ"],
        "rss_file": "04_16tv_timo.xml",
    },
      "tv_dau": {
        "queries": ["蓮見翔","ダウ90000","ダウ９００００"],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","情報／ワイドショー","ニュース／報道","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": [],
        "rss_file": "04_17tv_dau.xml",
    },
      "tv_sisonnu": {
        "queries": ["シソンヌ"],          # OR条件
        "genres": {"バラエティ","映画","ドラマ","ドキュメンタリー／教養","劇場／公演","趣味／教育","音楽","スポーツ"},
        "exclude_titles": ["有吉の壁"],
        "rss_file": "04_18tv_sisonnu.xml",
    },
    
}

# ============================================================
# 共通関数
# ============================================================

def now_rfc2822():
    return datetime.now().strftime("%a, %d %b %Y %H:%M:%S +0900")

def get_genres(li):
    raw = li.get("type_genre")
    if not raw:
        return set()
    try:
        return set(json.loads(raw))
    except:
        return set()

def parse_jp_datetime(text):
    """
    例: '3月31日 火曜 22:00'
    """
    m = re.search(r'(\d+)月(\d+)日.*?(\d+):(\d+)', text)
    if not m:
        return None
    month, day, hour, minute = map(int, m.groups())
    year = datetime.now().year
    return datetime(year, month, day, hour, minute)

def load_or_create_rss(path, title):
    if os.path.exists(path):
        tree = ET.parse(path)
        channel = tree.getroot().find("channel")
        existing = {
            item.findtext("guid")
            for item in channel.findall("item")
            if item.find("guid") is not None
        }
        return tree, channel, existing

    rss = ET.Element("rss", version="2.0")
    channel = ET.SubElement(rss, "channel")
    ET.SubElement(channel, "title").text = title
    ET.SubElement(channel, "link").text = "https://bangumi.org/"
    ET.SubElement(channel, "description").text = title
    ET.SubElement(channel, "lastBuildDate").text = now_rfc2822()
    return ET.ElementTree(rss), channel, set()

def prune_old_items(channel):
    cutoff = datetime.now() - timedelta(days=RETENTION_DAYS)
    removed = 0

    for item in list(channel.findall("item")):
        desc = item.findtext("description") or ""
        lines = desc.splitlines()
        if len(lines) < 2:
            continue

        dt = parse_jp_datetime(lines[0])
        if dt and dt < cutoff:
            channel.remove(item)
            removed += 1

    return removed

# ============================================================
# メイン処理
# ============================================================

for rule_name, rule in RSS_RULES.items():
    print(f"\n==== RSS更新: {rule_name} ====")

    rss_path = os.path.join(OUTPUT_DIR, rule["rss_file"])
    tree, channel, existing_guids = load_or_create_rss(
        rss_path,
        f"bangumi.org RSS: {rule_name}"
    )

    removed = prune_old_items(channel)
    print(f" - 30日超過 削除: {removed}")

    added = 0

    for query in rule["queries"]:
        print(f" - 検索語: {query}")

        res = requests.get(
            API_URL,
            params={"q": query, "type": "tv"},
            headers=HEADERS,
            timeout=30,
        )
        if res.status_code != 200:
            continue

        soup = BeautifulSoup(res.text, "lxml")

        for li in soup.select("#tv-content li.block"):
            box = li.select_one(".box-2")
            if not box:
                continue

            ps = box.select("p.repletion")
            if len(ps) < 2:
                continue

            title = ps[0].get_text(strip=True)
            meta = ps[1].get_text(strip=True)

            if "　" in meta:
                datetime_text, station = meta.split("　", 1)
            else:
                datetime_text, station = meta, ""

            if is_skyperfect(station):
                continue

            genres = get_genres(li)
            if rule["genres"] and not (genres & rule["genres"]):
                continue

            if any(x in title for x in rule["exclude_titles"]):
                continue

            link_tag = li.select_one("a[href^='/tv_events/']")
            if not link_tag:
                continue

            detail_url = "https://bangumi.org" + link_tag["href"]

            guid = f"{title}|{datetime_text}|{station}"
            if guid in existing_guids:
                continue

            item = ET.SubElement(channel, "item")
            ET.SubElement(item, "title").text = title
            ET.SubElement(item, "link").text = detail_url
            ET.SubElement(item, "description").text = (
                f"{datetime_text}\n"
                f"{station}\n"
                f"{detail_url}"
            )
            ET.SubElement(item, "pubDate").text = now_rfc2822()
            ET.SubElement(item, "guid").text = guid

            existing_guids.add(guid)
            added += 1

    tree.write(rss_path, encoding="utf-8", xml_declaration=True)
    print(f" - 新規追加: {added}")
    print(f" - 出力: {rss_path}")

# ============================================================
# GitHub 自動 push
# ============================================================

try:
    subprocess.run(["git", "add", "."], check=True)
    subprocess.run(["git", "commit", "-m", "update rss"], check=False)
    subprocess.run(["git", "push"], check=True)
    print("\n✅ GitHub に push しました")
except Exception as e:
    print("\n⚠ Git push 失敗:", e)

print("\n=== 完了 ===")
