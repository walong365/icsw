# -*- coding: utf-8 -*-

""" simple formulars for django / clustersoftware """

import re
from django.forms.widgets import TextInput, PasswordInput, SelectMultiple, Textarea
from django.forms import Form, ModelForm, ValidationError, CharField, ModelChoiceField, \
    ModelMultipleChoiceField, ChoiceField, TextInput
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
     csw_permission, kernel, network, network_type, network_device_type, image, partition_table, \
     mon_period, mon_notification, mon_contact, mon_service_templ, host_check_command, \
     mon_contactgroup, mon_device_templ, mon_host_cluster, mon_service_cluster, mon_host_dependency_templ, \
     mon_service_esc_templ, mon_device_esc_templ, mon_service_dependency_templ
from initat.cluster.frontend.widgets import device_tree_widget

# import PAM

class authentication_form(Form):
    username = CharField(label=_("Username"),
                         max_length=30)
    password = CharField(label=_("Password"),
                         widget=PasswordInput)
    helper = FormHelper()
    helper.form_id = "id_login_form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
    helper.layout = Layout(
        Div(
            Fieldset(
                HTML("<h2>Login credentials</h2>"),
                Field("username", placeholder="user name"),
                Field("password", placeholder="password"),
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
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
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
                Button("delete", "Delete", css_class="btn-danger")
            ),
        )
    )
    class Meta:
        model = domain_tree_node
        fields = ["name", "node_postfix", "create_short_names", "always_create_ip", "write_nameserver_config", "comment"]

class dtn_new_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_dtn_detail_form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
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
        )
    )
    class Meta:
        model = domain_tree_node
        fields = ["full_name", "node_postfix", "create_short_names", "always_create_ip", "write_nameserver_config", "comment"]

class device_general_form(ModelForm):
    domain_tree_node = ModelChoiceField(domain_tree_node.objects.none(), empty_label=None) # , widget=domain_name_tree_widget)
    helper = FormHelper()
    helper.form_id = "id_dtn_detail_form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
    helper.layout = Layout(
        Fieldset(
            "Device details",
            Field("name"),
            Field("domain_tree_node"),
            Field("comment"),
        ),
        Fieldset(
            "Monitor settings",
            Field("mon_device_templ"),
            Field("monitor_checks"),
            Field("enable_perfdata"),
            Field("flap_detection_enabled"),
        ),
        Fieldset(
            "Info",
            Button("uuid", "show UUID info"),
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
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
    helper.layout = Layout(
        Fieldset(
            "please enter the new password",
            Field("password1", placeholder="password"),
            Field("password2", placeholder="again"),
            FormActions(
                Button("check", "Check"),
                Button("leave", "Check and save"),
            ),
        )
    )
    password1 = CharField(label=_("New Password"),
                         widget=PasswordInput)
    password2 = CharField(label=_("Confirm Password"),
                         widget=PasswordInput)

class category_detail_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_cat_detail_form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
    helper.layout = Layout(
        Div(
            HTML("Category details"),
            Field("name"),
            Field("comment"),
            FormActions(
                Button("delete", "Delete", css_class="btn-danger")
            ),
        )
    )
    class Meta:
        model = category
        fields = ["name", "comment"]

class location_detail_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_cat_detail_form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
    helper.layout = Layout(
        Div(
            HTML("Category details"),
            Field("name"),
            Field("comment"),
            FormActions(
                Button("delete", "Delete", css_class="btn-danger"),
            ),
            Field("latitude"),
            Field("longitude"),
        )
    )
    class Meta:
        model = category
        fields = ["name", "comment", "latitude", "longitude"]

class category_new_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_dtn_detail_form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
    helper.layout = Layout(
        Div(
            HTML("Create new category"),
            Field("full_name"),
            Field("comment"),
            FormActions(
                Submit("submit", "Submit", css_class="primaryAction"),
                ),
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
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
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
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
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
                css_class="col-md-6",
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
                css_class="col-md-6",
            ),
            css_class="row",
        ),
        FormActions(
            Button("delete", "Delete", css_class="btn-danger"),
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
        self.helper.layout[2][0] = Submit("submit", "Create", css_class="btn-primary")
        if len(self.helper.layout[5]) == 2:
            # remove object permission button
            self.helper.layout[5].pop(1)
    def delete_mode(self):
        self.helper.layout[3].attrs["disabled"] = True
        self.helper.layout[2][0] = Submit("delete", "Delete", css_class="btn-danger")
        if len(self.helper.layout[5]) == 1:
            # add object permissions button
            self.helper.layout[5].append(Button("object_perms", "Object Permissions"))

class export_choice_field(ModelChoiceField):
    def reload(self):
        self.queryset = home_export_list()
    def label_from_instance(self, obj):
        return self.queryset.exp_dict[obj.pk]["info"]

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
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
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
                css_class="col-md-6",
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
                css_class="col-md-6",
            ),
            css_class="row"
        ),
        Field("group"),
        Field("password", css_class="passwordfields"),
        Field("aliases"),
        FormActions(
            Field("active"),
            Field("is_superuser"),
            Field("db_is_auth_for_password"),
            Button("delete", "Delete", css_class="btn-danger"),
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
        self.helper.layout[5][3] = Submit("submit", "Create", css_class="btn-primare")
        if len(self.helper.layout[9]) == 2:
            # remove object permission button
            self.helper.layout[9].pop(1)
    def delete_mode(self):
        self.helper.layout[2].attrs["disabled"] = True
        self.helper.layout[5][3] = Submit("delete", "Delete", css_class="btn-danger")
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
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
    helper.layout = Layout(
        HTML("<h2>Account info</h2>"),
        Div(
            Div(
                Fieldset(
                    "Basic data",
                    Field("first_name", placeholder="first name"),
                    Field("last_name", placeholder="last name"),
                    Field("shell", placeholder="shell to use"),
                    css_class="form-horizontal",
                    ),
                css_class="col-md-6",
            ),
            Div(
                Fieldset(
                    "Additional data",
                    Field("title", placeholder="Title"),
                    Field("email", placeholder="EMail address"),
                    Field("pager", placeholder="pager number"),
                    Field("tel", placeholder="Telefon number"),
                    Field("comment", placeholder="User comment"),
                    css_class="form-horizontal",
                    ),
                css_class="col-md-6",
            ),
            css_class="row",
        ),
        Div(
            Field("password", css_class="passwordfields"),
            css_class="form-horizontal"
        ),
    )
    class Meta:
        model = user
        fields = ["shell", "first_name", "last_name",
                  "title", "email", "pager", "tel", "comment",
                  "password"]

class kernel_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Kernel details</h2>"),
            Fieldset(
                "Basic data",
                Field("name", readonly=True),
                Field("initrd_built", readonly=True),
                Field("comment", rows=5),
                Field("target_module_list", rows=3),
                Field("module_list", readonly=True, rows=3),
                ),
            Div(
                Div(
                    FormActions(
                        Field("stage1_lo_present", disabled=True),
                        Field("stage1_cpio_present", disabled=True),
                        Field("stage1_cramfs_present", disabled=True),
                        Field("stage2_present", disabled=True),
                    ),
                    css_class="col-md-5",
                ),
                Div(
                    FormActions(
                        Field("enabled"),
                    ),
                    css_class="col-md-5",
                ),
                css_class="row",
            ),
            FormActions(
                Submit("submit", "", ng_value="get_action_string()", css_class="primaryAction"),
            ),
        )
    class Meta:
        model = kernel
        fields = ["name", "comment", "enabled",
            "stage1_lo_present", "stage1_cpio_present", "stage1_cramfs_present", "stage2_present",
            "module_list", "target_module_list", "initrd_built",
            ]

class image_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Image details</h2>"),
            Fieldset(
                "Basic data",
                Field("name", readonly=True),
                ),
            FormActions(
                Submit("submit", "", ng_value="get_action_string()", css_class="primaryAction"),
            ),
        )
    class Meta:
        model = image
        fields = ["name", "enabled",
            ]

class empty_query_set(object):
    def all(self):
        raise StopIteration

class network_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    master_network = ModelChoiceField(queryset=empty_query_set(), empty_label="No master network", required=False)
    network_type = ModelChoiceField(queryset=empty_query_set(), empty_label=None)
    network_device_type = ModelMultipleChoiceField(queryset=empty_query_set(), required=False)
    helper.layout = Layout(
        HTML("<h2>Network</h2>"),
            Fieldset(
                "Basic data",
                Field("identifier", wrapper_class="ng-class:form_error('identifier')", placeholder="Identifier"),
                Field("network"   , wrapper_class="ng-class:form_error('network')"   , ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Network"),
                Field("netmask"   , wrapper_class="ng-class:form_error('netmask')"   , ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Netmask"),
                Field("broadcast" , wrapper_class="ng-class:form_error('broadcast')" , ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Broadcast"),
                Field("gateway"   , wrapper_class="ng-class:form_error('gateway')"   , ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Gateway"),
            ),
            Fieldset(
                "Additional settings",
                Field("network_type", ng_options="value.idx as value.description for value in rest_data.network_types", chosen=True),
                Field("master_network", ng_options="value.idx as value.identifier for value in fn.get_production_networks(this)", wrapper_ng_show="fn.is_slave_network(this, edit_obj.network_type)", chosen=True),
                Field("network_device_type", ng_options="value.idx as value.identifier for value in rest_data.network_device_types", chosen=True),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    class Meta:
        model = network
        fields = ["identifier", "network", "netmask", "broadcast", "gateway", "master_network", "network_type", "network_device_type"]

class network_type_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    identifier = ModelChoiceField(queryset=empty_query_set(), empty_label=None)
    helper.layout = Layout(
        HTML("<h2>Network type</h2>"),
            Fieldset(
                "Basic data",
                Field("description", wrapper_class="ng-class:form_error('description')", placeholder="Description"),
                Field("identifier", ng_options="key as value for (key, value) in settings.network_types"),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    class Meta:
        model = network_type
        fields = ["identifier", "description"]

class network_device_type_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Network device type</h2>"),
            Fieldset(
                "Basic data",
                Field("identifier", wrapper_class="ng-class:form_error('identifier')", placeholder="Identifier"),
                Field("description", wrapper_class="ng-class:form_error('description')", placeholder="Description"),
                Field("mac_bytes", placeholder="MAC bytes", min=6, max=24),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    class Meta:
        model = network_device_type
        fields = ["identifier", "description", "mac_bytes"]

class partition_table_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Partition table</h2>"),
            Fieldset(
                "Basic data",
                Field("name", wrapper_class="ng-class:form_error('name')", placeholder="Name"),
                Field("description", wrapper_class="ng-class:form_error('description')", placeholder="Description"),
            ),
            Fieldset(
                "Flags",
                Field("enabled"),
                Field("nodeboot"),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    class Meta:
        model = partition_table
        fields = ["name", "description", "enabled", "nodeboot"]

class mon_period_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Monitoring period</h2>"),
            Fieldset(
                "Basic data",
                Field("name", wrapper_class="ng-class:form_error('name')", placeholder="Name"),
                Field("alias", wrapper_class="ng-class:form_error('alias')", placeholder="Alias"),
            ),
            Fieldset(
                "Time ranges",
                Field("sun_range", placeholder="00:00-24:00", wrapper_class="ng-class:form_error('sun_range')", ng_pattern="/^\d+:\d+-\d+:\d+$/", required=True),
                Field("mon_range", placeholder="00:00-24:00", wrapper_class="ng-class:form_error('sun_range')", ng_pattern="/^\d+:\d+-\d+:\d+$/", required=True),
                Field("tue_range", placeholder="00:00-24:00", wrapper_class="ng-class:form_error('sun_range')", ng_pattern="/^\d+:\d+-\d+:\d+$/", required=True),
                Field("wed_range", placeholder="00:00-24:00", wrapper_class="ng-class:form_error('sun_range')", ng_pattern="/^\d+:\d+-\d+:\d+$/", required=True),
                Field("thu_range", placeholder="00:00-24:00", wrapper_class="ng-class:form_error('sun_range')", ng_pattern="/^\d+:\d+-\d+:\d+$/", required=True),
                Field("fri_range", placeholder="00:00-24:00", wrapper_class="ng-class:form_error('sun_range')", ng_pattern="/^\d+:\d+-\d+:\d+$/", required=True),
                Field("sat_range", placeholder="00:00-24:00", wrapper_class="ng-class:form_error('sun_range')", ng_pattern="/^\d+:\d+-\d+:\d+$/", required=True),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    class Meta:
        model = mon_period
        fields = ["name", "alias", "sun_range", "mon_range", "tue_range", "wed_range", "thu_range",
            "fri_range", "sat_range"]

class mon_notification_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    channel = ChoiceField([("mail", "E-Mail"), ("sms" , "SMS")])
    not_type = ChoiceField([("host", "Host"), ("service", "Service")])
    content = CharField(widget=Textarea)
    helper.layout = Layout(
        HTML("<h2>Monitoring Notification</h2>"),
            Fieldset(
                "Basic data",
                Field("name", wrapper_class="ng-class:form_error('name')", placeholder="Name"),
                Field("channel"),
                Field("not_type"),
            ),
            Fieldset(
                "Flags and text",
                Field("enabled"),
                Field("subject", wrapper_ng_show="edit_obj.channel == 'mail'"),
                Field("content", required=True),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    class Meta:
        model = mon_notification
        fields = ["name", "channel", "not_type", "subject", "content", "enabled", ]

class mon_contact_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Monitoring Contact</h2>"),
            Fieldset(
                "Basic data",
                Field("user", ng_options="value.idx as value.login + ' (' + value.first_name + ' ' + value.last_name + ')' for value in rest_data.user | orderBy:'login'"),
                Field("notifications", ng_options="value.idx as value.name for value in rest_data.mon_notification | sortBy:'name'", chosen=True),
                Field("mon_alias"),
            ),
            Fieldset(
                "Service settings",
                Field("snperiod", ng_options="value.idx as value.name for value in rest_data.mon_period | orderBy:'name'"),
            ),
            Div(
                Div(
                    FormActions(
                        Field("snrecovery"),
                        Field("sncritical"),
                        Field("snwarning"),
                    ),
                    css_class="col-md-5",
                ),
                Div(
                    FormActions(
                        Field("snunknown"),
                        Field("sflapping"),
                        Field("splanned_downtime"),
                    ),
                    css_class="col-md-5",
                ),
                css_class="row",
            ),
            Fieldset(
                "Host settings",
                Field("hnperiod", ng_options="value.idx as value.name for value in rest_data.mon_period | orderBy:'name'"),
            ),
            Div(
                Div(
                    FormActions(
                        Field("hnrecovery"),
                        Field("hndown"),
                        Field("hnunreachable"),
                    ),
                    css_class="col-md-5",
                ),
                Div(
                    FormActions(
                        Field("hflapping"),
                        Field("hplanned_downtime"),
                    ),
                    css_class="col-md-5",
                ),
                css_class="row",
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["user", "snperiod", "hnperiod", "notifications"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
    class Meta:
        model = mon_contact
        fields = ["user", "snperiod", "hnperiod", "notifications", "mon_alias",
            "snrecovery", "sncritical", "snwarning", "snunknown", "sflapping", "splanned_downtime",
            "hnrecovery", "hndown", "hnunreachable", "hflapping", "hplanned_downtime", ]

class mon_service_templ_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Service template</h2>"),
            Fieldset(
                "Basic data",
                Field("name"),
                Field("volatile"),
            ),
            Fieldset(
                "Check",
                Field("nsc_period", ng_options="value.idx as value.name for value in rest_data.mon_period | orderBy:'name'"),
            ),
            FormActions(
                Field("max_attempts", min=1, max=10),
                Field("check_interval", min=1, max=60),
                Field("retry_interval", min=1, max=60),
            ),
            Fieldset(
                "Notification",
                Field("nsn_period", ng_options="value.idx as value.name for value in rest_data.mon_period | orderBy:'name'"),
            ),
            Div(
                Div(
                    Field("nrecovery"),
                    Field("ncritical"),
                    css_class="col-md-3",
                ),
                Div(
                    Field("nwarning"),
                    Field("nunknown"),
                    css_class="col-md-3",
                ),
                Div(
                    Field("nflapping"),
                    Field("nplanned_downtime"),
                    css_class="col-md-3",
                ),
                css_class="row",
            ),
            Fieldset(
                "Flap settings",
                Field("flap_detection_enabled"),
            ),
            FormActions(
                Field("low_flap_threshold", min=0, max=100),
                Field("high_flap_threshold", min=0, max=100),
            ),
            Div(
                Div(
                    Field("flap_detect_ok"),
                    Field("flap_detect_warn"),
                    css_class="col-md-5",
                ),
                Div(
                    Field("flap_detect_critical"),
                    Field("flap_detect_unknown"),
                    css_class="col-md-5",
                ),
                css_class="row",
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["nsc_period", "nsn_period"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
    class Meta:
        model = mon_service_templ

class mon_service_esc_templ_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Service Escalation template</h2>"),
            Fieldset(
                "Basic data",
                Field("name"),
            ),
            Fieldset(
                "Notifications",
                Field("first_notification", min=1, max=10),
                Field("last_notification", min=1, max=10),
                Field("esc_period", ng_options="value.idx as value.name for value in rest_data.mon_period | orderBy:'name'"),
                Field("ninterval", min=0, max=60),
            ),
            Div(
                Div(
                    Field("nrecovery"),
                    Field("ncritical"),
                    css_class="col-md-3",
                ),
                Div(
                    Field("nwarning"),
                    Field("nunknown"),
                    css_class="col-md-3",
                ),
                Div(
                    Field("nflapping"),
                    Field("nplanned_downtime"),
                    css_class="col-md-3",
                ),
                css_class="row",
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["esc_period"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
    class Meta:
        model = mon_service_esc_templ

class host_check_command_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Host check command</h2>"),
            Fieldset(
                "Basic data",
                Field("name"),
                Field("command_line"),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
    class Meta:
        model = host_check_command

class mon_contactgroup_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Contactgroup</h2>"),
            Fieldset(
                "Basic data",
                Field("name"),
                Field("alias"),
            ),
            Fieldset(
                "settings",
                Field("members", ng_options="value.idx as value.user_name for value in rest_data.mon_contact | orderBy:'user_name'", chosen=True),
                Field("device_groups", ng_options="value.idx as value.name for value in rest_data.device_group | orderBy:'name'", chosen=True),
                Field("service_templates", ng_options="value.idx as value.name for value in rest_data.mon_service_templ | orderBy:'name'", chosen=True),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["device_groups", "members", "service_templates"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
    class Meta:
        model = mon_contactgroup

class mon_device_templ_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Device template</h2>"),
            Fieldset(
                "Basic data",
                Field("name"),
                Field("mon_service_templ", ng_options="value.idx as value.name for value in rest_data.mon_service_templ | orderBy:'name'", chosen=True),
            ),
            Fieldset(
                "Check",
                Field("host_check_command", ng_options="value.idx as value.name for value in rest_data.host_check_command | orderBy:'name'", chosen=True),
                Field("mon_period", ng_options="value.idx as value.name for value in rest_data.mon_period | orderBy:'name'"),
            ),
            FormActions(
                Field("check_interval", min=1, max=60),
                Field("retry_interval", min=1, max=60),
                Field("max_attempts", min=1, max=10),
            ),
            Fieldset(
                "Notification",
            ),
            Div(
                Div(
                    Field("nrecovery"),
                    Field("ndown"),
                    css_class="col-md-3",
                ),
                Div(
                    Field("nunreachable"),
                    css_class="col-md-3",
                ),
                Div(
                    Field("nflapping"),
                    Field("nplanned_downtime"),
                    css_class="col-md-3",
                ),
                css_class="row",
            ),
            Fieldset(
                "Flap settings",
                Field("flap_detection_enabled"),
            ),
            FormActions(
                Field("low_flap_threshold", min=0, max=100),
                Field("high_flap_threshold", min=0, max=100),
            ),
            Div(
                Div(
                    Field("flap_detect_up"),
                    Field("flap_detect_down"),
                    css_class="col-md-5",
                ),
                Div(
                    Field("flap_detect_unreachable"),
                    css_class="col-md-5",
                ),
                css_class="row",
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["mon_service_templ", "host_check_command", "mon_period"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
    class Meta:
        model = mon_device_templ

class mon_device_esc_templ_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Device Escalation template</h2>"),
            Fieldset(
                "Basic data",
                Field("name"),
                Field("mon_service_esc_templ", ng_options="value.idx as value.name for value in rest_data.mon_service_esc_templ | orderBy:'name'", chosen=True),
            ),
            Fieldset(
                "Notifications",
                Field("first_notification", min=1, max=10),
                Field("last_notification", min=1, max=10),
                Field("esc_period", ng_options="value.idx as value.name for value in rest_data.mon_period | orderBy:'name'"),
                Field("ninterval", min=0, max=60),
            ),
            Fieldset(
                "Notification",
            ),
            Div(
                Div(
                    Field("nrecovery"),
                    Field("ndown"),
                    css_class="col-md-3",
                ),
                Div(
                    Field("nunreachable"),
                    css_class="col-md-3",
                ),
                Div(
                    Field("nflapping"),
                    Field("nplanned_downtime"),
                    css_class="col-md-3",
                ),
                css_class="row",
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["mon_service_esc_templ", "esc_period"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
    class Meta:
        model = mon_device_esc_templ

class mon_host_cluster_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Host Cluster</h2>"),
            Fieldset(
                "Basic data",
                Field("name"),
                Field("description"),
            ),
            Fieldset(
                "Devices",
                Field("main_device", ng_options="value.idx as value.name for value in rest_data.device | orderBy:'name'", chosen=True),
                Field("devices", ng_options="value.idx as value.name for value in rest_data.device | orderBy:'name'", chosen=True),
                # Field("device_groups", ng_options="value.idx as value.name for value in rest_data.device_group | orderBy:'name'", chosen=True),
            ),
            Fieldset(
                "Service",
                Field("mon_service_templ", ng_options="value.idx as value.name for value in rest_data.mon_service_templ | orderBy:'name'", chosen=True),
                Field("warn_value", min=0, max=128),
                Field("error_value", min=0, max=128),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["mon_service_templ", "devices", "main_device"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
    class Meta:
        model = mon_host_cluster

class mon_service_cluster_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Service Cluster</h2>"),
            Fieldset(
                "Basic data",
                Field("name"),
                Field("description"),
            ),
            Fieldset(
                "Devices",
                Field("main_device", ng_options="value.idx as value.name for value in rest_data.device | orderBy:'name'", chosen=True),
                Field("devices", ng_options="value.idx as value.name for value in rest_data.device | orderBy:'name'", chosen=True),
                # Field("device_groups", ng_options="value.idx as value.name for value in rest_data.device_group | orderBy:'name'", chosen=True),
            ),
            Fieldset(
                "Service",
                Field("mon_service_templ", ng_options="value.idx as value.name for value in rest_data.mon_service_templ | orderBy:'name'", chosen=True),
                Field("mon_check_command", ng_options="value.idx as value.name for value in rest_data.mon_check_command | orderBy:'name'", chosen=True),
                Field("warn_value", min=0, max=128),
                Field("error_value", min=0, max=128),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["mon_service_templ", "devices", "main_device", "mon_check_command"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
    class Meta:
        model = mon_service_cluster

class mon_host_dependency_templ_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Host dependence template</h2>"),
            Fieldset(
                "Basic data",
                Field("name"),
                Field("dependency_period", ng_options="value.idx as value.name for value in rest_data.mon_period | orderBy:'name'", chosen=True),
                Field("priority", min= -128, max=128),
                Field("inherits_parent"),
            ),
            Fieldset(
                "Execution failure criteria",
                Div(
                    Div(
                        Field("efc_up"),
                        Field("efc_down"),
                        css_class="col-md-5",
                    ),
                    Div(
                        Field("efc_unreachable"),
                        Field("efc_pending"),
                        css_class="col-md-5",
                    ),
                    css_class="rows",
                ),
            ),
            Fieldset(
                "Notification failure criteria",
                Div(
                    Div(
                        Field("nfc_up"),
                        Field("nfc_down"),
                        css_class="col-md-5",
                    ),
                    Div(
                        Field("nfc_unreachable"),
                        Field("nfc_pending"),
                        css_class="col-md-5",
                    ),
                    css_class="rows",
                ),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["dependency_period"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
    class Meta:
        model = mon_host_dependency_templ

class mon_service_dependency_templ_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Service dependence template</h2>"),
            Fieldset(
                "Basic data",
                Field("name"),
                Field("dependency_period", ng_options="value.idx as value.name for value in rest_data.mon_period | orderBy:'name'", chosen=True),
                Field("priority", min= -128, max=128),
                Field("inherits_parent"),
            ),
            Fieldset(
                "Execution failure criteria",
                Div(
                    Div(
                        Field("efc_ok"),
                        Field("efc_warn"),
                        Field("efc_unknown"),
                        css_class="col-md-5",
                    ),
                    Div(
                        Field("efc_critical"),
                        Field("efc_pending"),
                        css_class="col-md-5",
                    ),
                    css_class="rows",
                ),
            ),
            Fieldset(
                "Notification failure criteria",
                Div(
                    Div(
                        Field("nfc_ok"),
                        Field("nfc_warn"),
                        Field("nfc_unknown"),
                        css_class="col-md-5",
                    ),
                    Div(
                        Field("nfc_critical"),
                        Field("nfc_pending"),
                        css_class="col-md-5",
                    ),
                    css_class="rows",
                ),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["dependency_period"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
    class Meta:
        model = mon_service_dependency_templ

