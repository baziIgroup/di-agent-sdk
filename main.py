from fastapi import FastAPI, Query
from pydantic import BaseModel
import requests
from bs4 import BeautifulSoup

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

# 🔹 Парсинг списка компаний
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


@app.get("/")
def root():
    return {
        "status": "✅ DI-Agent SDK активен",
        "docs": "/docs",
        "search_example": "/search?q=ЛСТК"
    }


@app.get("/search")
def search(q: str = Query(..., description="Введите поисковый запрос")):
    print(f"🔍 Выполняю поиск по запросу: {q}")

    results = []

    # 🔸 Alibaba
    html = safe_request(f"https://www.alibaba.com/trade/search?fsb=y&IndexArea=product_en&searchText={q}")
    results += parse_suppliers(html, [{"title": "h2.title", "link": "h2.title a"}], "Alibaba")

    # 🔸 Made-in-China
    html = safe_request(f"https://www.made-in-china.com/search?word={q}")
    results += parse_suppliers(html, [{"title": ".company-name a", "link": ".company-name a"}], "Made-in-China")

    # 🔸 GlobalSources
    html = safe_request(f"https://www.globalsources.com/searchList?query={q}")
    results += parse_suppliers(html, [{"title": "a.gs-product-card__name", "link": "a.gs-product-card__name"}], "GlobalSources")

    # 🔸 1688 (через Baidu)
    html = safe_request(f"https://www.baidu.com/s?wd={q}+site:1688.com")
    results += parse_suppliers(html, [{"title": "h3.t", "link": "h3.t a"}], "1688")

    if not results:
        return {"status": "❌ Нет данных", "query": q, "results": []}

    return {
        "status": "✅ Успешно",
        "query": q,
        "count": len(results),
        "results": results[:5]
    }
