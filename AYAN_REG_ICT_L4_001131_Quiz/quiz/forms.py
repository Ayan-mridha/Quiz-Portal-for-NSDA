from django import forms
from django.contrib.auth.models import User

from .models import Participant, Quiz


class RegistrationForm(forms.Form):
    username = forms.CharField(max_length=150)
    email = forms.EmailField()
    password = forms.CharField(widget=forms.PasswordInput)
    confirm_password = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Username already exists.')
        return username

    def clean_email(self):
        email = self.cleaned_data['email']
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError('Email already exists.')
        return email

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get('password')
        confirm_password = cleaned_data.get('confirm_password')

        if password and confirm_password and password != confirm_password:
            raise forms.ValidationError('Password and confirm password do not match.')
        return cleaned_data


class LoginForm(forms.Form):
    username_or_email = forms.CharField(label='Username or Email')
    password = forms.CharField(widget=forms.PasswordInput)


class ParticipantProfileForm(forms.ModelForm):
    class Meta:
        model = Participant
        fields = ['name', 'class_name', 'age', 'gender', 'institution']
        widgets = {
            'gender': forms.Select(
                choices=[
                    ('', 'Select gender'),
                    ('Male', 'Male'),
                    ('Female', 'Female'),
                    ('Other', 'Other'),
                ]
            )
        }


class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = ['title', 'description']
