from django import forms
from .models import Party, LeadershipElection, ConfidenceVote, LeadershipCandidate, JoinRequest


class PartyForm(forms.ModelForm):
    """Form for creating a new party"""
    
    class Meta:
        model = Party
        fields = ['name', 'abbreviation', 'color', 'ideology', 'platform']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Full party name'
            }),
            'abbreviation': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Abbreviation (e.g., LPC, CPC)'
            }),
            'color': forms.TextInput(attrs={
                'class': 'form-control',
                'type': 'color',
            }),
            'ideology': forms.Select(attrs={
                'class': 'form-select'
            }),
            'platform': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Describe your party\'s platform and policies...'
            }),
        }


class LeadershipElectionForm(forms.ModelForm):
    """Form for creating a leadership election"""
    
    class Meta:
        model = LeadershipElection
        fields = ['title', 'description', 'closes_at']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Election title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Description of this leadership election...'
            }),
            'closes_at': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
        }


class LeadershipCandidateForm(forms.ModelForm):
    """Form for nominating yourself for leadership"""
    
    class Meta:
        model = LeadershipCandidate
        fields = ['platform']
        widgets = {
            'platform': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 8,
                'placeholder': 'Why should party members vote for you? What is your vision for the party?'
            }),
        }
        labels = {
            'platform': 'Campaign Platform'
        }


class ConfidenceVoteForm(forms.ModelForm):
    """Form for initiating a confidence vote"""
    
    class Meta:
        model = ConfidenceVote
        fields = ['reason']
        widgets = {
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 6,
                'placeholder': 'Explain why you are calling for a vote of no confidence...'
            }),
        }
        labels = {
            'reason': 'Reason for No Confidence Vote'
        }


class JoinRequestForm(forms.ModelForm):
    """Form for requesting to join a party"""
    
    class Meta:
        model = JoinRequest
        fields = ['message']
        widgets = {
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Why do you want to join this party? (optional)'
            }),
        }
        labels = {
            'message': 'Application Message'
        }