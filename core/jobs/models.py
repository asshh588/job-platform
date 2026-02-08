from hashlib import sha1

from django.db import models
from django.utils.text import slugify


class Job(models.Model):
    
    class Source(models.TextChoices):
        JADARAH = "jadarah", "Jadarah"
        JOBZATY = "jobzaty", "JobZaty"
        EWDIFH = "ewdifh", "أي وظيفة"
        LINKEDIN = "linkedin", "LinkedIn"  # موجود للاحتياط

    title = models.CharField(max_length=255, db_index=True)
    company = models.CharField(max_length=255, db_index=True)
    location = models.CharField(max_length=255, blank=True, default="", db_index=True)

    source = models.CharField(max_length=20, choices=Source.choices, db_index=True)

    # اختياري لبعض المصادر
    external_id = models.CharField(max_length=255, blank=True, default="", db_index=True)

    # صفحة الإعلان في المصدر
    url = models.URLField(max_length=800)

    # رابط التقديم
    apply_url = models.URLField(max_length=800, blank=True, default="")

    posted_at = models.DateField(null=True, blank=True, db_index=True)

    last_seen_at = models.DateTimeField(null=True, blank=True, db_index=True)

    fetched_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Slug فريد
    slug = models.SlugField(max_length=320, unique=True, blank=True)

    is_active = models.BooleanField(default=True, db_index=True)

    # ⚠️ وصف تقليدي (قد يكون فارغ لبعض المصادر مثل ewdifh)
    description = models.TextField(blank=True, null=True)

    # ✅ النص الخام المستخرج من <article> (للـ AI)
    raw_text = models.TextField(
        blank=True,
        null=True,
        help_text="Raw text extracted from source article (used for AI processing)"
    )

    # ✅ مخرجات الـ AI
    ai_summary = models.TextField(blank=True, null=True, help_text="AI-generated job summary")
    ai_skills = models.JSONField(blank=True, null=True, help_text="AI-extracted skills list")
    ai_generated_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        ordering = ["-posted_at", "-id"]
        indexes = [
            models.Index(fields=["source", "posted_at"]),
            models.Index(fields=["is_active", "posted_at"]),
        ]
        constraints = [
            models.UniqueConstraint(fields=["source", "url"], name="uniq_job_source_url"),
        ]

    def _build_unique_slug(self) -> str:
        """
        Slug حتمي وفريد:
        base من (title-company) + token مشتق من url
        """
        base = slugify(f"{self.title}-{self.company}")[:200] or "job"
        token_src = (self.url or self.external_id or f"{self.title}-{self.company}").encode("utf-8")
        token = sha1(token_src).hexdigest()[:8]
        return f"{base}-{token}"

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = self._build_unique_slug()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.title} ({self.company})"
        
