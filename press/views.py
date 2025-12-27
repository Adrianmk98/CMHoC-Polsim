from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from .models import PressRelease, PressImage, PressComment
from .forms import PressReleaseForm, ImageUploadForm, PressCommentForm
import base64
from io import BytesIO
from PIL import Image


def press_list(request):
    """List all published press releases"""
    # Get query parameters
    category = request.GET.get('category')
    tag = request.GET.get('tag')
    search = request.GET.get('search')
    
    # Base queryset
    press_releases = PressRelease.objects.filter(is_published=True)
    
    # Apply filters
    if category:
        press_releases = press_releases.filter(category=category)
    
    if tag:
        press_releases = press_releases.filter(tags__icontains=tag)
    
    if search:
        press_releases = press_releases.filter(
            Q(title__icontains=search) |
            Q(content__icontains=search) |
            Q(excerpt__icontains=search)
        )
    
    # Get featured releases
    featured = press_releases.filter(is_featured=True)[:3]
    
    # Paginate
    paginator = Paginator(press_releases, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get all categories and tags for filters
    all_categories = PressRelease.CATEGORY_CHOICES
    all_tags = set()
    for pr in PressRelease.objects.filter(is_published=True):
        all_tags.update(pr.get_tags_list())
    
    context = {
        'press_releases': page_obj,
        'featured': featured,
        'categories': all_categories,
        'tags': sorted(all_tags),
        'current_category': category,
        'current_tag': tag,
        'search_query': search,
    }
    return render(request, 'list.html', context)


def press_detail(request, slug):
    """View a single press release"""
    press_release = get_object_or_404(PressRelease, slug=slug, is_published=True)
    
    # Increment view count
    press_release.increment_views()
    
    # Get approved comments
    comments = press_release.comments.filter(is_approved=True)
    
    # Handle comment submission
    if request.method == 'POST' and request.user.is_authenticated:
        comment_form = PressCommentForm(request.POST)
        if comment_form.is_valid():
            comment = comment_form.save(commit=False)
            comment.press_release = press_release
            comment.author = request.user
            comment.save()
            messages.success(request, 'Your comment has been posted!')
            return redirect('press:detail', slug=slug)
    else:
        comment_form = PressCommentForm()
    
    # Get related press releases (same party or category)
    related = PressRelease.objects.filter(
        Q(party=press_release.party) | Q(category=press_release.category),
        is_published=True
    ).exclude(id=press_release.id)[:3]
    
    context = {
        'press_release': press_release,
        'comments': comments,
        'comment_form': comment_form,
        'related': related,
    }
    return render(request, 'detail.html', context)


@login_required
def press_create(request):
    """Create a new press release"""
    if request.method == 'POST':
        form = PressReleaseForm(request.POST)
        if form.is_valid():
            press_release = form.save(commit=False)
            press_release.author = request.user
            
            # Set party from user profile if available
            try:
                press_release.party = request.user.profile.party
            except:
                pass
            
            press_release.save()
            messages.success(request, 'Press release created successfully!')
            return redirect('press:detail', slug=press_release.slug)
    else:
        form = PressReleaseForm()
    
    context = {
        'form': form,
        'mode': 'create',
    }
    return render(request, 'form.html', context)


@login_required
def press_edit(request, slug):
    """Edit an existing press release"""
    press_release = get_object_or_404(PressRelease, slug=slug)
    
    # Check permission
    if press_release.author != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to edit this press release.")
        return redirect('press:detail', slug=slug)
    
    if request.method == 'POST':
        form = PressReleaseForm(request.POST, instance=press_release)
        if form.is_valid():
            form.save()
            messages.success(request, 'Press release updated successfully!')
            return redirect('press:detail', slug=press_release.slug)
    else:
        form = PressReleaseForm(instance=press_release)
    
    context = {
        'form': form,
        'press_release': press_release,
        'mode': 'edit',
    }
    return render(request, 'form.html', context)


@login_required
def press_delete(request, slug):
    """Delete a press release"""
    press_release = get_object_or_404(PressRelease, slug=slug)
    
    # Check permission
    if press_release.author != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to delete this press release.")
        return redirect('press:detail', slug=slug)
    
    if request.method == 'POST':
        press_release.delete()
        messages.success(request, 'Press release deleted successfully!')
        return redirect('press:list')
    
    context = {
        'press_release': press_release,
    }
    return render(request, 'delete_confirm.html', context)


@login_required
def upload_image(request):
    """Upload image and return base64 data for embedding (AJAX)"""
    if request.method == 'POST' and request.FILES.get('image'):
        try:
            image_file = request.FILES['image']
            
            # Open and process image
            img = Image.open(image_file)
            
            # Convert to RGB if necessary
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Resize if too large (max 1200px width)
            max_width = 1200
            if img.width > max_width:
                ratio = max_width / img.width
                new_height = int(img.height * ratio)
                img = img.resize((max_width, new_height), Image.Resampling.LANCZOS)
            
            # Convert to base64
            buffer = BytesIO()
            img.save(buffer, format='JPEG', quality=85)
            image_data = base64.b64encode(buffer.getvalue()).decode()
            
            return JsonResponse({
                'success': True,
                'image_data': f'data:image/jpeg;base64,{image_data}'
            })
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=400)
    
    return JsonResponse({
        'success': False,
        'error': 'No image provided'
    }, status=400)


@login_required
def my_press_releases(request):
    """View user's own press releases"""
    press_releases = PressRelease.objects.filter(author=request.user).order_by('-created_at')
    
    context = {
        'press_releases': press_releases,
    }
    return render(request, 'my_releases.html', context)


def press_by_party(request, party_id):
    """View press releases by party"""
    from forum.models import PoliticalParty
    
    party = get_object_or_404(PoliticalParty, pk=party_id)
    press_releases = PressRelease.objects.filter(party=party, is_published=True)
    
    # Paginate
    paginator = Paginator(press_releases, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'party': party,
        'press_releases': page_obj,
    }
    return render(request, 'by_party.html', context)


def press_by_author(request, username):
    """View press releases by author"""
    from django.contrib.auth.models import User
    
    author = get_object_or_404(User, username=username)
    press_releases = PressRelease.objects.filter(author=author, is_published=True)
    
    # Paginate
    paginator = Paginator(press_releases, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'author': author,
        'press_releases': page_obj,
    }
    return render(request, 'by_author.html', context)