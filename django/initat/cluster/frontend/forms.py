# -*- coding: utf-8 -*-

""" simple formulars for django / clustersoftware """

from django.forms.widgets import TextInput, PasswordInput
from django.forms import Form, ModelForm, ValidationError, CharField
from django.contrib.auth import authenticate
from django.utils.translation import ugettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, ButtonHolder, Button, Fieldset, Div, HTML
from crispy_forms.bootstrap import FormActions
from django.core.urlresolvers import reverse
from initat.cluster.backbone.models import domain_tree_node, device, category

class authentication_form(Form):
    username = CharField(label=_("Username"),
                         max_length=30)
    password = CharField(label=_("Password"),
                         widget=PasswordInput)
    def __init__(self, request=None, *args, **kwargs):
        """
        If request is passed in, the form will validate that cookies are
        enabled. Note that the request (a HttpRequest object) must have set a
        cookie with the key TEST_COOKIE_NAME and value TEST_COOKIE_VALUE before
        running this validation.
        """
        self.helper = FormHelper()
        self.helper.form_id = "id_login_form"
        self.helper.form_method = "post"
        self.helper.layout = Layout(
            Fieldset(
                "",
                HTML("<h2>Login credentials</h2>"),
                Field("username"),
                Field("password"),
                css_class="inlineLabels",
                ),
            ButtonHolder(
                Submit("submit", "Submit", css_class="primaryAction"),
            ),
        )
        #self.helper.add_input(Submit("submit", "Submit"))
        self.helper.form_action = reverse("session:login")
        self.request = request
        self.user_cache = None
        super(authentication_form, self).__init__(*args, **kwargs)
    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if username and password:
            self.user_cache = authenticate(username=username, password=password)
            if self.user_cache is None:
                raise ValidationError(_("Please enter a correct username and password. Note that both fields are case-sensitive."))
            elif not self.user_cache.is_active:
                raise ValidationError(_("This account is inactive."))
        else:
            raise ValidationError(_("Need username and password"))
        # TODO: determine whether this should move to its own method.
        if self.request:
            if not self.request.session.test_cookie_worked():
                raise ValidationError(_("Your Web browser doesn't appear to have cookies enabled. Cookies are required for logging in."))
        return self.cleaned_data
    def get_user(self):
        return self.user_cache

class dtn_detail_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_dtn_detail_form"
    helper.layout = Layout(
        Fieldset(
            "Domain tree node details",
            Field("name"),
            Field("node_postfix"),
            Field("comment"),
            ButtonHolder(
                Field("create_short_names"),
                Field("always_create_ip"),
                Field("write_nameserver_config"),
            ),
            ButtonHolder(
                Button("delete", "Delete", css_class="primaryAction"),
            ),
            css_class="inlineLabels",
        )
    )
    class Meta:
        model = domain_tree_node
        fields = ["name", "node_postfix", "create_short_names", "always_create_ip", "write_nameserver_config", "comment"]

class dtn_new_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_dtn_detail_form"
    helper.layout = Layout(
        Fieldset(
            "Create new node",
            Field("full_name"),
            Field("node_postfix"),
            Field("comment"),
            ButtonHolder(
                Field("create_short_names"),
                Field("always_create_ip"),
                Field("write_nameserver_config"),
            ),
            ButtonHolder(
                Submit("submit", "Submit", css_class="primaryAction"),
            ),
            css_class="inlineLabels",
        )
    )
    class Meta:
        model = domain_tree_node
        fields = ["full_name", "node_postfix", "create_short_names", "always_create_ip", "write_nameserver_config", "comment"]
    
class device_general_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_dtn_detail_form"
    helper.layout = Layout(
        Fieldset(
            "Device details",
            Field("name"),
            Field("domain_tree_node"),
            Field("comment"),
            Field("monitor_checks"),
            css_class="inlineLabels",
        )
    )
    class Meta:
        model = device
        fields = ["name", "comment", "monitor_checks", "domain_tree_node",]

class dummy_password_form(Form):
    helper = FormHelper()
    helper.layout = Layout(
        Fieldset(
            "please enter the new password",
            Field("password1"),
            Field("password2"),
            css_class="inlineLabels",
        )
    )
    password1 = CharField(label=_("New Password"),
                         widget=PasswordInput)
    password2 = CharField(label=_("Confirm Password"),
                         widget=PasswordInput)

class category_detail_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_cat_detail_form"
    helper.layout = Layout(
        Fieldset(
            "Category details",
            Field("name"),
            Field("comment"),
            ButtonHolder(
                Button("delete", "Delete", css_class="primaryAction"),
            ),
            css_class="inlineLabels",
        )
    )
    class Meta:
        model = category
        fields = ["name", "comment"]

class category_new_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_dtn_detail_form"
    helper.layout = Layout(
        Fieldset(
            "Create new category",
            Field("full_name"),
            Field("comment"),
            ButtonHolder(
                Submit("submit", "Submit", css_class="primaryAction"),
            ),
            css_class="inlineLabels",
        )
    )
    class Meta:
        model = category
        fields = ["full_name", "comment"]
