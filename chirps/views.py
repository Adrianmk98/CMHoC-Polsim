from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from django.core.paginator import Paginator

from .models import Chirp
from .forms import ChirpForm


def chirp_feed(request):
    """Global feed of chirps, newest first, with a post box for logged-in users."""
    if request.method == 'POST':
        if not request.user.is_authenticated:
            return redirect('login')
        form = ChirpForm(request.POST)
        if form.is_valid():
            chirp = form.save(commit=False)
            chirp.author = request.user
            chirp.save()
            return redirect('chirps:feed')
    else:
        form = ChirpForm()

    chirps = Chirp.objects.select_related('author__profile__party').all()
    paginator = Paginator(chirps, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'form': form,
        'chirps': page_obj,
    }
    return render(request, 'feed.html', context)


def chirps_by_user(request, username):
    """A single user's chirps."""
    author = get_object_or_404(User, username=username)
    chirps = Chirp.objects.filter(author=author).select_related('author__profile__party')
    paginator = Paginator(chirps, 25)
    page_obj = paginator.get_page(request.GET.get('page'))

    context = {
        'author': author,
        'chirps': page_obj,
    }
    return render(request, 'by_user.html', context)


@login_required
def chirp_delete(request, pk):
    """Delete your own chirp."""
    chirp = get_object_or_404(Chirp, pk=pk)
    if chirp.author != request.user and not request.user.is_staff:
        messages.error(request, "You don't have permission to delete this chirp.")
        return redirect('chirps:feed')

    if request.method == 'POST':
        chirp.delete()
        messages.success(request, 'Chirp deleted.')
    return redirect('chirps:feed')
