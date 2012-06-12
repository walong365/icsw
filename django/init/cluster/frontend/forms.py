# -*- coding: utf-8 -*-

import django.forms
import django.forms.widgets
from django.forms.formsets import formset_factory
from django.forms import ModelChoiceField, ValidationError
from django.contrib.auth import authenticate
from django.db.models import Q
import datetime
import django.core.urlresolvers
from django.utils.translation import ugettext_lazy as _
from django.forms.util import ErrorList
import datetime
from init.cluster.backbone.models import user, network, network_type
import ipvx_tools
import process_tools

class authentication_form(django.forms.Form):
    username = django.forms.CharField(label=_("Username"),
                                      max_length=30,
                                      widget=django.forms.widgets.TextInput(attrs={"class" : "logininput"}))
    password = django.forms.CharField(label=_("Password"),
                                      widget=django.forms.PasswordInput(attrs={"class" : "logininput"}))
    def __init__(self, request=None, *args, **kwargs):
        """
        If request is passed in, the form will validate that cookies are
        enabled. Note that the request (a HttpRequest object) must have set a
        cookie with the key TEST_COOKIE_NAME and value TEST_COOKIE_VALUE before
        running this validation.
        """
        self.request = request
        self.user_cache = None
        super(authentication_form, self).__init__(*args, **kwargs)
    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        if username and password:
            self.user_cache = authenticate(username=username, password=password)
            if self.user_cache is None:
                raise django.forms.ValidationError(_("Please enter a correct username and password. Note that both fields are case-sensitive."))
            elif not self.user_cache.is_active:
                raise django.forms.ValidationError(_("This account is inactive."))
        else:
            raise django.forms.ValidationError(_("Need username and password"))
        # TODO: determine whether this should move to its own method.
        if self.request:
            if not self.request.session.test_cookie_worked():
                raise django.forms.ValidationError(_("Your Web browser doesn't appear to have cookies enabled. Cookies are required for logging in."))
        return self.cleaned_data
    def get_user(self):
        return self.user_cache
    
class network_form(django.forms.ModelForm):
    master_network = ModelChoiceField(network.objects.filter(Q(network_type__identifier="p")).order_by("name"),
                                      required=False)
    network_type = ModelChoiceField(network_type.objects.all().order_by("identifier"),
                                    initial=network_type.objects.get(Q(identifier="o")),
                                    empty_label=None)
    def clean_identifier(self):
        id_str = self.cleaned_data["identifier"]
        if id_str != id_str.strip() or len(id_str.split()) > 1:
            raise ValidationError("no whitespace allowed")
        return id_str
    def clean_postfix(self):
        postfix = self.cleaned_data["postfix"]
        if not postfix and postfix.isalnum():
            raise ValidationError("illegal character(s)")
        return postfix
    def clean_penalty(self):
        cur_pen = self.cleaned_data["penalty"]
        if cur_pen < 1:
            raise ValidationError("must be greater than 0")
        return cur_pen
    def clean(self):
        django.forms.ModelForm.clean(self)
        in_data = self.cleaned_data
        # check for present keys
        if all([key in in_data for key in ["network", "netmask", "broadcast", "gateway"]]): 
            network, netmask, broadcast, gateway = (
                ipvx_tools.ipv4(in_data["network"]),
                ipvx_tools.ipv4(in_data["netmask"]),
                ipvx_tools.ipv4(in_data["broadcast"]),
                ipvx_tools.ipv4(in_data["gateway"]))
            if network & netmask != network:
                raise ValidationError("netmask / network error")
            if network | (~netmask) != broadcast:
                raise ValidationError("broadcast error")
            if in_data["gateway"] != "0.0.0.0" and gateway & netmask != network:
                raise ValidationError("gateway error")
        if all([key in in_data for key in ["start_range", "end_range", "network", "netmask"]]):
            network, netmask, s_range, e_range = (
                ipvx_tools.ipv4(in_data["network"]),
                ipvx_tools.ipv4(in_data["netmask"]),
                ipvx_tools.ipv4(in_data["start_range"]),
                ipvx_tools.ipv4(in_data["end_range"]))
            if in_data["start_range"] != "0.0.0.0":
                if s_range & network != network:
                    raise ValidationError("start_range not in network")
                if e_range < s_range:
                    raise ValidationError("start_range > end_range")
            if in_data["end_range"] != "0.0.0.0":
                if e_range & network != network:
                    raise ValidationError("end_range not in network")
                if e_range < s_range:
                    raise ValidationError("start_range > end_range")
        return in_data
    class Meta:
        model = network
