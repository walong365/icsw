from django import forms
from django.contrib import auth
from django.utils.translation import ugettext_lazy as _

class authentication_form(forms.Form):
    """ Standard login form """
    username = forms.CharField(label=_("Username"), max_length=30)
    password = forms.CharField(label=_("Password"), widget=forms.PasswordInput)
    def __init__(self, request=None, *args, **kwargs):
        self.request = request
        self.user_cache = None
        super(authentication_form, self).__init__(*args, **kwargs)
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

class user_config_form(forms.Form):
    css_theme = forms.ChoiceField(
        widget=forms.widgets.Select(
            attrs={"class" : "inputwidth200"}
        ), choices=(
            ("sunny", "Sunny"),
            ("cupertino", "Cupertino"),
            ("pepper-grinder", "Peeper Grinder"),
            ("smoothness", "Smoothness"),
            ("ui-lightness", "Lightness")
        ), label=_("CSS Theme")
    )
    font_scale = forms.ChoiceField(
        choices=(
            ("16", "Small"),
            ("27", "Big")
        ), label=_("size"), initial="small")
