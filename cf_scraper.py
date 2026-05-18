import os
import asyncio
import aiofiles
from playwright.async_api import async_playwright

CF_EMAIL = os.getenv("CF_EMAIL", "")
CF_PASSWORD = os.getenv("CF_PASSWORD", "")
DOWNLOAD_DIR = "/tmp/downloads"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

async def get_browser():
    """تشغيل متصفح حقيقي"""
    playwright = await async_playwright().start()
    browser = await playwright.chromium.launch(
        headless=True,
        args=[
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-gpu",
        ]
    )
    return playwright, browser

async def login(page):
    """تسجيل الدخول في Creative Fabrica"""
    await page.goto("https://www.creativefabrica.com/login/", wait_until="networkidle")
    await page.fill("input[name='username']", CF_EMAIL)
    await page.fill("input[name='password']", CF_PASSWORD)
    await page.click("button[type='submit'], input[type='submit']")
    await page.wait_for_load_state("networkidle")
    
    # التحقق من نجاح تسجيل الدخول
    if "login" in page.url or "incorrect" in await page.content():
        raise Exception("❌ فشل تسجيل الدخول - تحقق من CF_EMAIL و CF_PASSWORD")
    
    return True

async def search_products(query: str, limit: int = 8) -> list:
    """البحث عن منتجات في Creative Fabrica"""
    playwright, browser = await get_browser()
    products = []
    
    try:
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()
        
        # تسجيل الدخول
        await login(page)
        
        # البحث
        search_url = f"https://www.creativefabrica.com/?s={query.replace(' ', '+')}&post_type=product"
        await page.goto(search_url, wait_until="networkidle")
        
        # انتظار تحميل المنتجات
        await page.wait_for_timeout(2000)
        
        # استخراج المنتجات
        items = await page.query_selector_all(".product-card, .product-item, li.product, article.product")
        
        if not items:
            # بحث بديل
            items = await page.query_selector_all("a[href*='/product/']")
            for item in items[:limit]:
                href = await item.get_attribute("href")
                name = await item.inner_text()
                img = await item.query_selector("img")
                img_src = await img.get_attribute("src") if img else ""
                if href and name and len(name.strip()) > 3:
                    products.append({
                        "name": name.strip()[:80],
                        "url": href,
                        "image": img_src or "",
                        "query": query
                    })
        else:
            for item in items[:limit]:
                try:
                    name_el = await item.query_selector("h2, h3, .title, .product-title, .name")
                    link_el = await item.query_selector("a[href]")
                    img_el = await item.query_selector("img")
                    
                    if name_el and link_el:
                        name = await name_el.inner_text()
                        href = await link_el.get_attribute("href")
                        img_src = await img_el.get_attribute("src") if img_el else ""
                        
                        products.append({
                            "name": name.strip()[:80],
                            "url": href,
                            "image": img_src or "",
                            "query": query
                        })
                except Exception:
                    continue
        
        await context.close()
        
    finally:
        await browser.close()
        await playwright.stop()
    
    return products

async def download_product(product: dict) -> str:
    """تنزيل ملف المنتج"""
    playwright, browser = await get_browser()
    
    try:
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            accept_downloads=True
        )
        page = await context.new_page()
        
        # تسجيل الدخول
        await login(page)
        
        # فتح صفحة المنتج
        await page.goto(product["url"], wait_until="networkidle")
        await page.wait_for_timeout(2000)
        
        # البحث عن زر التنزيل
        download_btn = await page.query_selector(
            ".download-btn, .btn-download, a[href*='download'], button:has-text('Download'), a:has-text('Download')"
        )
        
        if download_btn:
            # تنزيل الملف
            async with page.expect_download() as download_info:
                await download_btn.click()
            
            download = await download_info.value
            safe_name = "".join(c for c in product['name'][:40] if c.isalnum() or c in ' _-').strip()
            filename = f"{DOWNLOAD_DIR}/{safe_name}.zip"
            await download.save_as(filename)
            return filename
        else:
            raise Exception("❌ لم يتم العثور على زر التنزيل")
            
    finally:
        await browser.close()
        await playwright.stop()
