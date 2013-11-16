# -*- coding: utf-8 -*-

""" simple formulars for django / clustersoftware """

import re
from django.forms.widgets import TextInput, PasswordInput, SelectMultiple
from django.forms import Form, ModelForm, ValidationError, CharField, ModelChoiceField, \
    ModelMultipleChoiceField
from django.contrib.auth import authenticate
from django.db.models import Q
from django.utils.translation import ugettext_lazy as _
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Button, Fieldset, Div, HTML
from crispy_forms.bootstrap import FormActions
# from crispy_forms.bootstrap import FormActions
from django.core.urlresolvers import reverse
from initat.cluster.backbone.models import domain_tree_node, device, category, mon_check_command, mon_service_templ, \
     domain_name_tree, user, group, device_group, home_export_list, device_config, TOP_LOCATIONS, \
     csw_permission, kernel
from initat.cluster.frontend.widgets import device_tree_widget

# import PAM

class authentication_form(Form):
    username = CharField(label=_("Username"),
                         max_length=30)
    password = CharField(label=_("Password"),
                         widget=PasswordInput)
    helper = FormHelper()
    helper.form_id = "id_login_form"
    helper.layout = Layout(
        Div(
            Fieldset(
                HTML("<h2>Login credentials</h2>"),
                Field("username"),
                Field("password"),
            ),
            FormActions(
                Submit("submit", "Submit", css_class="primaryAction"),
            ),
            css_class="form-horizontal",
        )
    )
    def __init__(self, request=None, *args, **kwargs):
        self.helper.form_action = reverse("session:login")
        self.request = request
        self.user_cache = None
        super(authentication_form, self).__init__(*args, **kwargs)
    def pam_conv(self, auth, query_list):
        print auth, query_list
        response = []
        # for idx, (cur_query, cur_type) in enumerate(query_list):
        #    if cur_type in [PAM.PAM_PROMPT_ECHO_OFF, PAM.PAM_PROMPT_ECHO_ON]:
        #        response.append(("hlMS975", 0))
        #    elif cur_type in [PAM.PAM_ERROR_MSG]:
        #        print "PAM_ERROR_MSG %s" % (cur_query)
        #        response.append(("", 0))
        #    else:
        #        print "+", idx, cur_query, cur_type, PAM.PAM_PROMPT_ECHO_OFF, PAM.PAM_PROMPT_ECHO_ON
        #        return None
        return response
    def clean(self):
        username = self.cleaned_data.get("username")
        password = self.cleaned_data.get("password")
        # auth = PAM.pam()
        # auth.start("passwd")
        # auth.set_item(PAM.PAM_USER, username)
        # auth.set_item(PAM.PAM_CONV, self.pam_conv)
        # print username, password
        # print auth.authenticate()
        # print "-" * 20
        # print pam.authenticate(username, password)
        if username and password:
            # get real user
            all_aliases = [(login_name, al_list.strip().split()) for login_name, al_list in user.objects.all().values_list("login", "aliases") if al_list is not None and al_list.strip()]
            rev_dict = {}
            all_logins = [login_name for login_name, al_list in all_aliases]
            for pk, al_list in all_aliases:
                for cur_al in al_list:
                    if cur_al in rev_dict:
                        raise ValidationError("Alias '%s' is not unique" % (cur_al))
                    elif cur_al in all_logins:
                        # ignore aliases which are also logins
                        pass
                    else:
                        rev_dict[cur_al] = pk
            if username in rev_dict:
                self.user_cache = authenticate(username=rev_dict[username], password=password)
            else:
                self.user_cache = authenticate(username=username, password=password)
            if self.user_cache is None:
                raise ValidationError(_("Please enter a correct username and password. Note that both fields are case-sensitive."))
            else:
                self.login_name = username
            if self.user_cache is not None and not self.user_cache.is_active:
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
    def get_login_name(self):
        # FIXME
        return self.login_name

class dtn_detail_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_dtn_detail_form"
    helper.layout = Layout(
        Div(
            HTML("Domain tree node details"),
            Field("name"),
            Field("node_postfix"),
            Field("comment"),
            FormActions(
                Field("create_short_names"),
                Field("always_create_ip"),
                Field("write_nameserver_config"),
            ),
            FormActions(
                Button("delete", "Delete", css_class="primaryAction"),
            ),
            css_class="form-horizontal",
        )
    )
    class Meta:
        model = domain_tree_node
        fields = ["name", "node_postfix", "create_short_names", "always_create_ip", "write_nameserver_config", "comment"]

class dtn_new_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_dtn_detail_form"
    helper.layout = Layout(
        Div(
            HTML("Create new node"),
            Field("full_name"),
            Field("node_postfix"),
            Field("comment"),
            FormActions(
                Field("create_short_names"),
                Field("always_create_ip"),
                Field("write_nameserver_config"),
            ),
            FormActions(
                Submit("submit", "Submit", css_class="primaryAction"),
            ),
            css_class="form-horizontal",
        )
    )
    class Meta:
        model = domain_tree_node
        fields = ["full_name", "node_postfix", "create_short_names", "always_create_ip", "write_nameserver_config", "comment"]

class device_general_form(ModelForm):
    domain_tree_node = ModelChoiceField(domain_tree_node.objects.none(), empty_label=None) # , widget=domain_name_tree_widget)
    helper = FormHelper()
    helper.form_id = "id_dtn_detail_form"
    helper.layout = Layout(
        Fieldset(
            "Device details",
            Field("name"),
            Field("domain_tree_node"),
            Field("comment"),
            css_class="form-horizontal",
        ),
        Fieldset(
            "Monitor settings",
            Field("mon_device_templ"),
            Field("monitor_checks"),
            Field("enable_perfdata"),
            Field("flap_detection_enabled"),
            css_class="form-horizontal",
        ),
        Fieldset(
            "Info",
            Button("uuid", "show UUID info"),
            # css_class="form-horizontal",
        )
    )
    def __init__(self, *args, **kwargs):
        super(device_general_form, self).__init__(*args, **kwargs)
        self.fields["domain_tree_node"].queryset = domain_name_tree()
    class Meta:
        model = device
        fields = ["name", "comment", "monitor_checks", "domain_tree_node", "mon_device_templ",
                  "enable_perfdata", "flap_detection_enabled"]

class dummy_password_form(Form):
    helper = FormHelper()
    helper.layout = Layout(
        Fieldset(
            "please enter the new password",
            Field("password1"),
            Field("password2"),
            FormActions(
                Button("check", "Check"),
            ),
            css_class="form-horizontal",
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
        Div(
            HTML("Category details"),
            Field("name"),
            Field("comment"),
            FormActions(
                Button("delete", "Delete", css_class="primaryAction"),
            ),
            css_class="form-horizontal",
        )
    )
    class Meta:
        model = category
        fields = ["name", "comment"]

class location_detail_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_cat_detail_form"
    helper.layout = Layout(
        Div(
            HTML("Category details"),
            Field("name"),
            Field("comment"),
            FormActions(
                Button("delete", "Delete", css_class="primaryAction"),
            ),
            Field("latitude"),
            Field("longitude"),
            css_class="form-horizontal",
        )
    )
    class Meta:
        model = category
        fields = ["name", "comment", "latitude", "longitude"]

class category_new_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_dtn_detail_form"
    helper.layout = Layout(
        Div(
            HTML("Create new category"),
            Field("full_name"),
            Field("comment"),
            FormActions(
                Submit("submit", "Submit", css_class="primaryAction"),
                ),
            css_class="form-horizontal",
        )
    )
    def clean_full_name(self):
        cur_name = self.cleaned_data["full_name"]
        loc_re = re.compile("^(?P<top_level>/[^/]+)/(?P<rest>.*)$")
        name_m = loc_re.match(cur_name)
        if not name_m:
            raise ValidationError("wrong format")
        if name_m.group("top_level") not in TOP_LOCATIONS:
            raise ValidationError("wrong top-level category '%s'" % (name_m.group("top_level")))
        return cur_name
    class Meta:
        model = category
        fields = ["full_name", "comment"]

class device_fqdn(ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        return (obj.device_group.name, obj.full_name)

class device_fqdn_comment(ModelMultipleChoiceField):
    def label_from_instance(self, obj):
        if obj.comment:
            dev_str = u"%s (%s)" % (obj.full_name, obj.comment)
        else:
            dev_str = obj.full_name
        return (obj.device_group.name, dev_str)

class event_handler_list(ModelChoiceField):
    def label_from_instance(self, obj):
        return u"%s on %s" % (obj.name, obj.config.name)

class moncc_template_flags_form(ModelForm):
    mon_service_templ = ModelChoiceField(queryset=mon_service_templ.objects.all(), empty_label=None)
    event_handler = event_handler_list(
        queryset=mon_check_command.objects.filter(Q(is_event_handler=True)).select_related("config")
    )
    exclude_devices = device_fqdn_comment(
        queryset=device.objects.exclude(
            Q(device_type__identifier__in=["MD"])
            ).filter(
            Q(enabled=True) &
            Q(device_group__enabled=True)).select_related("device_group", "domain_tree_node").order_by("device_group__name", "name"),
        widget=device_tree_widget
        )
    helper = FormHelper()
    helper.form_id = "form"
    helper.layout = Layout(
        Div(
            HTML("Templates and flags"),
            Field("mon_service_templ"),
            Field("exclude_devices"),
            FormActions(
                Field("enable_perfdata"),
                Field("volatile"),
                Field("is_event_handler"),
                Field("event_handler_enabled"),
                ),
            css_class="form-horizontal",
        )
    )
    class Meta:
        model = mon_check_command
        fields = ["mon_service_templ", "enable_perfdata", "volatile", "exclude_devices",
            "event_handler", "event_handler_enabled", "is_event_handler"]

class group_detail_form(ModelForm):
    permissions = ModelMultipleChoiceField(
        queryset=csw_permission.objects.exclude(Q(codename__in=["admin", "group_admin"])).select_related("content_type").order_by("codename"),
        widget=SelectMultiple(attrs={"size" : "8"}),
        required=False,
    )
    allowed_device_groups = ModelMultipleChoiceField(
        queryset=device_group.objects.exclude(Q(cluster_device_group=True)).filter(Q(enabled=True)),
        required=False,
    )
    helper = FormHelper()
    helper.form_id = "form"
    helper.layout = Layout(
        HTML("<h2>Group details</h2>"),
        Div(
            Div(
                Fieldset(
                    "Basic data",
                    Field("groupname"),
                    Field("gid"),
                    Field("homestart"),
                    FormActions(
                        Field("active"),
                        ),
                    ),
                css_class="form-horizontal span6",
            ),
            Div(
                Fieldset(
                    "Additional data",
                    Field("title"),
                    Field("email"),
                    Field("pager"),
                    Field("tel"),
                    Field("comment"),
                    ),
                css_class="form-horizontal span6",
            ),
            css_class="row-fluid",
        ),
        FormActions(
            Button("delete", "Delete", css_class="primaryAction"),
        ),
        Field("parent_group"),
        Field("allowed_device_groups"),
        Div(
            Field("permissions"),
        )
    )
    homestart = CharField(widget=TextInput())
    class Meta:
        model = group
        fields = ["groupname", "gid", "active", "homestart",
                  "title", "email", "pager", "tel", "comment",
                  "allowed_device_groups", "permissions", "parent_group"]
    def create_mode(self):
        if "disabled" in self.helper.layout[3].attrs:
            del self.helper.layout[3].attrs["disabled"]
        self.helper.layout[2][0] = Submit("submit", "Create", css_class="primaryAction")
        if len(self.helper.layout[5]) == 2:
            # remove object permission button
            self.helper.layout[5].pop(1)
    def delete_mode(self):
        self.helper.layout[3].attrs["disabled"] = True
        self.helper.layout[2][0] = Submit("delete", "Delete", css_class="primaryAction")
        if len(self.helper.layout[5]) == 1:
            # add object permissions button
            self.helper.layout[5].append(Button("object_perms", "Object Permissions"))

class export_choice_field(ModelChoiceField):
    def reload(self):
        self.queryset = home_export_list()
    def label_from_instance(self, obj):
        return self.queryset.exp_dict[obj.pk]["info"]

class kernel_detail_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.layout = Layout(
        HTML("<h2>Kernel details</h2>"),
            Fieldset(
                "Basic data",
                Field("name", readonly=True),
                Field("initrd_built", readonly=True),
                Field("comment"),
                Field("target_module_list"),
                Field("module_list", readonly=True),
                css_class="form-horizontal",
                ),
            Div(
                Div(
                    FormActions(
                        Field("stage1_lo_present", disabled=True),
                        Field("stage1_cpio_present", disabled=True),
                    ),
                    css_class="span6",
                ),
                Div(
                    FormActions(
                        Field("stage1_cramfs_present", disabled=True),
                        Field("stage2_present", disabled=True),
                    ),
                    css_class="span6",
                ),
                css_class="row-fluid",
            ),
            FormActions(
                Submit("submit", "Submit", css_class="primaryAction"),
            ),
        )
    class Meta:
        model = kernel
        fields = ["name", "comment",
            "stage1_lo_present", "stage1_cpio_present", "stage1_cramfs_present", "stage2_present",
            "module_list", "target_module_list", "initrd_built",
            ]

class user_detail_form(ModelForm):
    permissions = ModelMultipleChoiceField(
        queryset=csw_permission.objects.all().select_related("content_type").order_by("codename"),
        widget=SelectMultiple(attrs={"size" : "8"}),
        required=False,
    )
    allowed_device_groups = ModelMultipleChoiceField(
        queryset=device_group.objects.exclude(Q(cluster_device_group=True)).filter(Q(enabled=True)),
        required=False,
    )
    password = CharField(widget=PasswordInput)
    helper = FormHelper()
    helper.form_id = "form"
    helper.layout = Layout(
        HTML("<h2>User details</h2>"),
        Div(
            Div(
                Fieldset(
                    "Basic data",
                    Field("login"),
                    Field("uid"),
                    Field("first_name"),
                    Field("last_name"),
                    Field("shell"),
                    ),
                css_class="form-horizontal span6",
            ),
            Div(
                Fieldset(
                    "Additional data",
                    Field("title"),
                    Field("email"),
                    Field("pager"),
                    Field("tel"),
                    Field("comment"),
                ),
                css_class="form-horizontal span6",
            ),
            css_class="row-fluid"
        ),
        Field("group"),
        Field("password", css_class="passwordfields"),
        Field("aliases"),
        FormActions(
            Field("active"),
            Field("is_superuser"),
            Field("db_is_auth_for_password"),
            Button("delete", "Delete", css_class="primaryAction"),
        ),
        Field("export"),
        Field("allowed_device_groups"),
        Field("secondary_groups"),
        Div(
            Field("permissions"),
        ),
    )
    export = export_choice_field(device_config.objects.none(), required=False)
    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request")
        super(user_detail_form, self).__init__(*args, **kwargs)
        self.fields["export"].reload()
        clear_perms = True
        if request is not None:
            if request.user:
                if request.user.has_perm("backbone.admin"):
                    clear_perms = False
                elif request.user.has_object_perm("backbone.group_admin"):
                    self.fields["group"].queryset = group.objects.filter(Q(pk__in=request.user.get_allowed_object_list("backbone.group_admin")))
                    self.fields["group"].empty_label = None
                    # disable superuser field
                    self.fields["is_superuser"].widget.attrs["disabled"] = True
                    clear_perms = False
        if clear_perms:
            self.fields["group"].queryset = group.objects.none()
            self.fields["is_superuser"].widget.attrs["disabled"] = True
    def create_mode(self):
        if "disabled" in self.helper.layout[2].attrs:
            del self.helper.layout[2].attrs["disabled"]
        self.helper.layout[5][3] = Submit("submit", "Create", css_class="primaryAction")
        if len(self.helper.layout[9]) == 2:
            # remove object permission button
            self.helper.layout[9].pop(1)
    def delete_mode(self):
        self.helper.layout[2].attrs["disabled"] = True
        self.helper.layout[5][3] = Submit("delete", "Delete", css_class="primaryAction")
        if len(self.helper.layout[9]) == 1:
            # add object permissions button
            self.helper.layout[9].append(Button("object_perms", "Object Permissions"))
    class Meta:
        model = user
        fields = ["login", "uid", "shell", "first_name", "last_name", "active",
                  "title", "email", "pager", "tel", "comment", "is_superuser",
                  "allowed_device_groups", "secondary_groups", "permissions",
                  "aliases",
                  "db_is_auth_for_password", "export", "password", "group"]

class account_detail_form(ModelForm):
    password = CharField(widget=PasswordInput)
    helper = FormHelper()
    helper.form_id = "form"
    helper.layout = Layout(
        HTML("<h2>Account info</h2>"),
        Div(
            Div(
                Fieldset(
                    "Basic data",
                    Field("first_name"),
                    Field("last_name"),
                    Field("shell"),
                    css_class="form-horizontal",
                    ),
                css_class="span6",
            ),
            Div(
                Fieldset(
                    "Additional data",
                    Field("title"),
                    Field("email"),
                    Field("pager"),
                    Field("tel"),
                    Field("comment"),
                    css_class="form-horizontal",
                    ),
                css_class="span6",
            ),
            css_class="row-fluid",
        ),
        Div(
            Field("password", css_class="passwordfields"),
            css_class="form-horizontal"
        ),
    )
    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request")
        super(account_detail_form, self).__init__(*args, **kwargs)
    class Meta:
        model = user
        fields = ["shell", "first_name", "last_name",
                  "title", "email", "pager", "tel", "comment",
                  "password"]
