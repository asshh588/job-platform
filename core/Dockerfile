FROM python:3.11-slim

# منع إنشاء ملفات pyc
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# مجلد العمل داخل الحاوية
WORKDIR /app

# تثبيت المتطلبات
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# نسخ المشروع
COPY . .

# المنفذ
EXPOSE 8000
