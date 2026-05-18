import os
import asyncio
import aiofiles
from bs4 import BeautifulSoup
import cloudscraper
import json

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
        products = []

        # طريقة 1: API داخلي
        try:
            api_url = f"https://www.creativefabrica.com/wp-json/cf/v1/search?query={query.replace(' ', '+')}&per_page={limit}&commercial_use=1"
            resp = scraper.get(api_url)
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("products", data.get("items", data.get("results", [])))
                if isinstance(data, list):
                    items = data
                for item in items[:limit]:
                    name = item.get("name", item.get("title", item.get("post_title", "")))
                    url = item.get("url", item.get("link", item.get("permalink", "")))
                    image = item.get("image", item.get("thumbnail", item.get("featured_image", "")))
                    if isinstance(image, dict):
                        image = image.get("src", image.get("url", ""))
                    if name and url:
                        products.append({
                            "name": str(name)[:80],
                            "url": str(url),
                            "image": str(image) if image else "",
                            "query": query
                        })
                if products:
                    return products
        except Exception:
            pass

        # طريقة 2: WooCommerce API
        try:
            wc_url = f"https://www.creativefabrica.com/wp-json/wc/v3/products?search={query.replace(' ', '+')}&per_page={limit}"
            resp = scraper.get(wc_url)
            if resp.status_code == 200:
                items = resp.json()
                if isinstance(items, list):
                    for item in items[:limit]:
                        name = item.get("name", "")
                        url = item.get("permalink", "")
                        images = item.get("images", [])
                        image = images[0].get("src", "") if images else ""
                        if name and url:
                            products.append({
                                "name": name[:80],
                                "url": url,
                                "image": image,
                                "query": query
                            })
                    if products:
                        return products
        except Exception:
            pass

        # طريقة 3: HTML scraping مع selectors محدّثة
        try:
            search_url = f"https://www.creativefabrica.com/?s={query.replace(' ', '+')}&post_type=product"
            resp = scraper.get(search_url)
            soup = BeautifulSoup(resp.text, "html.parser")

            # جميع الـ selectors المحتملة
            all_selectors = [
                "div[class*='product']",
                "li[class*='product']",
                "article[class*='product']",
                "[data-product-id]",
                ".cf-product",
                ".grid-item",
            ]
            
            items = []
            for sel in all_selectors:
                items = soup.select(sel)
                if len(items) > 2:
                    break

            for item in items[:limit]:
                try:
                    # البحث عن اسم ورابط
                    link = item.select_one("a[href*='creativefabrica.com/product'], a[href*='/product/']")
                    if not link:
                        link = item.select_one("a[href]")
                    
                    name_el = item.select_one("h2, h3, h4, [class*='title'], [class*='name']")
                    img_el = item.select_one("img[src], img[data-src]")
                    
                    if link:
                        href = link.get("href", "")
                        name = name_el.get_text(strip=True) if name_el else link.get_text(strip=True)
                        img = img_el.get("src", img_el.get("data-src", "")) if img_el else ""
                        
                        if href and name and len(name) > 2 and "/product/" in href:
                            products.append({
                                "name": name[:80],
                                "url": href,
                                "image": img,
                                "query": query
                            })
                except Exception:
                    continue

            # طريقة 4: البحث عن كل روابط المنتجات
            if not products:
                seen = set()
                for a in soup.select("a[href]"):
                    href = a.get("href", "")
                    if "/product/" in href and href not in seen:
                        seen.add(href)
                        img = a.select_one("img")
                        name = a.get_text(strip=True) or href.split("/product/")[-1].replace("-", " ")
                        if name and len(name) > 2:
                            products.append({
                                "name": name[:80],
                                "url": href,
                                "image": img.get("src", "") if img else "",
                                "query": query
                            })
                        if len(products) >= limit:
                            break
        except Exception as e:
            raise Exception(f"فشل البحث: {str(e)}")

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
