from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, Item

class UserRegistrationForm(forms.ModelForm):
    email = forms.EmailField(
        label='',
        widget=forms.EmailInput(attrs={'placeholder': 'Email'})
    )

    username = forms.CharField(
        label='',
        max_length=150,
        widget=forms.TextInput(attrs={'placeholder': 'Username'})
        # No help_text here, so only the model's help_text is used
    )

    first_name = forms.CharField(
        label='',
        max_length=30,
        widget=forms.TextInput(attrs={'placeholder': 'First Name'})
    )
    last_name = forms.CharField(
        label='',
        max_length=30,
        widget=forms.TextInput(attrs={'placeholder': 'Last Name'})
    )
    password = forms.CharField(label='', widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))
    contact_number = forms.CharField(label='', max_length=20, widget=forms.TextInput(attrs={'placeholder': 'Contact Number'}))

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'password')
        widgets = {
            'username': forms.TextInput(attrs={'placeholder': 'Username'}),
            'email': forms.EmailInput(attrs={'placeholder': 'Email'}),
        }
    # help_texts removed to avoid duplicate username help text

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            # Set contact number on the auto-created profile
            if hasattr(user, 'userprofile'):
                user.userprofile.contact_number = self.cleaned_data['contact_number']
                user.userprofile.save()
        return user

class LoginForm(forms.Form):
    username = forms.CharField(
        label='',
        widget=forms.TextInput(attrs={'placeholder': 'Username'})
    )
    password = forms.CharField(
        label='',
        widget=forms.PasswordInput(attrs={'placeholder': 'Password'})
    )

class ItemForm(forms.ModelForm):
    class Meta:
        model = Item
        fields = ['title', 'description', 'category', 'location', 'photo', 'status']
        widgets = {
            'status': forms.RadioSelect,
        }

class MessageForm(forms.Form):
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Type your message...'}), label='Message')
