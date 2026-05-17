import os
import asyncio
import aiohttp
import aiofiles
from bs4 import BeautifulSoup
import json

CF_COOKIES = os.getenv("CF_COOKIES", "")
DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Cookie": CF_COOKIES,
}

async def search_products(query: str, limit: int = 10) -> list:
    """البحث عن منتجات في Creative Fabrica"""
    url = f"https://www.creativefabrica.com/?s={query.replace(' ', '+')}&post_type=product"
    
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS) as response:
            if response.status != 200:
                raise Exception(f"فشل الاتصال بـ Creative Fabrica: {response.status}")
            
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            
            products = []
            items = soup.select(".product-card, .product-item, article.product")
            
            for item in items[:limit]:
                try:
                    name_el = item.select_one("h2, h3, .product-title, .title")
                    link_el = item.select_one("a[href*='creativefabrica.com']")
                    img_el = item.select_one("img")
                    
                    if name_el and link_el:
                        products.append({
                            "name": name_el.get_text(strip=True),
                            "url": link_el.get("href", ""),
                            "image": img_el.get("src", "") if img_el else "",
                            "query": query
                        })
                except Exception:
                    continue
            
            return products

async def download_product(product: dict) -> str:
    """تنزيل ملف المنتج"""
    async with aiohttp.ClientSession() as session:
        # فتح صفحة المنتج
        async with session.get(product["url"], headers=HEADERS) as response:
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            
            # البحث عن رابط التنزيل
            download_link = None
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if "download" in href.lower() or ".zip" in href.lower():
                    download_link = href
                    break
            
            if not download_link:
                # محاولة API التنزيل المباشر
                product_id = product["url"].rstrip("/").split("/")[-1]
                download_link = f"https://www.creativefabrica.com/wp-json/cf/v1/download/{product_id}"
            
            # تنزيل الملف
            async with session.get(download_link, headers=HEADERS) as dl_response:
                if dl_response.status == 200:
                    filename = f"{DOWNLOAD_DIR}/{product['name'][:50].replace(' ', '_')}.zip"
                    async with aiofiles.open(filename, "wb") as f:
                        await f.write(await dl_response.read())
                    return filename
                else:
                    raise Exception(f"فشل التنزيل: {dl_response.status}")
