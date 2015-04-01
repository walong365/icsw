"""
Generalized forms for login and password change.
"""

from django import forms
from django.contrib import auth
from django.utils.translation import ugettext_lazy as _
from django.forms.util import ErrorList


class AuthenticationForm(forms.Form):
    """
    A standard login form that will fit most use cases.
    """
    username = forms.CharField(label=_("Username"), max_length=30)
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput)

    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super(AuthenticationForm, self).__init__(*args, **kwargs)

    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if username and password:
            self.user_cache = auth.authenticate(username=username, password=password)
            if self.user_cache is None:
                raise forms.ValidationError(_("Please enter a correct username and password. Note that both fields are case-sensitive."))
            elif not self.user_cache.is_active:
                raise forms.ValidationError(_("This account is inactive."))
        else:
            raise forms.ValidationError(_("Need username and password"))
        # TODO: determine whether this should move to its own method.
        if self.request:
            if not self.request.session.test_cookie_worked():
                raise forms.ValidationError(_("Your Web browser doesn't appear to have cookies enabled. Cookies are required for logging in."))
        return self.cleaned_data

    def get_user(self):
        return self.user_cache


class ChangePasswordForm(forms.Form):
    """
    A form to do password changes in a safe way. New password is input twice.
    """
    password_old = forms.CharField(label=_("Old Password"), widget=forms.PasswordInput)
    password_1 = forms.CharField(label=_("New Password"), widget=forms.PasswordInput)
    password_2 = forms.CharField(label=_("New Password (again)"), widget=forms.PasswordInput)

    def __init__(self, *args, **kwargs):
        self.username = kwargs.pop("username", None)
        super(ChangePasswordForm, self).__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = self.cleaned_data
        if cleaned_data:
            pass_ok = True
            username = self.username
            password_old = cleaned_data.get("password_old")
            password_1 = cleaned_data.get("password_1")
            password_2 = cleaned_data.get("password_2")
            if username and password_old and password_1 and password_2:
                if username and password_old:
                    my_cache = auth.authenticate(username=username, password=password_old)
                    if my_cache is None:
                        self._errors["password_old"] = ErrorList(["Please enter your correct password. Note that the fields are case-sensitive."])
                        pass_ok = False
                    elif not my_cache.is_active:
                        self._errors["password_old"] = ErrorList(["This account is inactive."])
                        pass_ok = False
                else:
                    self._errors["password_old"] = ErrorList(["Need old password"])
                    pass_ok = False
                if len(password_1) < 6:
                    self._errors["password_1"] = ErrorList(["password is too short (min 6 chars)"])
                    pass_ok = False
                if password_1 != password_2:
                    self._errors["password_2"] = ErrorList(["passwords do not match"])
                    pass_ok = False
                if password_old == password_1 and password_old == password_2 and pass_ok:
                    self._errors["password_1"] = ErrorList(["Your new password cannot be the same like your old password"])
                    pass_ok = False
        return self.cleaned_data
