from celery import shared_task
from openai import OpenAI
from django.utils import timezone
from jobs.models import Job
from jobs.prompts import build_job_prompt
import json

client = OpenAI()  # يستخدم OPENAI_API_KEY من البيئة


@shared_task(bind=True, autoretry_for=(Exception,), retry_kwargs={"max_retries": 2, "countdown": 10})
def generate_ai_job_summary(self, job_id: int):
    try:
        job = Job.objects.get(id=job_id)
    except Job.DoesNotExist:
        return "Job not found"

    # ❗ نستخدم raw_text فقط
    if not job.raw_text or len(job.raw_text.strip()) < 100:
        return "No sufficient raw_text"

    prompt = build_job_prompt(job.raw_text)

    # 🔥 استدعاء OpenAI
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": "أنت مساعد توظيف محترف."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )

    content = response.choices[0].message.content.strip()

    # 🧠 نحاول تحويل JSON
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        raise ValueError("AI did not return valid JSON")

    job.ai_summary = data.get("summary")
    job.ai_skills = data.get("skills", [])
    job.ai_generated_at = timezone.now()
    job.save(update_fields=["ai_summary", "ai_skills", "ai_generated_at"])

    return "AI summary generated"
@shared_task
def fetch_all_jobs_task():
    """
    Temporary test task to verify Celery + Beat execution
    """
    print("✅ Fetch all jobs task executed")
    return "fetch_all_jobs_task ran successfully"
