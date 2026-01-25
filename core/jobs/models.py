from django.db import models


class Job(models.Model):
    SOURCE_CHOICES = (
        ('jadarah', 'Jadarah'),
        ('linkedin', 'LinkedIn'),
    )

    title = models.CharField(max_length=255, db_index=True)
    company = models.CharField(max_length=255)
    location = models.CharField(max_length=255, blank=True)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    external_id = models.CharField(max_length=255, unique=True)
    url = models.URLField()
    posted_at = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
