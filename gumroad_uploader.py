import os
import aiohttp
import json

GUMROAD_TOKEN = os.getenv("GUMROAD_TOKEN")

async def upload_to_gumroad(file_path: str, content: dict) -> dict:
    """رفع المنتج على Gumroad"""
    
    headers = {
        "Authorization": f"Bearer {GUMROAD_TOKEN}"
    }
    
    # إنشاء المنتج أولاً
    product_data = {
        "name": content["title"],
        "description": content["description"],
        "price": int(float(content["price"]) * 100),  # بالسنت
        "tags": ",".join(content.get("keywords", [])),
        "published": True,
    }
    
    async with aiohttp.ClientSession() as session:
        # إنشاء المنتج
        async with session.post(
            "https://api.gumroad.com/v2/products",
            headers=headers,
            data=product_data
        ) as response:
            result = await response.json()
            
            if not result.get("success"):
                raise Exception(f"فشل إنشاء المنتج: {result.get('message', 'خطأ غير معروف')}")
            
            product_id = result["product"]["id"]
            product_url = result["product"]["short_url"]
            
        # رفع الملف
        with open(file_path, "rb") as f:
            file_data = aiohttp.FormData()
            file_data.add_field(
                "file",
                f,
                filename=os.path.basename(file_path),
                content_type="application/zip"
            )
            
            async with session.put(
                f"https://api.gumroad.com/v2/products/{product_id}/files",
                headers=headers,
                data=file_data
            ) as file_response:
                file_result = await file_response.json()
        
        return {
            "product_id": product_id,
            "url": product_url,
            "title": content["title"],
            "price": content["price"]
        }
