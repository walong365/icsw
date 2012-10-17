# -*- coding: utf-8 -*-

import django.forms
import django.forms.widgets
from django.forms.formsets import formset_factory
from django.forms import ModelChoiceField, ValidationError, ModelMultipleChoiceField, CharField, IPAddressField
from django.forms.widgets import CheckboxSelectMultiple, SelectMultiple, CheckboxInput, TextInput
from django.contrib.auth import authenticate
from django.db.models import Q
import datetime
import django.core.urlresolvers
from django.utils.translation import ugettext_lazy as _
from django.forms.util import ErrorList
import datetime
from initat.cluster.backbone.models import user, network, network_type, network_device_type, \
     device_class, device_location, config_type
from initat.cluster.frontend.widgets import simple_select_multiple
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
    """
    only make a full validation if identifier is set, otherwise we set mandatory fields
    from model as non-required to ease handling of this form in a formset
    """
    master_network = ModelChoiceField(network.objects.filter(Q(network_type__identifier="p")).order_by("name"),
                                      required=False)
    network_type = ModelChoiceField(network_type.objects.all().order_by("identifier"),
                                    initial=network_type.objects.get(Q(identifier="o")),
                                    empty_label=None)
    network_device_type = ModelMultipleChoiceField(
        network_device_type.objects.all().order_by("identifier"),
        widget=simple_select_multiple,
        required=False)
    identifier = CharField(required=False)
    name = CharField(required=False)
    network = CharField(required=False)
    netmask = CharField(required=False)
    broadcast = CharField(required=False)
    gateway = CharField(required=False)
    def can_be_deleted(self):
        if self.instance.pk:
            return False if self.instance.net_ip_set.all().count() else True
        else:
            # new network, can never be deleted
            return False
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
    def clean_name(self):
        val = self.cleaned_data["name"]
        if self.cleaned_data["identifier"] and not val.strip():
            raise ValidationError("can not be empty")
        return val
    def _clean_ipv4(self, val):
        if self.cleaned_data["identifier"]:
            try:
                addr = ipvx_tools.ipv4(val)
            except:
                raise ValidationError("not a valid IPv4 address")
            else:
                return val
        else:
            return val
    def clean_network(self):
        return self._clean_ipv4(self.cleaned_data["network"])
    def clean_netmask(self):
        return self._clean_ipv4(self.cleaned_data["netmask"])
    def clean_broadcast(self):
        return self._clean_ipv4(self.cleaned_data["broadcast"])
    def clean_gateway(self):
        return self._clean_ipv4(self.cleaned_data["gateway"])
    def clean_start_range(self):
        return self._clean_ipv4(self.cleaned_data["start_range"])
    def clean_end_range(self):
        return self._clean_ipv4(self.cleaned_data["end_range"])
    def clean(self):
        in_data = django.forms.ModelForm.clean(self)
        # check for present keys
        if in_data["identifier"]:
            # full validate only if identifier is set
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
    def save(self, **kwargs):
        if self.cleaned_data["identifier"]:
            return django.forms.ModelForm.save(self, **kwargs)
        else:
            return None
    class Meta:
        model = network

class network_type_form(django.forms.ModelForm):
    identifier = CharField(required=True)
    description = CharField(required=True)
    def can_be_deleted(self):
        if self.instance.pk:
            return False if self.instance.network_set.all().count() else True
        else:
            # new network, can never be deleted
            return False
    class Meta:
        model = network_type

class network_device_type_form(django.forms.ModelForm):
    identifier = CharField(required=True)
    description = CharField(required=True)
    def can_be_deleted(self):
        if self.instance.pk:
            return False if (self.instance.network_set.all().count() or self.instance.netdevice_set.all().count()) else True
        else:
            # new network, can never be deleted
            return False
    class Meta:
        model = network_device_type
        
class device_location_form(django.forms.ModelForm):
    def can_be_deleted(self):
        if self.instance.pk:
            return False if (self.instance.device_set.all().count()) else True
        else:
            # new network, can never be deleted
            return False
    def device_list(self):
        if self.instance.pk:
            return ", ".join(sorted(self.instance.device_set.all().values_list("name", flat=True)))
        else:
            return ""
    class Meta:
        model = device_location

class device_class_form(django.forms.ModelForm):
    def device_list(self):
        if self.instance.pk:
            return ", ".join(sorted(self.instance.device_set.all().values_list("name", flat=True)))
        else:
            return ""
    def can_be_deleted(self):
        if self.instance.pk:
            return False if (self.instance.device_set.all().count()) else True
        else:
            # new network, can never be deleted
            return False
    class Meta:
        model = device_class

class config_type_form(django.forms.ModelForm):
    def can_be_deleted(self):
        if self.instance.pk:
            return False if (self.instance.config_set.all().count()) else True
        else:
            # new network, can never be deleted
            return False
    class Meta:
        model = config_type
        