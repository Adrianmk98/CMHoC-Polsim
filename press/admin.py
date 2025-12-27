from django.contrib import admin
from .models import PressRelease, PressImage, PressComment


class PressImageInline(admin.TabularInline):
    model = PressImage
    extra = 0
    fields = ['caption', 'alt_text', 'uploaded_at']
    readonly_fields = ['uploaded_at']


class PressCommentInline(admin.TabularInline):
    model = PressComment
    extra = 0
    fields = ['author', 'content', 'created_at', 'is_approved']
    readonly_fields = ['created_at']


@admin.register(PressRelease)
class PressReleaseAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'party', 'category', 'is_published', 'is_featured', 'published_at', 'view_count']
    list_filter = ['is_published', 'is_featured', 'category', 'party', 'published_at']
    search_fields = ['title', 'content', 'author__username', 'tags']
    prepopulated_fields = {'slug': ('title',)}
    date_hierarchy = 'published_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'slug', 'author', 'party')
        }),
        ('Content', {
            'fields': ('content', 'excerpt', 'featured_image', 'featured_image_caption')
        }),
        ('Categorization', {
            'fields': ('category', 'tags')
        }),
        ('Publishing', {
            'fields': ('is_published', 'is_featured', 'published_at')
        }),
        ('Statistics', {
            'fields': ('view_count', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    readonly_fields = ['created_at', 'updated_at']
    
    inlines = [PressImageInline, PressCommentInline]
    
    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.author = request.user
        super().save_model(request, obj, form, change)


@admin.register(PressImage)
class PressImageAdmin(admin.ModelAdmin):
    list_display = ['press_release', 'caption', 'uploaded_at']
    list_filter = ['uploaded_at']
    search_fields = ['caption', 'alt_text', 'press_release__title']


@admin.register(PressComment)
class PressCommentAdmin(admin.ModelAdmin):
    list_display = ['author', 'press_release', 'created_at', 'is_approved']
    list_filter = ['is_approved', 'created_at']
    search_fields = ['content', 'author__username', 'press_release__title']
    actions = ['approve_comments', 'unapprove_comments']
    
    def approve_comments(self, request, queryset):
        queryset.update(is_approved=True)
    approve_comments.short_description = "Approve selected comments"
    
    def unapprove_comments(self, request, queryset):
        queryset.update(is_approved=False)
    unapprove_comments.short_description = "Unapprove selected comments"