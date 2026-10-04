import asyncio, json, re, sqlite3, statistics
from datetime import datetime
from pathlib import Path
from flask import Flask, jsonify, render_template, request
import requests
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

DB=ROOT/"prices.sqlite3"
ROOT=Path(__file__).parent
CFG=json.loads((ROOT/"config.json").read_text(encoding="utf-8"))
app=Flask(__name__)

def db():
    c=sqlite3.connect(DB)
    c.row_factory=sqlite3.Row
    c.execute("""CREATE TABLE IF NOT EXISTS prices(
      id INTEGER PRIMARY KEY, ts TEXT, store TEXT, brand TEXT,
      product_id TEXT, name TEXT, price REAL, url TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS alerts(
      id INTEGER PRIMARY KEY, ts TEXT, store TEXT, product_id TEXT,
      name TEXT, price REAL, reference REAL, score REAL, reason TEXT, url TEXT)""")
    c.commit()
    return c

def money(v):
    if v is None: return None
    m=re.search(r'(\d{1,4}(?:[.,]\d{1,3})?)\s*(?:€|EUR)',str(v),re.I)
    if not m: return None
    try:return float(m.group(1).replace(".","").replace(",","."))
    except:return None

def clean(v): return re.sub(r"\s+"," ",str(v or "")).strip()[:240]

def walk_json(x,out,url):
    if isinstance(x,dict):
        n=x.get("name") or x.get("title") or x.get("label")
        p=x.get("price")
        if p is None:p=x.get("salePrice") or x.get("sellingPrice") or x.get("currentPrice")
        if n is not None and p is not None:
            try:
                p=float(str(p).replace(",","."))
                if 0<p<10000:
                    pid=str(x.get("ean") or x.get("gtin") or x.get("sku") or x.get("id") or clean(n))
                    out.append((pid,clean(n),p,url))
            except:pass
        for v in x.values():walk_json(v,out,url)
    elif isinstance(x,list):
        for v in x:walk_json(v,out,url)

def extract(html,url):
    s=BeautifulSoup(html,"lxml"); out=[]
    for tag in s.find_all("script",type="application/ld+json"):
        try:walk_json(json.loads(tag.string or tag.get_text()),out,url)
        except:pass
    for node in s.find_all(string=re.compile("€")):
        p=money(node)
        if p is None:continue
        parent=node.parent
        txt=parent.get_text(" ",strip=True) if parent else ""
        if 3<=len(txt)<=220:
            name=clean(re.split(r"\s+€",txt)[0])
            if len(name)>3:out.append((name,name,p,url))
    d={}
    for x in out:d[(x[0],round(x[2],3))]=x
    return list(d.values())

async def crawl(store):
    if not store["url"]: return []
    found=[]
    async with async_playwright() as pw:
        browser=await pw.chromium.launch(headless=True)
        page=await browser.new_page(locale="fr-FR")
        async def resp(r):
            if "json" in r.headers.get("content-type",""):
                try:
                    t=await r.text()
                    if len(t)<8_000_000: walk_json(json.loads(t),found,r.url)
                except:pass
        page.on("response",resp)
        try:
            await page.goto(store["url"],wait_until="domcontentloaded",timeout=60000)
            await page.wait_for_timeout(6000)
            for _ in range(6):
                await page.mouse.wheel(0,2200); await page.wait_for_timeout(900)
            found += extract(await page.content(),page.url)
        except Exception as e: print(store["name"],e)
        await browser.close()
    d={}
    for x in found:d[(x[0],round(x[2],3))]=x
    return list(d.values())

def analyse(c,store,pid,price):
    rows=c.execute("SELECT price FROM prices WHERE product_id=? AND store=? ORDER BY id DESC LIMIT 40",(pid,store)).fetchall()
    vals=[r[0] for r in rows if r[0]>0]
    if len(vals)<3:return 0,None,""
    ref=statistics.median(vals)
    if price>=ref:return 0,ref,""
    pct=(1-price/ref)*100
    score=min(100,pct*1.15+(12 if pct>=80 else 0))
    return score,ref,f"{pct:.0f}% sous la référence"

def send_telegram(text):
    t=CFG.get("telegram_bot_token",""); chat=CFG.get("telegram_chat_id","")
    if not t or not chat:return
    try:requests.post(f"https://api.telegram.org/bot{t}/sendMessage",json={"chat_id":chat,"text":text},timeout=10)
    except:pass

def do_scan():
    stores=[s for s in CFG["stores"] if s.get("enabled")]
    async def go():
        result=[]
        for s in stores: result.append((s,await crawl(s)))
        return result
    results=asyncio.run(go()); c=db(); now=datetime.now().isoformat(timespec="seconds"); count=0
    for s,items in results:
        for pid,name,p,url in items:
            score,ref,reason=analyse(c,s["name"],pid,p)
            c.execute("INSERT INTO prices(ts,store,brand,product_id,name,price,url) VALUES(?,?,?,?,?,?,?)",
                      (now,s["name"],s["brand"],pid,name,p,url))
            if score>=CFG["alert_threshold_score"]:
                c.execute("""INSERT INTO alerts(ts,store,product_id,name,price,reference,score,reason,url)
                             VALUES(?,?,?,?,?,?,?,?,?)""",
                          (now,s["name"],pid,name,p,ref,score,reason,url))
                send_telegram(f"🚨 {s['name']} — {name}\nPrix: {p:.2f} € | Réf: {ref:.2f} €\nScore: {score:.0f}/100\n{reason}\n{url}")
                count+=1
    c.commit(); c.close()
    return count

@app.get("/")
def home(): return render_template("index.html")

@app.get("/api/status")
def status():
    c=db()
    last=c.execute("SELECT MAX(ts) t FROM prices").fetchone()["t"]
    alerts=c.execute("SELECT COUNT(*) n FROM alerts").fetchone()["n"]
    c.close()
    return jsonify({"last_scan":last,"alerts":alerts,"stores":CFG["stores"]})

@app.get("/api/alerts")
def alerts():
    c=db()
    rows=c.execute("""SELECT id,ts,store,name,price,reference,score,reason,url
                      FROM alerts ORDER BY id DESC LIMIT 100""").fetchall()
    c.close()
    return jsonify([dict(r) for r in rows])

@app.post("/api/scan")
def scan():
    try:
        n=do_scan()
        return jsonify({"ok":True,"alerts":n})
    except Exception as e:
        return jsonify({"ok":False,"error":str(e)}),500

if __name__=="__main__":
    db()
    app.run(host="0.0.0.0",port=10000)
