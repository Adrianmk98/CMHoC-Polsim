from django import forms
from .models import UserProfile

AVATAR_MAX_SIZE = 5 * 1024 * 1024


class ProfileEditForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['avatar']
        widgets = {
            'avatar': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }

    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar and hasattr(avatar, 'size') and avatar.size > AVATAR_MAX_SIZE:
            raise forms.ValidationError('Image must be smaller than 5MB.')
        return avatar
