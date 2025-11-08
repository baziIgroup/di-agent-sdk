from fastapi import FastAPI, Query
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup

# ====== ДОБАВЛЕНО ======
import concurrent.futures
from urllib.parse import quote
import re
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
# ====== /ДОБАВЛЕНО ======


app = FastAPI(
    title="DI-Agent SDK",
    description="Интеллектуальный агент для анализа поставщиков Китая",
    version="1.0.2"
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

    # Пробуем набор актуальных селекторов
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


# ====== ДОБАВЛЕНО: список 70+ источников ======
# Каждому сайту — URL-шаблон с {q}. Если сайт не принимает кириллицу, мы переведём.
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

    # Ещё B2B/агрегаторы (добавлено, чтобы было 70+)
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
    "Xiaohongshu": "https://www.xiaohongshu.com/search_result?keyword={q}",
    "Weixin": "https://weixin.sogou.com/weixin?type=2&query={q}",
    "Bilibili": "https://search.bilibili.com/all?keyword={q}",
    "Weibo": "https://s.weibo.com/weibo?q={q}",
    "LinkedIn": "https://www.linkedin.com/search/results/companies/?keywords={q}",
    "Pinterest": "https://www.pinterest.com/search/pins/?q={q}",
    "YouTube": "https://www.youtube.com/results?search_query={q}"
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

def _fetch_one(name: str, url: str) -> List[Dict]:
    html = safe_request(url)
    # Если есть спец-селекторы для сайта — применяем твой исходный парсер
    if name in SITE_SELECTORS:
        return parse_suppliers(html, SITE_SELECTORS[name], name)
    # Иначе — гибкий парсер
    return parse_flexible(html, name)

def extended_collect(query: str) -> List[Dict]:
    q_norm = normalize_query(query)
    q_enc = quote(q_norm)

    tasks = {}
    results: List[Dict] = []

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
# ====== /ДОБАВЛЕНО ======


# 🔹 ОБНОВЛЁННЫЙ /search: сначала расширенный сбор (70+),
#    если пусто — твой исходный блок (4 площадки)
@app.get("/search")
def search(q: str = Query(..., description="Введите поисковый запрос")):
    print(f"🔍 Выполняю поиск по запросу: {q}")

    # 1) Пытаемся собрать максимум
    big = extended_collect(q)
    if big:
        return {
            "status": "ok",
            "query": q,
            "count": len(big),
            "results": big[:MAX_RESULTS]
        }

    # 2) Фолбэк — твоя исходная логика (НЕ УДАЛЯЛ)
    results = []

    html = safe_request(f"https://www.alibaba.com/trade/search?fsb=y&IndexArea=product_en&searchText={quote(normalize_query(q))}")
    results += parse_suppliers(html, [{"title": "h2.title, .organic-gallery-title", "link": "h2.title a, .organic-gallery-title a"}], "Alibaba")

    html = safe_request(f"https://www.made-in-china.com/search?word={quote(normalize_query(q))}")
    results += parse_suppliers(html, [{"title": ".company-name a", "link": ".company-name a"}], "Made-in-China")

    html = safe_request(f"https://www.globalsources.com/searchList?query={quote(normalize_query(q))}")
    results += parse_suppliers(html, [{"title": "a.gs-product-card__name", "link": "a.gs-product-card__name"}], "GlobalSources")

    html = safe_request(f"https://www.baidu.com/s?wd={quote(normalize_query(q))}+site:1688.com")
    results += parse_suppliers(html, [{"title": "h3.t a", "link": "h3.t a"}], "1688")

    if not results:
        return {"status": "error", "query": q, "results": []}

    return {
        "status": "ok",
        "query": q,
        "count": len(results),
        "results": results[:50]
    }

# 🔹 ДОБАВЛЕНО: прямой эндпоинт расширенного сбора (удобно для GPT)
@app.get("/search_all")
def search_all(q: str = Query(..., description="Полный сбор по 70+ источникам")):
    data = extended_collect(q)
    return {
        "status": "ok" if data else "error",
        "query": q,
        "count": len(data),
        "results": data[:MAX_RESULTS]
    }