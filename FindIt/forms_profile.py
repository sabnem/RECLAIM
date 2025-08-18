from django import forms
from .models import UserProfile

class UserProfileForm(forms.ModelForm):
    class Meta:
        model = UserProfile
        fields = ['contact_number']
        widgets = {
            'contact_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Contact Number'})
        }
