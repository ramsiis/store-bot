import os
import asyncio
import aiofiles
from bs4 import BeautifulSoup
import cloudscraper

CF_EMAIL = os.getenv("CF_EMAIL", "")
CF_PASSWORD = os.getenv("CF_PASSWORD", "")
DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

def get_logged_scraper():
    scraper = cloudscraper.create_scraper(
        browser={"browser": "chrome", "platform": "windows", "mobile": False}
    )
    resp = scraper.get("https://www.creativefabrica.com/login/")
    soup = BeautifulSoup(resp.text, "html.parser")
    nonce_input = soup.select_one("input[name='woocommerce-login-nonce']")
    nonce = nonce_input.get("value", "") if nonce_input else ""

    scraper.post(
        "https://www.creativefabrica.com/login/",
        data={
            "username": CF_EMAIL,
            "password": CF_PASSWORD,
            "woocommerce-login-nonce": nonce,
            "_wp_http_referer": "/login/",
            "login": "Log in",
        },
        allow_redirects=True
    )
    return scraper

async def search_products(query: str, limit: int = 8) -> list:
    loop = asyncio.get_event_loop()
    def _search():
        scraper = get_logged_scraper()
        url = f"https://www.creativefabrica.com/?s={query.replace(' ', '+')}&post_type=product"
        resp = scraper.get(url)
        soup = BeautifulSoup(resp.text, "html.parser")
        products = []
        items = []
        for sel in [".product-card", ".product-item", "li.product", "article.product"]:
            items = soup.select(sel)
            if items:
                break
        if not items:
            for a in soup.select("a[href*='/product/']"):
                href = a.get("href", "")
                name = a.get_text(strip=True)
                img = a.select_one("img")
                if href and name and len(name) > 3:
                    products.append({
                        "name": name[:80],
                        "url": href,
                        "image": img.get("src", "") if img else "",
                        "query": query
                    })
                    if len(products) >= limit:
                        break
            return products
        for item in items[:limit]:
            try:
                name_el = item.select_one("h2, h3, .title, .product-title, .name")
                link_el = item.select_one("a[href]")
                img_el = item.select_one("img")
                if name_el and link_el:
                    products.append({
                        "name": name_el.get_text(strip=True)[:80],
                        "url": link_el.get("href", ""),
                        "image": img_el.get("src", img_el.get("data-src", "")) if img_el else "",
                        "query": query
                    })
            except Exception:
                continue
        return products
    return await loop.run_in_executor(None, _search)

async def download_product(product: dict) -> str:
    loop = asyncio.get_event_loop()
    def _download():
        scraper = get_logged_scraper()
        resp = scraper.get(product["url"])
        soup = BeautifulSoup(resp.text, "html.parser")
        download_link = None
        for a in soup.select("a[href]"):
            href = a.get("href", "")
            if "download" in href.lower() or ".zip" in href.lower():
                download_link = href
                break
        if not download_link:
            slug = product["url"].rstrip("/").split("/")[-1]
            download_link = f"https://www.creativefabrica.com/product/{slug}/download/"
        dl_resp = scraper.get(download_link, allow_redirects=True)
        if dl_resp.status_code == 200:
            safe_name = "".join(c for c in product['name'][:40] if c.isalnum() or c in ' _-').strip()
            filename = f"{DOWNLOAD_DIR}/{safe_name}.zip"
            with open(filename, "wb") as f:
                f.write(dl_resp.content)
            return filename
        else:
            raise Exception(f"فشل التنزيل: {dl_resp.status_code}")
    return await loop.run_in_executor(None, _download)
