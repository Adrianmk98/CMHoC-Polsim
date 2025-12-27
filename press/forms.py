from django import forms
from .models import PressRelease, PressComment


class PressReleaseForm(forms.ModelForm):
    """Form for creating/editing press releases with rich text editor"""
    
    class Meta:
        model = PressRelease
        fields = ['title', 'category', 'content', 'excerpt', 'tags', 'is_published', 'is_featured']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter press release title...'
            }),
            'category': forms.Select(attrs={
                'class': 'form-select'
            }),
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 20,
                'id': 'press-editor',
                'placeholder': 'Write your press release here...'
            }),
            'excerpt': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Short summary (optional - will be auto-generated if left blank)'
            }),
            'tags': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Comma-separated tags (e.g., healthcare, budget, announcement)'
            }),
            'is_published': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
            'is_featured': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        help_texts = {
            'content': 'Use the editor toolbar to format text and insert images',
            'excerpt': 'Leave blank to auto-generate from content',
            'is_featured': 'Show this press release prominently on the homepage',
        }


class ImageUploadForm(forms.Form):
    """Form for uploading images to embed in press releases"""
    
    image = forms.ImageField(
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': 'image/*'
        }),
        help_text='Select an image to upload (JPG, PNG, GIF)'
    )
    caption = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Image caption (optional)'
        })
    )
    alt_text = forms.CharField(
        required=False,
        max_length=200,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Alt text for accessibility (optional)'
        })
    )


class PressCommentForm(forms.ModelForm):
    """Form for commenting on press releases"""
    
    class Meta:
        model = PressComment
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Share your thoughts...'
            })
        }
        labels = {
            'content': 'Your Comment'
        }