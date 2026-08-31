# -*- coding: utf-8 -*-
"""
JグランツAPI(デジタル庁) から募集中の補助金情報を取得して data/subsidies.json に保存する。

- 標準ライブラリのみで動作（pip install 不要）
- 詳細APIのレスポンスは1件1.7MBと重いのでローカルキャッシュして差分だけ取得する
- 出典: Jグランツ（デジタル庁） https://www.jgrants-portal.go.jp/
"""
import datetime
import hashlib
import json
import os
import sys
import time
import urllib.parse
import urllib.request
import urllib.error

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://api.jgrants-portal.go.jp/exp"
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
CACHE_DIR = os.path.join(DATA_DIR, "cache")
OUT_FILE = os.path.join(DATA_DIR, "subsidies.json")

# 一覧APIは keyword 必須（2文字以上）で全件取得ができないため、
# 広めのキーワードを巡回して和集合をとる。
KEYWORDS = [
    "補助", "助成", "支援", "事業", "促進", "整備", "導入", "開発",
    "設備", "研究", "創業", "雇用", "人材", "育成", "環境", "省エネ",
    "脱炭素", "観光", "農業", "医療", "福祉", "教育", "文化", "防災",
    "IT", "DX", "輸出", "販路", "商店街", "空き家", "子育て", "移住",
]

# 詳細APIに含まれる添付ファイル（base64）は巨大なので保存しない
DROP_FIELDS = ("application_guidelines", "outline_of_grant", "application_form")

USER_AGENT = "kozeni-subsidy-site/1.0 (+static site generator; contact via site)"

# 詳細キャッシュの有効期限。締切や金額は変わるので永久保存はしない。
# 全件が同じ日に一斉失効して大量再取得が起きないよう、IDから決まる0〜7日のずれを足す。
CACHE_TTL_SEC = 7 * 24 * 3600
CACHE_SPREAD_SEC = 7 * 24 * 3600

JST = datetime.timezone(datetime.timedelta(hours=9))


def http_get_json(url, max_retry=5):
    """GETしてJSONを返す。429/5xxは指数バックオフでリトライ。"""
    wait = 2
    for attempt in range(max_retry):
        req = urllib.request.Request(url, headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json",
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as res:
                return json.loads(res.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < max_retry - 1:
                print("    HTTP %s -> %s秒待って再試行" % (e.code, wait))
                time.sleep(wait)
                wait = min(wait * 2, 30)
                continue
            raise
        except (urllib.error.URLError, TimeoutError) as e:
            if attempt < max_retry - 1:
                print("    通信エラー(%s) -> %s秒待って再試行" % (e, wait))
                time.sleep(wait)
                wait = min(wait * 2, 30)
                continue
            raise
    raise RuntimeError("リトライ上限に達しました: " + url)


def fetch_list(keyword):
    """一覧API。募集中(acceptance=1)のみ取得する。"""
    q = urllib.parse.urlencode({
        "keyword": keyword,
        "sort": "created_date",
        "order": "DESC",
        "acceptance": "1",
    })
    url = "%s/v1/public/subsidies?%s" % (BASE, q)
    data = http_get_json(url)
    return data.get("result") or []


def fetch_detail(subsidy_id):
    """詳細API(v1)。添付ファイル項目は捨てて軽くする。"""
    url = "%s/v1/public/subsidies/id/%s" % (BASE, urllib.parse.quote(subsidy_id))
    data = http_get_json(url)
    result = data.get("result") or []
    if not result:
        return None
    rec = dict(result[0])
    for f in DROP_FIELDS:
        rec.pop(f, None)
    return rec


def cache_ttl(subsidy_id):
    """IDごとに 7〜14日 のばらついた有効期限を返す（失効日を分散させるため）。"""
    h = hashlib.md5(subsidy_id.encode("utf-8")).hexdigest()
    return CACHE_TTL_SEC + int(h[:8], 16) % CACHE_SPREAD_SEC


def load_cache(subsidy_id):
    """有効期限内のキャッシュだけ返す。期限切れ・旧形式・壊れている場合は None。"""
    path = os.path.join(CACHE_DIR, subsidy_id + ".json")
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            blob = json.load(f)
    except (ValueError, OSError):
        return None
    if not isinstance(blob, dict):
        return None
    fetched_at = blob.get("_fetched_at")
    # 旧形式（取得時刻なし）は取得時期が不明なので再取得させる
    if not isinstance(fetched_at, (int, float)):
        return None
    if time.time() - fetched_at > cache_ttl(subsidy_id):
        return None
    return blob.get("record")


def save_cache(subsidy_id, rec):
    path = os.path.join(CACHE_DIR, subsidy_id + ".json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"_fetched_at": time.time(), "record": rec}, f, ensure_ascii=False)


def main():
    os.makedirs(CACHE_DIR, exist_ok=True)

    print("■ 一覧APIを巡回します（キーワード %d 個）" % len(KEYWORDS))
    summaries = {}
    for i, kw in enumerate(KEYWORDS, 1):
        try:
            rows = fetch_list(kw)
        except Exception as e:
            print("  [%2d/%d] %-6s 取得失敗: %s" % (i, len(KEYWORDS), kw, e))
            continue
        new = 0
        for row in rows:
            sid = row.get("id")
            if sid and sid not in summaries:
                summaries[sid] = row
                new += 1
        print("  [%2d/%d] %-6s %4d件 (新規 %d) 累計 %d" % (i, len(KEYWORDS), kw, len(rows), new, len(summaries)))
        time.sleep(0.3)

    if not summaries:
        print("!! 1件も取得できませんでした。ネットワークかAPI仕様の変更を確認してください。")
        return 1

    print("\n■ 詳細APIを取得します（キャッシュ済みはスキップ）")
    records = []
    fetched = cached = failed = 0
    ids = list(summaries.keys())
    for i, sid in enumerate(ids, 1):
        rec = load_cache(sid)
        if rec is None:
            try:
                rec = fetch_detail(sid)
            except Exception as e:
                print("  [%d/%d] %s 詳細取得失敗: %s" % (i, len(ids), sid, e))
                failed += 1
                rec = None
            if rec:
                save_cache(sid, rec)
                fetched += 1
                time.sleep(0.3)
        else:
            cached += 1

        # 一覧APIの値が常に最新。キャッシュ済みの詳細で上書きされないよう詳細を先に置く。
        merged = {}
        if rec:
            merged.update({k: v for k, v in rec.items() if v is not None})
        merged.update({k: v for k, v in summaries[sid].items() if v is not None})
        records.append(merged)

        if i % 100 == 0 or i == len(ids):
            print("  進捗 %d/%d (新規取得 %d / キャッシュ %d / 失敗 %d)" % (i, len(ids), fetched, cached, failed))

    payload = {
        "generated_at": datetime.datetime.now(JST).isoformat(timespec="seconds"),
        "source": "Jグランツ（デジタル庁）",
        "source_url": "https://www.jgrants-portal.go.jp/",
        "count": len(records),
        "subsidies": records,
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=1)

    size_mb = os.path.getsize(OUT_FILE) / 1024.0 / 1024.0
    print("\n✓ 保存しました: %s (%d件, %.1fMB)" % (OUT_FILE, len(records), size_mb))
    return 0


if __name__ == "__main__":
    sys.exit(main())
