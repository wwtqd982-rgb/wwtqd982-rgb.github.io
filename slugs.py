# -*- coding: utf-8 -*-
"""URLに使うASCIIスラッグの対応表。"""
import hashlib

PREF_SLUG = {
    "全国": "all", "北海道": "hokkaido", "青森県": "aomori", "岩手県": "iwate",
    "宮城県": "miyagi", "秋田県": "akita", "山形県": "yamagata", "福島県": "fukushima",
    "茨城県": "ibaraki", "栃木県": "tochigi", "群馬県": "gunma", "埼玉県": "saitama",
    "千葉県": "chiba", "東京都": "tokyo", "神奈川県": "kanagawa", "新潟県": "niigata",
    "富山県": "toyama", "石川県": "ishikawa", "福井県": "fukui", "山梨県": "yamanashi",
    "長野県": "nagano", "岐阜県": "gifu", "静岡県": "shizuoka", "愛知県": "aichi",
    "三重県": "mie", "滋賀県": "shiga", "京都府": "kyoto", "大阪府": "osaka",
    "兵庫県": "hyogo", "奈良県": "nara", "和歌山県": "wakayama", "鳥取県": "tottori",
    "島根県": "shimane", "岡山県": "okayama", "広島県": "hiroshima", "山口県": "yamaguchi",
    "徳島県": "tokushima", "香川県": "kagawa", "愛媛県": "ehime", "高知県": "kochi",
    "福岡県": "fukuoka", "佐賀県": "saga", "長崎県": "nagasaki", "熊本県": "kumamoto",
    "大分県": "oita", "宮崎県": "miyazaki", "鹿児島県": "kagoshima", "沖縄県": "okinawa",
}

INDUSTRY_SLUG = {
    "農業、林業": "nogyo", "漁業": "gyogyo", "鉱業、採石業、砂利採取業": "kogyo",
    "建設業": "kensetsu", "製造業": "seizo", "電気・ガス・熱供給・水道業": "denki-gas",
    "情報通信業": "joho-tsushin", "運輸業、郵便業": "unyu", "卸売業、小売業": "oroshi-kouri",
    "金融業、保険業": "kinyu-hoken", "不動産業、物品賃貸業": "fudosan",
    "学術研究、専門・技術サービス業": "gakujutsu", "宿泊業、飲食サービス業": "shukuhaku-inshoku",
    "生活関連サービス業、娯楽業": "seikatsu-goraku", "教育、学習支援業": "kyoiku",
    "医療、福祉": "iryo-fukushi", "複合サービス事業": "fukugo-service",
    "サービス業（他に分類されないもの）": "service-other",
    "公務（他に分類されるものを除く）": "komu", "分類不能の産業": "bunrui-funo",
}

PURPOSE_SLUG = {
    "新たな事業を行いたい": "new-business",
    "研究開発・実証事業を行いたい": "kenkyu-kaihatsu",
    "販路拡大・海外展開をしたい": "hanro-kaigai",
    "設備整備・IT導入をしたい": "setsubi-it",
    "人材育成を行いたい": "jinzai-ikusei",
    "雇用・職場環境を改善したい": "koyo-shokuba",
    "事業継承を行いたい": "jigyo-shokei",
    "経営を改善したい": "keiei-kaizen",
    "エコ・SDGs活動支援をしたい": "eco-sdgs",
    "地域活性化を行いたい": "chiiki-kasseika",
    "災害（自然災害・感染症等）支援を受けたい": "saigai",
    "資金繰りを改善したい": "shikinguri",
}


def slugify(value, table):
    """対応表にあればそれを、なければ安定したハッシュを返す。"""
    if value in table:
        return table[value]
    h = hashlib.md5(value.encode("utf-8")).hexdigest()[:10]
    return "x" + h
