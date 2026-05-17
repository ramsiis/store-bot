import os
import aiohttp
import json

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

async def generate_product_content(product: dict) -> dict:
    """توليد محتوى المنتج باستخدام Claude AI"""
    
    prompt = f"""أنت خبير تسويق رقمي متخصص في بيع الملفات الإبداعية.

المنتج: {product['name']}
النيش: {product.get('query', 'تصاميم إبداعية')}

اكتب لي بالإنجليزية:
1. عنوان جذاب للمنتج (max 80 حرف)
2. وصف تسويقي مقنع (150-200 كلمة)
3. 5 كلمات مفتاحية مهمة
4. سعر مناسب بالدولار (بين 3 و 9)
5. وسوم TikTok (10 هاشتاق)

أجب بصيغة JSON فقط بدون أي نص إضافي:
{{
  "title": "...",
  "description": "...",
  "keywords": ["...", "...", "...", "...", "..."],
  "price": "4.99",
  "tiktok_tags": "#tag1 #tag2 ..."
}}"""

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
    }
    
    payload = {
        "model": "claude-sonnet-4-20250514",
        "max_tokens": 1000,
        "messages": [{"role": "user", "content": prompt}]
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload
        ) as response:
            data = await response.json()
            text = data["content"][0]["text"]
            
            # تنظيف الرد وتحويله إلى JSON
            text = text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            content = json.loads(text)
            return content
