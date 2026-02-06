# jobs/management/commands/fetch_ewdifh_jobs.py

import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from django.core.management.base import BaseCommand
from django.db import transaction

from jobs.models import Job


BASE_URL = "https://www.ewdifh.com"

# ✅ صفحة القائمة الصحيحة (بدلاً من /jobs/)
LIST_URL = f"{BASE_URL}/category/all-jobs"  # https://www.ewdifh.com/category/all-jobs?page=2


def clean(x: str) -> str:
    return re.sub(r"\s+", " ", (x or "").strip())


def is_denied_url(u: str) -> bool:
    """استبعاد روابط السوشال/غير التقديم"""
    low = (u or "").lower()
    deny = [
        "twitter.com", "x.com", "facebook.com", "instagram.com",
        "t.me", "telegram.me", "wa.me", "whatsapp.com",
        "snapchat.com", "tiktok.com", "youtube.com",
    ]
    return any(d in low for d in deny)


def parse_job_detail(session: requests.Session, job_url: str, timeout: int = 25) -> dict | None:
    r = session.get(job_url, timeout=timeout)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # Title
    h1 = soup.find("h1")
    title = clean(h1.get_text(" ", strip=True)) if h1 else ""
    if not title:
        return None

    # Company (محاولة بسيطة: غالبًا يظهر اسم الجهة قريب من أعلى الصفحة)
    company = ""
    # أحيانًا يظهر تحت العنوان مباشرة
    if h1:
        for el in h1.find_all_next(["h2", "h3", "p", "span", "div"], limit=30):
            t = clean(el.get_text(" ", strip=True))
            if not t or t == title:
                continue
            # تجاهل عبارات زمن/تنقل
            if any(k in t for k in ["منذ", "دقيقة", "ساعة", "يوم", "الرئيسية", "جميع الوظائف"]):
                continue
            if 2 <= len(t) <= 80:
                company = t
                break

    # Location (مش دايم موجودة بشكل ثابت)
    location = ""

    # Apply URL: نبحث عن "رابط التقديم" / "التقديم" / "اضغط هنا"
    apply_url = ""
    keywords = ["رابط التقديم", "التقديم", "قدّم", "قدم", "اضغط هنا", "Apply", "Apply Now"]

    candidates = []
    for a in soup.select("a[href]"):
        href = (a.get("href") or "").strip()
        if not href:
            continue

        txt = clean(a.get_text(" ", strip=True))
        if not txt:
            continue

        if not any(k.lower() in txt.lower() for k in keywords):
            continue

        abs_url = urljoin(BASE_URL, href)

        if is_denied_url(abs_url):
            continue

        # استبعاد روابط داخلية واضحة غير تقديم
        low = abs_url.lower()
        if "ewdifh.com" in low and ("/category/" in low or "/privacy" in low or "/terms" in low):
            continue

        # ترجيح الروابط الخارجية
        host = urlparse(abs_url).netloc.lower()
        score = 0
        if host and "ewdifh.com" not in host:
            score += 20
        if a.get("target") == "_blank":
            score += 3

        candidates.append((score, abs_url))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        apply_url = candidates[0][1]

    return {
        "title": title,
        "company": company or "غير محدد",
        "location": location,
        "url": job_url,
        "apply_url": apply_url,
    }


def fetch_ewdifh_jobs(pages: int = 1, sleep_seconds: float = 1.0, timeout: int = 25, debug: bool = False):
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; JobPlatformBot/1.0)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ar,en-US;q=0.9,en;q=0.8",
        "Connection": "keep-alive",
    })

    summary = {
        "fetched_pages": 0,
        "list_job_links": 0,
        "parsed_jobs": 0,
        "created": 0,
        "updated": 0,
        "errors": [],
    }

    for page in range(1, pages + 1):
        list_url = LIST_URL if page == 1 else f"{LIST_URL}?page={page}"

        try:
            r = session.get(list_url, timeout=timeout)
            r.raise_for_status()
        except Exception as e:
            summary["errors"].append({"stage": "list", "page": page, "url": list_url, "error": str(e)})
            continue

        summary["fetched_pages"] += 1
        soup = BeautifulSoup(r.text, "html.parser")

        # روابط الوظائف عادةً تكون /jobs/<id>
        job_links = set()
        for a in soup.select("a[href]"):
            href = (a.get("href") or "").strip()
            if not href:
                continue
            abs_url = urljoin(BASE_URL, href)

            # التقط روابط التفاصيل: /jobs/<digits>
            if re.search(r"/jobs/\d+/?$", abs_url):
                job_links.add(abs_url)

        summary["list_job_links"] += len(job_links)

        if debug:
            print(f"[DEBUG] page={page} list_url={list_url}")
            print(f"[DEBUG] links_found={len(job_links)}")

        jobs_data = []
        for job_url in job_links:
            try:
                data = parse_job_detail(session, job_url, timeout=timeout)
                if not data:
                    continue
                jobs_data.append(data)
            except Exception as e:
                summary["errors"].append({"stage": "detail", "page": page, "url": job_url, "error": str(e)})

        summary["parsed_jobs"] += len(jobs_data)

        with transaction.atomic():
            for j in jobs_data:
                obj, created = Job.objects.update_or_create(
                    source="ewdifh",
                    url=j["url"],
                    defaults={
                        "title": j["title"],
                        "company": j["company"],
                        "location": j["location"],
                        "apply_url": j.get("apply_url", ""),
                    },
                )
                summary["created"] += int(created)
                summary["updated"] += int(not created)

        if sleep_seconds:
            time.sleep(sleep_seconds)

    return summary


class Command(BaseCommand):
    help = "Fetch jobs from ewdifh.com (أي وظيفة) and upsert into Job model."

    def add_arguments(self, parser):
        parser.add_argument("--pages", type=int, default=1)
        parser.add_argument("--sleep", type=float, default=1.0)
        parser.add_argument("--timeout", type=int, default=25)
        parser.add_argument("--debug", action="store_true")

    def handle(self, *args, **options):
        pages = max(1, int(options["pages"]))
        sleep_seconds = max(0.0, float(options["sleep"]))
        timeout = max(5, int(options["timeout"]))
        debug = bool(options["debug"])

        self.stdout.write(f"Fetching Ewdifh jobs: pages={pages}, sleep={sleep_seconds}, timeout={timeout}")
        summary = fetch_ewdifh_jobs(pages=pages, sleep_seconds=sleep_seconds, timeout=timeout, debug=debug)

        self.stdout.write(self.style.SUCCESS(
            "Done. "
            f"fetched_pages={summary['fetched_pages']} "
            f"list_job_links={summary['list_job_links']} "
            f"parsed_jobs={summary['parsed_jobs']} "
            f"created={summary['created']} updated={summary['updated']}"
        ))

        if summary["errors"]:
            self.stdout.write(self.style.WARNING("Errors (showing up to 20):"))
            for e in summary["errors"][:20]:
                self.stdout.write(f"- {e}")
