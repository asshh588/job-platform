from django.contrib import admin
from .models import Job


@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = (
        'title',
        'company',
        'location',
        'source',
        'posted_at',
        'created_at',
    )
    list_filter = ('source', 'location')
    search_fields = ('title', 'company')
    ordering = ('-created_at',)
