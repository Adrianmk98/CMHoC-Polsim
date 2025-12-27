from django import forms
from .models import Thread, Post, Flair


class ThreadForm(forms.ModelForm):
    # Explicitly define the flair field
    flair = forms.ModelChoiceField(
        queryset=Flair.objects.all(),
        required=False,
        empty_label="No Flair",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class Meta:
        model = Thread
        fields = ['title', 'flair']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter thread title...'
            }),
        }


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Write your post...'
            })
        }