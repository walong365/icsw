# -*- coding: utf-8 -*-

""" simple formulars for django / clustersoftware """

# from crispy_forms.bootstrap import FormActions
from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Button, Fieldset, Div, HTML
from django.contrib.auth import authenticate
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.forms import Form, ModelForm, ValidationError, CharField, ModelChoiceField, \
    ModelMultipleChoiceField, ChoiceField, TextInput, TypedChoiceField, BooleanField
from django.forms.widgets import TextInput, PasswordInput, SelectMultiple, Textarea
from django.utils.translation import ugettext_lazy as _
from initat.cluster.backbone.models import domain_tree_node, device, category, mon_check_command, mon_service_templ, \
     domain_name_tree, user, group, device_group, home_export_list, device_config, TOP_LOCATIONS, \
     csw_permission, kernel, network, network_type, network_device_type, image, partition_table, \
     mon_period, mon_notification, mon_contact, mon_service_templ, host_check_command, \
     mon_contactgroup, mon_device_templ, mon_host_cluster, mon_service_cluster, mon_host_dependency_templ, \
     mon_service_esc_templ, mon_device_esc_templ, mon_service_dependency_templ, package_search, \
     mon_service_dependency, mon_host_dependency, package_device_connection, partition, \
     partition_disc, sys_partition, device_variable, config, config_str, config_int, config_bool, \
     config_script
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
                "Please enter your login credentials",
                Field("username", placeholder="user name"),
                Field("password", placeholder="password"),
            ),
            FormActions(
                Submit("submit", "Submit", css_class="btn btn-primary"),
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

class domain_tree_node_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_dtn_detail_form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        Div(
            HTML("<h2>Domain tree node details for {% verbatim %}{{ edit_obj.full_name }}{% endverbatim %}</h2>"),
            Fieldset(
                "Basic settings",
                Field("name"),
                Field("parent", ng_options="value.idx as value.tree_info for value in fn.get_valid_parents(this)", chosen=True),
            ),
            Fieldset(
                "Additional settings",
                Field("node_postfix"),
                Field("comment"),
            ),
            Fieldset(
                "Flags",
                Field("create_short_names"),
                Field("always_create_ip"),
                Field("write_nameserver_config"),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
                HTML("&nbsp;"),
                Button("close", "close", css_class="btn-warning", ng_click="close_modal()"),
                HTML("&nbsp;"),
                Button("delete", "delete", css_class="btn-danger", ng_click="fn.delete_node(this, edit_obj)"),
            ),
        )
    )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["parent"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
    class Meta:
        model = domain_tree_node
        fields = ["name", "node_postfix", "create_short_names", "always_create_ip", "write_nameserver_config", "comment", "parent", ]

class device_general_form(ModelForm):
    domain_tree_node = ModelChoiceField(domain_tree_node.objects.none(), empty_label=None)
    helper = FormHelper()
    helper.form_id = "id_dtn_detail_form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-9'
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
            Div(
                Div(
                    Field("monitor_checks"),
                    Field("enable_perfdata"),
                    css_class="col-md-6",
                ),
                Div(
                    Field("flap_detection_enabled"),
                    Field("mon_resolve_name"),
                    css_class="col-md-6",
                ),
                css_class="row",
            ),
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
                  "enable_perfdata", "flap_detection_enabled", "mon_resolve_name"]

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

class category_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_partition_form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        Div(
            HTML("<h2>Category details for '{% verbatim %}{{ edit_obj.name }}{% endverbatim %}'</h2>"),
            Fieldset(
                "Basic settings",
                Field("name", wrapper_class="ng-class:form_error('name')"),
                Field("parent", ng_options="value.idx as value.full_name for value in fn.get_valid_parents(this)", chosen=True),
            ),
            Fieldset(
                "Additional fields",
                Field("comment"),
            ),
            Fieldset(
                "Positional data",
                Field("latitude", ng_pattern="/^\d+\.\d+$/"),
                Field("longitude", ng_pattern="/^\d+\.\d+$/"),
                ng_if="fn.is_location(edit_obj)",
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
                HTML("&nbsp;"),
                Button("close", "close", css_class="btn-warning", ng_click="close_modal()"),
                HTML("&nbsp;"),
                Button("delete", "delete", css_class="btn-danger", ng_click="fn.delete_node(this, edit_obj)", ng_show="!create_mode && !edit_obj.num_refs"),
            ),
        )
    )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["parent"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
    class Meta:
        model = category
        fields = ["name", "comment", "parent", "longitude", "latitude"]

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
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "group_edit.modify(this)"
    helper.layout = Layout(
        HTML("<h2>Details for group {% verbatim %}'{{ _edit_obj.groupname }}'{% endverbatim %}</h2>"),
        Div(
            Div(
                Fieldset(
                    "Basic data",
                    Field("groupname", ng_pattern="/^.+$/", wrapper_class="ng-class:group_edit.form_error('groupname')"),
                    Field("gid", ng_pattern="/^\d+$/", wrapper_class="ng-class:group_edit.form_error('gid')"),
                    Field("homestart", ng_pattern="/^\/.*/", wrapper_class="ng-class:group_edit.form_error('homestart')"),
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
        Fieldset(
            "Permissions",
            Field("parent_group", ng_options="value.idx as value.groupname for value in group_list", chosen=True),
            Field("allowed_device_groups", ng_options="value.idx as value.name for value in valid_device_groups()", chosen=True),
            Field("permissions", ng_options="value.idx as value.info for value in valid_group_csw_permissions()", chosen=True),
        ),
        Fieldset(
            "Object permissions",
            HTML("<div ng-if='!create_mode' objectpermissions></div>"),
        ),
        FormActions(
            Submit("modify", "Modify", css_class="btn-success", ng_show="!create_mode"),
            Submit("create", "Create", css_class="btn-success", ng_show="create_mode"),
            HTML("&nbsp;"),
            Button("close", "close", css_class="btn-primary", ng_click="group_edit.close_modal()", ng_show="!create_mode"),
            HTML("&nbsp;"),
            Button("delete", "delete", css_class="btn-danger", ng_click="group_edit.delete_obj(_edit_obj)", ng_show="!create_mode"),
        ),
    )
    homestart = CharField(widget=TextInput())
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["parent_group", "allowed_device_groups", "permissions"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
    class Meta:
        model = group
        fields = ["groupname", "gid", "active", "homestart",
                  "title", "email", "pager", "tel", "comment",
                  "allowed_device_groups", "permissions", "parent_group"]

class export_choice_field(ModelChoiceField):
    def reload(self):
        self.queryset = home_export_list()
    def label_from_instance(self, obj):
        return self.queryset.exp_dict[obj.pk]["info"]

class user_detail_form(ModelForm):
    password = CharField(widget=PasswordInput)
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "user_edit.modify()"
    helper.layout = Layout(
        HTML("<h2>Details for user {% verbatim %}'{{ _edit_obj.login }}'{% endverbatim %}</h2>"),
        Div(
            Div(
                Fieldset(
                    "Base data",
                    Field("login"),
                    Field("uid"),
                    Field("first_name", placeholder="first name"),
                    Field("last_name", placeholder="last name"),
                    Field("shell", placeholder="shell to use"),
                    ),
                css_class="col-md-6",
            ),
            Div(
                Fieldset(
                    "Additional data",
                    Field("title", placeholder="title"),
                    Field("email", placeholder="email address"),
                    Field("pager", placeholder="pager number"),
                    Field("tel", placeholder="telefon number"),
                    Field("comment", placeholder="comment"),
                ),
                css_class="col-md-6",
            ),
            css_class="row"
        ),
        Fieldset(
            "Flags",
            Div(
                Div(
                    Field("active"),
                    Field("is_superuser"),
                    css_class="col-md-6",
                ),
                Div(
                    Field("db_is_auth_for_password"),
                    css_class="col-md-6",
                ),
                css_class="row",
            ),
        ),
        Fieldset(
            "Permissions",
            Field("allowed_device_groups", ng_options="value.idx as value.name for value in valid_device_groups()", chosen=True),
            Field("permissions", ng_options="value.idx as value.info for value in valid_user_csw_permissions()", chosen=True),
        ),
        Fieldset(
            "Groups / export entry",
            Field("group", ng_options="value.idx as value.groupname for value in group_list", chosen=True),
            Field("secondary_groups", ng_options="value.idx as value.groupname for value in group_list", chosen=True),
            Field("export", ng_options="value.idx as value.info_string for value in get_export_list()", chosen=True),
        ),
        Fieldset(
            "Aliases",
            Field("aliases", rows=3),
        ),
        Fieldset(
            "Object permissions",
            HTML("<div objectpermissions ng-if='!create_mode'></div>"),
        ),
        FormActions(
            Submit("modify", "Modify", css_class="btn-success", ng_show="!create_mode"),
            Submit("create", "Create", css_class="btn-success", ng_show="create_mode"),
            HTML("&nbsp;"),
            Button("close", "close", css_class="btn-primary", ng_click="user_edit.close_modal()", ng_show="!create_mode"),
            HTML("&nbsp;"),
            Button("delete", "delete", css_class="btn-danger", ng_click="user_edit.delete_obj(_edit_obj)", ng_show="!create_mode"),
            HTML("&nbsp;"),
            Button("change password", "change password", css_class="btn-warning", ng_click="change_password()", ng_show="!create_mode"),
            Button("set password", "set password", css_class="btn-warning", ng_click="change_password()", ng_show="create_mode"),
        ),
    )
    def __init__(self, *args, **kwargs):
        # request = kwargs.pop("request")
        super(user_detail_form, self).__init__(*args, **kwargs)
        for clear_f in ["group", "secondary_groups", "permissions", "allowed_device_groups"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
        self.fields["export"].queryset = empty_query_set()
        self.fields["export"].empty_label = "None"
        if False:
            # to avoid validation errors
            request = None
            # FIXME, TODO
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
    class Meta:
        model = user
        fields = ["login", "uid", "shell", "first_name", "last_name", "active",
                  "title", "email", "pager", "tel", "comment", "is_superuser",
                  "allowed_device_groups", "secondary_groups", "permissions",
                  "aliases", "db_is_auth_for_password", "export", "group"]

class account_detail_form(ModelForm):
    password = CharField(widget=PasswordInput)
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
    helper.ng_model = "edit_obj"
    helper.ng_submit = "update_account()"
    helper.layout = Layout(
        HTML("<h2>Account info for '{% verbatim %}{{ edit_obj.login }}{% endverbatim %}'</h2>"),
        Div(
            Div(
                Fieldset(
                    "Base data",
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
        FormActions(
            Submit("submit", "Modify", css_class="primaryAction"),
            HTML("&nbsp;"),
            Button("change password", "change password", ng_click="change_password()", css_class="btn-warning")
        ),
    )
    class Meta:
        model = user
        fields = ["shell", "first_name", "last_name",
            "title", "email", "pager", "tel", "comment", ]


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
                "Base data",
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
                    css_class="col-md-6",
                ),
                Div(
                    FormActions(
                        Field("enabled"),
                    ),
                    css_class="col-md-6",
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
                "Base data",
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
                "Base data",
                Field("identifier", wrapper_class="ng-class:form_error('identifier')", placeholder="Identifier"),
                Field("network"   , wrapper_class="ng-class:form_error('network')"   , ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Network"),
                Field("netmask"   , wrapper_class="ng-class:form_error('netmask')"   , ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Netmask"),
                Field("broadcast" , wrapper_class="ng-class:form_error('broadcast')" , ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Broadcast"),
                Field("gateway"   , wrapper_class="ng-class:form_error('gateway')"   , ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Gateway"),
            ),
            Fieldset(
                "Additional settings",
                Field("network_type", ng_options="value.idx as value.description for value in rest_data.network_types", ng_disabled="fn.has_master_network(edit_obj)", chosen=True),
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
                "Base data",
                Field("description", wrapper_class="ng-class:form_error('description')", placeholder="Description"),
                Field("identifier", ng_options="key as value for (key, value) in settings.network_types", chosen=True),
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
                "Base data",
                Field("identifier", wrapper_class="ng-class:form_error('identifier')", placeholder="Identifier"),
                Field("description", wrapper_class="ng-class:form_error('description')", placeholder="Description"),
                Field("name_re", wrapper_class="ng-class:form_error('name_re')", placeholder="Regular expression"),
                Field("mac_bytes", placeholder="MAC bytes", min=6, max=24),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    class Meta:
        model = network_device_type
        fields = ("identifier", "description", "mac_bytes", "name_re",)

class partition_table_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_partition_form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        Div(
            HTML("<h3>Partition table '{% verbatim %}{{ edit_obj.name }}{% endverbatim %}'</h3>"),
            Fieldset(
                "Base data",
                Div(
                    Div(
                        Field("name", wrapper_class="ng-class:cur_edit.form_error('name')", placeholder="Name"),
                        css_class="col-md-6",
                    ),
                    Div(
                        Field("description", wrapper_class="ng-class:cur_edit.form_error('description')", placeholder="Description"),
                        css_class="col-md-6",
                    ),
                    css_class="row",
                ),
            ),
            Fieldset(
                "Flags",
                Div(
                    Div(
                        Field("enabled"),
                        css_class="col-md-4",
                    ),
                    Div(
                        Field("nodeboot"),
                        css_class="col-md-4",
                    ),
                    Div(
                        Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
                        css_class="col-md-4",
                    ),
                    css_class="row",
                ),
            ),
            Fieldset(
                "Detailed partition layout",
                HTML('<div disklayout ng-if="modal_active && !settings.use_modal">'),
            ),
        )
    )
    class Meta:
        model = partition_table
        fields = ["name", "description", "enabled", "nodeboot", ]

class partition_disc_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_partition_disc_form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        Div(
            HTML("<h2>Disc '{% verbatim %}{{ _edit_obj.disc }}{% endverbatim %}'</h2>"),
            Fieldset(
                "Base data",
                Field("disc", wrapper_class="ng-class:cur_edit.form_error('disc')", placeholder="discname"),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
            ),
        )
    )
    class Meta:
        model = partition_disc
        fields = ["disc"]

class partition_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_partition_form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        Div(
            HTML("<h2>Partition '{% verbatim %}{{ _edit_obj.pnum }}{% endverbatim %}'</h2>"),
            Fieldset(
                "Base data",
                Field("partition_disc", ng_options="value.idx as value.disc for value in edit_obj.partition_disc_set | orderBy:'disc'", chosen=True, readonly=True),
                Field("pnum", placeholder="partition", min=1, max=16),
                Field("partition_fs", ng_options="value.idx as value.full_info for value in this.get_partition_fs() | orderBy:'name'", chosen=True),
                Field("size", min=0, max=1000000000000),
                Field("partition_hex", readonly=True),
            ),
            Fieldset(
                "Mount options",
                Field("mountpoint"),
                Field("mount_options"),
                Field("bootable"),
                Field("fs_freq", min=0, max=1),
                Field("fs_passno", min=0, max=2),
            ),
            Fieldset(
                "Check thresholds",
                Field("warn_threshold", min=0, max=100),
                Field("crit_threshold", min=0, max=100),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
            ),
        )
    )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["partition_fs", "partition_disc"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
    class Meta:
        model = partition
        fields = ["mountpoint", "partition_hex", "partition_disc", "size", "mount_options", "pnum",
            "bootable", "fs_freq", "fs_passno", "warn_threshold", "crit_threshold", "partition_fs"]

class partition_sys_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_partition_sys_form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        Div(
            HTML("<h2>Sys Partition '{% verbatim %}{{ _edit_obj.name }}{% endverbatim %}'</h2>"),
            Fieldset(
                "Base data",
                Field("name"),
            ),
            Fieldset(
                "Mount options",
                Field("mountpoint"),
                Field("mount_options"),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
            ),
        )
    )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
    class Meta:
        model = sys_partition
        fields = ["name", "mountpoint", "mount_options"]

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
                "Base data",
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
                "Base data",
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
                "Base data",
                Field("user", ng_options="value.idx as value.login + ' (' + value.first_name + ' ' + value.last_name + ')' for value in rest_data.user | orderBy:'login'"),
                Field("notifications", ng_options="value.idx as value.name for value in rest_data.mon_notification | orderBy:'name'", chosen=True),
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
                    css_class="col-md-6",
                ),
                Div(
                    FormActions(
                        Field("snunknown"),
                        Field("sflapping"),
                        Field("splanned_downtime"),
                    ),
                    css_class="col-md-6",
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
                    css_class="col-md-6",
                ),
                Div(
                    FormActions(
                        Field("hflapping"),
                        Field("hplanned_downtime"),
                    ),
                    css_class="col-md-6",
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
                "Base data",
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
                Field("ninterval", min=0, max=60),
            ),
            Div(
                Div(
                    Field("nrecovery"),
                    Field("ncritical"),
                    css_class="col-md-4",
                ),
                Div(
                    Field("nwarning"),
                    Field("nunknown"),
                    css_class="col-md-4",
                ),
                Div(
                    Field("nflapping"),
                    Field("nplanned_downtime"),
                    css_class="col-md-4",
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
                    css_class="col-md-6",
                ),
                Div(
                    Field("flap_detect_critical"),
                    Field("flap_detect_unknown"),
                    css_class="col-md-6",
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
                "Base data",
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
                    css_class="col-md-4",
                ),
                Div(
                    Field("nwarning"),
                    Field("nunknown"),
                    css_class="col-md-4",
                ),
                Div(
                    Field("nflapping"),
                    Field("nplanned_downtime"),
                    css_class="col-md-4",
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
                "Base data",
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
                "Base data",
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
                "Base data",
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
                Field("not_period", ng_options="value.idx as value.name for value in rest_data.mon_period | orderBy:'name'"),
                Field("ninterval", min=0, max=60),
            ),
            Div(
                Div(
                    Field("nrecovery"),
                    Field("ndown"),
                    css_class="col-md-4",
                ),
                Div(
                    Field("nunreachable"),
                    css_class="col-md-4",
                ),
                Div(
                    Field("nflapping"),
                    Field("nplanned_downtime"),
                    css_class="col-md-4",
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
                    css_class="col-md-6",
                ),
                Div(
                    Field("flap_detect_unreachable"),
                    css_class="col-md-6",
                ),
                css_class="row",
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["mon_service_templ", "host_check_command", "mon_period", "not_period"]:
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
                "Base data",
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
                    css_class="col-md-4",
                ),
                Div(
                    Field("nunreachable"),
                    css_class="col-md-4",
                ),
                Div(
                    Field("nflapping"),
                    Field("nplanned_downtime"),
                    css_class="col-md-4",
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
                "Base data",
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
                "Base data",
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
        HTML("<h2>Host dependency template</h2>"),
            Fieldset(
                "Base data",
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
                        css_class="col-md-6",
                    ),
                    Div(
                        Field("efc_unreachable"),
                        Field("efc_pending"),
                        css_class="col-md-6",
                    ),
                    css_class="row",
                ),
            ),
            Fieldset(
                "Notification failure criteria",
                Div(
                    Div(
                        Field("nfc_up"),
                        Field("nfc_down"),
                        css_class="col-md-6",
                    ),
                    Div(
                        Field("nfc_unreachable"),
                        Field("nfc_pending"),
                        css_class="col-md-6",
                    ),
                    css_class="row",
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

class mon_host_dependency_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Host dependency</h2>"),
            Fieldset(
                "Basic settings",
                Field("mon_host_dependency_templ", ng_options="value.idx as value.name for value in rest_data.mon_host_dependency_templ | orderBy:'name'", chosen=True),
            ),
            Fieldset(
                "Parent",
                Field("devices", ng_options="value.idx as value.name for value in rest_data.device | orderBy:'name'", chosen=True),
            ),
            Fieldset(
                "Child",
                Field("dependent_devices", ng_options="value.idx as value.name for value in rest_data.device | orderBy:'name'", chosen=True),
            ),
            Fieldset(
                "Cluster",
                Field("mon_host_cluster", ng_options="value.idx as value.name for value in rest_data.mon_host_cluster | orderBy:'name'", chosen=True),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["devices", "dependent_devices", "mon_host_dependency_templ", "mon_host_cluster"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
    class Meta:
        model = mon_host_dependency

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
                "Base data",
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
                        css_class="col-md-6",
                    ),
                    Div(
                        Field("efc_critical"),
                        Field("efc_pending"),
                        css_class="col-md-6",
                    ),
                    css_class="row",
                ),
            ),
            Fieldset(
                "Notification failure criteria",
                Div(
                    Div(
                        Field("nfc_ok"),
                        Field("nfc_warn"),
                        Field("nfc_unknown"),
                        css_class="col-md-6",
                    ),
                    Div(
                        Field("nfc_critical"),
                        Field("nfc_pending"),
                        css_class="col-md-6",
                    ),
                    css_class="row",
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

class mon_service_dependency_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Service dependency</h2>"),
            Fieldset(
                "Basic settings",
                Field("mon_service_dependency_templ", ng_options="value.idx as value.name for value in rest_data.mon_service_dependency_templ | orderBy:'name'", chosen=True),
            ),
            Fieldset(
                "Parent",
                Field("devices", ng_options="value.idx as value.name for value in rest_data.device | orderBy:'name'", chosen=True),
                Field("mon_check_command", ng_options="value.idx as value.name for value in rest_data.mon_check_command | orderBy:'name'", chosen=True),
            ),
            Fieldset(
                "Child",
                Field("dependent_devices", ng_options="value.idx as value.name for value in rest_data.device | orderBy:'name'", chosen=True),
                Field("dependent_mon_check_command", ng_options="value.idx as value.name for value in rest_data.mon_check_command | orderBy:'name'", chosen=True),
            ),
            Fieldset(
                "Cluster",
                Field("mon_service_cluster", ng_options="value.idx as value.name for value in rest_data.mon_service_cluster | orderBy:'name'", chosen=True),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["devices", "dependent_devices", "mon_service_dependency_templ", "mon_service_cluster", "mon_check_command", "dependent_mon_check_command"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
    class Meta:
        model = mon_service_dependency

class package_search_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Package search</h2>"),
            Fieldset(
                "Base data",
                Field("search_string"),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    def __init__(self, *args, **kwargs):
        request = kwargs.pop("request")
        ModelForm.__init__(self, *args, **kwargs)
        self.fields["user"].initial = request.user
    class Meta:
        model = package_search

class package_action_form(Form):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    target_state = ChoiceField()
    nodeps_flag = ChoiceField()
    force_flag = ChoiceField()
    helper.layout = Layout(
        HTML("<h2>PDC action</h2>"),
            Fieldset(
                "Base data",
                Field("target_state", ng_options="key as value for (key, value) in target_states", initial="keep", chosen=True),
            ),
            Fieldset(
                "Flags",
                Field("nodeps_flag", ng_options="key as value for (key, value) in flag_states", initital="keep", chosen=True),
                Field("force_flag", ng_options="key as value for (key, value) in flag_states", initial="keep", chosen=True),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="submit"),
            ),
        )

class device_monitoring_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    md_cache_mode = ChoiceField()
    nagvis_parent = ModelChoiceField(queryset=empty_query_set(), required=False)
    helper.layout = Layout(
        HTML("<h2>Monitoring settings for {% verbatim %}{{ edit_obj.full_name }}{% endverbatim %}</h2>"),
            Fieldset(
                "Basic settings",
                Field("md_cache_mode", ng_options="value.idx as value.name for value in settings.md_cache_modes", initial=1),
                Field("mon_device_templ", ng_options="value.idx as value.name for value in rest_data.mon_device_templ", initial=None),
                Field("mon_ext_host", ng_options="value.idx as value.name for value in rest_data.mon_ext_host", initial=None, chosen=True),
                Field("monitor_server", ng_options="value.idx as value.full_name for value in rest_data.mon_server", initial=None, chosen=True),
            ),
            Fieldset(
                "Flags",
                Div(
                    Div(
                        Field("enable_perfdata"),
                        Field("flap_detection_enabled"),
                        css_class="col-md-6",
                    ),
                    Div(
                        Field("monitor_checks"),
                        Field("mon_resolve_name"),
                        css_class="col-md-6",
                    ),
                    css_class="row",
                ),
            ),
            Fieldset(
                "NagVis settings",
                Field("automap_root_nagvis"),
                Field("nagvis_parent", ng_options="value.idx as value.name for value in entries | filter:{'automap_root_nagvis' : true} | orderBy:'name'", initial=None),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
                Button("fetch", "Fetch disk layout", css_class="btn-warning", ng_click="settings.fn.fetch(this.edit_obj)"),
            ),
        )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["mon_device_templ", "nagvis_parent", "mon_ext_host", "monitor_server"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = "---"
    class Meta:
        model = device

class device_tree_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Device settings for {% verbatim %}{{ edit_obj.name }}{% endverbatim %}</h2>"),
            Fieldset(
                "Basic settings",
                Field("name"),
                Field("comment"),
                Field("device_type", ng_options="value.idx as value.description for value in rest_data.device_type | filter:ignore_md", chosen=True),
                Field("device_group", ng_options="value.idx as value.name for value in rest_data.device_group | filter:ignore_cdg", chosen=True),
            ),
            Fieldset(
                "Additional settings",
                Field("curl"),
                Field("domain_tree_node", ng_options="value.idx as value.tree_info for value in rest_data.domain_tree_node", chosen=True),
                Field("bootserver", ng_options="value.idx as value.full_name for value in rest_data.mother_server", chosen=True),
                Field("monitor_server", ng_options="value.idx as value.full_name for value in rest_data.monitor_server", chosen=True),
            ),
            Fieldset(
                "Flags",
                Div(
                    Div(
                        Field("enabled"),
                        css_class="col-md-6",
                    ),
                    Div(
                        css_class="col-md-6",
                    ),
                    css_class="row",
                ),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["device_type", "device_group", "domain_tree_node"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
    class Meta:
        model = device

class device_tree_many_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-8'
    helper.ng_model = "edit_obj"
    helper.ng_submit = "modify_many()"
    change_device_type = BooleanField(label="DeviceType", required=False)
    change_device_group = BooleanField(label="DeviceGroup", required=False)
    curl = CharField(label="Curl", required=False)
    change_curl = BooleanField(label="Curl", required=False)
    change_domain_tree_node = BooleanField(label="DTN", required=False)
    change_bootserver = BooleanField(label="Bootserver", required=False)
    change_monitor_server = BooleanField(label="MonitorServer", required=False)
    change_enabled = BooleanField(label="EnabledFlag", required=False)
    helper.layout = Layout(
        HTML("<h2>Change settings of {%verbatim %}{{ num_selected() }}{% endverbatim %} devices</h2>"),
    )
    for fs_string, el_list in [
        (
            "Basic settings", [
                ("device_type", "value.idx as value.description for value in rest_data.device_type | filter:ignore_md", {"chosen" : True}),
                ("device_group", "value.idx as value.name for value in rest_data.device_group | filter:ignore_cdg", {"chosen" : True}),
            ]
        ),
        (
            "Additional settings", [
                ("curl", None, {}),
                ("domain_tree_node", "value.idx as value.tree_info for value in rest_data.domain_tree_node", {"chosen" : True}),
                ("bootserver", "value.idx as value.full_name for value in rest_data.monitor_server", {"chosen" : True}),
                ("monitor_server", "value.idx as value.full_name for value in rest_data.mother_server", {"chosen" : True}),
            ]
        ),
        (
            "Flags", [
                ("enabled", None, {}),
            ]
        ),
        ]:
        helper.layout.append(
            Fieldset(
                fs_string,
                *[
                    Div(
                        Div(
                            Field("change_%s" % (f_name)),
                            css_class="col-md-2",
                        ),
                        Div(
                            Field(f_name, wrapper_ng_show="edit_obj.change_%s" % (f_name), ng_options=ng_options if ng_options else None, **f_options),
                            css_class="col-md-10",
                        ),
                        css_class="row",
                    ) for f_name, ng_options, f_options in el_list

                ]
            )
        )
    helper.layout.append(
        FormActions(
            Submit("submit", "Modify many", css_class="primaryAction"),
        ),
    )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["device_type", "device_group", "domain_tree_node"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
            self.fields[clear_f].required = False
    class Meta:
        model = device

class device_group_tree_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Settings for devicegroup {% verbatim %}{{ edit_obj.name }}{% endverbatim %}</h2>"),
            Fieldset(
                "Basic settings",
                Field("name"),
                Field("description"),
            ),
            Fieldset(
                "Additional settings",
                Field("domain_tree_node", ng_options="value.idx as value.tree_info for value in rest_data.domain_tree_node", chosen=True),
            ),
            Fieldset(
                "Flags",
                Div(
                    Div(
                        # disable enabled-flag for clusterdevicegroup
                        Field("enabled", ng_show="!edit_obj.cluster_device_group"),
                        css_class="col-md-6",
                    ),
                    Div(
                        css_class="col-md-6",
                    ),
                    css_class="row",
                ),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            ),
        )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["domain_tree_node"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
    class Meta:
        model = device_group

class device_variable_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        HTML("<h2>Device variable {% verbatim %}'{{ _edit_obj.name }}'{% endverbatim %}</h2>"),
            Fieldset(
                "Basic settings",
                Field("name"),
                Field("val_str", wrapper_ng_show="_edit_obj.var_type == 's'"),
                Field("val_int", wrapper_ng_show="_edit_obj.var_type == 'i'"),
                Field("val_date", wrapper_ng_show="_edit_obj.var_type == 'd'"),
                Field("val_time", wrapper_ng_show="_edit_obj.var_type == 't'"),
                Field("val_blob", wrapper_ng_show="_edit_obj.var_type == 'b'"),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
            ),
        )
    class Meta:
        model = device_variable

class device_variable_new_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        HTML("<h2>New device variable</h2>"),
            Fieldset(
                "Basic settings",
                Field("name", wrapper_class="ng-class:form_error('name')"),
                Field("val_str"),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
            ),
        )
    class Meta:
        model = device_variable

class config_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        HTML("<h2>Configuration '{% verbatim %}{{ _edit_obj.name }}{% endverbatim %}'</h2>"),
            Fieldset(
                "Basic settings",
                Field("name", wrapper_class="ng-class:form_error('name')"),
                Field("description"),
                Field("parent_config", ng_options="value.idx as value.name for value in this.get_valid_parents()", chosen=True),
            ),
            Fieldset(
                "other settings",
                Field("enabled"),
                Field("priority"),
            ),
            Fieldset(
                "Categories",
                HTML("<div category edit_obj='{% verbatim %}{{_edit_obj }}{% endverbatim %}' mode='conf'></div>"),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
            ),
        )
    class Meta:
        model = config
        fields = ("name", "description", "enabled", "priority", "parent_config",)

class config_str_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        HTML("<h2>String var '{% verbatim %}{{ _edit_obj.name }}{% endverbatim %}'</h2>"),
            Fieldset(
                "Basic settings",
                Field("name", wrapper_class="ng-class:form_error('name')"),
                Field("description"),
                Field("value"),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
            )
        )
    class Meta:
        model = config_str
        fields = ("name", "description", "value",)

class config_int_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        HTML("<h2>Integer var '{% verbatim %}{{ _edit_obj.name }}{% endverbatim %}'</h2>"),
            Fieldset(
                "Basic settings",
                Field("name", wrapper_class="ng-class:form_error('name')"),
                Field("description"),
                Field("value"),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
            )
        )
    class Meta:
        model = config_int
        fields = ("name", "description", "value",)

class config_bool_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        HTML("<h2>Bool var '{% verbatim %}{{ _edit_obj.name }}{% endverbatim %}'</h2>"),
            Fieldset(
                "Basic settings",
                Field("name", wrapper_class="ng-class:form_error('name')"),
                Field("description"),
                Field("value", min=0, max=1),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
            )
        )
    class Meta:
        model = config_bool
        fields = ("name", "description", "value",)

class config_script_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-9'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        HTML("<h2>Config script '{% verbatim %}{{ _edit_obj.name }}{% endverbatim %}'</h2>"),
            Fieldset(
                "Basic settings",
                Field("name", wrapper_class="ng-class:form_error('name')"),
                Field("description"),
            ),
            Fieldset(
                "Script",
                HTML("<textarea ui-codemirror='editorOptions' ng-model='_edit_obj.edit_value'></textarea>"), # Field("value"),
            ),
            Fieldset(
                "Flags",
                Div(
                    Div(
                        # disable enabled-flag for clusterdevicegroup
                        Field("priority"),
                        css_class="col-md-6",
                    ),
                    Div(
                        Field("enabled"),
                        css_class="col-md-6",
                    ),
                    css_class="row",
                ),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
            )
        )
    class Meta:
        model = config_script
        fields = ("name", "description", "priority", "enabled",)

class mon_check_command_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-9'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        HTML("<h2>Check command '{% verbatim %}{{ _edit_obj.name }}{% endverbatim %}'</h2>"),
            Fieldset(
                "Basic settings",
                Field("name", wrapper_class="ng-class:form_error('name')"),
                Field("description"),
                Field("command_line"),
            ),
            Fieldset(
                "Additional settings",
                Field("mon_service_templ", ng_options="value.idx as value.name for value in mon_service_templ", chosen=True),
                Field("event_handler", ng_options="value.idx as value.name for value in get_event_handlers(_edit_obj)", chosen=True, wrapper_ng_show="!_edit_obj.is_event_handler"),
            ),
            Fieldset(
                "Flags",
                Div(
                    Div(
                        # disable enabled-flag for clusterdevicegroup
                        Field("volatile"),
                        Field("enable_perfdata"),
                        css_class="col-md-6",
                    ),
                    Div(
                        Field("event_handler_enabled"),
                        Field("is_event_handler", wrapper_ng_show="_edit_obj.event_handler == undefined"),
                        css_class="col-md-6",
                    ),
                    css_class="row",
                ),
            ),
            Fieldset(
                "Categories",
                HTML("<div category edit_obj='{% verbatim %}{{_edit_obj }}{% endverbatim %}' mode='mon'></div>"),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
            )
        )
    def __init__(self, *args, **kwargs):
        ModelForm.__init__(self, *args, **kwargs)
        for clear_f in ["mon_service_templ", "event_handler"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = "----"
    class Meta:
        model = mon_check_command
        fields = ("name", "mon_service_templ", "command_line",
            "description", "enable_perfdata", "volatile", "is_event_handler",
            "event_handler", "event_handler_enabled",)

