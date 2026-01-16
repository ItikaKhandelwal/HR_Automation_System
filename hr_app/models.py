# hr_app/models.py
from django.db import models
from django.contrib.auth.models import User
import os

class Category(models.Model):
    """
    Represents candidate categories like 'Python Developer', 'Data Analyst', etc.
    This model stores predefined categories that can be assigned to candidates.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    keywords = models.TextField(
        help_text="Comma-separated keywords to identify this category"
    )
    
    class Meta:
        verbose_name_plural = "Categories"
    
    def __str__(self):
        return self.name


class Candidate(models.Model):
    """
    Stores information about job candidates.
    Each candidate can have multiple skills, education, and experience entries.
    """
    # Personal Information
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)
    
    # CV Information
    cv_file = models.FileField(upload_to='cvs/')
    uploaded_at = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='uploaded_candidates'
    )
    
    # Extracted Information
    raw_text = models.TextField(blank=True, help_text="Extracted text from CV")
    skills = models.TextField(blank=True, help_text="Comma-separated skills")
    experience_years = models.FloatField(default=0)
    education = models.TextField(blank=True)
    
    # Categorization
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    is_processed = models.BooleanField(default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-uploaded_at']  # Newest candidates first
    
    def __str__(self):
        return f"{self.name} - {self.category if self.category else 'Uncategorized'}"
    
    def get_filename(self):
        """Returns only the filename without path"""
        return os.path.basename(self.cv_file.name)
    
    def get_skills_list(self):
        """Returns skills as a Python list"""
        if self.skills:
            return [skill.strip() for skill in self.skills.split(',')]
        return []
    
    def get_experience_level(self):
        """Categorizes experience level based on years"""
        if self.experience_years == 0:
            return "Fresher"
        elif self.experience_years < 3:
            return "Junior"
        elif self.experience_years < 7:
            return "Mid-Level"
        else:
            return "Senior"


class SkillKeyword(models.Model):
    """
    Predefined list of skills and their variations.
    Helps in skill extraction from CV text.
    Example: 'Python' skill might have variations: 'python', 'python3', 'python programming'
    """
    name = models.CharField(max_length=100)
    variations = models.TextField(
        help_text="Comma-separated variations of this skill"
    )
    category = models.ForeignKey(
        Category, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )
    
    def __str__(self):
        return self.name
    
    def get_variations_list(self):
        """Returns variations as a list"""
        if self.variations:
            return [v.strip().lower() for v in self.variations.split(',')]
        return []