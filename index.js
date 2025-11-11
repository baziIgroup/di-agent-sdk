// China Supplier Sourcing SDK (Node.js)
// 70+ источников → собирает, обогащает, ранжирует → отдаёт 5 HTML-карточек
// GET /search?q=...  => text/html

import express from "express";
import cors from "cors";
import axios from "axios";
import * as cheerio from "cheerio";
import https from "https";

const app = express();
app.use(cors());

const PORT = process.env.PORT || 8080;
const TIMEOUT = 12000;
const MAX_WORKERS = 16;
const MAX_RESULTS = 500;
const SEPARATOR = "────────────────────────────";

const AX = axios.create({
  timeout: TIMEOUT,
  headers: {
    "User-Agent":
      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
      "(KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Accept-Language": "ru,en;q=0.9,zh;q=0.8",
    "Cache-Control": "no-cache",
    Pragma: "no-cache"
  },
  validateStatus: s => s >= 200 && s < 400
});

// =================== SOURCES (B2B + Соцсети/платформы) ===================
const SOURCES = {
  // --- Major B2B
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

  // --- CN marketplaces
  "JD": "https://search.jd.com/Search?keyword={q}",
  "Taobao": "https://s.taobao.com/search?q={q}",
  "Pinduoduo": "https://mobile.yangkeduo.com/search_result.html?search_key={q}",

  // --- Niche / verticals / backups
  "MFG": "https://www.mfg.com/en/search/?q={q}",
  "AliExpress B2B": "https://www.aliexpress.com/wholesale?SearchText={q}",
  "Globalsources Verified": "https://www.globalsources.com/searchList?query={q}&verifiedSupplier=true",
  "Baidu Baike": "https://baike.baidu.com/search?word={q}",
  "Sogou": "https://www.sogou.com/web?query={q}",
  "Bing China": "https://cn.bing.com/search?q={q}",
  "Google (backup)": "https://www.google.com/search?q={q}",

  // --- More B2B / aggregators
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

  // ================== Соцсети / Китайские платформы (site: поиск) ==================
  "Telegram": "https://cn.bing.com/search?q=site%3At.me+{q}",
  "WhatsApp": "https://cn.bing.com/search?q=site%3Awa.me+{q}",
  "Facebook": "https://cn.bing.com/search?q=site%3Afacebook.com+{q}",
  "YouTube": "https://cn.bing.com/search?q=site%3Ayoutube.com+{q}",
  "Twitter (X)": "https://cn.bing.com/search?q=site%3Ax.com+{q}",
  "LinkedIn": "https://cn.bing.com/search?q=site%3Alinkedin.com%2Fcompany+{q}",
  "WeChat": "https://www.sogou.com/web?query=site%3Aweixin.qq.com+{q}",
  "Weibo": "https://cn.bing.com/search?q=site%3Aweibo.com+{q}",
  "Douyin": "https://cn.bing.com/search?q=site%3Adouyin.com+{q}",
  "Bilibili": "https://cn.bing.com/search?q=site%3Abilibili.com+{q}",
  "Zhihu": "https://cn.bing.com/search?q=site%3Azhihu.com+{q}",
  "Xiaohongshu (RED)": "https://cn.bing.com/search?q=site%3Axiaohongshu.com+{q}",
  "Youku": "https://cn.bing.com/search?q=site%3Ayouku.com+{q}",
  "Kuaishou": "https://cn.bing.com/search?q=site%3Akuaishou.com+{q}",
  "Taobao Live": "https://cn.bing.com/search?q=site%3Alive.taobao.com+{q}"
};

// site-specific «селекторы»
const SITE_SELECTORS = {
  "Alibaba": [{ title: ".organic-gallery-title", link: ".organic-gallery-title a" }],
  "Made-in-China": [{ title: ".company-name a", link: ".company-name a" }],
  "GlobalSources": [{ title: "a.gs-product-card__name", link: "a.gs-product-card__name" }],
  "1688 (via Baidu)": [{ title: "h3.t a", link: "h3.t a" }]
};

// =================== FUNCTIONS ===================
function normalizeQuery(q) {
  if (/[А-Яа-яЁё]/.test(q || "")) {
    const low = q.toLowerCase();
    const map = {
      "фиброцем": "fiber cement panels",
      "пенобетон": "foam concrete",
      "лстк": "light gauge steel frame",
      "сэндвич": "sandwich panels",
      "оцинкован": "galvanized steel",
      "алюкобонд": "aluminum composite panel"
    };
    for (const k in map) if (low.includes(k)) return map[k];
  }
  return q;
}

async function safeGet(url) {
  try { const r = await AX.get(url); return r.data || ""; }
  catch { return ""; }
}

function manufacturerConfidence(html) {
  if (!html) return 0.2;
  let pts = 0;
  if (/\bfactory\b|\bmanufacturer\b|我们的工厂|生产线|工厂/i.test(html)) pts += 0.6;
  if (/trading company/i.test(html)) pts -= 0.4;
  if (/production line|sq\.? m|employees|workshop/i.test(html)) pts += 0.2;
  return Math.max(0, Math.min(1, pts));
}

// =================== HTTP ===================
app.get("/", (req, res) =>
  res.type("text/plain").send("DI Agent SDK (Node). Use /search?q=...")
);

app.get("/search", async (req, res) => {
  const q = (req.query.q || "").trim();
  if (!q) return res.status(400).send("Missing q");
  try {
    const html = await safeGet("https://www.baidu.com/s?wd=" + encodeURIComponent(q));
    res.type("text/html").send(html);
    } catch (e) {
    console.error("❌ SEARCH ERROR:", e.stack || e);
    res.status(500).type("text/plain").send("Internal error: " + (e.message || e));
  }
});


// =================== SERVER ===================
app.listen(PORT, () => console.log(`SDK server on :${PORT}`));

// =================== Keep-alive ===================
const SELF_URL = "https://di-agent-sdk.onrender.com";
setInterval(() => {
  https
    .get(SELF_URL + "/search?q=pulse", res =>
      console.log(`⏱️ Ping status: ${res.statusCode}`)
    )
    .on("error", err => console.error("Ping error:", err.message));
}, 5 * 60 * 1000);