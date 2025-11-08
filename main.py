from fastapi import FastAPI, Query
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup

# ====== ДОБАВЛЕНО ======
import concurrent.futures
from urllib.parse import quote
import re, os
from typing import List, Dict

# Общие заголовки, чтобы меньше блокировали
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/127.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ru,en;q=0.9,zh;q=0.8",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}
SESSION = requests.Session()
SESSION.headers.update(DEFAULT_HEADERS)
TIMEOUT = 12
MAX_WORKERS = 16
MAX_RESULTS = 500

# КЛЮЧИ (ставь на Render → Environment)
APIFY_TOKEN = os.getenv("APIFY_TOKEN", "").strip()
SERPAPI_KEY = os.getenv("SERPAPI_KEY", "").strip()
# ====== /ДОБАВЛЕНО ======


app = FastAPI(
    title="DI-Agent SDK",
    description="Интеллектуальный агент для анализа поставщиков Китая",
    version="2.0.0"
)

# 🔹 Модель данных для запроса
class SearchRequest(BaseModel):
    query: str

# 🔹 Безопасный запрос страницы
def safe_request(url):
    try:
        r = SESSION.get(url, timeout=TIMEOUT)
        if r.status_code == 200:
            return r.text
        else:
            print(f"⚠️ Ошибка {r.status_code} при загрузке {url}")
            return ""
    except Exception as e:
        print(f"❌ Ошибка при запросе {url}: {e}")
        return ""

# 🔹 Парсинг списка компаний (твой исходный парсер — НЕ ТРОГАЛ)
def parse_suppliers(html, selectors, source):
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    titles, links = [], []

    for sel in selectors:
        for t in soup.select(sel["title"]):
            title = t.get_text(strip=True)
            if title and title not in titles:
                titles.append(title)
        for a in soup.select(sel["link"]):
            href = a.get("href")
            if href and href not in links:
                links.append(href)

    suppliers = []
    for i in range(min(5, len(titles))):
        suppliers.append({
            "Название": titles[i],
            "Ссылка": links[i] if i < len(links) else "N/A",
            "Источник": source
        })
    return suppliers

# ====== ДОБАВЛЕНО: гибкий парсер под разные сайты ======
GENERIC_SELECTORS = [
    {"title": "h2 a", "link": "h2 a"},
    {"title": ".title a", "link": ".title a"},
    {"title": ".product-title a", "link": ".product-title a"},
    {"title": ".company-name a", "link": ".company-name a"},
    {"title": "a.gs-product-card__name", "link": "a.gs-product-card__name"},
    {"title": ".organic-gallery-title a", "link": ".organic-gallery-title a"},
    {"title": "h3 a", "link": "h3 a"},
    {"title": "a", "link": "a"},
]

def parse_flexible(html: str, source: str) -> List[Dict]:
    if not html:
        return []
    soup = BeautifulSoup(html, "lxml")
    results: List[Dict] = []
    seen = set()

    for sel in GENERIC_SELECTORS:
        for a in soup.select(sel["link"]):
            href = a.get("href", "").strip()
            title = a.get_text(" ", strip=True)
            if not href or not title:
                continue
            if href.startswith("//"):
                href = "https:" + href
            if not href.startswith("http"):
                continue
            key = (title, href)
            if key in seen:
                continue
            seen.add(key)
            results.append({
                "Название": title[:200],
                "Ссылка": href,
                "Источник": source
            })
            if len(results) >= 50:
                break
        if len(results) >= 50:
            break
    return results
# ====== /ДОБАВЛЕНО ======


@app.get("/")
def root():
    return {
        "status": "✅ DI-Agent SDK активен",
        "docs": "/docs",
        "search_example": "/search?q=ЛСТК"
    }


# ====== ДОБАВЛЕНО: список 70+ источников (B2B/каталоги/поиски) ======
SOURCES: Dict[str, str] = {
    # Крупные B2B
    "Alibaba": "https://www.alibaba.com/trade/search?fsb=y&IndexArea=product_en&searchText={q}",
    "Made-in-China": "https://www.made-in-china.com/search?word={q}",
    "GlobalSources": "https://www.globalsources.com/searchList?query={q}",
    "1688 (via Baidu)": "https://www.baidu.com/s?wd={q}+site:1688.com",
    "HKTDC": "https://sourcing.hktdc.com/Search-Product?keyword={q}",
    "ECVV": "https://www.ecvv.com/catalog/{q}.html",
    "ECER": "https://www.ecer.com/search?kw={q}",
    "HC360": "https://s.hc360.com/seller/search.html?kwd={q}",
    "DHgate": "https://www.dhgate.com/wholesale/search.do?act=search&searchkey={q}",
    "YiwuGo": "https://en.yiwugo.com/search/{q}.html",
    "TradeKey": "https://www.tradekey.com/suppliers/{q}.html",
    "ExportHub": "https://www.exporthub.com/search?q={q}",
    "TradeWheel": "https://www.tradewheel.com/search/{q}/",
    "En.China.cn": "https://en.china.cn/search.html?searchKey={q}",
    "Hisupplier": "https://www.hisupplier.com/wholesale/{q}/",
    "Epoly": "https://www.etwinternational.com/search?kw={q}",
    "Globalspec": "https://www.globalspec.com/Search/Results?query={q}",
    "ThomasNet": "https://www.thomasnet.com/search.html?what={q}",
    "Kompass": "https://us.kompass.com/en/searchCompanies/companies/{q}/",
    "Qcc (companies)": "https://www.qcc.com/web/search?key={q}",
    "Tianyancha": "https://www.tianyancha.com/search?key={q}",

    # Маркеты Китая
    "JD": "https://search.jd.com/Search?keyword={q}",
    "Taobao": "https://s.taobao.com/search?q={q}",
    "Pinduoduo": "https://mobile.yangkeduo.com/search_result.html?search_key={q}",

    # Проф. каталоги/биржи/тендеры
    "MFG": "https://www.mfg.com/en/search/?q={q}",
    "AliExpress B2B": "https://www.aliexpress.com/wholesale?SearchText={q}",
    "Globalsources Verified": "https://www.globalsources.com/searchList?query={q}&verifiedSupplier=true",
    "Baidu Baike": "https://baike.baidu.com/search?word={q}",
    "Sohu": "https://www.sogou.com/web?query={q}",
    "Bing China": "https://cn.bing.com/search?q={q}",
    "Google (backup)": "https://www.google.com/search?q={q}",

    # Ещё B2B/агрегаторы
    "E-WorldTrade": "https://www.eworldtrade.com/search/{q}/",
    "China.cn": "https://www.china.cn/search.html?searchKey={q}",
    "B2BManufactures": "https://www.manufacturers.com.tw/search.php?words={q}",
    "Maker-In-China": "https://www.maker-in-china.com/search.html?kw={q}",
    "Manufacturers Directory": "https://www.manufacturersdirectory.com/search?query={q}",
    "IndiaMART": "https://dir.indiamart.com/search.mp?ss={q}",
    "TradeIndia": "https://www.tradeindia.com/search.html?search_text={q}",
    "ECPlaza": "https://www.ecplaza.net/search/1?keyword={q}",
    "YellowPages": "https://www.yellowpages.com/search?search_terms={q}",
    "B2Brazil": "https://b2brazil.com/hotsite/search?term={q}",
    "B2BMit": "https://www.b2bmit.com/search.html?q={q}",
    "Globalsources Suppliers": "https://www.globalsources.com/suppliers?query={q}",
    "AliBaba Suppliers": "https://www.alibaba.com/company_directory/search/{q}.html",
    "CantonFair": "https://www.cantonfair.org.cn/en-US/search?key={q}",
    "HKTDC Suppliers": "https://sourcing.hktdc.com/en/supplier-search/{q}",
    "Europages": "https://www.europages.com/companies/{q}.html",
    "Kompass CN": "https://cn.kompass.com/en/searchCompanies/companies/{q}/",
    "Made-in-China Companies": "https://www.made-in-china.com/company-search/?word={q}",
    "MIC Verified": "https://www.made-in-china.com/company-search/?word={q}&select=verified",
    "GlobalMarket": "https://www.globalmarket.com/search/{q}.html",
    "EtradeAsia": "https://www.etradeasia.com/search?keyword={q}",
    "Mawoo": "https://www.made-in-asia.net/search?kw={q}",
    "EveryChina": "https://www.everychina.com/search.html?kw={q}",
    "ChinaProducts": "https://www.china-products-manufacturers.com/search?keyword={q}",
    "Crov": "https://www.crov.com/search?q={q}",
    "DiyTrade": "https://www.diytrade.com/china/search/products.do?keyword={q}",
    "Okchem": "https://www.okchem.com/search?keyword={q}",
    "ChemNet": "https://www.chemnet.com/global/en/search.html?keyword={q}",
    "Food2China": "https://www.food2china.com/search?keyword={q}",
    "PharmaSources": "https://www.pharmasources.com/searchResult?keyword={q}",
    "MedicaTradeFair": "https://www.medica-tradefair.com/vis/v1/en/search?term={q}",
    "HKTDC Products": "https://sourcing.hktdc.com/Search-Product?keyword={q}&productonly=1",
}

# Точечные селекторы для нескольких ключевых площадок (остальные — гибкий парсер)
SITE_SELECTORS: Dict[str, List[Dict[str, str]]] = {
    "Alibaba": [{"title": ".organic-gallery-title", "link": ".organic-gallery-title a"}],
    "Made-in-China": [{"title": ".company-name a", "link": ".company-name a"}],
    "GlobalSources": [{"title": "a.gs-product-card__name", "link": "a.gs-product-card__name"}],
    "1688 (via Baidu)": [{"title": "h3.t a", "link": "h3.t a"}],
    "HKTDC": [{"title": ".product-name a, .cmpny-name a", "link": ".product-name a, .cmpny-name a"}],
    "ECER": [{"title": ".pro-title a, .supplier-name a", "link": ".pro-title a, .supplier-name a"}],
    "ECVV": [{"title": ".pro-title a, .company a", "link": ".pro-title a, .company a"}],
    "HC360": [{"title": ".search-list .title a", "link": ".search-list .title a"}],
    "DHgate": [{"title": ".item-title a", "link": ".item-title a"}],
    "YiwuGo": [{"title": ".title a", "link": ".title a"}],
    "TradeWheel": [{"title": ".item-title a", "link": ".item-title a"}],
    "ExportHub": [{"title": "h4.media-heading a", "link": "h4.media-heading a"}],
}

# Быстрый перевод частых русских материалов в англ-запросы
def normalize_query(q: str) -> str:
    if re.search(r"[А-Яа-яЁё]", q):
        low = q.lower()
        mapping = {
            "фиброцем": "fiber cement panels",
            "пенобетон": "foam concrete",
            "лстк": "light gauge steel frame",
            "сэндвич": "sandwich panels",
            "оцинкован": "galvanized steel",
            "алюкобонд": "aluminum composite panel",
        }
        for k, v in mapping.items():
            if k in low:
                return v
    return q

# ====== ДОБАВЛЕНО: Соц-источники через официальные/разрешённые API ======
def serpapi_site_search(query: str, site: str, source_name: str) -> List[Dict]:
    """Site: search через SerpAPI (реальные ссылки + сниппеты + иногда картинки)."""
    if not SERPAPI_KEY:
        return []
    try:
        params = {
            "engine": "google",
            "q": f"site:{site} {query}",
            "num": 10,
            "api_key": SERPAPI_KEY
        }
        r = requests.get("https://serpapi.com/search.json", params=params, timeout=12)
        js = r.json()
        out = []
        for item in js.get("organic_results", []):
            title = item.get("title")
            link = item.get("link")
            if not title or not link:
                continue
            out.append({
                "Название": title,
                "Ссылка": link,
                "Источник": source_name
            })
        return out
    except Exception as e:
        print(f"❌ SerpAPI {source_name}: {e}")
        return []

def apify_instagram_search(query: str) -> List[Dict]:
    """Public Instagram via Apify actor (официальный способ получения публичных профилей/постов)."""
    if not APIFY_TOKEN:
        return []
    try:
        url = f"https://api.apify.com/v2/acts/apify~instagram-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
        payload = {
            "search": query,
            "resultsType": "posts",
            "profilesType": "hashtag",
            "resultsLimit": 10
        }
        r = requests.post(url, json=payload, timeout=30)
        items = r.json() if r.status_code == 200 else []
        out = []
        for it in items:
            title = it.get("caption") or it.get("ownerUsername") or "Instagram result"
            link = it.get("url") or it.get("shortCodeUrl")
            if not link:
                continue
            out.append({
                "Название": title[:200],
                "Ссылка": link,
                "Источник": "Instagram (Apify)"
            })
        return out
    except Exception as e:
        print(f"❌ Apify Instagram: {e}")
        return []

def apify_tiktok_search(query: str) -> List[Dict]:
    if not APIFY_TOKEN:
        return []
    try:
        url = f"https://api.apify.com/v2/acts/apify~tiktok-scraper/run-sync-get-dataset-items?token={APIFY_TOKEN}"
        payload = {
            "search": query,
            "resultsType": "videos",
            "resultsLimit": 10
        }
        r = requests.post(url, json=payload, timeout=30)
        items = r.json() if r.status_code == 200 else []
        out = []
        for it in items:
            title = it.get("desc") or it.get("authorName") or "TikTok result"
            link = it.get("webVideoUrl") or it.get("shareUrl")
            if not link:
                continue
            out.append({
                "Название": title[:200],
                "Ссылка": link,
                "Источник": "TikTok (Apify)"
            })
        return out
    except Exception as e:
        print(f"❌ Apify TikTok: {e}")
        return []

def social_collect(query: str) -> List[Dict]:
    q = normalize_query(query)
    results = []

    # Instagram/TikTok (через Apify)
    results += apify_instagram_search(q)
    results += apify_tiktok_search(q)

    # --- Через SerpAPI site: ---
    # NEW ↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓↓
    social_sites = {
        # 🔹 Западные соцсети
        "Telegram": "t.me",
        "WhatsApp": "wa.me",
        "YouTube": "youtube.com",
        "Facebook": "facebook.com",
        "Twitter (X)": "x.com",
        "Pinterest": "pinterest.com",
        "Reddit": "reddit.com",
        "LinkedIn": "linkedin.com/company",
        "Threads (Meta)": "threads.net",
        "Instagram (backup)": "instagram.com",
        "Snapchat": "snapchat.com",
        "Twitch": "twitch.tv",
        "Discord": "discord.com",
        "Tumblr": "tumblr.com",
        "Medium": "medium.com",

        # 🔹 Восточные и китайские
        "WeChat": "weixin.qq.com",
        "QQ": "qq.com",
        "Weibo": "weibo.com",
        "Douyin (CN TikTok)": "douyin.com",
        "Bilibili": "bilibili.com",
        "Zhihu": "zhihu.com",
        "Youku": "youku.com",
        "Xiaohongshu (RED)": "xiaohongshu.com",
        "Taobao Live": "live.taobao.com",
        "Kuaishou": "kuaishou.com",

        # 🔹 Российские и региональные
        "VK": "vk.com",
        "Odnoklassники": "ok.ru",
        "Rutube": "rutube.ru",
        "Yappy": "yappy.media",
        "Dzen": "dzen.ru",
    }

    for name, site in social_sites.items():
        results += serpapi_site_search(q, site, name)
    # NEW ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑

    return results
# ====== /ДОБАВЛЕНО ======

def _fetch_one(name: str, url: str) -> List[Dict]:
    html = safe_request(url)
    if name in SITE_SELECTORS:
        return parse_suppliers(html, SITE_SELECTORS[name], name)
    return parse_flexible(html, name)

def extended_collect(query: str) -> List[Dict]:
    q_norm = normalize_query(query)
    q_enc = quote(q_norm)

    tasks = {}
    results: List[Dict] = []

    # 1) Социальные источники (API) — реальные ссылки
    try:
        social = social_collect(q_norm)
        if social:
            print(f"✅ SOCIAL: {len(social)}")
            results.extend(social)
    except Exception as e:
        print(f"❌ SOCIAL error: {e}")

    # 2) B2B/каталоги/поисковые страницы
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as ex:
        for name, tmpl in SOURCES.items():
            url = tmpl.format(q=q_enc)
            tasks[ex.submit(_fetch_one, name, url)] = name

        for fut in concurrent.futures.as_completed(tasks):
            name = tasks[fut]
            try:
                chunk = fut.result() or []
                if chunk:
                    print(f"✅ {name}: {len(chunk)}")
                results.extend(chunk)
            except Exception as e:
                print(f"❌ {name}: {e}")

    # Дедупликация по полной ссылке
    uniq, seen = [], set()
    for item in results:
        link = (item.get("Ссылка") or "").strip()
        if not link or link in seen:
            continue
        seen.add(link)
        uniq.append(item)
        if len(uniq) >= MAX_RESULTS:
            break
    # <<< исправлено: возврат на уровне функции (не внутри цикла)
    return uniq


# 🔹 ПРЯМОЙ эндпоинт расширенного сбора (для GPT)
from fastapi.responses import PlainTextResponse

@app.get("/search_all", response_class=PlainTextResponse)
def search_all(q: str = Query(..., description="Полный сбор по 70+ источникам")):
    """Основной эндпоинт — принимает запрос q (например, LGSF)"""
    data = extended_collect(q)
    text_output = format_for_silent_agent_cards(data, q)
    return text_output


# ====== KEEP-ALIVE (чтобы Render не засыпал) ======
import threading, time

def keep_alive():
    """Периодически пингует сам сервер, чтобы Render не засыпал."""
    while True:
        try:
            requests.get("https://di-agent-sdk.onrender.com/", timeout=5)
            print("🔄 Keep-alive ping OK")
        except Exception as e:
            print(f"⚠️ Keep-alive error: {e}")
        time.sleep(300)  # каждые 5 минут

# Запускаем отдельный поток после старта FastAPI
threading.Thread(target=keep_alive, daemon=True).start()
# ====== /KEEP-ALIVE ======# ====== ДОБАВЛЕНО: формат вывода карточек SILENT SUPPLIER AGENT ======
import random
from datetime import datetime

def format_for_silent_agent_cards(results: List[Dict], query: str) -> str:
    """Создаёт текст с эмодзи и заголовком 'Полный сбор по 70+ источникам' без изменения существующего кода"""
    if not results:
        return f"❌ Нет данных. 📡 Полный сбор по 70+ источникам — запрос: \"{query}\""

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    out = [f"📡 Полный сбор по 70+ источникам — запрос: \"{query}\"\n────────────────────────────"]

    for i, r in enumerate(results[:5]):
        out.append(f"""{medals[i]} **TOP {i+1} — {r.get('Название', 'Unknown')}**
🌍 **Регион:** {r.get('Регион', '—')}
🏷️ **Продукт:** {r.get('Product', query)}
💰 **Цена:** {r.get('Price', '—')}
📦 **MOQ:** {r.get('MOQ', '—')}
🧾 **Сертификаты:** {r.get('Certificates', '—')}
📞 **Контакты:** WeChat: {r.get('WeChat', '')} | WhatsApp: {r.get('WhatsApp', '')} | Telegram: {r.get('Telegram', '')} | Email: {r.get('Email', '')} | Phone: {r.get('Phone', '')} | Website: {r.get('Ссылка', '')}
🧠 **Рейтинг:** {r.get('Rating', '—')} / 100
🔗 **Источник:** {r.get('Источник', '—')}
🖼️ [Image]({r.get('Image', 'https://via.placeholder.com/400x300?text=Supplier')})
────────────────────────────""")

    return "\n\n".join(out)
# ====== /ДОБАВЛЕНО ======
# ================== КОНЕЦ ТВОЕГО КОДА БЕЗ ИЗМЕНЕНИЙ ==================


# ================== ДОБАВЛЕНО НИЖЕ: КАРТОЧКИ В HTML ==================
# (ничего выше не меняет; отдельный эндпоинт с HTML-вёрсткой карточек)
from fastapi.responses import HTMLResponse as _HTMLResponse

@app.get("/search_all_html", response_class=_HTMLResponse)
def search_all_html(q: str = Query(..., description="Полный сбор по 70+ источникам (HTML карточки)")):
    data = extended_collect(q)
    if not data:
        return f"""
        <html><body style="font-family:Arial;max-width:900px;margin:40px auto;">
            <h2>❌ Нет данных по запросу: <b>{q}</b></h2>
        </body></html>
        """

    cards_html = []
    for i, r in enumerate(data[:5], start=1):
        name = r.get("Название", "Без названия")
        link = r.get("Ссылка", "")
        src  = r.get("Источник", "—")

        # Доп. поля — если когда-то появятся в данных, будут показаны; иначе "—"
        region = r.get("Регион", "—")
        price  = r.get("Price", "—")
        moq    = r.get("MOQ", "—")
        certs  = r.get("Certificates", "—")
        phone  = r.get("Phone", "—")
        email  = r.get("Email", "—")
        wa     = r.get("WhatsApp", "—")
        tg     = r.get("Telegram", "—")

        cards_html.append(f"""
        <div style="border:1px solid #e5e7eb;border-radius:12px;padding:16px;margin:18px 0;
                    box-shadow:0 2px 6px rgba(0,0,0,0.06);font-family:Arial,Helvetica,sans-serif;">
            <div style="display:flex;align-items:center;gap:8px;">
                <div style="font-size:20px;font-weight:700;">#{i}</div>
                <div style="font-size:18px;font-weight:700;line-height:1.2;">{name}</div>
            </div>
            <div style="margin-top:8px;color:#374151;">
                <div><b>Источник:</b> {src}</div>
                <div><b>Ссылка:</b> <a href="{link}" target="_blank" rel="noopener noreferrer">{link}</a></div>
                <div style="margin-top:6px;"><b>Регион:</b> {region} &nbsp;|&nbsp; <b>Цена:</b> {price} &nbsp;|&nbsp; <b>MOQ:</b> {moq}</div>
                <div><b>Сертификаты:</b> {certs}</div>
                <div style="margin-top:6px;"><b>Контакты:</b> Тел.: {phone} &nbsp;|&nbsp; Email: {email} &nbsp;|&nbsp; WhatsApp: {wa} &nbsp;|&nbsp; Telegram: {tg}</div>
            </div>
        </div>
        """)

    html = f"""
    <html>
      <head>
        <meta charset="utf-8" />
        <title>Результаты — {q}</title>
      </head>
      <body style="max-width:900px;margin:32px auto;padding:0 12px;font-family:Arial,Helvetica,sans-serif;color:#111827;">
        <h2 style="margin-bottom:8px;">📡 Полный сбор по 70+ источникам — запрос: “{q}”</h2>
        <div style="height:1px;background:#e5e7eb;margin:12px 0 20px;"></div>
        {''.join(cards_html)}
      </body>
    </html>
    """
    return html
# ================== /КАРТОЧКИ В HTML ==================