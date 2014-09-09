# -*- coding: utf-8 -*-

""" formulars for the NOCTUA / CORVUS webfrontend """

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Button, Fieldset, Div, HTML, MultiField
from django.contrib.auth import authenticate
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.forms import Form, ModelForm, ValidationError, CharField, ModelChoiceField, \
    ModelMultipleChoiceField, ChoiceField, BooleanField
from django.forms.widgets import TextInput, PasswordInput, Textarea
from django.utils.translation import ugettext_lazy as _
from initat.cluster.backbone.models import domain_tree_node, device, category, mon_check_command, mon_service_templ, \
     domain_name_tree, user, group, device_group, home_export_list, device_config, TOP_LOCATIONS, \
     csw_permission, kernel, network, network_type, network_device_type, image, partition_table, \
     mon_period, mon_notification, mon_contact, mon_service_templ, host_check_command, \
     mon_contactgroup, mon_device_templ, mon_host_cluster, mon_service_cluster, mon_host_dependency_templ, \
     mon_service_esc_templ, mon_device_esc_templ, mon_service_dependency_templ, package_search, \
     mon_service_dependency, mon_host_dependency, package_device_connection, partition, \
     partition_disc, sys_partition, device_variable, config, config_str, config_int, config_bool, \
     config_script, netdevice, net_ip, peer_information, config_catalog, cd_connection, \
     cluster_setting, location_gfx

# empty query set


class empty_query_set(object):
    def all(self):
        raise StopIteration


class authentication_form(Form):
    username = CharField(
        label=_("Username"),
        max_length=30
    )
    password = CharField(
        label=_("Password"),
        widget=PasswordInput
    )
    helper = FormHelper()
    helper.form_id = "id_login_form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
    helper.layout = Layout(
        Div(
            Fieldset(
                "Please enter your login credentials {% if CLUSTER_NAME %} for {{ CLUSTER_NAME }}{% endif %}",
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
            all_aliases = [
                (login_name, al_list.strip().split()) for login_name, al_list in user.objects.all().values_list(
                    "login", "aliases"
                ) if al_list is not None and al_list.strip()
            ]
            rev_dict = {}
            all_logins = [login_name for login_name, al_list in all_aliases]
            for pk, al_list in all_aliases:
                for cur_al in al_list:
                    if cur_al in rev_dict:
                        raise ValidationError("Alias '{}' is not unique".format(cur_al))
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
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        Div(
            HTML("<h2>Domain tree node details for {% verbatim %}{{ _edit_obj.full_name }}{% endverbatim %}</h2>"),
            Fieldset(
                "Basic settings",
                Field("name"),
                Field("parent", ng_options="value.idx as value.tree_info for value in get_valid_parents(_edit_obj)", chosen=True),
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
                Button("delete", "delete", css_class="btn-danger", ng_click="delete_obj(_edit_obj)"),
            ),
        )
    )

    def __init__(self, *args, **kwargs):
        super(domain_tree_node_form, self).__init__(*args, **kwargs)
        for clear_f in ["parent"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None

    class Meta:
        model = domain_tree_node
        fields = ["name", "node_postfix", "create_short_names", "always_create_ip", "write_nameserver_config", "comment", "parent", ]


class device_boot_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "id_dtn_detail_form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-9'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    dhcp_mac = BooleanField(required=False, label="Greedy flag")
    dhcp_write = BooleanField(required=False, label="write DHCP address (when valid)")
    helper.layout = Layout(
        Div(
            HTML("<h2>Boot / DHCP settings for '{% verbatim %}{{ _edit_obj.name }}{% endverbatim %}'</h2>"),
            Fieldset(
                "DHCP settings",
                Field("dhcp_mac"),
                Field("dhcp_write"),
            ),
            FormActions(
                Submit("submit", "Modify", css_class="primaryAction"),
            )
        )
    )

    class Meta:
        model = device
        fields = ["dhcp_mac", "dhcp_write"]


class device_info_form(ModelForm):
    domain_tree_node = ModelChoiceField(domain_tree_node.objects.none(), empty_label=None)
    helper = FormHelper()
    helper.form_id = "id_dtn_detail_form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-9'
    helper.ng_model = "_edit_obj"
    helper.layout = Layout(
        Div(
            HTML(
                "<h2>Details for '{% verbatim %}{{ _edit_obj.name }}'&nbsp;"
                "<img ng-if='_edit_obj.mon_ext_host' ng-src='{{ get_image_src() }}' width='16'></img></h2>{% endverbatim %}"
            ),
            Fieldset(
                "Basic settings",
                Field("name"),
                Field("domain_tree_node", ng_options="value.idx as value.tree_info for value in domain_tree_node", chosen=True),
                # Field("domain_tree_node", ng_options="value.idx as value.tree_info for value in domain_tree_node", ui_select2=True),
                Field("comment"),
                Field("curl", wrapper_ng_show="is_device()"),
                HTML("""
<div class='form-group' ng-show="is_device()">
    <label class='control-label col-sm-3'>
        IP Info
    </label>
    <div class='col-sm-9'>
        {% verbatim %}{{ get_ip_info() }}{% endverbatim %}
    </div>
</div>
                """),
            ),
            # HTML("<ui-select ng-model='_edit_obj.domain_tree_node'><choices repeat='value in domain_tree_node'>dd</choices></ui-select>"),
            Fieldset(
                "Monitor settings",
                Field(
                    "mon_device_templ",
                    ng_options="value.idx as value.name for value in mon_device_templ_list",
                    chosen=True,
                    wrapper_ng_show="mon_device_templ_list"
                ),
                HTML("""
<div class='form-group' ng-show="is_device()">
    <label class='control-label col-sm-3'>
        Monitoring hints
    </label>
    <div class='col-sm-9'>
        {% verbatim %}{{ get_monitoring_hint_info() }}{% endverbatim %}
    </div>
</div>
                """),
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
                ng_show="is_device()",
            ),
            Fieldset(
                "RRD / graph settings",
                Field("store_rrd_data"),
                ng_show="is_device()",
            ),
            Fieldset(
                "Info",
                Div(
                    Div(
                        Button("uuid", "UUID info", css_class="btn-info", ng_click="toggle_uuid()"),
                        css_class="col-md-6",
                        ng_show="is_device()",
                    ),
                    Div(
                        Submit("modify", "modify", css_class="primaryAction", ng_show="acl_modify(_edit_obj, 'backbone.device.change_basic')"),
                        css_class="col-md-6",
                    ),
                    css_class="row",
                ),
            ),
        )
    )

    def __init__(self, *args, **kwargs):
        super(device_info_form, self).__init__(*args, **kwargs)
        for clear_f in ["domain_tree_node"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
        for clear_f in ["mon_device_templ"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = "---"

    class Meta:
        model = device
        fields = [
            "name", "comment", "monitor_checks", "domain_tree_node", "mon_device_templ",
            "enable_perfdata", "flap_detection_enabled", "mon_resolve_name", "curl",
            "store_rrd_data",
        ]


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
    password1 = CharField(
        label=_("New Password"),
        widget=PasswordInput
    )
    password2 = CharField(
        label=_("Confirm Password"),
        widget=PasswordInput
    )


class category_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        Div(
            HTML("<h2>Category details for '{% verbatim %}{{ _edit_obj.name }}{% endverbatim %}'</h2>"),
            Fieldset(
                "Basic settings",
                Field("name", wrapper_class="ng-class:form_error('name')"),
                Field("parent", ng_options="value.idx as value.full_name for value in get_valid_parents(_edit_obj)", chosen=True),
            ),
            Fieldset(
                "Additional fields",
                Field("comment"),
            ),
            Fieldset(
                "Positional data",
                Field("latitude", ng_pattern="/^\d+(\.\d+)*$/", wrapper_class="ng-class:form_error('latitude')"),
                Field("longitude", ng_pattern="/^\d+(\.\d+)*$/", wrapper_class="ng-class:form_error('longitude')"),
                Field("locked"),
                ng_if="is_location(_edit_obj)",
            ),
            FormActions(
                Submit("submit", "", css_class="btn-sm primaryAction", ng_value="get_action_string()"),
                HTML("&nbsp;"),
                Button("close", "close", css_class="btn-sm btn-warning", ng_click="close_modal()"),
                HTML("&nbsp;"),
                Button("delete", "delete", css_class="btn-sm btn-danger", ng_click="delete_obj(_edit_obj)", ng_show="!create_mode && !_edit_obj.num_refs"),
            ),
        )
    )

    def __init__(self, *args, **kwargs):
        super(category_form, self).__init__(*args, **kwargs)
        for clear_f in ["parent"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None

    class Meta:
        model = category
        fields = ["name", "comment", "parent", "longitude", "latitude", "locked"]


class location_gfx_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-9'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        Div(
            HTML("<h2>Location graphic '{% verbatim %}{{ _edit_obj.name }}{% endverbatim %}'</h2>"),
            Fieldset(
                "Basic settings",
                Field("name", wrapper_class="ng-class:form_error('name')"),
                Field("comment"),
            ),
            Fieldset(
                "Graphic",
                Field("locked"),
                HTML("""
<div class='form-group'>
    <label class='control-label col-sm-3'>
        Current Graphic
    </label>
    <div class='col-sm-6'>
        <input type="file" nv-file-select="" class="form-control" uploader="uploader"></input>
    </div>
    <div class='col-sm-3'>
        <input type="button" ng-show="uploader.queue.length "class="btn btn-warning btn-sm" value="upload" ng-click="uploader.uploadAll()"></input>
    </div>
</div>
                """),
                ng_if="!create_mode",
            ),
            FormActions(
                Submit("submit", "", css_class="btn-sm primaryAction", ng_value="get_action_string()"),
                HTML("&nbsp;"),
                Button("close", "close", css_class="btn-sm btn-warning", ng_click="close_modal()"),
            ),
        )
    )

    class Meta:
        model = location_gfx
        fields = ["name", "comment", "locked"]


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


class group_detail_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "group_edit.modify(this)"
    permission = ModelChoiceField(queryset=empty_query_set(), required=False)
    object = ModelChoiceField(queryset=empty_query_set(), required=False)
    permission_level = ModelChoiceField(queryset=empty_query_set(), required=False)
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
                    Field("email", placeholder="email address"),
                    Field("pager", placeholder="mobile number"),
                    Field("tel", placeholder="telefon number"),
                    Field("comment", placeholder="comment"),
                ),
                css_class="col-md-6",
            ),
            css_class="row",
        ),
        Fieldset(
            "Permissions",
            Field("parent_group", ng_options="value.idx as value.groupname for value in get_parent_group_list(_edit_obj)", chosen=True),
            Field("allowed_device_groups", ng_options="value.idx as value.name for value in valid_device_groups()", chosen=True),
            Field(
                "permission",
                wrapper_ng_show="!create_mode",
                ng_options="value.idx as value.info group by value.content_type.model for value in valid_group_csw_perms(_edit_obj)",
                chosen=True
            ),
            Field(
                "object",
                wrapper_ng_show="!create_mode && _edit_obj.permission",
                ng_options="value.idx as value.name group by value.group for value in object_list()",
                chosen=True
            ),
            Field(
                "permission_level",
                wrapper_ng_show="!create_mode",
                ng_options="value.level as value.info for value in ac_levels",
                chosen=True
            ),
            Button(
                "",
                "create global permission",
                css_class="btn btn-sm btn-success",
                ng_show="!create_mode && _edit_obj.permission",
                ng_click="create_permission()"
            ),
            HTML("&nbsp;"),
            Button(
                "",
                "create object permission",
                css_class="btn btn-sm btn-primary",
                ng_show="!create_mode && _edit_obj.permission && _edit_obj.object",
                ng_click="create_object_permission()"
            ),
            HTML("<div permissions ng_if='!create_mode'></div>"),
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
        super(group_detail_form, self).__init__(*args, **kwargs)
        self.fields["permission"].empty_label = "---"
        for clear_f in ["allowed_device_groups", "permission_level", "object"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
        for clear_f in ["parent_group"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = "---"

    class Meta:
        model = group
        fields = [
            "groupname", "gid", "active", "homestart",
            "email", "pager", "tel", "comment",
            "allowed_device_groups", "parent_group"
        ]


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
    permission = ModelChoiceField(queryset=empty_query_set(), required=False)
    object = ModelChoiceField(queryset=empty_query_set(), required=False)
    permission_level = ModelChoiceField(queryset=empty_query_set(), required=False)
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
                    Field("pager", placeholder="mobile number"),
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
            "Groups / export entry",
            Field("group", ng_options="value.idx as value.groupname for value in group_list", chosen=True),
            Field("secondary_groups", ng_options="value.idx as value.groupname for value in group_list", chosen=True),
            # do not use chosen here (will not refresh on export_list change)
            Field("export", ng_options="value.idx as get_home_info_string(value) for value in get_export_list()"),  # , chosen=True),
            HTML("""
<div class='form-group'>
    <label class='control-label col-sm-2'>
        Homedir status
    </label>
    <div class='col-sm-8'>
        {% verbatim %}<input
            type="button"
            ng-disabled="!_edit_obj.home_dir_created"
            ng-class="get_home_dir_created_class(_edit_obj)"
            ng-value="get_home_dir_created_value(_edit_obj)"
            ng-click="clear_home_dir_created(_edit_obj)"
            ></input>
        {% endverbatim %}
    </div>
</div>
            """),
        ),
        Fieldset(
            "Aliases",
            Field("aliases", rows=3),
        ),
        Fieldset(
            "Permissions",
            Field("allowed_device_groups", ng_options="value.idx as value.name for value in valid_device_groups()", chosen=True),
            Field(
                "permission",
                wrapper_ng_show="!create_mode",
                ng_options="value.idx as value.info group by value.content_type.model for value in valid_user_csw_perms()",
                chosen=True
            ),
            Field(
                "object",
                wrapper_ng_show="!create_mode && _edit_obj.permission",
                ng_options="value.idx as value.name group by value.group for value in object_list()",
                chosen=True
            ),
            Field("permission_level", wrapper_ng_show="!create_mode", ng_options="value.level as value.info for value in ac_levels", chosen=True),
            Button(
                "",
                "create global permission",
                css_class="btn btn-sm btn-success",
                ng_show="!create_mode && _edit_obj.permission",
                ng_click="create_permission()"
            ),
            HTML("&nbsp;"),
            Button(
                "",
                "create object permission",
                css_class="btn btn-sm btn-primary",
                ng_show="!create_mode && _edit_obj.permission && _edit_obj.object",
                ng_click="create_object_permission()"
            ),
            HTML("<div permissions ng_if='!create_mode'></div>"),
        ),
        FormActions(
            Submit("modify", "Modify", css_class="btn-success", ng_show="!create_mode"),
            Submit("create", "Create", css_class="btn-success", ng_show="create_mode", ng_disabled="!_edit_obj.password"),
            HTML("&nbsp;"),
            Button("close", "close", css_class="btn-primary", ng_click="user_edit.close_modal()", ng_show="!create_mode"),
            HTML("&nbsp;"),
            Button("delete", "delete", css_class="btn-danger", ng_click="user_edit.delete_obj(_edit_obj)", ng_show="!create_mode"),
            HTML("&nbsp;"),
            Button("change password", "change password", css_class="btn-warning", ng_click="change_password()", ng_show="!create_mode"),
            Button("set password", "set password", css_class="btn-warning", ng_click="change_password()", ng_show="create_mode && !_edit_obj.password"),
            Button("change password", "change password", css_class="btn-warning", ng_click="change_password()", ng_show="create_mode && _edit_obj.password"),
        ),
    )

    def __init__(self, *args, **kwargs):
        # request = kwargs.pop("request")
        super(user_detail_form, self).__init__(*args, **kwargs)
        self.fields["permission"].empty_label = "---"
        for clear_f in ["group", "secondary_groups", "allowed_device_groups", "permission_level", "object"]:
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
        fields = [
            "login", "uid", "shell", "first_name", "last_name", "active",
            "title", "email", "pager", "tel", "comment", "is_superuser",
            "allowed_device_groups", "secondary_groups",
            "aliases", "db_is_auth_for_password", "export", "group"
        ]


class global_settings_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
    helper.ng_model = "edit_obj"
    helper.ng_submit = "update_settings()"
    helper.layout = Layout(
        HTML("<h2>Global settings</h2>"),
        Fieldset(
            "Base data",
            Field("login_screen_type"),
        ),
        FormActions(
            Submit("submit", "Modify", css_class="primaryAction"),
        ),
    )

    class Meta:
        model = cluster_setting
        fields = ["login_screen_type", ]


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
        fields = [
            "shell", "first_name", "last_name",
            "title", "email", "pager", "tel", "comment",
        ]


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
            Field("comment", rows=5),
            Field("target_module_list", rows=3),
            Field("module_list", readonly=True, rows=3),
            ),
        HTML("""
<div class='form-group'>
    <label class='control-label col-sm-3'>
        initrd built
    </label>
    <div class='col-sm-7'>
        {% verbatim %}{{ fn.get_initrd_built(edit_obj) }}{% endverbatim %}
    </div>
</div>
        """),
        Div(
            FormActions(
                Field("enabled"),
            ),
        ),
        HTML("""
<div class='form-group'>
    <label class='control-label col-sm-6'>
        stage1 lo present
    </label>
    <div class='col-sm-6'>
        {% verbatim %}<input
            type="button"
            disabled="disabled"
            ng-class="edit_obj.stage1_lo_present && 'btn btn-sm btn-success' || 'btn btn-sm btn-danger'"
            ng-value="fn.get_flag_value(edit_obj, 'stage1_lo_present')"
            ></input>{% endverbatim %}
    </div>
</div>
<div class='form-group'>
    <label class='control-label col-sm-6'>
        stage1 cpio present
    </label>
    <div class='col-sm-6'>
        {% verbatim %}<input
            type="button"
            disabled="disabled"
            ng-class="edit_obj.stage1_cpio_present && 'btn btn-sm btn-success' || 'btn btn-sm btn-danger'"
            ng-value="fn.get_flag_value(edit_obj, 'stage1_cpio_present')"
            ></input>{% endverbatim %}
    </div>
</div>
<div class='form-group'>
    <label class='control-label col-sm-6'>
        stage1 cramfs present
    </label>
    <div class='col-sm-6'>
        {% verbatim %}<input
            type="button"
            disabled="disabled"
            ng-class="edit_obj.stage1_cramfs_present && 'btn btn-sm btn-success' || 'btn btn-sm btn-danger'"
            ng-value="fn.get_flag_value(edit_obj, 'stage1_cramfs_present')"
            ></input>{% endverbatim %}
    </div>
</div>
<div class='form-group'>
    <label class='control-label col-sm-6'>
        stage2 present
    </label>
    <div class='col-sm-6'>
        {% verbatim %}<input
            type="button"
            disabled="disabled"
            ng-class="edit_obj.stage2_present && 'btn btn-sm btn-success' || 'btn btn-sm btn-danger'"
            ng-value="fn.get_flag_value(edit_obj, 'stage2_present')"
            ></input>{% endverbatim %}
    </div>
</div>
        """),
        FormActions(
            Submit("submit", "", ng_value="get_action_string()", css_class="primaryAction"),
        ),
    )

    class Meta:
        model = kernel
        fields = [
            "name", "comment", "enabled",
            "module_list", "target_module_list"
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
        fields = [
            "name", "enabled",
        ]


class network_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "edit_mixin.modify()"
    master_network = ModelChoiceField(queryset=empty_query_set(), empty_label="No master network", required=False)
    network_type = ModelChoiceField(queryset=empty_query_set(), empty_label=None)
    network_device_type = ModelMultipleChoiceField(queryset=empty_query_set(), required=False)
    helper.layout = Layout(
        HTML("<h2>Network</h2>"),
        Fieldset(
            "Base data",
            Field("identifier", wrapper_class="ng-class:edit_mixin.form_error('identifier')", placeholder="Identifier"),
            Field("network", wrapper_class="ng-class:edit_mixin.form_error('network')", ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Network"),
            Field("netmask", wrapper_class="ng-class:edit_mixin.form_error('netmask')", ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Netmask"),
            Field("broadcast", wrapper_class="ng-class:edit_mixin.form_error('broadcast')", ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Broadcast"),
            Field("gateway", wrapper_class="ng-class:edit_mixin.form_error('gateway')", ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Gateway"),
        ),
        Fieldset(
            "Additional settings",
            Field(
                "network_type",
                ng_options="value.idx as value.description for value in rest_data.network_types",
                ng_disabled="has_master_network(_edit_obj)",
                chosen=True
            ),
            Field(
                "master_network",
                ng_options="value.idx as value.identifier for value in get_production_networks(this)",
                wrapper_ng_show="is_slave_network(this, _edit_obj.network_type)",
                chosen=True
            ),
            Field(
                "network_device_type",
                ng_options="value.idx as value.identifier for value in rest_data.network_device_types",
                chosen=True
            ),
        ),
        Fieldset(
            "Flags and priority",  # {% verbatim %}{{ _edit_obj }}{% endverbatim %}",
            Field("enforce_unique_ips"),
            Field("gw_pri"),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        ),
    )

    class Meta:
        model = network
        fields = (
            "identifier", "network", "netmask", "broadcast", "gateway", "master_network",
            "network_type", "network_device_type", "enforce_unique_ips", "gw_pri",
        )


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
        Fieldset(
            "Flags",
            Field("allow_virtual_interfaces"),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
        ),
    )

    class Meta:
        model = network_device_type
        fields = ("identifier", "description", "mac_bytes", "name_re", "allow_virtual_interfaces",)


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
                        Submit("submit", "", css_class="primaryAction", ng_value="submit"),
                        css_class="col-md-4",
                    ),
                    css_class="row",
                ),
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
            Fieldset(
                "label type",
                Field("label_type", ng_options="value.label as value.info_string for value in valid_label_types()"),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
            ),
        )
    )

    class Meta:
        model = partition_disc
        fields = ["disc", "label_type"]


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
                Field(
                    "partition_disc",
                    ng_options="value.idx as value.disc for value in edit_obj.partition_disc_set | orderBy:'disc'",
                    chosen=True,
                    readonly=True
                ),
                Field("pnum", placeholder="partition", min=1, max=16),
                Field("partition_fs", ng_options="value.idx as value.full_info for value in this.get_partition_fs() | orderBy:'name'", chosen=True),
                Field("size", min=0, max=1000000000000),
                Field("partition_hex", readonly=True),
            ),
            Fieldset(
                "Partition flags",
                Field("bootable"),
            ),
            Fieldset(
                "Mount options",
                Field("mountpoint", wrapper_ng_show="partition_need_mountpoint(_edit_obj)"),
                Field("mount_options", wrapper_ng_show="partition_need_mountpoint(_edit_obj)"),
                Field("fs_freq", min=0, max=1, wrapper_ng_show="partition_need_mountpoint(_edit_obj)"),
                Field("fs_passno", min=0, max=2, wrapper_ng_show="partition_need_mountpoint(_edit_obj)"),
            ),
            Fieldset(
                "Check thresholds",
                Field("warn_threshold", min=0, max=100, wrapper_ng_show="partition_need_mountpoint(_edit_obj)"),
                Field("crit_threshold", min=0, max=100, wrapper_ng_show="partition_need_mountpoint(_edit_obj)"),
            ),
            FormActions(
                Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
            ),
        )
    )

    def __init__(self, *args, **kwargs):
        super(partition_form, self).__init__(*args, **kwargs)
        for clear_f in ["partition_fs", "partition_disc"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None

    class Meta:
        model = partition
        fields = [
            "mountpoint", "partition_hex", "partition_disc", "size", "mount_options", "pnum",
            "bootable", "fs_freq", "fs_passno", "warn_threshold", "crit_threshold", "partition_fs"
        ]


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
        super(partition_sys_form, self).__init__(*args, **kwargs)

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
        fields = [
            "name", "alias", "sun_range", "mon_range", "tue_range", "wed_range", "thu_range",
            "fri_range", "sat_range"
        ]


class mon_notification_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    channel = ChoiceField([("mail", "E-Mail"), ("sms", "SMS")])
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
            Field(
                "user",
                ng_options="value.idx as value.login + ' (' + value.first_name + ' ' + value.last_name + ')' for value in rest_data.user | orderBy:'login'"
            ),
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
        super(mon_contact_form, self).__init__(*args, **kwargs)
        for clear_f in ["user", "snperiod", "hnperiod", "notifications"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None

    class Meta:
        model = mon_contact
        fields = [
            "user", "snperiod", "hnperiod", "notifications", "mon_alias",
            "snrecovery", "sncritical", "snwarning", "snunknown", "sflapping", "splanned_downtime",
            "hnrecovery", "hndown", "hnunreachable", "hflapping", "hplanned_downtime",
        ]


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
            "Freshness settings",
            Field("check_freshness"),
            Field("freshness_threshold", wrapper_ng_show="edit_obj.check_freshness"),
        ),
        Fieldset(
            "Flap settings",
            Field("flap_detection_enabled"),
        ),
        FormActions(
            Field("low_flap_threshold", min=0, max=100, wrapper_ng_show="edit_obj.flap_detection_enabled"),
            Field("high_flap_threshold", min=0, max=100, wrapper_ng_show="edit_obj.flap_detection_enabled"),
        ),
        Div(
            Div(
                Field("flap_detect_ok", wrapper_ng_show="edit_obj.flap_detection_enabled"),
                Field("flap_detect_warn", wrapper_ng_show="edit_obj.flap_detection_enabled"),
                css_class="col-md-6",
            ),
            Div(
                Field("flap_detect_critical", wrapper_ng_show="edit_obj.flap_detection_enabled"),
                Field("flap_detect_unknown", wrapper_ng_show="edit_obj.flap_detection_enabled"),
                css_class="col-md-6",
            ),
            css_class="row",
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
        ),
    )

    def __init__(self, *args, **kwargs):
        super(mon_service_templ_form, self).__init__(*args, **kwargs)
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
        super(mon_service_esc_templ_form, self).__init__(*args, **kwargs)
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
        super(mon_contactgroup_form, self).__init__(*args, **kwargs)
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
            "Freshness settings",
            Field("check_freshness"),
            Field("freshness_threshold", wrapper_ng_show="edit_obj.check_freshness"),
        ),
        Fieldset(
            "Flap settings",
            Field("flap_detection_enabled"),
        ),
        FormActions(
            Field("low_flap_threshold", min=0, max=100, wrapper_ng_show="edit_obj.flap_detection_enabled"),
            Field("high_flap_threshold", min=0, max=100, wrapper_ng_show="edit_obj.flap_detection_enabled"),
        ),
        Div(
            Div(
                Field("flap_detect_up", wrapper_ng_show="edit_obj.flap_detection_enabled"),
                Field("flap_detect_down", wrapper_ng_show="edit_obj.flap_detection_enabled"),
                css_class="col-md-6",
            ),
            Div(
                Field("flap_detect_unreachable", wrapper_ng_show="edit_obj.flap_detection_enabled"),
                css_class="col-md-6",
            ),
            css_class="row",
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
        ),
    )

    def __init__(self, *args, **kwargs):
        super(mon_device_templ_form, self).__init__(*args, **kwargs)
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
        super(mon_device_esc_templ_form, self).__init__(*args, **kwargs)
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
        super(mon_host_cluster_form, self).__init__(*args, **kwargs)
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
        super(mon_service_cluster_form, self).__init__(*args, **kwargs)
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
            Field("priority", min=-128, max=128),
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
        super(mon_host_dependency_templ_form, self).__init__(*args, **kwargs)
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
            Field(
                "mon_host_dependency_templ",
                ng_options="value.idx as value.name for value in rest_data.mon_host_dependency_templ | orderBy:'name'",
                chosen=True
            ),
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
        super(mon_host_dependency_form, self).__init__(*args, **kwargs)
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
            Field("priority", min=-128, max=128),
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
        super(mon_service_dependency_templ_form, self).__init__(*args, **kwargs)
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
            Field(
                "mon_service_dependency_templ",
                ng_options="value.idx as value.name for value in rest_data.mon_service_dependency_templ | orderBy:'name'",
                chosen=True
            ),
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
        super(mon_service_dependency_form, self).__init__(*args, **kwargs)
        for clear_f in [
            "devices", "dependent_devices", "mon_service_dependency_templ", "mon_service_cluster", "mon_check_command", "dependent_mon_check_command"
        ]:
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
        super(package_search_form, self).__init__(*args, **kwargs)
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
    target_state = ChoiceField(required=False)
    nodeps_flag = ChoiceField(required=False)
    force_flag = ChoiceField(required=False)
    image_dep = ChoiceField(required=False)
    image_change = BooleanField(label="change image list", required=False)
    image_list = ModelMultipleChoiceField(queryset=empty_query_set(), required=False)
    kernel_dep = ChoiceField(required=False)
    kernel_change = BooleanField(label="change kernel list", required=False)
    kernel_list = ModelMultipleChoiceField(queryset=empty_query_set(), required=False)
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
        Fieldset(
            "Image Dependency",
            Field("image_dep", ng_options="key as value for (key, value) in dep_states", initital="keep", chosen=True),
            Field("image_change"),
            Field(
                "image_list",
                ng_options="img.idx as img.name for img in image_list",
                initital="keep",
                chosen=True,
                wrapper_ng_show="edit_obj.image_change"
            ),
        ),
        Fieldset(
            "Kernel Dependency",
            Field("kernel_dep", ng_options="key as value for (key, value) in dep_states", initial="keep", chosen=True),
            Field("kernel_change"),
            Field(
                "kernel_list",
                ng_options="val.idx as val.name for val in kernel_list",
                initital="keep",
                chosen=True,
                wrapper_ng_show="edit_obj.kernel_change"
            ),
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
            Field(
                "nagvis_parent",
                ng_options="value.idx as value.name for value in entries | filter:{'automap_root_nagvis' : true} | orderBy:'name'",
                initial=None
            ),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
            Button("fetch", "Fetch disk layout", css_class="btn-warning", ng_click="settings.fn.fetch(this.edit_obj)"),
        ),
    )

    def __init__(self, *args, **kwargs):
        super(device_monitoring_form, self).__init__(*args, **kwargs)
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
    root_passwd = CharField(widget=PasswordInput, required=False)
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
            Field("monitor_server", ng_options="value.idx as value.full_name_wt for value in rest_data.monitor_server", chosen=True),
        ),
        Fieldset(
            "Security",
            Field("root_passwd"),
        ),
        Fieldset(
            "Flags",
            Div(
                Div(
                    Field("enabled"),
                    css_class="col-md-6",
                ),
                Div(
                    Field("store_rrd_data"),
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
        super(device_tree_form, self).__init__(*args, **kwargs)
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
    root_passwd = CharField(widget=PasswordInput, required=False)
    change_root_passwd = BooleanField(label="pwd", required=False)
    curl = CharField(label="Curl", required=False)
    change_curl = BooleanField(label="Curl", required=False)
    change_domain_tree_node = BooleanField(label="DTN", required=False)
    change_bootserver = BooleanField(label="Bootserver", required=False)
    change_monitor_server = BooleanField(label="MonitorServer", required=False)
    change_enabled = BooleanField(label="EnabledFlag", required=False)
    change_store_rrd_data = BooleanField(label="store RRD data", required=False)
    helper.layout = Layout(
        HTML("<h2>Change settings of {%verbatim %}{{ num_selected() }}{% endverbatim %} devices</h2>"),
    )
    for fs_string, el_list in [
        (
            "Basic settings", [
                ("device_type", "value.idx as value.description for value in rest_data.device_type | filter:ignore_md", {"chosen": True}),
                ("device_group", "value.idx as value.name for value in rest_data.device_group | filter:ignore_cdg", {"chosen": True}),
            ]
        ),
        (
            "Additional settings", [
                ("curl", None, {}),
                ("domain_tree_node", "value.idx as value.tree_info for value in rest_data.domain_tree_node", {"chosen": True}),
                ("bootserver", "value.idx as value.full_name for value in rest_data.mother_server", {"chosen": True}),
                ("monitor_server", "value.idx as value.full_name_wt for value in rest_data.monitor_server", {"chosen": True}),
            ]
        ),
        (
            "Security", [
                ("root_passwd", None, {}),
            ]
        ),
        (
            "Flags", [
                ("enabled", None, {}),
                ("store_rrd_data", None, {}),
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
        super(device_tree_many_form, self).__init__(*args, **kwargs)
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
        super(device_group_tree_form, self).__init__(*args, **kwargs)
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
    helper.field_class = 'col-sm-8'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    # var_type = ChoiceField(choices=[("i", "integer"), ("s", "string")])
    var_type = ChoiceField()
    helper.layout = Layout(
        HTML("<h2>New device variable {% verbatim %}'{{ _edit_obj.name }}'{% endverbatim %}</h2>"),
        Fieldset(
            "Monitoring variables",
            HTML("""
<div class='form-group'>
    <label class='control-label col-sm-3'>Copy</label>
    <div class='controls col-sm-8'>
        <select chosen="1" ng-model="_edit_obj._mon_copy" ng-options="entry.idx as entry.info for entry in mon_vars" ng-change="take_mon_var()"></select>
    </div>
</div>
            """),
            ng_show="_edit_obj.device && mon_vars.length",
        ),
        Fieldset(
            "Basic settings",
            Field("name", wrapper_class="ng-class:form_error('name')"),
            Field("var_type", chosen=True, ng_options="value.short as value.long for value in valid_var_types"),
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
            Field(
                "name",
                wrapper_class="ng-class:form_error('name')",
                typeahead="hint for hint in get_config_hints() | filter:$viewValue",
                typeahead_on_select="config_selected_vt($item, $model, $label)",
                typeahead_min_length=1,
            ),
            Field("description"),
            Field(
                "parent_config",
                ng_options="value.idx as value.name for value in this.get_valid_parents()",
                chosen=True,
                wrapper_ng_show="!_edit_obj.system_config && !_edit_obj.server_config"
            ),
        ),
        HTML(
            "<div ng-bind-html='show_config_help()'></div>",
        ),
        Fieldset(
            "other settings",
            Field("enabled"),
            Field("priority"),
            Field("server_config", wrapper_ng_show="!_edit_obj.system_config && !_edit_obj.parent_config"),
        ),
        Fieldset(
            "Categories",
            Field("config_catalog", ng_options="value.idx as value.name for value in this.config_catalogs", chosen=True),
            HTML("<div category edit_obj='{% verbatim %}{{_edit_obj }}{% endverbatim %}' mode='conf'></div>"),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        ),
    )

    def __init__(self, *args, **kwargs):
        super(config_form, self).__init__(*args, **kwargs)
        for clear_f in ["config_catalog"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None

    class Meta:
        model = config
        fields = ("name", "description", "enabled", "priority", "parent_config", "config_catalog", "server_config",)


class config_catalog_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        HTML("<h2>Config catalog '{% verbatim %}{{ _edit_obj.name }}{% endverbatim %}'</h2>"),
        Fieldset(
            "Basic settings",
            Field("name", wrapper_class="ng-class:form_error('name')"),
            Field("author"),
            Field("url"),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        ),
    )

    class Meta:
        model = config_catalog
        fields = ("name", "author", "url",)


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
            Field("name", wrapper_class="ng-class:form_error('name')", typeahead="hint for hint in get_config_var_hints(_config) | filter:$viewValue"),
            Field("description"),
            Field("value"),
        ),
        HTML(
            "<div ng-bind-html='show_config_var_help()'></div>",
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
            Field("name", wrapper_class="ng-class:form_error('name')", typeahead="hint for hint in get_config_var_hints(_config) | filter:$viewValue"),
            Field("description"),
            Field("value"),
        ),
        HTML(
            "<div ng-bind-html='show_config_var_help()'></div>",
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
            Field("name", wrapper_class="ng-class:form_error('name')", typeahead="hint for hint in get_config_var_hints(_config) | filter:$viewValue"),
            Field("description"),
            HTML("""
<div class='form-group'>
    <label class='control-label col-sm-3'>Value</label>
    <div class='controls col-sm-7'>
        <input type='button'
            ng-class='_edit_obj.value && "btn btn-sm btn-success" || "btn btn-sm"'
            ng-click='_edit_obj.value = 1 - _edit_obj.value' ng-value='_edit_obj.value && "true" || "false"'>
        </input>
    </div>
</div>
            """),
            # Field("value", min=0, max=1),
        ),
        HTML(
            "<div ng-bind-html='show_config_var_help()'></div>",
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        )
    )

    class Meta:
        model = config_bool
        fields = ("name", "description",)


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
            HTML("<textarea ui-codemirror='editorOptions' ng-model='_edit_obj.edit_value'></textarea>"),  # Field("value"),
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
            Field("mon_check_command_special", ng_options="value.idx as value.name for value in mccs_list", chosen=True),
            Field("command_line", wrapper_ng_show="!_edit_obj.mon_check_command_special"),
            HTML("""
<div class='form-group' ng-show="_edit_obj.mon_check_command_special">
    <label class="control-label col-sm-2">Info</label>
    <div class="col-sm-9 list-group">
        {% verbatim %}
        <ul>
            <li class="list-group-item">{{ get_mccs_info() }}</li>
            <li class="list-group-item">{{ get_mccs_cmdline() }}</li>
        </ul>
        {% endverbatim %}
    </div>
</div>
            """),
            HTML("""
<div class='form-group' ng-show="!_edit_obj.mon_check_command_special">
    <label class='control-label col-sm-2'>Tools</label>
    <div class='controls col-sm-9'>
        <div class="form-inline">
        <input type='button' ng-class='"btn btn-sm btn-primary"' ng-click='add_argument()' ng-value='"add argument"'>
        </input>
        name:
        <input type='text' class="form-control input-sm" title="default value" ng-model="_edit_obj.arg_name"></input>
        value:
        <input type='text' class="form-control input-sm" title="default value" ng-model="_edit_obj.arg_value"></input>
        </div>
    </div>
</div>
            """),
            HTML("""
<div class='form-group' ng-show="!_edit_obj.mon_check_command_special">
    <label class="control-label col-sm-2">Info</label>
    <div class="col-sm-9 list-group">
        <ul>
            <li class="list-group-item" ng-repeat="value in get_moncc_info()">{% verbatim %}{{ value }}{% endverbatim %}</li>
        </ul>
    </div>
</div>
            """),
        ),
        Fieldset(
            "Additional settings",
            Field("mon_service_templ", ng_options="value.idx as value.name for value in mon_service_templ", chosen=True),
            Field(
                "event_handler",
                ng_options="value.idx as value.name for value in get_event_handlers(_edit_obj)", chosen=True,
                wrapper_ng_show="!_edit_obj.is_event_handler"
            ),
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
            HTML("""
<div ng-mouseenter='show_cat_tree()' ng-mouseleave='hide_cat_tree()' category edit_obj='{% verbatim %}{{_edit_obj }}{% endverbatim %}' mode='mon'>
</div>
            """),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        )
    )

    def __init__(self, *args, **kwargs):
        super(mon_check_command_form, self).__init__(*args, **kwargs)
        for clear_f in ["mon_service_templ", "event_handler"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = "----"

    class Meta:
        model = mon_check_command
        fields = (
            "name", "mon_service_templ", "command_line",
            "description", "enable_perfdata", "volatile", "is_event_handler",
            "event_handler", "event_handler_enabled", "mon_check_command_special"
        )


class netdevice_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-8'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    ethtool_speed = ChoiceField(choices=[(0, "default"), (1, "10 MBit"), (2, "100 MBit"), (3, "1 GBit"), (4, "10 GBit")])
    ethtool_autoneg = ChoiceField(choices=[(0, "default"), (1, "on"), (2, "off")])
    ethtool_duplex = ChoiceField(choices=[(0, "default"), (1, "on"), (2, "off")])
    dhcp_device = BooleanField(required=False, label="force write DHCP address")
    show_ethtool = BooleanField(required=False)
    show_hardware = BooleanField(required=False)
    show_mac = BooleanField(required=False)
    show_vlan = BooleanField(required=False)
    routing = BooleanField(required=False, label="routing target")
    inter_device_routing = BooleanField(required=False)
    enabled = BooleanField(required=False)
    helper.layout = Layout(
        HTML("<h2>Netdevice '{% verbatim %}{{ _edit_obj.devname }}{% endverbatim %}'</h2>"),
        Fieldset(
            "Basic settings",
            Field("devname", wrapper_class="ng-class:form_error('devname')", placeholder="devicename"),
            Field("description"),
            Field("netdevice_speed", ng_options="value.idx as value.info_string for value in netdevice_speeds", chosen=True),
            Field("enabled"),
            Field(
                "is_bridge",
                wrapper_ng_show="!_edit_obj.vlan_id && !_edit_obj.bridge_device",
                ng_disabled="has_bridge_slaves(_edit_obj)",
            ),
            Field(
                "bridge_device",
                ng_options="value.idx as value.devname for value in get_bridge_masters(_edit_obj)",
                chosen=True,
                wrapper_ng_show="!_edit_obj.is_bridge && get_bridge_masters(_edit_obj).length",
            ),
        ),
        Fieldset(
            "Routing settings",
            Field("penalty", min=1, max=128),
            Field("routing"),
            Field("inter_device_routing"),
        ),
        Fieldset(
            "",
            Button(
                "show ethtool", "show ethtool", ng_click="_edit_obj.show_ethtool = !_edit_obj.show_ethtool",
                ng_class="_edit_obj.show_ethtool && 'btn btn-sm btn-success' || 'btn btn-sm'",
            ),
            Button(
                "show hardware", "show hardware", ng_click="_edit_obj.show_hardware = !_edit_obj.show_hardware",
                ng_class="_edit_obj.show_hardware && 'btn btn-sm btn-success' || 'btn btn-sm'",
            ),
            Button(
                "show vlan", "show vlan", ng_click="_edit_obj.show_vlan = !_edit_obj.show_vlan",
                ng_class="_edit_obj.show_vlan && 'btn btn-sm btn-success' || 'btn btn-sm'",
            ),
            Button(
                "show mac", "show mac", ng_click="_edit_obj.show_mac = !_edit_obj.show_mac",
                ng_class="_edit_obj.show_mac && 'btn btn-sm btn-success' || 'btn btn-sm'",
            ),
        ),
        Fieldset(
            "hardware settings",
            Field("driver"),
            Field("driver_options"),
            ng_show="_edit_obj.show_hardware",
        ),
        Fieldset(
            "ethtool settings (for cluster boot)",
            Field("ethtool_autoneg", ng_change="update_ethtool(_edit_obj)"),
            Field("ethtool_duplex", ng_change="update_ethtool(_edit_obj)"),
            Field("ethtool_speed", ng_change="update_ethtool(_edit_obj)"),
            ng_show="_edit_obj.show_ethtool",
        ),
        Fieldset(
            "MAC Address settings",
            Div(
                Div(
                    # disable enabled-flag for clusterdevicegroup
                    Field("macaddr"),
                    css_class="col-md-6",
                ),
                Div(
                    Field("fake_macaddr"),
                    css_class="col-md-6",
                ),
                css_class="row",
            ),
            Field("dhcp_device"),
            ng_show="_edit_obj.show_mac",
        ),
        Fieldset(
            "VLAN settings",
            Field("master_device", ng_options="value.idx as value.devname for value in get_vlan_masters(_edit_obj)", chosen=True),
            Field("vlan_id", min=0, max=255),
            ng_show="_edit_obj.show_vlan && !_edit_obj.is_bridge",
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        )
    )

    def __init__(self, *args, **kwargs):
        super(netdevice_form, self).__init__(*args, **kwargs)
        for clear_f in ["netdevice_speed"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
        for clear_f in ["master_device"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = "---"

    class Meta:
        model = netdevice
        fields = (
            "devname", "netdevice_speed", "description", "driver", "driver_options", "is_bridge",
            "macaddr", "fake_macaddr", "dhcp_device", "vlan_id", "master_device", "routing", "penalty",
            "bridge_device", "inter_device_routing", "enabled")


class net_ip_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-9'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    alias_excl = BooleanField(required=False)
    helper.layout = Layout(
        HTML("<h2>IP Address '{% verbatim %}{{ _edit_obj.ip }}{% endverbatim %}'</h2>"),
        Fieldset(
            "Basic settings",
            Field("netdevice", wrapper_ng_show="create_mode", ng_options="value.idx as value.devname for value in _current_dev.netdevice_set", chosen=True),
            Field("ip", wrapper_class="ng-class:form_error('devname')", placeholder="IP address"),
            Field("network", ng_options="value.idx as value.info_string for value in networks", chosen=True),
            Field("domain_tree_node", ng_options="value.idx as value.tree_info for value in domain_tree_node", chosen=True),
        ),
        Fieldset(
            "Alias settings (will be written without node postfixes)",
            Field("alias"),
            Field("alias_excl"),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        )
    )

    def __init__(self, *args, **kwargs):
        super(net_ip_form, self).__init__(*args, **kwargs)
        for clear_f in ["network", "domain_tree_node", "netdevice"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None

    class Meta:
        model = net_ip
        fields = ("ip", "network", "domain_tree_node", "alias", "alias_excl", "netdevice",)


class peer_information_s_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-9'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        HTML("<h2>Peer information from {% verbatim %}{{ get_peer_src_info() }}{% endverbatim %}</h2>"),
        Fieldset(
            "Settings",
            Field("penalty", min=1, max=128),
            Field("d_netdevice", wrapper_ng_show="create_mode", ng_options="value.idx as value.devname for value in _current_dev.netdevice_set", chosen=True),
            Field("s_netdevice", ng_options="value.idx as value.info_string group by value.device_group_name for value in get_route_peers()", chosen=True),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        )
    )

    def __init__(self, *args, **kwargs):
        super(peer_information_s_form, self).__init__(*args, **kwargs)
        for clear_f in ["s_netdevice", "d_netdevice"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
        self.fields["s_netdevice"].label = "Source"
        self.fields["d_netdevice"].label = "Destination"

    class Meta:
        model = peer_information
        fields = ("penalty", "s_netdevice", "d_netdevice")


class peer_information_d_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-9'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        HTML("<h2>Peer information from {% verbatim %}{{ get_peer_src_info() }}{% endverbatim %}</h2>"),
        Fieldset(
            "Settings",
            Field("penalty", min=1, max=128),
            Field("s_netdevice", wrapper_ng_show="create_mode", ng_options="value.idx as value.devname for value in _current_dev.netdevice_set", chosen=True),
            Field("d_netdevice", ng_options="value.idx as value.info_string group by value.device_group_name for value in get_route_peers()", chosen=True),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        )
    )

    def __init__(self, *args, **kwargs):
        super(peer_information_d_form, self).__init__(*args, **kwargs)
        for clear_f in ["s_netdevice", "d_netdevice"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
        self.fields["s_netdevice"].label = "Source"
        self.fields["d_netdevice"].label = "Destination"

    class Meta:
        model = peer_information
        fields = ("penalty", "s_netdevice", "d_netdevice",)


class cd_connection_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-4'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        HTML("<h2>Connection {% verbatim %}{{ get_cd_info() }}{% endverbatim %}</h2>"),
        Fieldset(
            "Settings",
            Field("connection_info"),
            Field("parameter_i1", min=0, max=256),
            Field("parameter_i2", min=0, max=256),
            Field("parameter_i3", min=0, max=256),
            Field("parameter_i4", min=0, max=256),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        )
    )

    class Meta:
        model = cd_connection
        fields = (
            "connection_info", "parameter_i1", "parameter_i2", "parameter_i3",
            "parameter_i4",
        )


class boot_form(Form):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-4'
    helper.field_class = 'col-sm-7'
    helper.ng_submit = "cur_edit.modify(this)"
    image = ModelMultipleChoiceField(queryset=empty_query_set(), required=False)
    helper.layout = Layout(
        HTML("<h2>Connection {% verbatim %}{{ get_cd_info() }}{% endverbatim %}</h2>"),
        Fieldset(
            "Settings",
            Field("image"),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        )
    )


class boot_single_form(Form):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-4'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    target_state = ModelChoiceField(queryset=empty_query_set(), required=False)
    new_kernel = ModelChoiceField(queryset=empty_query_set(), required=False)
    new_image = ModelChoiceField(queryset=empty_query_set(), required=False)
    stage1_flavour = ModelChoiceField(queryset=empty_query_set(), required=False)
    partition_table = ModelChoiceField(queryset=empty_query_set(), required=False)
    kernel_append = CharField(max_length=384, required=False)
    macaddr = CharField(max_length=177, required=False)
    driver = CharField(max_length=384, required=False)
    dhcp_mac = BooleanField(required=False, label="Greedy")
    dhcp_write = BooleanField(required=False)
    helper.layout = Layout(
        HTML("<h2>{% verbatim %}Device setting for {{ device_info_str }}{% endverbatim %}</h2>"),
        Fieldset(
            "basic settings",
            HTML("""
{% verbatim %}
<div ng-repeat="netstate in network_states" class='form-group' ng-show="bo_enabled['t']">
    <label class='control-label col-sm-4'>
        network {{ netstate.info }}
    </label>
    <div class='col-sm-7'>
        <select ng-model="_edit_obj.target_state" ng-options="value.idx as value.info for value in netstate.states" chosen="1"></select>
    </div>
</div>
<div class='form-group' ng-show="bo_enabled['t']">
    <label class='control-label col-sm-4'>
        special state
    </label>
    <div class='col-sm-7'>
        <select ng-model="_edit_obj.target_state" ng-options="value.idx as value.info for value in special_states" chosen="1"></select>
    </div>
</div>
{% endverbatim %}
            """),
            Field("new_kernel", ng_options="value.idx as value.name for value in kernels", chosen=True, wrapper_ng_show="bo_enabled['k']"),
            Field("stage1_flavour", ng_options="value.val as value.name for value in stage1_flavours", chosen=True, wrapper_ng_show="bo_enabled['k']"),
            Field("kernel_append", wrapper_ng_show="bo_enabled['k']"),
            Field("new_image", ng_options="value.idx as value.name for value in images", chosen=True, wrapper_ng_show="bo_enabled['i']"),
            Field("partition_table", ng_options="value.idx as value.name for value in partitions", chosen=True, wrapper_ng_show="bo_enabled['p']"),
        ),
        Fieldset(
            "bootdevice settings",
            Div(
                Div(
                    # disable enabled-flag for clusterdevicegroup
                    Field("dhcp_mac", wrapper_ng_show="bo_enabled['b']"),
                    css_class="col-md-6",
                ),
                Div(
                    Field("dhcp_write", wrapper_ng_show="bo_enabled['b']"),
                    css_class="col-md-6",
                ),
                css_class="row"
            ),
            Field("macaddr", wrapper_ng_show="bo_enabled['b'] && _edit_obj.bootnetdevice"),
            Field("driver", wrapper_ng_show="bo_enabled['b'] && _edit_obj.bootnetdevice"),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        )
    )

    def __init__(self, *args, **kwargs):
        super(boot_single_form, self).__init__(*args, **kwargs)
        for clear_f in ["target_state", "partition_table", "new_image", "new_kernel", "stage1_flavour"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = "not set"


class boot_many_form(Form):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-4'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    target_state = ModelChoiceField(queryset=empty_query_set(), required=False)
    new_kernel = ModelChoiceField(queryset=empty_query_set(), required=False)
    new_image = ModelChoiceField(queryset=empty_query_set(), required=False)
    stage1_flavour = ModelChoiceField(queryset=empty_query_set(), required=False)
    partition_table = ModelChoiceField(queryset=empty_query_set(), required=False)
    kernel_append = CharField(max_length=384, required=False)
    macaddr = CharField(max_length=177, required=False)
    driver = CharField(max_length=384, required=False)
    dhcp_mac = BooleanField(required=False, label="Greedy")
    dhcp_write = BooleanField(required=False)
    change_target_state = BooleanField(required=False, label="target state")
    change_new_kernel = BooleanField(required=False, label="kernel")
    change_new_image = BooleanField(required=False, label="image")
    change_partition_table = BooleanField(required=False, label="partition")
    change_dhcp_mac = BooleanField(required=False, label="bootdevice")
    helper.layout = Layout(
        HTML("<h2>Change boot settings of {%verbatim %}{{ device_info_str }}{% endverbatim %}</h2>"),
    )
    helper.layout.append(
        Fieldset(
            "target state",
            Div(
                Field(
                    "change_target_state",
                    wrapper_ng_show="bo_enabled['t']",
                ),
                css_class="col-md-3",
            ),
            HTML("""
{% verbatim %}
<div class="col-md-9">
<div ng-repeat="netstate in network_states" class='form-group' ng-show="bo_enabled['t'] && _edit_obj.change_target_state">
    <label class='control-label col-sm-4'>
        network {{ netstate.info }}
    </label>
    <div class='col-sm-7'>
        <select ng-model="_edit_obj.target_state" ng-options="value.idx as value.info for value in netstate.states" chosen="1"></select>
    </div>
</div>
<div class='form-group' ng-show="bo_enabled['t'] && _edit_obj.change_target_state">
    <label class='control-label col-sm-4'>
        special state
    </label>
    <div class='col-sm-7'>
        <select ng-model="_edit_obj.target_state" ng-options="value.idx as value.info for value in special_states" chosen="1"></select>
    </div>
</div>
</div>
{% endverbatim %}
            """),
            css_class="row",
        )
    )
    for fs_string, el_list in [
        (
            "settings", [
                # ("target_state", "value.idx as value.info for value in valid_states", {"chosen": True}, "t", "target_state"),
                ("new_kernel", "value.idx as value.name for value in kernels", {"chosen": True}, "k", "new_kernel"),
                ("stage1_flavour", "value.val as value.name for value in stage1_flavours", {"chosen": True}, "k", ""),
                ("kernel_append", None, {}, "k", ""),
                ("new_image", "value.idx as value.name for value in images", {"chosen": True}, "i", "new_image"),
                ("partition_table", "value.idx as value.name for value in partitions", {"chosen": True}, "p", "partition_table"),
                ("dhcp_mac", None, {}, "b", "dhcp_mac"),
                ("dhcp_write", None, {}, "b", ""),
                ("macaddr", None, {}, "b", ""),
                ("driver", None, {}, "b", ""),
            ]
        ),
    ]:
        helper.layout.append(
            Fieldset(
                fs_string,
                *[
                    Div(
                        Div(
                            Field(
                                "change_{}".format(en_field),
                                wrapper_ng_show="bo_enabled['{}']".format(en_flag),
                            ) if en_field else HTML(""),
                            css_class="col-md-3",
                        ),
                        Div(
                            Field(
                                f_name,
                                wrapper_ng_show="_edit_obj.change_{} && bo_enabled['{}']".format(
                                    {
                                        "k": "new_kernel",
                                        "i": "new_image",
                                        "p": "partition_table",
                                        "b": "dhcp_mac",
                                        "t": "target_state",
                                    }[en_flag],
                                    en_flag,
                                ),
                                ng_options=ng_options if ng_options else None,
                                **f_options),
                            css_class="col-md-9",
                        ),
                        css_class="row",
                    ) for f_name, ng_options, f_options, en_flag, en_field in el_list
                ]
            )
        )
    helper.layout.append(
        FormActions(
            Submit("submit", "Modify many", css_class="primaryAction"),
        ),
    )

    def __init__(self, *args, **kwargs):
        super(boot_many_form, self).__init__(*args, **kwargs)
        for clear_f in ["target_state", "partition_table", "new_image", "new_kernel", "stage1_flavour"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = "not set"
            self.fields[clear_f].required = False


class device_network_scan_form(Form):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    scan_address = CharField(max_length=128)
    strict_mode = BooleanField(required=False)
    helper.layout = Layout(
        HTML("<h2>Scan device</h2>"),
        Fieldset(
            "Base data",
            Field("scan_address"),
        ),
        Fieldset(
            "Flags",
            Field("strict_mode"),
        ),
        FormActions(
            Button("scan", "scan", css_class="btn btn-sm btn-primary", ng_click="fetch_device_network()"),
            Submit("cancel", "cancel", css_class="btn btn-sm btn-warning"),
        ),
    )


class create_device_form(Form):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    scan_address = CharField(max_length=128)
    strict_mode = BooleanField(required=False)
    helper.layout = Layout(
        HTML("<h2>Create new device</h2>"),
        Fieldset(
            "Base data",
            Field("scan_address"),
        ),
        Fieldset(
            "Flags",
            Field("strict_mode"),
        ),
        FormActions(
            Button("scan", "scan", css_class="btn btn-sm btn-primary", ng_click="fetch_device_network()"),
            Submit("cancel", "cancel", css_class="btn btn-sm btn-warning"),
        ),
    )
