from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.core.paginator import Paginator
from .models import Notification, NotificationPreference


@login_required
def notification_list(request):
    """Display all notifications for the user"""
    notifications = request.user.notifications.all()
    
    # Filter by read/unread
    filter_type = request.GET.get('filter', 'all')
    if filter_type == 'unread':
        notifications = notifications.filter(is_read=False)
    elif filter_type == 'read':
        notifications = notifications.filter(is_read=True)
    
    # Filter by type
    notification_type = request.GET.get('type', '')
    if notification_type:
        notifications = notifications.filter(notification_type=notification_type)
    
    # Pagination
    paginator = Paginator(notifications, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get counts
    unread_count = request.user.notifications.filter(is_read=False).count()
    
    context = {
        'page_obj': page_obj,
        'filter_type': filter_type,
        'notification_type': notification_type,
        'unread_count': unread_count,
        'notification_types': Notification.NOTIFICATION_TYPES,
    }
    return render(request, 'notification_list.html', context)


@login_required
def mark_as_read(request, notification_id):
    """Mark a notification as read"""
    notification = get_object_or_404(Notification, pk=notification_id, user=request.user)
    notification.mark_as_read()
    
    # Redirect to link if provided, otherwise back to notifications
    if notification.link:
        return redirect(notification.link)
    return redirect('notifications:notification_list')


@login_required
def mark_all_as_read(request):
    """Mark all notifications as read"""
    if request.method == 'POST':
        request.user.notifications.filter(is_read=False).update(is_read=True)
    return redirect('notifications:notification_list')


@login_required
def delete_notification(request, notification_id):
    """Delete a notification"""
    notification = get_object_or_404(Notification, pk=notification_id, user=request.user)
    if request.method == 'POST':
        notification.delete()
    return redirect('notifications:notification_list')


@login_required
def notification_preferences(request):
    """Manage notification preferences"""
    preferences, created = NotificationPreference.objects.get_or_create(user=request.user)
    
    if request.method == 'POST':
        # Update preferences
        preferences.email_on_cabinet_change = request.POST.get('email_on_cabinet_change') == 'on'
        preferences.email_on_vote_opened = request.POST.get('email_on_vote_opened') == 'on'
        preferences.email_on_vote_closing = request.POST.get('email_on_vote_closing') == 'on'
        preferences.email_on_thread_reply = request.POST.get('email_on_thread_reply') == 'on'
        preferences.email_on_mention = request.POST.get('email_on_mention') == 'on'
        
        preferences.notify_cabinet_change = request.POST.get('notify_cabinet_change') == 'on'
        preferences.notify_vote_opened = request.POST.get('notify_vote_opened') == 'on'
        preferences.notify_vote_closing = request.POST.get('notify_vote_closing') == 'on'
        preferences.notify_bill_updates = request.POST.get('notify_bill_updates') == 'on'
        preferences.notify_thread_reply = request.POST.get('notify_thread_reply') == 'on'
        preferences.notify_mention = request.POST.get('notify_mention') == 'on'
        
        preferences.save()
        
        return redirect('notifications:notification_preferences')
    
    context = {
        'preferences': preferences,
    }
    return render(request, 'preferences.html', context)


@login_required
def unread_count(request):
    """API endpoint for unread notification count"""
    count = request.user.notifications.filter(is_read=False).count()
    return JsonResponse({'count': count})