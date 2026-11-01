from django.db import models
from django.contrib.auth.models import User


class Chirp(models.Model):
    """A short, in-world message. Basic Twitter-style feed, human-posted only."""

    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='chirps')
    content = models.CharField(max_length=280)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.author.username}: {self.content[:40]}"
