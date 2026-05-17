import os
import asyncio
import aiohttp
import aiofiles
from PIL import Image, ImageDraw, ImageFont
import imageio
import numpy as np

DOWNLOAD_DIR = "/tmp/videos"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

async def create_promo_video(product: dict, content: dict) -> str:
    """إنشاء فيديو ترويجي بسيط للمنتج"""
    
    output_path = f"{DOWNLOAD_DIR}/{product['name'][:30].replace(' ', '_')}_promo.mp4"
    
    # تنزيل صورة المنتج
    image_path = await download_image(product.get("image", ""))
    
    # إنشاء فريمات الفيديو
    frames = []
    
    # الفريم 1: صورة المنتج مع العنوان
    frame1 = create_frame(
        image_path=image_path,
        title=content["title"],
        subtitle="✨ Available Now on Gumroad!",
        bg_color=(25, 25, 35),
        duration=90  # 3 ثواني بـ 30fps
    )
    frames.extend(frame1)
    
    # الفريم 2: الوصف
    frame2 = create_text_frame(
        text=content["description"][:150] + "...",
        bg_color=(35, 25, 55),
        duration=90
    )
    frames.extend(frame2)
    
    # الفريم 3: السعر والهاشتاقات
    frame3 = create_text_frame(
        text=f"💰 Only ${content['price']}\n\n{content['tiktok_tags'][:100]}",
        bg_color=(25, 35, 55),
        duration=60
    )
    frames.extend(frame3)
    
    # حفظ الفيديو
    writer = imageio.get_writer(output_path, fps=30, quality=8)
    for frame in frames:
        writer.append_data(frame)
    writer.close()
    
    return output_path

def create_frame(image_path, title, subtitle, bg_color, duration):
    """إنشاء فريم مع صورة"""
    frames = []
    
    for i in range(duration):
        img = Image.new("RGB", (1080, 1920), bg_color)
        draw = ImageDraw.Draw(img)
        
        # رسم الصورة
        if image_path and os.path.exists(image_path):
            try:
                product_img = Image.open(image_path).convert("RGB")
                product_img = product_img.resize((900, 900))
                img.paste(product_img, (90, 200))
            except Exception:
                pass
        
        # العنوان
        draw.rectangle([0, 1150, 1080, 1920], fill=(15, 15, 25))
        draw_text_wrapped(draw, title, 540, 1250, max_width=900, font_size=52, color=(255, 255, 255))
        draw_text_wrapped(draw, subtitle, 540, 1500, max_width=900, font_size=40, color=(150, 220, 255))
        
        frames.append(np.array(img))
    
    return frames

def create_text_frame(text, bg_color, duration):
    """إنشاء فريم نصي"""
    frames = []
    
    for i in range(duration):
        img = Image.new("RGB", (1080, 1920), bg_color)
        draw = ImageDraw.Draw(img)
        draw_text_wrapped(draw, text, 540, 800, max_width=950, font_size=44, color=(255, 255, 255))
        frames.append(np.array(img))
    
    return frames

def draw_text_wrapped(draw, text, x, y, max_width, font_size, color):
    """رسم نص مع التفاف تلقائي"""
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()
    
    words = text.split()
    lines = []
    current_line = ""
    
    for word in words:
        test_line = f"{current_line} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word
    
    if current_line:
        lines.append(current_line)
    
    total_height = len(lines) * (font_size + 10)
    start_y = y - total_height // 2
    
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text((x - text_width // 2, start_y), line, font=font, fill=color)
        start_y += font_size + 10

async def download_image(url: str) -> str:
    """تنزيل صورة المنتج"""
    if not url:
        return ""
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    img_path = f"{DOWNLOAD_DIR}/product_img.jpg"
                    async with aiofiles.open(img_path, "wb") as f:
                        await f.write(await response.read())
                    return img_path
    except Exception:
        pass
    return ""
