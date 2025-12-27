from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('forum.urls')),
    path('', include('notifications.urls')), 
    path('voting/', include('voting.urls')),
    path('moderator/', include('moderator.urls')),
    path('elections/', include('elections.urls')),
    path('press/', include('press.urls')),
    path('parties/', include('parties.urls')),
    path('accounts/login/', auth_views.LoginView.as_view(template_name='forum/login.html'), name='login'),
    path('accounts/logout/', auth_views.LogoutView.as_view(next_page='forum_index'), name='logout'),
]