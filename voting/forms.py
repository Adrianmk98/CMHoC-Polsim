from django import forms
from .models import Bill, Vote, Ballot


class BillForm(forms.ModelForm):
    class Meta:
        model = Bill
        fields = ['bill_number', 'title', 'short_title', 'chamber', 'status', 'summary', 'full_text']
        widgets = {
            'bill_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., C-123 or S-45'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'short_title': forms.TextInput(attrs={'class': 'form-control'}),
            'chamber': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'summary': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
            'full_text': forms.Textarea(attrs={'class': 'form-control', 'rows': 10}),
        }


class VoteForm(forms.ModelForm):
    class Meta:
        model = Vote
        fields = ['vote_type', 'description', 'closes_at']
        widgets = {
            'vote_type': forms.Select(attrs={'class': 'form-select'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'closes_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }


class BallotForm(forms.ModelForm):
    class Meta:
        model = Ballot
        fields = ['vote']
        widgets = {
            'vote': forms.RadioSelect(attrs={'class': 'form-check-input'}),
        }