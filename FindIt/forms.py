from django import forms
from django.contrib.auth.models import User
from .models import UserProfile, Item
from .models import UserReview
from .models import ReturnConfirmation
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
        labels = {
            'status': 'Status',
        }

    def __init__(self, *args, **kwargs):
        super(ItemForm, self).__init__(*args, **kwargs)
        # Remove any '-----' or '--------' option from status choices
        status_choices = [(val, label) for val, label in self.fields['status'].choices if label.strip('-') and label not in ('-----', '--------')]
        self.fields['status'].choices = [('', 'Select')] + status_choices

        # Remove any '-----' or '--------' option from category choices
        cat_choices = [(val, label) for val, label in self.fields['category'].choices if label.strip('-') and label not in ('-----', '--------')]
        self.fields['category'].choices = [('', 'Select')] + cat_choices

class MessageForm(forms.Form):
    message = forms.CharField(widget=forms.Textarea(attrs={'rows': 3, 'placeholder': 'Type your message...'}), label='Message')


#USER PROFILE
class UserReviewForm(forms.ModelForm):
    class Meta:
        model = UserReview
        fields = ['rating', 'comment']
class ReturnConfirmationForm(forms.ModelForm):
    class Meta:
        model = ReturnConfirmation
        fields = [
            'finder_confirmed', 'owner_confirmed',
            'finder_photo', 'owner_photo',
            'finder_signature', 'owner_signature'
        ]
        widgets = {
            'finder_signature': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Paste signature data here or sign below.'}),
            'owner_signature': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Paste signature data here or sign below.'}),
        }
class UserProfileForm(forms.ModelForm):
    username = forms.CharField(
        label='',
        widget=forms.TextInput(attrs={'placeholder': 'Username'})
    )
    first_name = forms.CharField(
        label='',
        widget=forms.TextInput(attrs={'placeholder': 'First Name'})
    )

    last_name = forms.CharField(
        label='',
        widget=forms.TextInput(attrs={'placeholder': 'Last Name'})
    )

    email = forms.EmailField(
        label='',
        widget=forms.EmailInput(attrs={'placeholder': 'Email'})
    )

    contact_number = forms.CharField(
        label='',
        widget=forms.TextInput(attrs={'placeholder': 'Contact Number'})
    )
    profile_picture = forms.ImageField(required=False)
    
    address = forms.CharField(
        label='',
        widget=forms.TextInput(attrs={'placeholder': 'Address'})
    )
    
    bio = forms.CharField(
        label='',
        widget=forms.Textarea(attrs={'placeholder': 'Bio', 'rows': 3}),
        required=False
    )
    
    social_links = forms.CharField(
        label='',
        widget=forms.TextInput(attrs={'placeholder': 'Social Links (comma separated)'}),
        required=False
    )

    class Meta:
        model = UserProfile
        fields = ['first_name', 'last_name', 'email', 'contact_number', 'profile_picture', 'username', 'address', 'bio', 'social_links']


    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
            self.fields['username'].initial = self.instance.user.username
            self.fields['contact_number'].initial = self.instance.contact_number
            self.fields['address'].initial = self.instance.address
            self.fields['bio'].initial = self.instance.bio
            self.fields['social_links'].initial = self.instance.social_links

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.email = self.cleaned_data['email']
        user.username = self.cleaned_data['username']  
        profile.contact_number = self.cleaned_data['contact_number']
        profile.address = self.cleaned_data['address']
        profile.bio = self.cleaned_data['bio']
        profile.social_links = self.cleaned_data['social_links']
        if commit:
            user.save()
            profile.save()
        return profile