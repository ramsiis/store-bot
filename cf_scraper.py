import os
import aiohttp
import aiofiles
from bs4 import BeautifulSoup

CF_EMAIL = os.getenv("CF_EMAIL", "")
CF_PASSWORD = os.getenv("CF_PASSWORD", "")
DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
}

async def get_logged_in_session() -> aiohttp.ClientSession:
    """إنشاء جلسة مع تسجيل الدخول التلقائي"""
    session = aiohttp.ClientSession(headers=HEADERS)
    try:
        # الخطوة 1: الحصول على nonce
        async with session.get("https://www.creativefabrica.com/login/") as resp:
            html = await resp.text()
            soup = BeautifulSoup(html, "html.parser")
            nonce_input = soup.select_one("input[name='woocommerce-login-nonce']")
            nonce = nonce_input.get("value", "") if nonce_input else ""

        # الخطوة 2: تسجيل الدخول
        login_data = {
            "username": CF_EMAIL,
            "password": CF_PASSWORD,
            "woocommerce-login-nonce": nonce,
            "_wp_http_referer": "/login/",
            "login": "Log in",
        }
        async with session.post(
            "https://www.creativefabrica.com/login/",
            data=login_data,
            allow_redirects=True
        ) as resp:
            html = await resp.text()
            if "incorrect" in html.lower() or "wrong password" in html.lower():
                raise Exception("❌ بيانات Creative Fabrica خاطئة! تحقق من CF_EMAIL و CF_PASSWORD")
        return session
    except Exception as e:
        if "CF_EMAIL" in str(e) or "بيانات" in str(e):
            await session.close()
            raise e
        return session

async def search_products(query: str, limit: int = 10) -> list:
    """البحث عن منتجات في Creative Fabrica"""
    url = f"https://www.creativefabrica.com/?s={query.replace(' ', '+')}&post_type=product"
    session = await get_logged_in_session()
    try:
        async with session.get(url) as response:
            if response.status == 403:
                raise Exception("❌ فشل تسجيل الدخول - تحقق من CF_EMAIL و CF_PASSWORD في Railway Variables")
            if response.status != 200:
                raise Exception(f"فشل الاتصال بـ Creative Fabrica: {response.status}")

            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")
            products = []

            # محاولة عدة selectors
            items = []
            for sel in [".product-card", ".product-item", "article.product", "li.product"]:
                items = soup.select(sel)
                if items:
                    break

            # بحث بديل عبر الروابط
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
                    name_el = item.select_one("h2, h3, .product-title, .title, .name")
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
    finally:
        await session.close()

async def download_product(product: dict) -> str:
    """تنزيل ملف المنتج"""
    session = await get_logged_in_session()
    try:
        async with session.get(product["url"]) as response:
            html = await response.text()
            soup = BeautifulSoup(html, "html.parser")

            download_link = None
            for a in soup.select("a[href]"):
                href = a.get("href", "")
                if "download" in href.lower() or ".zip" in href.lower():
                    download_link = href
                    break

            if not download_link:
                btn = soup.select_one(".download-btn, .btn-download, [data-download]")
                if btn:
                    download_link = btn.get("href") or btn.get("data-download")

            if not download_link:
                slug = product["url"].rstrip("/").split("/")[-1]
                download_link = f"https://www.creativefabrica.com/product/{slug}/download/"

            async with session.get(download_link, allow_redirects=True) as dl_response:
                if dl_response.status == 200:
                    safe_name = "".join(c for c in product['name'][:40] if c.isalnum() or c in ' _-').strip()
                    filename = f"{DOWNLOAD_DIR}/{safe_name}.zip"
                    async with aiofiles.open(filename, "wb") as f:
                        await f.write(await dl_response.read())
                    return filename
                else:
                    raise Exception(f"فشل التنزيل: {dl_response.status}")
    finally:
        await session.close()
