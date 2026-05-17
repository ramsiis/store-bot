# 🛒 بوت المتجر التلقائي

## الملفات:
- `bot.py` - البوت الرئيسي
- `cf_scraper.py` - البحث والتنزيل من Creative Fabrica
- `ai_helper.py` - توليد المحتوى بالذكاء الاصطناعي
- `gumroad_uploader.py` - الرفع على Gumroad
- `video_maker.py` - إنشاء فيديو TikTok
- `requirements.txt` - المكتبات المطلوبة
- `railway.toml` - إعدادات Railway

---

## خطوات الرفع على Railway:

### 1. إنشاء حساب GitHub
- اذهب إلى github.com
- أنشئ حساباً مجانياً
- أنشئ Repository جديد اسمه: store-bot

### 2. رفع الملفات
- في GitHub انقر "Add file" > "Upload files"
- ارفع جميع الملفات

### 3. ربط Railway
- اذهب إلى railway.app
- انقر "New Project" > "Deploy from GitHub"
- اختر الـ Repository

### 4. إضافة المتغيرات
في Railway > Variables أضف:
```
TELEGRAM_TOKEN = توكن_تيليجرام
ADMIN_ID = رقم_حسابك
ANTHROPIC_API_KEY = مفتاح_انثروبيك
GUMROAD_TOKEN = توكن_جمرود
CF_COOKIES = كوكيز_كريتيف_فابريكا
```

### 5. كيف تعرف ADMIN_ID؟
- افتح تيليجرام وتحدث مع @userinfobot
- سيرسل لك رقم حسابك

### 6. كيف تحصل على CF_COOKIES؟
- افتح creativefabrica.com من متصفح الكمبيوتر
- سجل دخول
- اضغط F12 > Network > أي طلب > Headers > Cookie
- انسخ قيمة Cookie

---

## كيف يعمل البوت:

1. افتح البوت في تيليجرام
2. اكتب /start
3. اختر "🔍 ابحث عن منتجات" أو "🤖 تشغيل تلقائي"
4. البوت يتولى الباقي تلقائياً!
