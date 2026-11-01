from django import forms
from .models import Chirp


class ChirpForm(forms.ModelForm):
    class Meta:
        model = Chirp
        fields = ['content']
        widgets = {
            'content': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'maxlength': 280,
                'placeholder': "What's happening?",
            }),
        }
