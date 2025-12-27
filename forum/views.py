from datetime import timedelta
from django.utils import timezone
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator

from .models import Cabinet, ForumCategory, PositionHistory, Thread, Post, UserProfile
from .forms import ThreadForm, PostForm
from django.shortcuts import render
from django.contrib.auth.models import User
from .models import ForumCategory, Thread, Post, Cabinet
from voting.models import Bill, Vote
from django.db.models import Count

def index(request):
    """
    New homepage focused on press releases and upcoming events
    This replaces the old forum_index as the main homepage
    """
    # Statistics
    stats = {
        'total_threads': Thread.objects.count(),
        'total_posts': Post.objects.count(),
        'total_users': User.objects.count(),
        'active_bills': Vote.objects.filter(is_active=True).count(),
        'total_parties': 0,
    }
    
    # Try to get party count
    try:
        from parties.models import Party
        stats['total_parties'] = Party.objects.filter(is_active=True).count()
    except:
        pass
    
    # Latest press releases (requires press app)
    latest_press = []
    try:
        from press.models import PressRelease
        latest_press = PressRelease.objects.filter(
            is_published=True
        ).select_related('author', 'party').order_by('-published_at')[:6]
    except:
        pass
    
    # Current cabinet
    current_cabinet = None
    try:
        current_cabinet = Cabinet.objects.filter(is_current=True).select_related(
            'prime_minister__user', 'prime_minister__party'
        ).first()
    except:
        pass
    
    # Active votes
    active_votes = []
    try:
        active_votes = Vote.objects.filter(
            is_active=True
        ).select_related('bill', 'bill__sponsor').order_by('closes_at')[:5]
    except:
        pass
    
    # Upcoming elections (not yet completed)
    upcoming_elections = []
    try:
        from elections.models import Election
        upcoming_elections = Election.objects.filter(
            is_completed=False,
            election_date__gte=timezone.now().date()
        ).order_by('election_date')[:5]
    except:
        pass
    
    # Active party leadership elections
    party_elections = []
    try:
        from parties.models import LeadershipElection
        party_elections = LeadershipElection.objects.filter(
            is_active=True,
            closes_at__gt=timezone.now()
        ).select_related('party').order_by('closes_at')[:5]
    except:
        pass
    
    # Recent forum threads
    recent_threads = Thread.objects.select_related(
        'author', 'category'
    ).order_by('-created_at')[:5]
    
    context = {
        'stats': stats,
        'latest_press': latest_press,
        'current_cabinet': current_cabinet,
        'active_votes': active_votes,
        'upcoming_elections': upcoming_elections,
        'party_elections': party_elections,
        'recent_threads': recent_threads,
    }
    
    return render(request, 'index.html', context)


def forum_categories(request):
    """
    Separate page showing all forum categories (the old forum_index content)
    """
    # Get categories with counts and latest thread
    categories = ForumCategory.objects.annotate(
        thread_count=Count('threads'),
        post_count=Count('threads__posts')
    ).prefetch_related('threads__author')
    
    # Add latest thread to each category
    for category in categories:
        category.latest_thread = category.threads.order_by('-created_at').first()
    
    # Statistics
    total_threads = Thread.objects.count()
    total_posts = Post.objects.count()
    active_members = User.objects.filter(
        is_active=True,
        last_login__gte=timezone.now() - timedelta(days=30)
    ).count()
    
    # Recent threads across all categories
    recent_threads = Thread.objects.select_related(
        'author', 'category'
    ).annotate(
        post_count=Count('posts')
    ).order_by('-created_at')[:10]
    
    context = {
        'categories': categories,
        'total_threads': total_threads,
        'total_posts': total_posts,
        'active_members': active_members,
        'recent_threads': recent_threads,
    }
    
    return render(request, 'forum_categories.html', context)


def forum_index(request):
    """Backward compatibility - redirects to forum categories"""
    return forum_categories(request)

def category_detail(request, category_id):
    """Display threads in a category with flair filtering"""
    category = get_object_or_404(ForumCategory, pk=category_id)
    threads = category.threads.all()
    
    # Flair filtering
    flair_filter = request.GET.get('flair', '')
    if flair_filter:
        threads = threads.filter(flair__id=flair_filter)
    
    # Get available flairs for this category
    from .models import Flair
    available_flairs = Flair.objects.filter(category=category)
    
    paginator = Paginator(threads, 20)  # 20 threads per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'category': category,
        'page_obj': page_obj,
        'available_flairs': available_flairs,
        'flair_filter': flair_filter,
    }
    return render(request, 'category_detail.html', context)


def thread_detail(request, thread_id):
    """Display posts in a thread"""
    thread = get_object_or_404(Thread, pk=thread_id)
    
    # Increment view count
    thread.views += 1
    thread.save()
    
    posts = thread.posts.all()
    paginator = Paginator(posts, 15)  # 15 posts per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Reply form
    if request.method == 'POST' and request.user.is_authenticated:
        form = PostForm(request.POST)
        if form.is_valid():
            post = form.save(commit=False)
            post.thread = thread
            post.author = request.user
            post.save()
            messages.success(request, 'Reply posted successfully!')
            return redirect('thread_detail', thread_id=thread.id)
    else:
        form = PostForm()
    
    context = {
        'thread': thread,
        'page_obj': page_obj,
        'form': form,
    }
    return render(request, 'thread_detail.html', context)


@login_required
def create_thread(request, category_id):
    """Create a new thread"""
    category = get_object_or_404(ForumCategory, pk=category_id)
    
    if request.method == 'POST':
        thread_form = ThreadForm(request.POST)
        post_form = PostForm(request.POST)
        
        if thread_form.is_valid() and post_form.is_valid():
            # Create thread
            thread = thread_form.save(commit=False)
            thread.category = category
            thread.author = request.user
            thread.save()
            
            # Create first post
            post = post_form.save(commit=False)
            post.thread = thread
            post.author = request.user
            post.save()
            
            messages.success(request, 'Thread created successfully!')
            return redirect('thread_detail', thread_id=thread.id)
    else:
        thread_form = ThreadForm()
        post_form = PostForm()
    
    context = {
        'category': category,
        'thread_form': thread_form,
        'post_form': post_form,
    }
    return render(request, 'create_thread.html', context)


@login_required
def user_profile(request, userid):
    """Display user profile with player history"""
    from django.contrib.auth.models import User
    from voting.models import PlayerHistory, Ballot
    
    user = get_object_or_404(User, id=userid)
    
    # Get or create profile
    profile, created = UserProfile.objects.get_or_create(user=user)
    
    # Get or create player history
    history, created = PlayerHistory.objects.get_or_create(user=user)
    history.update_stats()  # Refresh stats
    
    recent_threads = user.threads.all()[:5]
    recent_posts = user.posts.all()[:10]
    recent_votes = Ballot.objects.filter(voter=user).order_by('-cast_at')[:10]
    
    context = {
        'profile_user': user,
        'profile': profile,
        'history': history,
        'recent_threads': recent_threads,
        'recent_posts': recent_posts,
        'recent_votes': recent_votes,
    }
    return render(request, 'user_profile.html', context)


def search(request):
    """Search threads and posts by keywords"""
    query = request.GET.get('q', '')
    search_type = request.GET.get('type', 'all')  # all, threads, posts
    flair_filter = request.GET.get('flair', '')
    
    threads = []
    posts = []
    
    if query:
        if search_type in ['all', 'threads']:
            threads = Thread.search(query)
            if flair_filter:
                threads = threads.filter(flair__id=flair_filter)
        if search_type in ['all', 'posts']:
            posts = Post.search(query)
    
    from .models import Flair
    available_flairs = Flair.objects.all()
    
    context = {
        'query': query,
        'search_type': search_type,
        'flair_filter': flair_filter,
        'threads': threads[:20],
        'posts': posts[:50],
        'available_flairs': available_flairs,
    }
    return render(request, 'search_results.html', context)


def riding_list(request):
    """Display all ridings grouped by province"""
    from .models import Riding
    
    province_filter = request.GET.get('province', '')
    
    ridings = Riding.objects.filter(is_active=True)
    if province_filter:
        ridings = ridings.filter(province=province_filter)
    
    # Group by province
    provinces = {}
    for riding in ridings:
        prov = riding.get_province_display()
        if prov not in provinces:
            provinces[prov] = []
        provinces[prov].append(riding)
    
    # Sort provinces
    provinces = dict(sorted(provinces.items()))
    
    context = {
        'provinces': provinces,
        'province_filter': province_filter,
        'province_choices': Riding.PROVINCE_CHOICES,
        'total_ridings': ridings.count(),
    }
    return render(request, 'riding_list.html', context)


def riding_detail(request, riding_id):
    """Display riding details and current MP"""
    from .models import Riding
    
    riding = get_object_or_404(Riding, pk=riding_id)
    current_mp = riding.current_mp()
    
    # Get all MPs who have represented this riding
    past_mps = PositionHistory.objects.filter(
        riding_obj=riding,
        position_type='MP'
    ).select_related('user_profile__user', 'user_profile__party').order_by('-start_date')
    
    context = {
        'riding': riding,
        'current_mp': current_mp,
        'past_mps': past_mps,
    }
    return render(request, 'riding_detail.html', context)


def cabinet_list(request):
    """Display current cabinet and cabinet history"""
    from .models import Cabinet, CabinetPosition
    
    current_cabinet = Cabinet.objects.filter(is_current=True).first()
    past_cabinets = Cabinet.objects.filter(is_current=False).order_by('-start_date')[:10]
    
    # Get current cabinet positions grouped by type
    current_positions = {}
    if current_cabinet:
        positions = current_cabinet.positions.filter(end_date__isnull=True).select_related('user_profile__user', 'user_profile__party').order_by('order', 'portfolio')
        
        for position in positions:
            pos_type = position.get_position_type_display()
            if pos_type not in current_positions:
                current_positions[pos_type] = []
            current_positions[pos_type].append(position)
    
    context = {
        'current_cabinet': current_cabinet,
        'current_positions': current_positions,
        'past_cabinets': past_cabinets,
    }
    return render(request, 'cabinet_list.html', context)


def cabinet_detail(request, cabinet_id):
    """Display detailed cabinet information"""
    from .models import Cabinet
    
    cabinet = get_object_or_404(Cabinet, pk=cabinet_id)
    positions = cabinet.positions.all().select_related('user_profile__user', 'user_profile__party').order_by('order', 'portfolio')
    
    # Group positions by type
    grouped_positions = {}
    for position in positions:
        pos_type = position.get_position_type_display()
        if pos_type not in grouped_positions:
            grouped_positions[pos_type] = []
        grouped_positions[pos_type].append(position)
    
    context = {
        'cabinet': cabinet,
        'grouped_positions': grouped_positions,
        'all_positions': positions,
    }
    return render(request, 'cabinet_detail.html', context)


def cabinet_position_history(request, portfolio):
    """Show history of a specific cabinet position/portfolio"""
    from .models import CabinetPosition
    
    positions = CabinetPosition.objects.filter(
        portfolio__iexact=portfolio
    ).select_related('user_profile__user', 'user_profile__party', 'cabinet').order_by('-start_date')
    
    context = {
        'portfolio': portfolio,
        'positions': positions,
    }
    return render(request, 'portfolio_history.html', context)


@login_required
def manage_cabinet(request):
    """Cabinet management page for Prime Minister"""
    from .models import Cabinet, CabinetPosition
    
    # Check if user is current PM
    current_cabinet = Cabinet.objects.filter(is_current=True).first()
    
    if not current_cabinet:
        messages.error(request, "No current cabinet exists.")
        return redirect('cabinet_list')
    
    # Check if user is the PM of current cabinet
    if request.user != current_cabinet.prime_minister:
        messages.error(request, "Only the Prime Minister can manage the cabinet.")
        return redirect('cabinet_list')
    
    current_positions = current_cabinet.positions.filter(
        end_date__isnull=True
    ).select_related('user_profile__user', 'user_profile__party').order_by('order', 'portfolio')
    
    context = {
        'cabinet': current_cabinet,
        'current_positions': current_positions,
    }
    return render(request, 'manage_cabinet.html', context)


@login_required
def add_cabinet_position(request):
    """Add a new cabinet position"""
    from .models import Cabinet, CabinetPosition, UserProfile
    from django import forms
    
    current_cabinet = Cabinet.objects.filter(is_current=True).first()
    
    if not current_cabinet or request.user != current_cabinet.prime_minister:
        messages.error(request, "Only the Prime Minister can add cabinet positions.")
        return redirect('cabinet_list')
    
    class CabinetPositionForm(forms.Form):
        user = forms.ModelChoiceField(
            queryset=UserProfile.objects.all(),
            label="Member",
            widget=forms.Select(attrs={'class': 'form-select'})
        )
        position_type = forms.ChoiceField(
            choices=CabinetPosition.POSITION_TYPES,
            label="Position Type",
            widget=forms.Select(attrs={'class': 'form-select'})
        )
        portfolio = forms.CharField(
            max_length=200,
            label="Portfolio",
            widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Finance, Foreign Affairs'})
        )
        title = forms.CharField(
            max_length=300,
            label="Full Title",
            widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Minister of Finance'})
        )
        order = forms.IntegerField(
            initial=10,
            label="Order (1=PM, 2=Deputy PM, 10+=Ministers)",
            widget=forms.NumberInput(attrs={'class': 'form-control'})
        )
        start_date = forms.DateField(
            initial=timezone.now().date(),
            label="Start Date",
            widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
        )
        notes = forms.CharField(
            required=False,
            label="Notes",
            widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
        )
    
    if request.method == 'POST':
        form = CabinetPositionForm(request.POST)
        if form.is_valid():
            CabinetPosition.objects.create(
                cabinet=current_cabinet,
                user_profile=form.cleaned_data['user'],
                position_type=form.cleaned_data['position_type'],
                portfolio=form.cleaned_data['portfolio'],
                title=form.cleaned_data['title'],
                order=form.cleaned_data['order'],
                start_date=form.cleaned_data['start_date'],
                notes=form.cleaned_data['notes']
            )
            messages.success(request, f"Added {form.cleaned_data['title']} to cabinet.")
            return redirect('manage_cabinet')
    else:
        form = CabinetPositionForm()
    
    context = {
        'form': form,
        'cabinet': current_cabinet,
    }
    return render(request, 'add_cabinet_position.html', context)


@login_required
def remove_cabinet_position(request, position_id):
    """Remove a cabinet position (set end date)"""
    from .models import Cabinet, CabinetPosition
    
    position = get_object_or_404(CabinetPosition, pk=position_id)
    current_cabinet = Cabinet.objects.filter(is_current=True).first()
    
    if not current_cabinet or request.user != current_cabinet.prime_minister:
        messages.error(request, "Only the Prime Minister can remove cabinet positions.")
        return redirect('cabinet_list')
    
    if position.cabinet != current_cabinet:
        messages.error(request, "Cannot remove positions from past cabinets.")
        return redirect('cabinet_list')
    
    if request.method == 'POST':
        end_date = request.POST.get('end_date')
        position.end_date = end_date if end_date else timezone.now().date()
        position.save()
        messages.success(request, f"Removed {position.title} from cabinet.")
        return redirect('manage_cabinet')
    
    context = {
        'position': position,
        'cabinet': current_cabinet,
        'today': timezone.now().date(),
    }
    return render(request, 'remove_cabinet_position.html', context)


@login_required
def edit_cabinet_position(request, position_id):
    """Edit a cabinet position"""
    from .models import Cabinet, CabinetPosition
    from django import forms
    
    position = get_object_or_404(CabinetPosition, pk=position_id)
    current_cabinet = Cabinet.objects.filter(is_current=True).first()
    
    if not current_cabinet or request.user != current_cabinet.prime_minister:
        messages.error(request, "Only the Prime Minister can edit cabinet positions.")
        return redirect('cabinet_list')
    
    if position.cabinet != current_cabinet:
        messages.error(request, "Cannot edit positions from past cabinets.")
        return redirect('cabinet_list')
    
    class EditPositionForm(forms.Form):
        portfolio = forms.CharField(
            max_length=200,
            initial=position.portfolio,
            widget=forms.TextInput(attrs={'class': 'form-control'})
        )
        title = forms.CharField(
            max_length=300,
            initial=position.title,
            widget=forms.TextInput(attrs={'class': 'form-control'})
        )
        order = forms.IntegerField(
            initial=position.order,
            widget=forms.NumberInput(attrs={'class': 'form-control'})
        )
        notes = forms.CharField(
            required=False,
            initial=position.notes,
            widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
        )
    
    if request.method == 'POST':
        form = EditPositionForm(request.POST)
        if form.is_valid():
            position.portfolio = form.cleaned_data['portfolio']
            position.title = form.cleaned_data['title']
            position.order = form.cleaned_data['order']
            position.notes = form.cleaned_data['notes']
            position.save()
            messages.success(request, f"Updated {position.title}.")
            return redirect('manage_cabinet')
    else:
        form = EditPositionForm()
    
    context = {
        'form': form,
        'position': position,
        'cabinet': current_cabinet,
    }
    return render(request, 'edit_cabinet_position.html', context)