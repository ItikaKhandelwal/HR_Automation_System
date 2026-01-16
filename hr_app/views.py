# hr_app/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth import login, logout, authenticate
from django.http import JsonResponse
from django.db.models import Q
from collections import Counter
import os

from .models import Candidate, Category, SkillKeyword
from .utils.cv_parser import CVParser, CVAnalyzer


def home(request):
    """
    Home page view - shows card-based dashboard similar to iLovePDF
    """
    # Count statistics
    total_candidates = Candidate.objects.count()
    processed_candidates = Candidate.objects.filter(is_processed=True).count()
    categories_count = Category.objects.count()
    
    context = {
        'total_candidates': total_candidates,
        'processed_candidates': processed_candidates,
        'categories_count': categories_count,
    }
    return render(request, 'hr_app/home.html', context)


def login_view(request):
    """
    Custom login view for HR authentication
    """
    # If user is already authenticated, redirect to home
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, 'Login successful!')
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password')
    
    return render(request, 'hr_app/login.html')


@login_required
def logout_view(request):
    """
    Logout view
    """
    logout(request)
    messages.success(request, 'You have been logged out successfully.')
    return redirect('login')


@login_required
def upload_cv(request):
    """
    Handle CV file upload and initial processing
    """
    if request.method == 'POST':
        # Get form data
        name = request.POST.get('name', '').strip()
        cv_file = request.FILES.get('cv_file')
        
        if not cv_file:
            messages.error(request, 'Please select a CV file')
            return redirect('upload_cv')
        
        # Validate file type
        allowed_extensions = ['.pdf', '.docx']
        file_extension = os.path.splitext(cv_file.name)[1].lower()
        
        if file_extension not in allowed_extensions:
            messages.error(request, 'Only PDF and DOCX files are allowed')
            return redirect('upload_cv')
        
        # Validate file size (10MB max)
        if cv_file.size > 10 * 1024 * 1024:  # 10MB in bytes
            messages.error(request, 'File size must be less than 10MB')
            return redirect('upload_cv')
        
        # Save candidate with basic info
        candidate = Candidate(
            name=name or os.path.splitext(cv_file.name)[0],  # Use filename without extension if name not provided
            cv_file=cv_file,
            uploaded_by=request.user
        )
        candidate.save()
        
        messages.success(request, f'CV uploaded successfully for {candidate.name}')
        
        # Redirect to processing page
        return redirect('process_cv', candidate_id=candidate.id)
    
    return render(request, 'hr_app/upload_cv.html')


@login_required
def process_cv(request, candidate_id):
    """
    Process uploaded CV: extract text, analyze, and categorize
    """
    candidate = get_object_or_404(Candidate, id=candidate_id)
    
    # Add skill keywords context for the template
    skill_keywords = CVAnalyzer.SKILL_KEYWORDS
    
    if request.method == 'POST':
        try:
            # Check if file exists
            if not candidate.cv_file or not os.path.exists(candidate.cv_file.path):
                messages.error(request, 'CV file not found. Please upload again.')
                return redirect('upload_cv')
            
            # Get file path and extension
            file_path = candidate.cv_file.path
            file_extension = os.path.splitext(candidate.cv_file.name)[1].lower()
            
            # Step 1: Extract text from CV with cleaning
            cv_text = CVParser.extract_text(file_path, file_extension)
            cv_text = CVParser.clean_extracted_text(cv_text)  # Clean the text
            
            if not cv_text.strip():
                messages.warning(request, 'No text could be extracted. The PDF might be scanned or image-based.')
                candidate.raw_text = "No text could be extracted. Possibly a scanned PDF."
            else:
                candidate.raw_text = cv_text
            
            # Step 2: Extract additional information if not already provided
            if not candidate.name or candidate.name == os.path.splitext(candidate.cv_file.name)[0]:
                extracted_name = CVAnalyzer.extract_name(cv_text)
                if extracted_name:
                    candidate.name = extracted_name
            
            if not candidate.email:
                extracted_email = CVAnalyzer.extract_email(cv_text)
                if extracted_email:
                    candidate.email = extracted_email
            
            if not candidate.phone:
                extracted_phone = CVAnalyzer.extract_phone(cv_text)
                if extracted_phone:
                    candidate.phone = extracted_phone
            
            # Step 3: Analyze text (only if we have text)
            if cv_text.strip():
                skills = CVAnalyzer.extract_skills(cv_text)
                experience_years = CVAnalyzer.extract_experience(cv_text)
                education = CVAnalyzer.extract_education(cv_text)
                
                # Step 4: Categorize candidate
                category_name = CVAnalyzer.categorize_candidate(skills, experience_years)
                
                # Get or create category
                category, created = Category.objects.get_or_create(
                    name=category_name,
                    defaults={
                        'description': f'Auto-generated category: {category_name}',
                        'keywords': ','.join(skills) if skills else ''
                    }
                )
                
                # Update candidate with extracted information
                candidate.skills = ','.join(skills)
                candidate.experience_years = experience_years
                candidate.education = education
                candidate.category = category
            else:
                # If no text, mark as processed but keep empty
                candidate.skills = ''
                candidate.experience_years = 0
                candidate.education = 'Could not extract education'
                # Create or get an "Unknown" category
                category, created = Category.objects.get_or_create(
                    name='Unknown',
                    defaults={
                        'description': 'CVs that could not be processed',
                        'keywords': 'unknown'
                    }
                )
                candidate.category = category
            
            candidate.is_processed = True
            candidate.save()
            
            messages.success(request, f'CV processed successfully! Category: {candidate.category.name}')
            
            # Show what was extracted
            if candidate.skills:
                messages.info(request, f'Skills detected: {candidate.skills}')
            
            return redirect('candidate_detail', candidate_id=candidate.id)
            
        except Exception as e:
            messages.error(request, f'Error processing CV: {str(e)}')
            print(f"Error processing CV {candidate_id}: {str(e)}")
            return redirect('process_cv', candidate_id=candidate.id)
    
    # For GET request, show extracted text for verification
    context = {
        'candidate': candidate,
        'skill_keywords': skill_keywords,
    }
    
    # Try to extract text for preview
    if candidate.cv_file and os.path.exists(candidate.cv_file.path):
        file_extension = os.path.splitext(candidate.cv_file.name)[1].lower()
        try:
            preview_text = CVParser.extract_text(candidate.cv_file.path, file_extension)
            preview_text = CVParser.clean_extracted_text(preview_text)
            
            if preview_text:
                # Show better preview with line breaks preserved
                context['preview_text'] = preview_text[:1000] + '...' if len(preview_text) > 1000 else preview_text
            else:
                context['preview_error'] = "No text could be extracted. This might be a scanned PDF or image-based document."
        except Exception as e:
            context['preview_error'] = f"Error extracting text: {str(e)}"
    
    return render(request, 'hr_app/process_cv.html', context)


@login_required
def dashboard(request):
    """
    Main dashboard to view and filter candidates
    """
    candidates = Candidate.objects.all().select_related('category').order_by('-uploaded_at')
    categories = Category.objects.all()
    
    # Get filter parameters
    category_filter = request.GET.get('category')
    skill_filter = request.GET.get('skill')
    search_query = request.GET.get('search')
    experience_filter = request.GET.get('experience')
    
    # Apply filters
    if category_filter and category_filter != 'all':
        candidates = candidates.filter(category__name=category_filter)
    
    if skill_filter and skill_filter.strip():
        candidates = candidates.filter(skills__icontains=skill_filter.strip())
    
    if search_query and search_query.strip():
        candidates = candidates.filter(
            Q(name__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(raw_text__icontains=search_query)
        )
    
    if experience_filter:
        if experience_filter == 'fresher':
            candidates = candidates.filter(experience_years=0)
        elif experience_filter == 'junior':
            candidates = candidates.filter(experience_years__gt=0, experience_years__lt=3)
        elif experience_filter == 'mid':
            candidates = candidates.filter(experience_years__gte=3, experience_years__lt=7)
        elif experience_filter == 'senior':
            candidates = candidates.filter(experience_years__gte=7)
    
    # Get counts for statistics
    total_count = candidates.count()
    processed_count = candidates.filter(is_processed=True).count()
    unprocessed_count = total_count - processed_count
    
    context = {
        'candidates': candidates,
        'categories': categories,
        'current_category': category_filter,
        'current_skill': skill_filter,
        'search_query': search_query,
        'experience_filter': experience_filter,
        'total_count': total_count,
        'processed_count': processed_count,
        'unprocessed_count': unprocessed_count,
    }
    return render(request, 'hr_app/dashboard.html', context)


@login_required
def candidate_detail(request, candidate_id):
    """
    View detailed information about a candidate
    """
    candidate = get_object_or_404(Candidate, id=candidate_id)
    
    # Convert comma-separated skills to list for template
    skills_list = candidate.get_skills_list()
    
    # Get similar candidates (same category)
    similar_candidates = Candidate.objects.filter(
        category=candidate.category
    ).exclude(
        id=candidate.id
    )[:5]  # Limit to 5 similar candidates
    
    context = {
        'candidate': candidate,
        'skills_list': skills_list,
        'experience_level': candidate.get_experience_level(),
        'similar_candidates': similar_candidates,
    }
    return render(request, 'hr_app/candidate_detail.html', context)


@login_required
def categorize_candidates(request):
    """
    Bulk categorization view - categorize all unprocessed candidates
    """
    categories = Category.objects.all()
    
    if request.method == 'POST':
        unprocessed_candidates = Candidate.objects.filter(is_processed=False)
        categorized_count = 0
        error_count = 0
        
        for candidate in unprocessed_candidates:
            try:
                # Check if we have the file
                if candidate.cv_file and os.path.exists(candidate.cv_file.path):
                    # Extract text from CV
                    file_extension = os.path.splitext(candidate.cv_file.name)[1].lower()
                    cv_text = CVParser.extract_text(candidate.cv_file.path, file_extension)
                    
                    if cv_text.strip():
                        candidate.raw_text = cv_text
                        
                        # Extract skills and experience
                        skills = CVAnalyzer.extract_skills(cv_text)
                        experience_years = CVAnalyzer.extract_experience(cv_text)
                        education = CVAnalyzer.extract_education(cv_text)
                        
                        # Categorize
                        category_name = CVAnalyzer.categorize_candidate(skills, experience_years)
                        category, created = Category.objects.get_or_create(
                            name=category_name,
                            defaults={
                                'description': f'Auto-generated category: {category_name}',
                                'keywords': ','.join(skills) if skills else ''
                            }
                        )
                        
                        # Update candidate
                        candidate.skills = ','.join(skills)
                        candidate.experience_years = experience_years
                        candidate.education = education
                        candidate.category = category
                        candidate.is_processed = True
                        candidate.save()
                        
                        categorized_count += 1
                    else:
                        # No text extracted
                        candidate.raw_text = "No text could be extracted"
                        category, created = Category.objects.get_or_create(
                            name='Unknown',
                            defaults={
                                'description': 'CVs that could not be processed',
                                'keywords': 'unknown'
                            }
                        )
                        candidate.category = category
                        candidate.is_processed = True
                        candidate.save()
                        categorized_count += 1
                else:
                    # File doesn't exist
                    candidate.is_processed = True
                    candidate.save()
                    categorized_count += 1
                    
            except Exception as e:
                error_count += 1
                print(f"Error categorizing candidate {candidate.id}: {e}")
                # Mark as processed anyway to avoid infinite loops
                candidate.is_processed = True
                candidate.save()
        
        if error_count > 0:
            messages.warning(request, f'Successfully categorized {categorized_count} candidates with {error_count} errors')
        else:
            messages.success(request, f'Successfully categorized {categorized_count} candidates')
        
        return redirect('dashboard')
    
    # GET request - show statistics
    unprocessed_count = Candidate.objects.filter(is_processed=False).count()
    total_count = Candidate.objects.count()
    
    # Get category distribution for chart
    category_distribution = Candidate.objects.filter(
        is_processed=True
    ).values(
        'category__name'
    ).annotate(
        count=models.Count('id')
    ).order_by('-count')
    
    context = {
        'unprocessed_count': unprocessed_count,
        'total_count': total_count,
        'processed_percentage': ((total_count - unprocessed_count) / total_count * 100) if total_count > 0 else 0,
        'categories': categories,
        'category_distribution': category_distribution,
    }
    return render(request, 'hr_app/categorize.html', context)


@login_required
def skill_filter(request):
    """
    Filter candidates by specific skills
    """
    # Get all unique skills from processed candidates
    all_candidates = Candidate.objects.filter(is_processed=True)
    all_skills = set()
    
    for candidate in all_candidates:
        if candidate.skills:
            skills = [s.strip().lower() for s in candidate.skills.split(',') if s.strip()]
            all_skills.update(skills)
    
    # Sort skills alphabetically
    all_skills = sorted(all_skills)
    
    # Get skill filter from query parameter
    selected_skill = request.GET.get('skill')
    filtered_candidates = []
    
    if selected_skill:
        filtered_candidates = Candidate.objects.filter(
            skills__icontains=selected_skill,
            is_processed=True
        ).order_by('-uploaded_at')
    
    # Get skill counts for visualization
    skill_counts = {}
    for candidate in all_candidates:
        if candidate.skills:
            skills = [s.strip().lower() for s in candidate.skills.split(',') if s.strip()]
            for skill in skills:
                skill_counts[skill] = skill_counts.get(skill, 0) + 1
    
    # Sort skills by frequency
    top_skills = sorted(skill_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    context = {
        'all_skills': all_skills,
        'selected_skill': selected_skill,
        'filtered_candidates': filtered_candidates,
        'skill_counts': skill_counts,
        'top_skills': top_skills,
    }
    return render(request, 'hr_app/skill_filter.html', context)


@login_required
def delete_candidate(request, candidate_id):
    """
    Delete a candidate (with confirmation)
    """
    candidate = get_object_or_404(Candidate, id=candidate_id)
    
    if request.method == 'POST':
        candidate_name = candidate.name
        candidate.delete()
        messages.success(request, f'Candidate "{candidate_name}" deleted successfully.')
        return redirect('dashboard')
    
    # GET request - show confirmation page
    return render(request, 'hr_app/confirm_delete.html', {'candidate': candidate})


@login_required
def bulk_actions(request):
    """
    Handle bulk actions on candidates
    """
    if request.method == 'POST':
        action = request.POST.get('action')
        candidate_ids = request.POST.getlist('candidate_ids')
        
        if not candidate_ids:
            messages.warning(request, 'No candidates selected.')
            return redirect('dashboard')
        
        candidates = Candidate.objects.filter(id__in=candidate_ids)
        
        if action == 'delete':
            count = candidates.count()
            candidates.delete()
            messages.success(request, f'Deleted {count} candidate(s).')
        elif action == 'reprocess':
            for candidate in candidates:
                candidate.is_processed = False
                candidate.save()
            messages.success(request, f'Marked {candidates.count()} candidate(s) for reprocessing.')
        elif action == 'export':
            # Simple CSV export
            import csv
            from django.http import HttpResponse
            
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="candidates_export.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['Name', 'Email', 'Skills', 'Experience', 'Category', 'Uploaded Date'])
            
            for candidate in candidates:
                writer.writerow([
                    candidate.name,
                    candidate.email or '',
                    candidate.skills,
                    candidate.experience_years,
                    candidate.category.name if candidate.category else '',
                    candidate.uploaded_at.strftime('%Y-%m-%d')
                ])
            
            return response
        
        return redirect('dashboard')
    
    return redirect('dashboard')


@login_required
def analytics_dashboard(request):
    """
    Advanced analytics dashboard
    """
    # Total statistics
    total_candidates = Candidate.objects.count()
    processed_candidates = Candidate.objects.filter(is_processed=True).count()
    unprocessed_candidates = total_candidates - processed_candidates
    
    # Category distribution
    category_data = Candidate.objects.filter(
        is_processed=True
    ).values(
        'category__name'
    ).annotate(
        count=models.Count('id')
    ).order_by('-count')
    
    # Experience level distribution
    experience_levels = {
        'Fresher': Candidate.objects.filter(experience_years=0, is_processed=True).count(),
        'Junior (0-2 yrs)': Candidate.objects.filter(experience_years__gt=0, experience_years__lt=3, is_processed=True).count(),
        'Mid (3-6 yrs)': Candidate.objects.filter(experience_years__gte=3, experience_years__lt=7, is_processed=True).count(),
        'Senior (7+ yrs)': Candidate.objects.filter(experience_years__gte=7, is_processed=True).count(),
    }
    
    # Monthly upload trend (last 6 months)
    from django.utils import timezone
    from datetime import datetime, timedelta
    
    monthly_data = []
    for i in range(5, -1, -1):  # Last 6 months
        month_start = timezone.now().replace(day=1) - timedelta(days=30*i)
        month_end = month_start + timedelta(days=30)
        count = Candidate.objects.filter(
            uploaded_at__gte=month_start,
            uploaded_at__lt=month_end
        ).count()
        monthly_data.append({
            'month': month_start.strftime('%b %Y'),
            'count': count
        })
    
    # Top skills
    all_skills = []
    candidates = Candidate.objects.filter(is_processed=True)
    for candidate in candidates:
        if candidate.skills:
            skills = [s.strip().lower() for s in candidate.skills.split(',') if s.strip()]
            all_skills.extend(skills)
    
    from collections import Counter
    skill_counter = Counter(all_skills)
    top_skills = skill_counter.most_common(10)
    
    context = {
        'total_candidates': total_candidates,
        'processed_candidates': processed_candidates,
        'unprocessed_candidates': unprocessed_candidates,
        'category_data': category_data,
        'experience_levels': experience_levels,
        'monthly_data': monthly_data,
        'top_skills': top_skills,
        'processing_rate': (processed_candidates / total_candidates * 100) if total_candidates > 0 else 0,
    }
    
    return render(request, 'hr_app/analytics.html', context)


# Helper function to get category statistics
def get_category_stats():
    """
    Get statistics for all categories
    """
    categories = Category.objects.all()
    stats = []
    
    for category in categories:
        count = category.candidate_set.count()
        if count > 0:
            # Calculate average experience for this category
            candidates = category.candidate_set.all()
            avg_experience = sum(c.experience_years for c in candidates) / count
            
            stats.append({
                'category': category.name,
                'count': count,
                'avg_experience': round(avg_experience, 1),
                'description': category.description,
            })
    
    return sorted(stats, key=lambda x: x['count'], reverse=True)


# Import models at the top of the file if not already imported
from django.db import models