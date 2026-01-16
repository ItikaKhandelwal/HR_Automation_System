# hr_app/admin.py
from django.contrib import admin
from .models import Candidate, Category, SkillKeyword


class CandidateAdmin(admin.ModelAdmin):
    """
    Custom admin interface for Candidate model
    """
    list_display = ('name', 'email', 'category', 'experience_years', 'is_processed', 'uploaded_at')
    list_filter = ('is_processed', 'category', 'uploaded_at')
    search_fields = ('name', 'email', 'skills', 'raw_text')
    readonly_fields = ('uploaded_at', 'created_at', 'updated_at')
    fieldsets = (
        ('Personal Information', {
            'fields': ('name', 'email', 'phone')
        }),
        ('CV Information', {
            'fields': ('cv_file', 'uploaded_by', 'uploaded_at')
        }),
        ('Extracted Information', {
            'fields': ('raw_text', 'skills', 'experience_years', 'education')
        }),
        ('Categorization', {
            'fields': ('category', 'is_processed')
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        """Automatically set uploaded_by if not set"""
        if not obj.uploaded_by:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)


class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'keywords')


class SkillKeywordAdmin(admin.ModelAdmin):
    list_display = ('name', 'category')
    list_filter = ('category',)
    search_fields = ('name', 'variations')


# Register models with custom admin classes
admin.site.register(Candidate, CandidateAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(SkillKeyword, SkillKeywordAdmin)

# Customize admin site header
admin.site.site_header = "HR Automation System Admin"
admin.site.site_title = "HR Admin Portal"
admin.site.index_title = "Welcome to HR Automation System Administration"