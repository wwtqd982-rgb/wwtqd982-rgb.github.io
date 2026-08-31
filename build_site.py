# -*- coding: utf-8 -*-
"""
data/subsidies.json から静的サイトを public/ に生成する。
標準ライブラリのみ。pip install 不要。
"""
import html
import json
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser

from slugs import PREF_SLUG, INDUSTRY_SLUG, PURPOSE_SLUG, slugify

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(HERE, "data", "subsidies.json")
OUT = os.path.join(HERE, "public")
JST = timezone(timedelta(hours=9))

# ---- サイト設定（公開時にここだけ書き換える） -------------------------------
SITE_NAME = "補助金サーチ"
SITE_DESC = "全国の募集中の補助金・助成金を、締切が近い順・金額順で探せる無料の検索サイト。国のJグランツの公開データを毎日自動更新しています。"


def resolve_site_url():
    """公開URLを決める。優先順は 環境変数SITE_URL > GitHub Actions > ローカル。

    生成HTMLのリンクは "/" 起点の絶対パスなので、サイトはドメイン直下に
    置く必要がある。サブディレクトリ配信にすると全リンクが壊れる。
    """
    env = os.environ.get("SITE_URL", "").strip()
    if env:                                    # 独自ドメインを使う場合
        return env.rstrip("/")
    repo = os.environ.get("GITHUB_REPOSITORY", "")   # "owner/name" 形式
    if "/" in repo:
        owner, name = repo.split("/", 1)
        owner = owner.lower()
        if name.lower() == owner + ".github.io":     # ユーザーサイト = ドメイン直下
            return "https://%s.github.io" % owner
        return "https://%s.github.io/%s" % (owner, name)   # プロジェクトサイト
    return "http://localhost:8000"             # ローカル生成時


SITE_URL = resolve_site_url()
OPERATOR = "（運営者名を入れてください）"
CONTACT = "（連絡用メールアドレスを入れてください）"
ADSENSE_CLIENT = ""   # 例: "ca-pub-1234567890123456"（審査通過後に設定）
# ---------------------------------------------------------------------------

SAFE_TAGS = {"p", "br", "strong", "b", "em", "i", "u", "ul", "ol", "li",
             "table", "thead", "tbody", "tr", "th", "td", "h3", "h4", "h5", "a"}
VOID_TAGS = {"br"}


class Sanitizer(HTMLParser):
    """APIのHTMLから危険なタグとインラインstyleを取り除く。"""

    def __init__(self):
        HTMLParser.__init__(self)
        self.out = []
        self.stack = []

    def handle_starttag(self, tag, attrs):
        if tag not in SAFE_TAGS:
            return
        if tag in VOID_TAGS:
            self.out.append("<br>")
            return
        if tag == "a":
            href = dict(attrs).get("href", "")
            if href.startswith(("http://", "https://")):
                self.out.append('<a href="%s" rel="nofollow noopener" target="_blank">'
                                % html.escape(href, quote=True))
            else:
                self.out.append("<span>")
                self.stack.append("span")
                return
        else:
            self.out.append("<%s>" % tag)
        self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID_TAGS or tag not in SAFE_TAGS:
            return
        if self.stack and self.stack[-1] in (tag, "span"):
            closing = self.stack.pop()
            self.out.append("</%s>" % closing)

    def handle_data(self, data):
        self.out.append(html.escape(data))

    def result(self):
        while self.stack:
            self.out.append("</%s>" % self.stack.pop())
        text = "".join(self.out)
        text = re.sub(r"(\s|&nbsp;|<br>)*(</p>)", r"\2", text)
        text = re.sub(r"<p>(\s|&nbsp;|<br>)*</p>", "", text)
        return text


def sanitize(raw):
    if not raw:
        return ""
    s = Sanitizer()
    s.feed(raw)
    return s.result()


def strip_tags(raw, limit=160):
    if not raw:
        return ""
    text = re.sub(r"<[^>]+>", "", raw)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def esc(v):
    return html.escape(v if v else "", quote=True)


def parse_dt(value):
    if not value:
        return None
    v = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(v).astimezone(JST)
    except ValueError:
        return None


def fmt_date(dt):
    return dt.strftime("%Y年%m月%d日") if dt else "未定"


def fmt_yen(v):
    if not v:
        return "記載なし"
    v = int(v)
    if v >= 100000000:
        oku = v / 100000000.0
        return ("%g億円" % round(oku, 2))
    if v >= 10000:
        return "%s万円" % format(v // 10000, ",")
    return "%s円" % format(v, ",")


def split_multi(value):
    if not value:
        return []
    return [p.strip() for p in value.split("/") if p.strip()]


def days_left(end_dt, now):
    if not end_dt:
        return None
    return (end_dt.date() - now.date()).days


def write(path, content):
    full = os.path.join(OUT, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


CSS = """
:root{--bg:#fbfaf8;--card:#fff;--ink:#1c1b19;--sub:#6b6862;--line:#e6e2db;
--accent:#1f6f5c;--accent-ink:#12503f;--warn:#b4451f;--chip:#f0ede7}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);
font-family:system-ui,-apple-system,"Hiragino Kaku Gothic ProN","Noto Sans JP",sans-serif;
line-height:1.75;font-size:16px}
a{color:var(--accent-ink)}
.wrap{max-width:960px;margin:0 auto;padding:0 16px}
header.site{background:var(--card);border-bottom:1px solid var(--line);padding:14px 0;
position:sticky;top:0;z-index:10}
header.site .wrap{display:flex;align-items:center;gap:16px;flex-wrap:wrap}
.logo{font-weight:700;font-size:18px;color:var(--ink);text-decoration:none;letter-spacing:.02em}
.logo span{color:var(--accent)}
nav.site a{margin-right:14px;font-size:14px;text-decoration:none;color:var(--sub)}
nav.site a:hover{color:var(--accent-ink)}
h1{font-size:26px;line-height:1.45;margin:24px 0 8px}
h2{font-size:19px;margin:36px 0 12px;padding-bottom:6px;border-bottom:2px solid var(--line)}
h3{font-size:16px;margin:24px 0 8px}
.lead{color:var(--sub);font-size:15px;margin:0 0 20px}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:16px 18px;margin-bottom:12px}
.card h3{margin:0 0 8px;font-size:17px;line-height:1.5}
.card h3 a{text-decoration:none;color:var(--ink)}
.card h3 a:hover{color:var(--accent-ink);text-decoration:underline}
.meta{display:flex;flex-wrap:wrap;gap:8px 16px;font-size:13px;color:var(--sub);margin-top:8px}
.meta b{color:var(--ink);font-weight:600}
.chips{margin-top:10px;display:flex;flex-wrap:wrap;gap:6px}
.chip{background:var(--chip);border-radius:999px;padding:2px 10px;font-size:12px;
color:var(--sub);text-decoration:none}
a.chip:hover{background:#e4dfd6;color:var(--ink)}
.badge{display:inline-block;font-size:12px;font-weight:700;border-radius:5px;
padding:2px 9px;vertical-align:middle}
.b-soon{background:#fdecdf;color:var(--warn)}
.b-open{background:#e3f0ea;color:var(--accent-ink)}
table.kv{width:100%;border-collapse:collapse;margin:16px 0;font-size:15px}
table.kv th,table.kv td{border:1px solid var(--line);padding:10px 12px;text-align:left;
vertical-align:top}
table.kv th{background:#f5f2ec;width:32%;font-weight:600;white-space:nowrap}
.detail{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:4px 18px 18px}
.detail p{font-size:15px}
.detail table{max-width:100%;border-collapse:collapse}
.detail td,.detail th{border:1px solid var(--line);padding:6px 8px;font-size:14px}
.cta{display:inline-block;background:var(--accent);color:#fff;text-decoration:none;
padding:11px 22px;border-radius:8px;font-weight:600;margin:8px 0}
.cta:hover{background:var(--accent-ink)}
.controls{background:var(--card);border:1px solid var(--line);border-radius:10px;
padding:14px;margin-bottom:18px;display:flex;flex-wrap:wrap;gap:10px}
.controls input,.controls select{font:inherit;font-size:15px;padding:9px 10px;
border:1px solid var(--line);border-radius:7px;background:#fff;color:var(--ink)}
.controls input{flex:1 1 240px;min-width:0}
.grid-links{display:grid;grid-template-columns:repeat(auto-fill,minmax(150px,1fr));gap:8px}
.grid-links a{background:var(--card);border:1px solid var(--line);border-radius:7px;
padding:9px 12px;text-decoration:none;font-size:14px;color:var(--ink)}
.grid-links a:hover{border-color:var(--accent);color:var(--accent-ink)}
.grid-links a i{font-style:normal;color:var(--sub);font-size:12px}
.ad{margin:24px 0;min-height:1px}
.note{font-size:13px;color:var(--sub);background:#f5f2ec;border-radius:8px;padding:12px 14px}
footer.site{margin-top:56px;border-top:1px solid var(--line);background:var(--card);
padding:24px 0;font-size:13px;color:var(--sub)}
footer.site a{color:var(--sub)}
.pager{text-align:center;margin:24px 0}
.pager button{font:inherit;padding:10px 24px;border:1px solid var(--line);background:var(--card);
border-radius:8px;cursor:pointer;color:var(--ink)}
.crumb{font-size:13px;color:var(--sub);margin:14px 0 0}
.crumb a{color:var(--sub)}
@media(max-width:600px){h1{font-size:21px}table.kv th{width:38%;white-space:normal}}
"""


def layout(title, desc, body, path, extra_head="", extra_body=""):
    canonical = SITE_URL.rstrip("/") + "/" + path.lstrip("/")
    canonical = canonical.replace("/index.html", "/")
    ads = ""
    if ADSENSE_CLIENT:
        ads = ('<script async src="https://pagead2.googlesyndication.com/pagead/js/'
               'adsbygoogle.js?client=%s" crossorigin="anonymous"></script>' % ADSENSE_CLIENT)
    return """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%(title)s</title>
<meta name="description" content="%(desc)s">
<link rel="canonical" href="%(canonical)s">
<meta property="og:title" content="%(title)s">
<meta property="og:description" content="%(desc)s">
<meta property="og:type" content="website">
<meta property="og:site_name" content="%(site)s">
<style>%(css)s</style>
%(ads)s%(extra_head)s
</head>
<body>
<header class="site"><div class="wrap">
<a class="logo" href="/">補助金<span>サーチ</span></a>
<nav class="site">
<a href="/deadline.html">締切が近い順</a>
<a href="/amount.html">金額が大きい順</a>
<a href="/area/">地域から探す</a>
<a href="/purpose/">目的から探す</a>
</nav>
</div></header>
<main class="wrap">
%(body)s
</main>
<footer class="site"><div class="wrap">
<p>%(site)s は、デジタル庁「Jグランツ」の公開APIで提供されている補助金データをもとに、
自動で毎日更新している非公式の検索サイトです。</p>
<p>出典：<a href="https://www.jgrants-portal.go.jp/" rel="nofollow noopener" target="_blank">Jグランツ（デジタル庁）</a>
／ 本サイトの掲載内容は正確性を保証するものではありません。
申請の際は必ず各補助金の公募要領および公式ページをご確認ください。</p>
<p><a href="/about.html">このサイトについて・運営者情報</a></p>
</div></footer>
%(extra_body)s
</body>
</html>""" % {
        "title": esc(title), "desc": esc(desc), "canonical": esc(canonical),
        "site": esc(SITE_NAME), "css": CSS, "ads": ads,
        "extra_head": extra_head, "body": body, "extra_body": extra_body,
    }


def ad_slot(label="ad"):
    return '<div class="ad" data-slot="%s"><!-- 広告枠：AdSense審査通過後にここにコードを貼る --></div>' % label


def normalize(raw, now):
    """APIの生レコードを、ページ生成しやすい形に整える。"""
    end = parse_dt(raw.get("acceptance_end_datetime"))
    start = parse_dt(raw.get("acceptance_start_datetime"))
    left = days_left(end, now)
    areas = split_multi(raw.get("target_area_search"))
    return {
        "id": raw.get("id") or "",
        "code": raw.get("name") or "",
        "title": (raw.get("title") or "").strip(),
        "catch": (raw.get("subsidy_catch_phrase") or "").strip(),
        "detail_html": sanitize(raw.get("detail")),
        "summary": strip_tags(raw.get("detail"), 110),
        "org": (raw.get("institution_name") or "").strip(),
        "areas": areas,
        "area_label": "、".join(areas) if areas else "指定なし",
        "purposes": split_multi(raw.get("use_purpose")),
        "industries": split_multi(raw.get("industry")),
        "employees": (raw.get("target_number_of_employees") or "").strip(),
        "rate": (raw.get("subsidy_rate") or "").strip(),
        "max_limit": raw.get("subsidy_max_limit") or 0,
        "start": start, "end": end, "days_left": left,
        "official": raw.get("front_subsidy_detail_page_url") or "",
    }


def short_rate(rate):
    """補助率は長文のことがあるので一覧では短縮する。"""
    r = (rate or "").strip()
    if not r:
        return "記載なし"
    r = r.split("※")[0].strip() or r
    return r if len(r) <= 20 else r[:20] + "…"


def badge(rec):
    d = rec["days_left"]
    if d is None:
        return '<span class="badge b-open">募集中</span>'
    if d < 0:
        return '<span class="badge b-soon">受付終了</span>'
    if d <= 14:
        return '<span class="badge b-soon">締切まであと%d日</span>' % d
    return '<span class="badge b-open">締切まであと%d日</span>' % d


def card(rec):
    chips = "".join(
        '<a class="chip" href="/purpose/%s.html">%s</a>' % (slugify(p, PURPOSE_SLUG), esc(p))
        for p in rec["purposes"][:3])
    return """<article class="card">
<h3>%(badge)s <a href="/s/%(id)s.html">%(title)s</a></h3>
<div class="meta">
<span>上限 <b>%(max)s</b></span>
<span>補助率 <b>%(rate)s</b></span>
<span>締切 <b>%(end)s</b></span>
<span>対象地域 <b>%(area)s</b></span>
</div>
<div class="chips">%(chips)s</div>
</article>""" % {
        "badge": badge(rec), "id": esc(rec["id"]), "title": esc(rec["title"]),
        "max": esc(fmt_yen(rec["max_limit"])), "rate": esc(short_rate(rec["rate"])),
        "end": fmt_date(rec["end"]), "area": esc(rec["area_label"][:40]), "chips": chips,
    }


def detail_page(rec, related):
    rows = [
        ("補助金の上限額", fmt_yen(rec["max_limit"])),
        ("補助率", esc(rec["rate"] or "公募要領を参照")),
        ("募集開始", fmt_date(rec["start"])),
        ("募集締切", fmt_date(rec["end"]) + (
            "（あと%d日）" % rec["days_left"] if rec["days_left"] is not None and rec["days_left"] >= 0 else "")),
        ("対象地域", esc(rec["area_label"])),
        ("対象従業員数", esc(rec["employees"] or "記載なし")),
        ("実施機関", esc(rec["org"] or "記載なし")),
        ("補助金番号", esc(rec["code"])),
    ]
    kv = "".join("<tr><th>%s</th><td>%s</td></tr>" % (k, v) for k, v in rows)

    def linkchips(values, table, base):
        return "".join('<a class="chip" href="/%s/%s.html">%s</a>'
                       % (base, slugify(v, table), esc(v)) for v in values)

    purpose_chips = linkchips(rec["purposes"], PURPOSE_SLUG, "purpose")
    industry_chips = linkchips(rec["industries"], INDUSTRY_SLUG, "industry")
    area_chips = linkchips([a for a in rec["areas"] if a in PREF_SLUG], PREF_SLUG, "area")

    catch = ""
    if rec["catch"]:
        catch = '<p class="note">%s</p>' % esc(rec["catch"]).replace("\n", "<br>")

    official = ""
    if rec["official"]:
        official = ('<p><a class="cta" href="%s" rel="nofollow noopener" target="_blank">'
                    '公式ページで詳細を見る・申請する →</a></p>' % esc(rec["official"]))

    rel_html = "".join(card(r) for r in related)
    rel_block = ("<h2>関連する補助金</h2>" + rel_html) if rel_html else ""

    body = """<p class="crumb"><a href="/">補助金サーチ</a> ＞ 補助金の詳細</p>
<h1>%(title)s</h1>
<p class="lead">%(badge)s ／ 実施機関：%(org)s</p>
%(catch)s
<table class="kv">%(kv)s</table>
%(official)s
%(ad1)s
<h2>対象となる目的・業種</h2>
<div class="chips">%(pchips)s%(ichips)s%(achips)s</div>
<h2>制度の概要</h2>
<div class="detail">%(detail)s</div>
%(official2)s
<p class="note">この情報はJグランツ（デジタル庁）の公開データを自動取得したものです。
内容は変更される場合があります。申請前に必ず公式ページと公募要領をご確認ください。</p>
%(ad2)s
%(rel)s""" % {
        "title": esc(rec["title"]), "badge": badge(rec), "org": esc(rec["org"] or "記載なし"),
        "catch": catch, "kv": kv, "official": official, "official2": official,
        "pchips": purpose_chips, "ichips": industry_chips, "achips": area_chips,
        "detail": rec["detail_html"] or "<p>詳細情報は公式ページをご確認ください。</p>",
        "ad1": ad_slot("detail-top"), "ad2": ad_slot("detail-bottom"), "rel": rel_block,
    }
    desc = "%s（上限%s／締切%s）の概要・対象地域・補助率をまとめました。%s" % (
        rec["title"][:40], fmt_yen(rec["max_limit"]), fmt_date(rec["end"]), rec["summary"][:60])
    return layout("%s｜%s" % (rec["title"][:50], SITE_NAME), desc, body, "s/%s.html" % rec["id"])


def list_page(title, h1, desc, recs, path, intro=""):
    if recs:
        cards = "".join(card(r) for r in recs[:300])
        if len(recs) > 300:
            cards += '<p class="note">該当件数が多いため上位300件を表示しています。' \
                     '<a href="/">トップの検索</a>で絞り込んでください。</p>'
    else:
        cards = '<p class="note">現在、条件に合う募集中の補助金はありません。' \
                'データは毎日自動更新しているので、時間をおいて再度ご確認ください。</p>'
    body = """<p class="crumb"><a href="/">補助金サーチ</a> ＞ %(h1)s</p>
<h1>%(h1)s</h1>
<p class="lead">%(intro)s現在 <b>%(n)d件</b> の募集中の補助金があります。</p>
%(ad)s
%(cards)s""" % {"h1": esc(h1), "intro": intro, "n": len(recs),
                "ad": ad_slot("list-top"), "cards": cards}
    return layout(title, desc, body, path)


SEARCH_JS = """
(function(){
var DATA=[],view=[],shown=0,PAGE=40;
var q=document.getElementById('q'),area=document.getElementById('area'),
    purpose=document.getElementById('purpose'),sort=document.getElementById('sort'),
    list=document.getElementById('list'),count=document.getElementById('count'),
    more=document.getElementById('more');
function yen(v){if(!v)return'記載なし';
  if(v>=100000000)return(Math.round(v/1000000)/100)+'億円';
  if(v>=10000)return(v/10000).toLocaleString()+'万円';return v.toLocaleString()+'円';}
function badge(d){if(d===null||d===undefined)return'<span class="badge b-open">募集中</span>';
  if(d<0)return'<span class="badge b-soon">受付終了</span>';
  return'<span class="badge '+(d<=14?'b-soon':'b-open')+'">締切まであと'+d+'日</span>';}
function shortRate(r){r=(r||'').trim();if(!r)return'記載なし';
  r=r.split('※')[0].trim()||r;return r.length<=20?r:r.slice(0,20)+'…';}
function esc(s){return String(s).replace(/[&<>"]/g,function(c){
  return{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
function render(reset){
  if(reset){list.innerHTML='';shown=0;}
  var frag=document.createDocumentFragment();
  var end=Math.min(shown+PAGE,view.length);
  for(var i=shown;i<end;i++){var r=view[i];var el=document.createElement('article');
    el.className='card';
    el.innerHTML='<h3>'+badge(r.d)+' <a href="/s/'+r.id+'.html">'+esc(r.t)+'</a></h3>'+
      '<div class="meta"><span>上限 <b>'+yen(r.m)+'</b></span>'+
      '<span>補助率 <b>'+esc(shortRate(r.r))+'</b></span>'+
      '<span>締切 <b>'+esc(r.e||'未定')+'</b></span>'+
      '<span>対象地域 <b>'+esc((r.a||[]).join('、').slice(0,40)||'指定なし')+'</b></span></div>';
    frag.appendChild(el);}
  list.appendChild(frag);shown=end;
  more.style.display=shown<view.length?'':'none';
  more.textContent='さらに表示（残り'+(view.length-shown)+'件）';}
function apply(){
  var kw=q.value.trim().toLowerCase(),av=area.value,pv=purpose.value;
  view=DATA.filter(function(r){
    if(av&&(r.a||[]).indexOf(av)<0&&(r.a||[]).indexOf('全国')<0)return false;
    if(pv&&(r.p||[]).indexOf(pv)<0)return false;
    if(kw&&(r.t+' '+(r.o||'')).toLowerCase().indexOf(kw)<0)return false;
    return true;});
  var s=sort.value;
  view.sort(function(x,y){
    if(s==='amount')return(y.m||0)-(x.m||0);
    var a=x.d===null?9999:x.d,b=y.d===null?9999:y.d;
    return a-b;});
  count.textContent=view.length.toLocaleString();
  render(true);}
[q,area,purpose,sort].forEach(function(el){
  el.addEventListener('input',apply);el.addEventListener('change',apply);});
more.addEventListener('click',function(){render(false);});
fetch('/search-index.json').then(function(r){return r.json();}).then(function(d){
  DATA=d;apply();}).catch(function(){
  list.innerHTML='<p class="note">データの読み込みに失敗しました。'+
  'ページを再読み込みしてください。</p>';});
})();
"""


def index_page(recs, now, areas_count, purposes_count):
    area_opts = "".join('<option value="%s">%s（%d件）</option>' % (esc(a), esc(a), n)
                        for a, n in areas_count)
    purpose_opts = "".join('<option value="%s">%s（%d件）</option>' % (esc(p), esc(p), n)
                           for p, n in purposes_count)
    soon = [r for r in recs if r["days_left"] is not None and 0 <= r["days_left"] <= 14]
    body = """<h1>募集中の補助金・助成金をまとめて検索</h1>
<p class="lead">国のJグランツで公開されている補助金データから、いま応募できるものだけを
<b>%(n)d件</b>掲載しています。締切が近い順・金額が大きい順に並べ替えて、
地域や目的で絞り込めます。%(soon)s
データは毎日自動更新（最終更新：%(updated)s）。</p>
<div class="controls">
<input id="q" type="search" placeholder="キーワードで検索（例：省エネ、創業、IT導入）" aria-label="キーワード検索">
<select id="area" aria-label="対象地域"><option value="">全ての地域</option>%(areas)s</select>
<select id="purpose" aria-label="目的"><option value="">全ての目的</option>%(purposes)s</select>
<select id="sort" aria-label="並び替え">
<option value="deadline">締切が近い順</option>
<option value="amount">金額が大きい順</option>
</select>
</div>
<p class="lead"><b id="count">%(n)d</b>件が該当しています。</p>
%(ad)s
<div id="list"></div>
<div class="pager"><button id="more" type="button">さらに表示</button></div>
<h2>地域から探す</h2>
<div class="grid-links">%(arealinks)s</div>
<h2>目的から探す</h2>
<div class="grid-links">%(purposelinks)s</div>
<h2>このサイトについて</h2>
<p>補助金の公式データベースであるJグランツは情報が正確な一方で、
「締切が近いものだけ見たい」「金額の大きい順に並べたい」といった探し方ができません。
本サイトはその公開データを毎日自動で取得し、締切・金額・地域・目的で
すばやく絞り込めるように整理し直したものです。掲載しているのは
<b>現在応募を受け付けている補助金のみ</b>で、受付が終了したものは自動的に除外されます。</p>
<p class="note">出典：Jグランツ（デジタル庁）。本サイトは非公式のサービスです。
掲載情報の正確性・最新性は保証できませんので、申請の際は必ず公式ページと
公募要領をご確認ください。</p>""" % {
        "n": len(recs),
        "soon": ("いま締切まで2週間以内のものが%d件あります。" % len(soon)) if soon else "",
        "updated": now.strftime("%Y年%m月%d日"),
        "areas": area_opts, "purposes": purpose_opts, "ad": ad_slot("index-top"),
        "arealinks": "".join(
            '<a href="/area/%s.html">%s <i>%d</i></a>' % (slugify(a, PREF_SLUG), esc(a), n)
            for a, n in areas_count),
        "purposelinks": "".join(
            '<a href="/purpose/%s.html">%s <i>%d</i></a>' % (slugify(p, PURPOSE_SLUG), esc(p), n)
            for p, n in purposes_count),
    }
    return layout("%s｜募集中の補助金・助成金を締切順で検索" % SITE_NAME, SITE_DESC,
                  body, "index.html",
                  extra_body="<script>%s</script>" % SEARCH_JS)


def about_page(now, total):
    body = """<p class="crumb"><a href="/">補助金サーチ</a> ＞ このサイトについて</p>
<h1>このサイトについて・運営者情報</h1>
<h2>サイトの概要</h2>
<p>%(site)sは、デジタル庁が運営する補助金申請システム「Jグランツ」が公開している
オープンAPIのデータを利用して、現在募集中の補助金・助成金を検索できるようにした
個人運営の非公式サイトです。現在 %(n)d件を掲載しています。</p>
<h2>データの出典と更新頻度</h2>
<p>出典：<a href="https://www.jgrants-portal.go.jp/" rel="nofollow noopener" target="_blank">Jグランツ（デジタル庁）</a>
の公開API。データは1日1回自動で取得・更新しています（最終更新：%(updated)s）。
公開データの利用にあたっては政府標準利用規約に基づき出典を明示しています。</p>
<h2>免責事項</h2>
<p>掲載情報は自動取得したものであり、正確性・完全性・最新性を保証するものではありません。
補助金の要件・金額・締切は変更されることがあります。実際に申請される際は、
必ず各補助金の公式ページおよび公募要領をご確認ください。
本サイトの情報を利用したことにより生じた損害について、運営者は一切の責任を負いません。</p>
<h2>補助金の申請代行について</h2>
<p>本サイトは情報提供のみを行っており、補助金の申請代行・コンサルティングは行っていません。</p>
<h2>広告について</h2>
<p>本サイトでは第三者配信の広告サービスを利用する場合があります。
広告配信事業者はユーザーの興味に応じた広告を表示するためにCookieを使用することがあります。</p>
<h2>運営者情報</h2>
<table class="kv">
<tr><th>運営者</th><td>%(operator)s</td></tr>
<tr><th>連絡先</th><td>%(contact)s</td></tr>
</table>
<p class="note">※ 有料サービスを開始する場合は、特定商取引法に基づく表記をこのページに追加してください。</p>""" % {
        "site": esc(SITE_NAME), "n": total, "updated": now.strftime("%Y年%m月%d日"),
        "operator": esc(OPERATOR), "contact": esc(CONTACT),
    }
    return layout("このサイトについて｜%s" % SITE_NAME,
                  "補助金サーチの運営者情報、データの出典、免責事項について。", body, "about.html")


def hub_page(title, h1, items, base, table, path, desc):
    links = "".join('<a href="/%s/%s.html">%s <i>%d件</i></a>'
                    % (base, slugify(k, table), esc(k), n) for k, n in items)
    body = """<p class="crumb"><a href="/">補助金サーチ</a> ＞ %(h1)s</p>
<h1>%(h1)s</h1>
<p class="lead">募集中の補助金を%(h1)s一覧にまとめました。</p>
%(ad)s
<div class="grid-links">%(links)s</div>""" % {
        "h1": esc(h1), "ad": ad_slot("hub"), "links": links}
    return layout(title, desc, body, path)


def build_sitemap(paths, now):
    lastmod = now.strftime("%Y-%m-%d")
    urls = []
    for p, prio in paths:
        loc = SITE_URL.rstrip("/") + "/" + p.lstrip("/")
        loc = loc.replace("/index.html", "/")
        urls.append("<url><loc>%s</loc><lastmod>%s</lastmod><priority>%s</priority></url>"
                    % (html.escape(loc, quote=True), lastmod, prio))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n%s\n</urlset>\n'
            % "\n".join(urls))


def main():
    if not os.path.exists(DATA_FILE):
        print("!! %s がありません。先に fetch_data.py を実行してください。" % DATA_FILE)
        return 1

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        payload = json.load(f)

    now = datetime.now(JST)
    recs = [normalize(r, now) for r in payload.get("subsidies", [])]
    recs = [r for r in recs if r["id"] and r["title"]]
    # 受付終了済みは掲載しない（内容の薄いページを増やさないため）
    recs = [r for r in recs if r["days_left"] is None or r["days_left"] >= 0]
    print("■ 掲載対象: %d件" % len(recs))

    by_deadline = sorted(recs, key=lambda r: (r["days_left"] is None, r["days_left"] or 0))
    by_amount = sorted(recs, key=lambda r: -(r["max_limit"] or 0))

    def tally(key):
        counts = {}
        for r in recs:
            for v in r[key]:
                counts[v] = counts.get(v, 0) + 1
        return counts

    area_counts = tally("areas")
    purpose_counts = tally("purposes")
    industry_counts = tally("industries")

    pref_order = [p for p in PREF_SLUG if p in area_counts]
    areas_sorted = [(p, area_counts[p]) for p in pref_order]
    purposes_sorted = sorted(purpose_counts.items(), key=lambda kv: -kv[1])
    industries_sorted = sorted(industry_counts.items(), key=lambda kv: -kv[1])

    sitemap = [("index.html", "1.0"), ("deadline.html", "0.9"),
               ("amount.html", "0.8"), ("about.html", "0.3"),
               ("area/index.html", "0.7"), ("purpose/index.html", "0.7"),
               ("industry/index.html", "0.6")]

    # --- トップと主要一覧 ---
    write("index.html", index_page(by_deadline, now, areas_sorted, purposes_sorted))
    write("deadline.html", list_page(
        "締切が近い補助金一覧｜%s" % SITE_NAME, "締切が近い補助金",
        "応募締切が近い順に並べた、募集中の補助金・助成金の一覧です。", by_deadline,
        "deadline.html", intro="締切が早いものから順に並べています。"))
    write("amount.html", list_page(
        "補助金額が大きい補助金一覧｜%s" % SITE_NAME, "金額が大きい補助金",
        "補助金の上限額が大きい順に並べた、募集中の補助金・助成金の一覧です。", by_amount,
        "amount.html", intro="上限額が大きいものから順に並べています。"))
    write("about.html", about_page(now, len(recs)))

    # --- 個別ページ ---
    for i, rec in enumerate(recs, 1):
        related = [r for r in by_deadline
                   if r["id"] != rec["id"] and set(r["purposes"]) & set(rec["purposes"])][:3]
        write("s/%s.html" % rec["id"], detail_page(rec, related))
        sitemap.append(("s/%s.html" % rec["id"], "0.6"))
        if i % 500 == 0:
            print("  個別ページ %d/%d" % (i, len(recs)))

    # --- 分類ページ ---
    groups = [
        ("area", PREF_SLUG, areas_sorted, "areas", "%sの補助金・助成金",
         "%sが対象の、募集中の補助金・助成金の一覧です。締切順・金額順で確認できます。"),
        ("purpose", PURPOSE_SLUG, purposes_sorted, "purposes", "「%s」ための補助金",
         "%s事業者向けの、募集中の補助金・助成金の一覧です。"),
        ("industry", INDUSTRY_SLUG, industries_sorted, "industries", "%s向けの補助金",
         "%sを対象にした、募集中の補助金・助成金の一覧です。"),
    ]
    for base, table, items, key, h1fmt, descfmt in groups:
        for value, _n in items:
            subset = [r for r in by_deadline if value in r[key]]
            if base == "area" and value != "全国":
                subset = [r for r in by_deadline if value in r["areas"] or "全国" in r["areas"]]
            h1 = h1fmt % value
            path = "%s/%s.html" % (base, slugify(value, table))
            write(path, list_page("%s｜%s" % (h1, SITE_NAME), h1, descfmt % value,
                                  subset, path))
            sitemap.append((path, "0.5"))
        print("  %s ページ %d件" % (base, len(items)))

    write("area/index.html", hub_page("地域から補助金を探す｜%s" % SITE_NAME, "地域から探す",
          areas_sorted, "area", PREF_SLUG, "area/index.html",
          "都道府県ごとに、募集中の補助金・助成金を探せます。"))
    write("purpose/index.html", hub_page("目的から補助金を探す｜%s" % SITE_NAME, "目的から探す",
          purposes_sorted, "purpose", PURPOSE_SLUG, "purpose/index.html",
          "設備投資、人材育成、販路拡大など目的別に補助金を探せます。"))
    write("industry/index.html", hub_page("業種から補助金を探す｜%s" % SITE_NAME, "業種から探す",
          industries_sorted, "industry", INDUSTRY_SLUG, "industry/index.html",
          "製造業、建設業、飲食業など業種別に補助金を探せます。"))

    # --- 検索用インデックス ---
    index = [{
        "id": r["id"], "t": r["title"], "a": r["areas"], "p": r["purposes"],
        "m": r["max_limit"], "r": short_rate(r["rate"]),
        "e": r["end"].strftime("%Y年%m月%d日") if r["end"] else "",
        "d": r["days_left"], "o": r["org"],
    } for r in by_deadline]
    write("search-index.json", json.dumps(index, ensure_ascii=False, separators=(",", ":")))

    write("robots.txt", "User-agent: *\nAllow: /\n\nSitemap: %s/sitemap.xml\n"
          % SITE_URL.rstrip("/"))
    write("sitemap.xml", build_sitemap(sitemap, now))

    total = sum(len(files) for _, _, files in os.walk(OUT))
    print("\n✓ 生成しました: %s（%d ファイル / URL %d本）" % (OUT, total, len(sitemap)))
    if SITE_URL.startswith("http://localhost"):
        print("※ ローカル生成のため URL は %s として出力しました。" % SITE_URL)
        print("   GitHub Actions 上ではリポジトリ名から自動設定されます。")
    elif SITE_URL.rstrip("/").count("/") > 2:
        print("!! %s はサブディレクトリ配信です。" % SITE_URL)
        print("   ページ内リンクが \"/\" 起点のため、このままでは全リンクが404になります。")
        print("   リポジトリ名を <ユーザー名>.github.io にするか、独自ドメインを設定してください。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
