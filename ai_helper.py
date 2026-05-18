import os
import aiohttp
import json
import re

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

async def generate_product_content(product: dict) -> dict:
    """توليد محتوى المنتج باستخدام Claude AI"""
    
    prompt = f"""You are a digital marketing expert specializing in selling creative design files.

Product name: {product['name']}
Niche: {product.get('query', 'creative designs')}

Write marketing content in English. Respond ONLY with a valid JSON object, no extra text, no markdown:

{{
  "title": "catchy product title max 80 chars",
  "description": "compelling marketing description 150-200 words",
  "keywords": ["keyword1", "keyword2", "keyword3", "keyword4", "keyword5"],
  "price": "4.99",
  "tiktok_tags": "#svg #design #cricut #crafts #diy #silhouette #crafting #svgfile #cuttingfile #designbundle"
}}"""

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
    }
    
    payload = {
        "model": "claude-haiku-4-5-20251001",
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
            
            if "error" in data:
                raise Exception(f"Anthropic API error: {data['error'].get('message', 'Unknown error')}")
            
            text = data["content"][0]["text"].strip()
            
            # تنظيف الرد
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            text = text.strip()
            
            # استخراج JSON
            json_match = re.search(r'\{.*\}', text, re.DOTALL)
            if json_match:
                text = json_match.group()
            
            content = json.loads(text)
            
            # التأكد من وجود جميع الحقول
            content.setdefault("title", product['name'])
            content.setdefault("description", f"Beautiful {product['name']} for your creative projects!")
            content.setdefault("keywords", ["svg", "design", "cricut", "crafts", "diy"])
            content.setdefault("price", "4.99")
            content.setdefault("tiktok_tags", "#svg #design #cricut #crafts #diy")
            
            return content
