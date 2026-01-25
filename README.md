# Job Platform

منصة وظائف مبنية باستخدام Django، تقوم بجمع وعرض الوظائف من عدة مصادر.

## المميزات
- عرض الوظائف
- بحث وتصفية
- Pagination
- واجهة مبنية بـ Tailwind CSS

## المتطلبات
- Python 3.9+
- Django

## طريقة التشغيل
```bash
git clone https://github.com/asshh588/job-platform.git
cd job-platform
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
