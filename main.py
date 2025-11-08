from fastapi import FastAPI, Query
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup
import concurrent.futures

app = FastAPI(
    title="DI-Agent SDK",
    description="Универсальный SDK для поиска поставщиков по 70+ площадкам Китая",
    version="2.0.0"
)

# 🔹 Безопасный HTTP-запрос
def safe_request(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code == 200:
            return r.text
        else:
            print(f"⚠️ Ошибка {r.status_code} при загрузке {url}")
            return ""
    except Exception as e:
        print(f"❌ Ошибка при запросе {url}: {e}")
        return ""

# 🔹 Упрощённый парсер
def parse_suppliers(html, selectors, source):
    if not html:
        return []

    soup = BeautifulSoup(html, "lxml")
    results = []
    for sel in selectors:
        titles = [t.get_text(strip=True) for t in soup.select(sel.get("title", "")) if t.get_text(strip=True)]
        links = [a.get("href") for a in soup.select(sel.get("link", "")) if a.get("href")]
        for i in range(min(len(titles), 5)):
            results.append({
                "Название": titles[i],
                "Ссылка": links[i] if i < len(links) else "",
                "Источник": source
            })
    return results


@app.get("/")
def root():
    return {
        "status": "ok",
        "docs": "/docs",
        "search_example": "/search?q=ЛСТК"
    }

@app.get("/search")
def search(q: str = Query(..., description="Введите поисковый запрос")):
    print(f"🔍 Выполняю поиск по запросу: {q}")

    sources = {
        # 🔸 Китайские B2B и маркетплейсы
        "Alibaba": f"https://www.alibaba.com/trade/search?fsb=y&IndexArea=product_en&searchText={q}",
        "Made-in-China": f"https://www.made-in-china.com/search?word={q}",
        "GlobalSources": f"https://www.globalsources.com/searchList?query={q}",
        "1688": f"https://www.baidu.com/s?wd={q}+site:1688.com",
        "ECPlaza": f"https://www.ecplaza.net/search?keywords={q}",
        "Tradewheel": f"https://www.tradewheel.com/search/{q}/",
        "ExportHub": f"https://www.exporthub.com/search?q={q}",
        "DHgate": f"https://www.dhgate.com/wholesale/search.do?act=search&searchkey={q}",
        "HKTDC": f"https://sourcing.hktdc.com/Search-Product?keyword={q}",
        "Taiwantrade": f"https://www.taiwantrade.com/search-result.html?searchKey={q}",
        "B2Brazil": f"https://b2brazil.com/hotsite/search?keyword={q}",
        "TradeIndia": f"https://www.tradeindia.com/search.html?keyword={q}",
        "IndiaMART": f"https://dir.indiamart.com/search.mp?ss={q}",
        "Kompass": f"https://cn.kompass.com/en/searchCompanies/?q={q}",
        "YellowPagesChina": f"https://en.yellowpages.china.cn/search.html?kw={q}",
        "China.cn": f"https://www.china.cn/search?wd={q}",
        "ChinaManufacturers": f"https://www.chinamanufacturers.cn/search/{q}",
        "Globalsuppliersonline": f"https://globalsuppliersonline.com/search/{q}",
        "WorldTradeRef": f"https://www.worldtradesuppliers.com/search?q={q}",
        # ... (можно добавить остальные до 70)
    }

    selectors = {
        "Alibaba": [{"title": "h2.title", "link": "h2.title a"}],
        "Made-in-China": [{"title": ".company-name a", "link": ".company-name a"}],
        "GlobalSources": [{"title": "a.gs-product-card__name", "link": "a.gs-product-card__name"}],
        "1688": [{"title": "h3.t", "link": "h3.t a"}],
        "ECPlaza": [{"title": ".item-title a", "link": ".item-title a"}],
        "Tradewheel": [{"title": "a.item-title", "link": "a.item-title"}],
        "ExportHub": [{"title": "h4.media-heading a", "link": "h4.media-heading a"}],
        "DHgate": [{"title": ".item-name", "link": ".item-name a"}],
        "HKTDC": [{"title": ".product-name a", "link": ".product-name a"}],
        "Taiwantrade": [{"title": ".pro-name a", "link": ".pro-name a"}],
    }

    results = []

    # 🔹 Параллельный обход всех площадок
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        future_to_source = {
            executor.submit(
                lambda name, url: parse_suppliers(
                    safe_request(url),
                    selectors.get(name, [{"title": "h2", "link": "a"}]),
                    name
                ), name, url
            ): name for name, url in sources.items()
        }

        for future in concurrent.futures.as_completed(future_to_source):
            source_name = future_to_source[future]
            try:
                suppliers = future.result()
                results.extend(suppliers)
                print(f"✅ {source_name}: найдено {len(suppliers)} компаний")
            except Exception as e:
                print(f"❌ Ошибка в {source_name}: {e}")

    if not results:
        return {"status": "error", "query": q, "results": []}

    # 🔹 Убираем дубликаты
    unique = []
    seen = set()
    for r in results:
        key = (r["Название"], r["Источник"])
        if key not in seen:
            seen.add(key)
            unique.append(r)

    # 🔹 Формируем ответ
    return {
        "status": "ok",
        "query": q,
        "count": len(unique),
        "results": unique[:70]  # первые 70 результатов
    }