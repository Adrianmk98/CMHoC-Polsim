from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.urls import reverse
from forum.models import PoliticalParty


class PressRelease(models.Model):
    """Press releases with rich text content and embedded images"""
    
    CATEGORY_CHOICES = [
        ('ANNOUNCEMENT', 'Announcement'),
        ('STATEMENT', 'Statement'),
        ('POLICY', 'Policy Release'),
        ('EVENT', 'Event Coverage'),
        ('RESPONSE', 'Response'),
        ('OPINION', 'Opinion/Editorial'),
        ('OTHER', 'Other'),
    ]
    
    # Basic info
    title = models.CharField(max_length=300)
    slug = models.SlugField(max_length=350, unique=True, blank=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='press_releases')
    party = models.ForeignKey(PoliticalParty, on_delete=models.SET_NULL, null=True, blank=True, related_name='press_releases')
    
    # Content (rich text with embedded images)
    content = models.TextField(help_text='Full press release content with HTML formatting')
    excerpt = models.TextField(max_length=500, blank=True, help_text='Short summary (auto-generated if blank)')
    
    # Featured image (optional)
    featured_image = models.TextField(blank=True, help_text='Base64 encoded image data')
    featured_image_caption = models.CharField(max_length=200, blank=True)
    
    # Metadata
    category = models.CharField(max_length=20, choices=CATEGORY_CHOICES, default='ANNOUNCEMENT')
    tags = models.CharField(max_length=200, blank=True, help_text='Comma-separated tags')
    
    # Publishing
    is_published = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False, help_text='Show on homepage')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_at = models.DateTimeField(default=timezone.now)
    
    # Stats
    view_count = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['-published_at']
        indexes = [
            models.Index(fields=['-published_at']),
            models.Index(fields=['is_published', '-published_at']),
        ]
    
    def __str__(self):
        return self.title
    
    def save(self, *args, **kwargs):
        # Auto-generate slug from title
        if not self.slug:
            from django.utils.text import slugify
            base_slug = slugify(self.title)[:300]
            slug = base_slug
            counter = 1
            while PressRelease.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
        
        # Auto-generate excerpt if blank
        if not self.excerpt and self.content:
            # Strip HTML tags for excerpt
            import re
            text = re.sub('<[^<]+?>', '', self.content)
            self.excerpt = text[:500]
        
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        return reverse('press:detail', kwargs={'slug': self.slug})
    
    def get_tags_list(self):
        """Return tags as a list"""
        if self.tags:
            return [tag.strip() for tag in self.tags.split(',')]
        return []
    
    def increment_views(self):
        """Increment view count"""
        self.view_count += 1
        self.save(update_fields=['view_count'])


class PressImage(models.Model):
    """Embedded images within press releases"""
    
    press_release = models.ForeignKey(PressRelease, on_delete=models.CASCADE, related_name='images')
    image_data = models.TextField(help_text='Base64 encoded image data')
    caption = models.CharField(max_length=200, blank=True)
    alt_text = models.CharField(max_length=200, blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['uploaded_at']
    
    def __str__(self):
        return f"Image for {self.press_release.title}"


class PressComment(models.Model):
    """Comments on press releases"""
    
    press_release = models.ForeignKey(PressRelease, on_delete=models.CASCADE, related_name='comments')
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_approved = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['created_at']
    
    def __str__(self):
        return f"Comment by {self.author.username} on {self.press_release.title}"