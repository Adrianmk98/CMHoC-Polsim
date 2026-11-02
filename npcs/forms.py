from django import forms

from .models import NPCProfile


class NPCPersonaForm(forms.ModelForm):
    """Party leader/deputy/executive-level editing: persona + kill switch only."""

    class Meta:
        model = NPCProfile
        fields = ['persona', 'is_active']
        widgets = {
            'persona': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class NPCAdminForm(forms.ModelForm):
    """Staff-level editing: all behavior-tuning fields."""

    class Meta:
        model = NPCProfile
        fields = ['persona', 'is_active', 'reply_chance', 'cooldown_minutes']
        widgets = {
            'persona': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'reply_chance': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.05', 'min': 0, 'max': 1}),
            'cooldown_minutes': forms.NumberInput(attrs={'class': 'form-control', 'min': 0}),
        }
