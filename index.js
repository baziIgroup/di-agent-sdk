// China Supplier Sourcing SDK (Node.js)
// 70+ источников → собирает, обогащает, ранжирует → отдаёт 5 HTML-карточек
// GET /search?q=...  => text/html

import express from "express";
import cors from "cors";
import axios from "axios";
import * as cheerio from "cheerio";

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

// =================== SOURCES (70+) ===================
const SOURCES = {
  // Major B2B
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

  // CN marketplaces
  "JD": "https://search.jd.com/Search?keyword={q}",
  "Taobao": "https://s.taobao.com/search?q={q}",
  "Pinduoduo": "https://mobile.yangkeduo.com/search_result.html?search_key={q}",

  // Niche / verticals / backups
  "MFG": "https://www.mfg.com/en/search/?q={q}",
  "AliExpress B2B": "https://www.aliexpress.com/wholesale?SearchText={q}",
  "Globalsources Verified": "https://www.globalsources.com/searchList?query={q}&verifiedSupplier=true",
  "Baidu Baike": "https://baike.baidu.com/search?word={q}",
  "Sogou": "https://www.sogou.com/web?query={q}",
  "Bing China": "https://cn.bing.com/search?q={q}",
  "Google (backup)": "https://www.google.com/search?q={q}",

  // More B2B / aggregators
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
  "HKTDC Products": "https://sourcing.hktdc.com/Search-Product?keyword={q}&productonly=1"
};

// site-specific «селекторы» (минимально)
const SITE_SELECTORS = {
  "Alibaba": [{ title: ".organic-gallery-title", link: ".organic-gallery-title a" }],
  "Made-in-China": [{ title: ".company-name a", link: ".company-name a" }],
  "GlobalSources": [{ title: "a.gs-product-card__name", link: "a.gs-product-card__name" }],
  "1688 (via Baidu)": [{ title: "h3.t a", link: "h3.t a" }],
  "HKTDC": [{ title: ".product-name a, .cmpny-name a", link: ".product-name a, .cmpny-name a" }],
  "ECER": [{ title: ".pro-title a, .supplier-name a", link: ".pro-title a, .supplier-name a" }],
  "ECVV": [{ title: ".pro-title a, .company a", link: ".pro-title a, .company a" }],
  "HC360": [{ title: ".search-list .title a", link: ".search-list .title a" }],
  "DHgate": [{ title: ".item-title a", link: ".item-title a" }],
  "YiwuGo": [{ title: ".title a", link: ".title a" }],
  "TradeWheel": [{ title: ".item-title a", link: ".item-title a" }],
  "ExportHub": [{ title: "h4.media-heading a", link: "h4.media-heading a" }]
};

const GENERIC_SELECTORS = [
  { title: "h2 a", link: "h2 a" },
  { title: ".title a", link: ".title a" },
  { title: ".product-title a", link: ".product-title a" },
  { title: ".company-name a", link: ".company-name a" },
  { title: "a.gs-product-card__name", link: "a.gs-product-card__name" },
  { title: ".organic-gallery-title a", link: ".organic-gallery-title a" },
  { title: "h3 a", link: "h3 a" },
  { title: "a", link: "a" }
];

// =================== UTILS ===================
function normalizeQuery(q) {
  if (/[А-Яа-яЁё]/.test(q || "")) {
    const low = (q || "").toLowerCase();
    const map = {
      "фиброцем": "fiber cement panels",
      "пенобетон": "foam concrete",
      "лстк": "light gauge steel frame",
      "сэндвич": "sandwich panels",
      "оцинкован": "galvanized steel",
      "алюкобонд": "aluminum composite panel"
    };
    for (const k in map) {
      if (low.includes(k)) return map[k];
    }
  }
  return q;
}

async function safeGet(url) {
  try {
    const r = await AX.get(url);
    return r.data || "";
  } catch {
    return "";
  }
}

function parseSuppliers(html, selectors, source) {
  if (!html) return [];
  const $ = cheerio.load(html);
  let titles = [], links = [];
  for (const sel of selectors) {
    $(sel.title).each((_, el) => titles.push($(el).text().trim()));
    $(sel.link).each((_, el) => links.push($(el).attr("href") || ""));
  }
  titles = titles.filter((t, i, a) => t && a.indexOf(t) === i);
  links  = links.filter((h, i, a) => h && a.indexOf(h) === i);
  const out = [];
  const n = Math.min(5, titles.length);
  for (let i=0;i<n;i++){
    let href = links[i] || "";
    if (href.startsWith("//")) href = "https:" + href;
    if (href && !href.startsWith("http")) continue;
    out.push({ "Название": titles[i], "Ссылка": href, "Источник": source });
  }
  return out;
}

function parseFlexible(html, source) {
  if (!html) return [];
  const $ = cheerio.load(html);
  const seen = new Set();
  const out = [];
  for (const sel of GENERIC_SELECTORS) {
    $(sel.link).each((_, a) => {
      const href = ($(a).attr("href") || "").trim();
      const title = $(a).text().trim();
      if (!href || !title) return;
      let link = href;
      if (link.startsWith("//")) link = "https:" + link;
      if (!link.startsWith("http")) return;
      const key = `${title}|${link}`;
      if (seen.has(key)) return;
      seen.add(key);
      out.push({ "Название": title.slice(0,200), "Ссылка": link, "Источник": source });
    });
    if (out.length >= 50) break;
  }
  return out.slice(0, 50);
}

async function fetchOne(name, tmpl, qEnc) {
  const url = tmpl.replace("{q}", encodeURIComponent(qEnc));
  const html = await safeGet(url);
  if (SITE_SELECTORS[name]) return parseSuppliers(html, SITE_SELECTORS[name], name);
  return parseFlexible(html, name);
}

function isLogisticsOrBanned(text) {
  const ban = ["shipping","delivery","物流","доставка","Филиппины","philippines","стоимость доставки","логистика","logistics"];
  const low = (text || "").toLowerCase();
  return ban.some(w => low.includes(w));
}

function manufacturerConfidence(html) {
  if (!html) return 0.2;
  let pts = 0;
  if (/\bfactory\b|\bmanufacturer\b|我们的工厂|生产线|工厂/i.test(html)) pts += 0.6;
  if (/trading company/i.test(html)) pts -= 0.4;
  if (/production line|sq\.? m|employees|workshop/i.test(html)) pts += 0.2;
  return Math.max(0, Math.min(1, pts));
}

function extractContacts(html, url) {
  const out = {
    Phone:"", Email:"", WhatsApp:"", Telegram:"", WeChat:"",
    Region:"", Price:"", MOQ:"", Certificates:"", Website:url, ImageLink:""
  };
  if (!html) return out;
  const $ = cheerio.load(html);

  const text = $.root().text();
  const phoneMatch = text.match(/(\+?\d[\d\-\s\(\)]{6,}\d)/g) || [];
  const emailMatch = text.match(/[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/);
  const waMatch = html.match(/(?:wa\.me\/|whatsapp(?:\.com)?\/send\?phone=)(\+?\d[\d\-]{5,})/i);
  const tgMatch = html.match(/(?:t\.me\/|telegram\.me\/)([A-Za-z0-9_]{3,})/i);
  const wcMatch = html.match(/(weixin\.qq\.com|wxid|wechat|微信|WeChat)[^\s'\"<>]{0,40}/i);
  const certs = [...(html.match(/(ISO|CE|RoHS|BSCI|FCC|UL|CSA|GMP|HACCP|REACH|FDA|сертификат|certificate)/gi)||[])];
  const region = text.match(/(province|city|регион|所在地|所在省|address)[:\s\-–]*([A-Za-zА-Яа-я0-9\-\s,]+)/i);
  const moq = text.match(/(?:MOQ|минимальный заказ|минимальный объём)[^\d]{0,10}([0-9,.\s]+)/i);
  const price = text.match(/(?:price|цена)[^\d]{0,10}([\d\$\€\£\.,\s/]+)/i);

  const ogImg = $('meta[property="og:image"]').attr("content") || $('meta[name="og:image"]').attr("content");
  if (ogImg) out.ImageLink = ogImg;
  if (!out.ImageLink) {
    const img = $("img[src]").first().attr("src");
    if (img) out.ImageLink = img;
  }
  out.Email = emailMatch ? emailMatch[0].trim() : "";
  out.Phone = phoneMatch.length ? phoneMatch[0].trim() : "";
  out.WhatsApp = waMatch ? waMatch[1].trim() : "";
  out.Telegram = tgMatch ? tgMatch[1].trim() : "";
  out.WeChat = wcMatch ? wcMatch[0].trim() : "";
  out.Region = region ? (region[2] || "").trim() : "";
  out.MOQ = moq ? (moq[1] || "").trim() : "";
  out.Price = price ? (price[1] || "").trim() : "";
  out.Certificates = certs.length ? Array.from(new Set(certs)).slice(0,10).join("; ") : "";

  // anchor fallbacks
  $("a[href]").each((_,a)=>{
    const href = ($(a).attr("href")||"").trim();
    const txt = $(a).text().trim();
    if (href.startsWith("mailto:") && !out.Email) out.Email = href.split("mailto:")[1].split("?")[0];
    if ((href.includes("wa.me") || href.includes("whatsapp")) && !out.WhatsApp) out.WhatsApp = href;
    if ((href.includes("t.me") || href.includes("telegram")) && !out.Telegram) out.Telegram = href || txt;
  });
  return out;
}

function computeRating(html, contacts, sourceUrl){
  let rep = 0.5;
  try {
    const host = new URL(sourceUrl).host;
    if (/(alibaba\.com|made-in-china\.com|globalsources\.com|hktdc\.com|thomasnet\.com|kompass\.com|qcc\.com|tianyancha\.com)/.test(host)) {
      rep = 1.0;
    }
  } catch { rep = 0.5; }
  const cert = contacts.Certificates ? 1.0 : 0.2;
  const prod = manufacturerConfidence(html);
  const pq = (contacts.Price && contacts.MOQ) ? 0.7 : 0.4;
  const legal = /(ICP|备案|license|营业执照|统一社会信用代码)/i.test(html||"") ? 0.8 : 0.4;
  const exportA = /(export|出口|海外|国际)/i.test(html||"") ? 0.7 : 0.4;
  const score = (0.25*rep + 0.20*cert + 0.20*prod + 0.15*pq + 0.10*legal + 0.10*exportA) * 100;
  return Math.max(0, Math.min(100, Math.round(score)));
}

function makeContactsHTML(c){
  const parts = [];
  if (c.WeChat) parts.push(`WeChat: ${c.WeChat}`);
  if (c.WhatsApp){
    let wa = c.WhatsApp;
    if (!/^https?:\/\//i.test(wa)) wa = "https://wa.me/" + (wa||"").replace(/\D/g,"");
    parts.push(`WhatsApp: <a href="${wa}" target="_blank">${wa}</a>`);
  }
  if (c.Telegram){
    let tg = c.Telegram;
    if (!/^https?:\/\//i.test(tg)) tg = "https://t.me/" + tg;
    parts.push(`Telegram: <a href="${tg}" target="_blank">${tg}</a>`);
  }
  if (c.Email) parts.push(`Email: <a href="mailto:${c.Email}">${c.Email}</a>`);
  if (c.Phone) parts.push(`Phone: <a href="tel:${c.Phone.replace(/\D/g,"")}">${c.Phone}</a>`);
  if (c.Website) parts.push(`Website: <a href="${c.Website}" target="_blank">${c.Website}</a>`);
  return parts.join(" | ");
}

function rankEmoji(i){ return ["🥇","🥈","🥉","4️⃣","5️⃣"][i] || " "; }

function cardHTML(idx, item){
  const re = (lbl, val)=> val ? `<div><b>${lbl}</b> ${val}</div>` : "";
  const title = `${rankEmoji(idx)} <b>TOP ${idx+1} — ${item.CompanyName}</b>`;
  const src = item.Website ? `<a href="${item.Website}" target="_blank" rel="noopener">${item.Source}</a>` : (item.Source || "-");
  const img = item.ImageLink ? `<div><a href="${item.ImageLink}" target="_blank">Image</a></div>` : "";
  return [
    `${title}<br/>`,
    re("🌍 Регион:", item.Region),
    re("🏷️ Продукт:", item.Product),
    re("💰 Цена:", item.Price),
    re("📦 MOQ:", item.MOQ),
    re("🧾 Сертификаты:", item.Certificates),
    re("📞 Контакты:", makeContactsHTML(item.Contacts || {})),
    re("🧠 Рейтинг:", `${item.Rating} / 100`),
    re("🔗 Источник:", src),
    img
  ].join("\n");
}

// =============== CORE ===============
async function extendedCollect(query){
  const q = normalizeQuery(query);
  const entries = Object.entries(SOURCES);
  const results = [];
  // простая «пулами» чтобы не улететь в 70 параллелей
  const CHUNK = 10;
  for (let i=0;i<entries.length;i+=CHUNK){
    const slice = entries.slice(i, i+CHUNK);
    const promises = slice.map(async ([name, tmpl]) => {
      try {
        const html = await safeGet(tmpl.replace("{q}", encodeURIComponent(q)));
        if (!html) return [];
        if (SITE_SELECTORS[name]) return parseSuppliers(html, SITE_SELECTORS[name], name);
        return parseFlexible(html, name);
      } catch { return []; }
    });
    const chunkRes = await Promise.all(promises);
    chunkRes.forEach(arr => results.push(...arr));
    if (results.length >= MAX_RESULTS) break;
  }
  // dedup by link
  const seen = new Set();
  const uniq = [];
  for (const it of results){
    const link = (it["Ссылка"]||"").trim();
    if (!link || seen.has(link)) continue;
    seen.add(link);
    uniq.push(it);
    if (uniq.length >= MAX_RESULTS) break;
  }
  return uniq;
}

async function buildTop5(query){
  const base = await extendedCollect(query);
  const enriched = [];
  for (const r of base){
    const url = r["Ссылка"]||"";
    const title = (r["Название"]||"").trim();
    const src = r["Источник"]||"-";
    if (!url || !title) continue;
    if (isLogisticsOrBanned(title)) continue;
    const page = await safeGet(url);
    if (isLogisticsOrBanned(page)) continue;
    if (manufacturerConfidence(page) < 0.3) continue;

    const contacts = extractContacts(page, url);
    const rating = computeRating(page, contacts, url);
    enriched.push({
      CompanyName: title.slice(0,140),
      Region: contacts.Region || "",
      Product: title.slice(0,140),
      Price: contacts.Price || "",
      MOQ: contacts.MOQ || "",
      Certificates: contacts.Certificates || "",
      Contacts: contacts,
      Rating: rating,
      Source: src,
      Website: url,
      ImageLink: contacts.ImageLink || ""
    });
    if (enriched.length >= 40) break;
  }
  if (enriched.length === 0) return "";

  // dedup by (host + normalized name)
  const seen = new Set();
  const uniq = [];
  for (const e of enriched){
    let host = "-";
    try { host = new URL(e.Website).host; } catch {}
    const key = host + "|" + e.CompanyName.toLowerCase().replace(/\W+/g,"").slice(0,40);
    if (seen.has(key)) continue;
    seen.add(key);
    uniq.push(e);
  }

  const top = uniq.sort((a,b)=> b.Rating - a.Rating).slice(0,5);
  const cards = top.map((it, i) => cardHTML(i, it))
                  .flatMap((c,i)=> i<4 ? [c, SEPARATOR] : [c]);
  return cards.join("\n\n");
}

// =============== HTTP ===============
app.get("/", (req,res)=> res.type("text/plain").send("China Supplier Sourcing SDK (Node). Use /search?q=..."));

app.get("/search", async (req, res) => {
  const q = (req.query.q || "").toString().trim();
  if (!q) return res.status(400).type("text/plain").send("Missing q");
  try {
    const html = await buildTop5(q);
    if (!html) return res.status(204).send(); // no content
    res.type("text/html").send(html);
  } catch (e) {
    res.status(500).type("text/plain").send("Internal error");
  }
});

app.listen(PORT, () => {
  console.log(`SDK server on :${PORT}`);
});// =====================================================
// 🛰️ Keep-alive ping — чтобы Render не засыпал
// =====================================================
import https from "https";

const SELF_URL = "https://di-agent-sdk.onrender.com"; // замени, если Render другой
setInterval(() => {
  https
    .get(SELF_URL + "/search?q=pulse", (res) => {
      console.log(`⏱️ Ping status: ${res.statusCode}`);
    })
    .on("error", (err) => {
      console.error("Ping error:", err.message);
    });
}, 5 * 60 * 1000); // каждые 5 минут