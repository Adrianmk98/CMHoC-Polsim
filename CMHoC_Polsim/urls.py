from django.conf import settings
from django.conf.urls.static import static
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
    path('chirps/', include('chirps.urls')),
    path('npcs/', include('npcs.urls')),
]

if settings.DEBUG and hasattr(settings, 'MEDIA_ROOT'):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)