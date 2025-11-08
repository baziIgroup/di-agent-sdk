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
        "Odnokлассники": "ok.ru",
        "Rutube": "rutube.ru",
        "Yappy": "yappy.media",
        "Dzen": "dzen.ru",
    }

    for name, site in social_sites.items():
        results += serpapi_site_search(q, site, name)

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
    return uniq


# 🔹 ПРЯМОЙ эндпоинт расширенного сбора (HTML карточки)
from fastapi.responses import HTMLResponse

@app.get("/search_all", response_class=HTMLResponse)
def search_all(q: str = Query(..., description="Полный сбор по 70+ источникам (HTML карточки)")):
    """Основной эндпоинт — принимает запрос q (например, LGSF) и возвращает HTML карточки с контактами."""
    data = extended_collect(q)
    html_output = format_for_silent_agent_cards(data, q)
    return html_output


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
# ====== /KEEP-ALIVE ======


# ====== ДОБАВЛЕНО: извлечение контактов и HTML-карточки для вывода ======
def extract_contacts(html: str, url: str = "") -> Dict[str, str]:
    """
    Пытается вытащить из HTML: телефоны, email, соцссылки (WhatsApp/Telegram/WeChat),
    сертификаты/ICP/регион/MOQ/Price и т.п.
    Возвращает словарь с полями (строки или пустые строки).
    """
    out = {
        "Phone": "",
        "Email": "",
        "WhatsApp": "",
        "Telegram": "",
        "WeChat": "",
        "Region": "",
        "Price": "",
        "MOQ": "",
        "Certificates": "",
        "CNAME": "",
        "RawURL": url
    }
    if not html:
        return out

    phone_re = re.compile(r"(\+?\d[\d\-\s\(\)]{6,}\d)")
    email_re = re.compile(r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")
    whatsapp_re = re.compile(r"(?:wa\.me/|whatsapp(?:\.com)?/send\?phone=)(\+?\d[\d\-]{5,})", re.I)
    telegram_re = re.compile(r"(?:t\.me/|telegram\.me/)([A-Za-z0-9_]{3,})", re.I)
    wechat_re = re.compile(r"(?:weixin\.qq\.com|wxid|wechat|微信|WeChat)[^\s'\"<>]{0,40}", re.I)

    cert_re = re.compile(r"(ICP[^\s,;:<\)]{1,30}|备案|certificate|Сертификат[^\n\r]{0,80})", re.I)
    region_re = re.compile(r"(Region|Регион|City|Province|所在地|所在省|город|город:)[\s:-–]*([A-Za-zА-Яа-я0-9\-\s,]+)", re.I)
    moq_re = re.compile(r"(MOQ|Минимальный заказ|мин\. заказ|минимальный объем)[^\d]{0,10}([0-9,.\s]+)", re.I)
    price_re = re.compile(r"(?:price|цена|Цена)[^\d]{0,10}([\d\$\€\£\.,\s/]+)", re.I)
    cname_re = re.compile(r"(CNAME|cname)[^\w]{0,3}([A-Za-z0-9\.\-]+)", re.I)

    m_email = email_re.search(html)
    if m_email:
        out["Email"] = m_email.group(1).strip()

    phones = phone_re.findall(html)
    phones = [p.strip() for p in phones if len(re.sub(r"\D", "", p)) >= 6]
    if phones:
        out["Phone"] = phones[0]

    m_wa = whatsapp_re.search(html)
    if m_wa:
        out["WhatsApp"] = m_wa.group(1).strip()
    m_tg = telegram_re.search(html)
    if m_tg:
        out["Telegram"] = m_tg.group(1).strip()
    m_wx = wechat_re.search(html)
    if m_wx:
        out["WeChat"] = m_wx.group(0).strip()

    m_cert = cert_re.search(html)
    if m_cert:
        out["Certificates"] = m_cert.group(0).strip()
    m_region = region_re.search(html)
    if m_region:
        out["Region"] = m_region.group(2).strip()
    m_moq = moq_re.search(html)
    if m_moq:
        out["MOQ"] = m_moq.group(2).strip()
    m_price = price_re.search(html)
    if m_price:
        out["Price"] = m_price.group(1).strip()
    m_cname = cname_re.search(html)
    if m_cname:
        out["CNAME"] = m_cname.group(2).strip()

    soup = BeautifulSoup(html, "lxml")
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if "wa.me" in href or "whatsapp" in href:
            if not out["WhatsApp"]:
                out["WhatsApp"] = href
        if "t.me" in href or "telegram" in href:
            if not out["Telegram"]:
                out["Telegram"] = href
        if "weixin" in href or "wechat" in href:
            if not out["WeChat"]:
                out["WeChat"] = href
        if "mailto:" in href:
            em = href.split("mailto:")[1].split("?")[0]
            if not out["Email"]:
                out["Email"] = em

    return out


def format_for_silent_agent_cards(results: List[Dict], query: str) -> str:
    """
    Возвращает HTML (string) — набор карточек. Для каждого результата:
    - безопасно грузит страницу и извлекает контакты
    - выводит аккуратные кликабельные карточки
    """
    if not results:
        return f"""
        <html><body style="font-family:-apple-system,Roboto,Arial;background:#f6f7fb;padding:18px">
        <div class="wrap" style="max-width:980px;margin:0 auto">
        <h1>❌ Нет данных. Полный сбор по 70+ источникам — запрос: “{query}”</h1>
        </div></body></html>"""

    header = f"""
    <html><head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width,initial-scale=1">
      <style>
        body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial;background:#f6f7fb;color:#111;padding:18px}}
        .wrap{{max-width:980px;margin:0 auto}}
        .card{{background:#fff;border:1px solid #e0e4e8;border-radius:10px;padding:14px;margin-bottom:14px;box-shadow:0 1px 2px rgba(0,0,0,0.06)}}
        .meta{{color:#555;font-size:13px;margin-top:6px}}
        .link{{display:block;margin-top:8px}}
        .row{{margin-top:6px}}
        .label{{font-weight:600}}
      </style>
    </head><body><div class="wrap">
      <h1>📡 Полный сбор по 70+ источникам — запрос: “{query}”</h1>
      <div style="height:1px;background:#e5e7eb;margin:10px 0 14px;"></div>
    """

    cards = [header]

    for i, r in enumerate(results[:5], start=1):
        url = r.get("Ссылка") or ""
        page_html = safe_request(url) if url and url != "N/A" else ""
        c = extract_contacts(page_html, url)

        title = r.get("Название") or f"Result {i}"
        source = r.get("Источник") or "—"
        region = c.get("Region") or r.get("Регион") or "—"
        price  = c.get("Price")  or r.get("Price")  or "—"
        moq    = c.get("MOQ")    or r.get("MOQ")    or "—"
        certs  = c.get("Certificates") or r.get("Certificates") or "—"
        phone  = c.get("Phone") or r.get("Phone") or ""
        email  = c.get("Email") or r.get("Email") or ""
        wa     = c.get("WhatsApp") or r.get("WhatsApp") or ""
        tg     = c.get("Telegram") or r.get("Telegram") or ""
        wx     = c.get("WeChat") or r.get("WeChat") or ""

        contacts_parts = []
        if phone:   contacts_parts.append(f"Тел.: <a href='tel:{re.sub(r'\\D','',phone)}'>{phone}</a>")
        if email:   contacts_parts.append(f"Email: <a href='mailto:{email}'>{email}</a>")
        if wa:
            if wa.startswith("http"):
                contacts_parts.append(f"WhatsApp: <a href='{wa}' target='_blank'>{wa}</a>")
            else:
                contacts_parts.append(f"WhatsApp: <a href='https://wa.me/{re.sub(r'\\D','',wa)}' target='_blank'>{wa}</a>")
        if tg:
            if tg.startswith("http"):
                contacts_parts.append(f"Telegram: <a href='{tg}' target='_blank'>{tg}</a>")
            else:
                contacts_parts.append(f"Telegram: <a href='https://t.me/{tg}' target='_blank'>{tg}</a>")
        if wx:      contacts_parts.append(f"WeChat: {wx}")

        contacts_html = " | ".join(contacts_parts) if contacts_parts else "—"

        cards.append(f"""
        <div class="card">
          <div><span class="label">#{i}</span> <strong>{title}</strong></div>
          <div class="meta">Источник: {source}</div>
          <div class="row">Регион: {region} &nbsp;|&nbsp; Цена: {price} &nbsp;|&nbsp; MOQ: {moq}</div>
          <div class="row">Сертификаты: {certs}</div>
          <div class="row"><a class="link" href="{url}" target="_blank" rel="noopener noreferrer">🔗 Ссылка — {url}</a></div>
          <div class="row"><b>Контакты:</b> {contacts_html}</div>
        </div>
        """)

    cards.append("</div></body></html>")
    return "\n".join(cards)
# ====== /ДОБАВЛЕНО ======