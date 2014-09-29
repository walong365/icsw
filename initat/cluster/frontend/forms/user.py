# -*- coding: utf-8 -*-

""" formulars for the NOCTUA / CORVUS webfrontend """

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Button, Fieldset, Div, HTML
from django.contrib.auth import authenticate
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.forms import Form, ModelForm, ValidationError, CharField, ModelChoiceField
from django.forms.widgets import TextInput, PasswordInput
from django.utils.translation import ugettext_lazy as _
from initat.cluster.backbone.models import user, group, home_export_list
from initat.cluster.frontend.widgets import ui_select_widget, ui_select_multiple_widget


__all__ = [
    "authentication_form",
    "group_detail_form",
    "user_detail_form",
    "account_detail_form",
    "dummy_password_form",
]


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
    next = CharField(required=False)
    helper.layout = Layout(
        Div(
            Fieldset(
                "Please enter your login credentials {% if CLUSTER_NAME %} for {{ CLUSTER_NAME }}{% endif %}",
                Field("username", placeholder="user name"),
                Field("password", placeholder="password"),
                Field("next", type="hidden"),
            ),
            FormActions(
                Submit("submit", "Submit", css_class="btn btn-primary"),
            ),
            css_class="form-horizontal",
        )
    )

    def __init__(self, request=None, *args, **kwargs):
        self.helper.form_action = reverse("session:login")
        _next = kwargs.pop("next", "")
        self.request = request
        self.user_cache = None
        super(authentication_form, self).__init__(*args, **kwargs)
        self.fields["next"].initial = _next

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
            _all_users = user.objects.all()  # @UndefinedVariable
            # get real user
            all_aliases = [
                (
                    login_name,
                    [_entry for _entry in al_list.strip().split() if _entry not in [None, "None"]]
                ) for login_name, al_list in _all_users.values_list(
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
        # TODO: determine whether this should be moved to its own method.
        if self.request:
            if not self.request.session.test_cookie_worked():
                raise ValidationError(_("Your Web browser doesn't appear to have cookies enabled. Cookies are required for logging in."))
        return self.cleaned_data

    def get_user(self):
        return self.user_cache

    def get_login_name(self):
        # FIXME
        return self.login_name


class group_detail_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-8'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "group_edit.modify(this)"
    permission = ModelChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_widget)
    object = ModelChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_widget)
    permission_level = ModelChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_widget)
    helper.layout = Layout(
        HTML("<h2>Details for group {% verbatim %}'{{ _edit_obj.groupname }}'{% endverbatim %}</h2>"),
        # tabset not implemented because of limitations in angular-chosen (replace with ui-select)
        # HTML("<tabset><tab heading='base data'>"),
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
        # HTML("</tab><tab heading='permissions'>"),
        Fieldset(
            "Permissions",
            Field(
                "parent_group",
                repeat="value.idx as value in parent_groups[_edit_obj.idx]",
                placeholder="Select a parent group",
                display="groupname",
                filter="{groupname:$select.search}",
                null=True,
                wrapper_ng_show="!create_mode",
            ),
            Field(
                "allowed_device_groups",
                repeat="value.idx as value in valid_device_groups()",
                # repeat="value.idx as value in valid_group_csw_perms(_edit_obj)",
                placeholder="Select one or more device groups",
                display="name",
                filter="{name:$select.search}",
            ),
            # HTML("{% verbatim %}{{ valid_device_groups() }}{% endverbatim %}"),
            Field(
                "permission",
                repeat="value.idx as value in valid_group_csw_perms(_edit_obj)",
                placeholder="Select a permission",
                display="info",
                groupby="'model_name'",
                filter="{info:$select.search}",
                null=True,
                wrapper_ng_show="!create_mode",
            ),
            Field(
                "object",
                wrapper_ng_show="!create_mode && _edit_obj.permission",
                repeat="value.idx as value in object_list()",
                placeholder="Select an object",
                display="name",
                groupby="'group'",
                filter="{name:$select.search}",
                null=True,
            ),
            Field(
                "permission_level",
                wrapper_ng_show="!create_mode",
                repeat="value.level as value in ac_levels",
                placeholder="Select a permission mode",
                display="info",
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
            HTML("<div class='col-sm-12'><div permissions ng_if='!create_mode' object='_edit_obj' type='group' action='true'></div></div>"),
        ),
        # HTML("</tab></tabset>"),
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

    class Meta:
        model = group
        fields = [
            "groupname", "gid", "active", "homestart",
            "email", "pager", "tel", "comment",
            "allowed_device_groups", "parent_group"
        ]
        widgets = {
            "parent_group": ui_select_widget(),
            "allowed_device_groups": ui_select_multiple_widget(),
        }


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
    permission = ModelChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_widget)
    object = ModelChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_widget)
    permission_level = ModelChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_widget)
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
            Field("group", ng_options="value.idx as value.groupname for value in group_list"),
            Field(
                "secondary_groups",
                repeat="value.idx as value in group_list",
                placeholder="Select secondary groups",
                display="groupname",
                filter="{groupname:$select.search}",
            ),
            # do not use ui-select here (will not refresh on export_list change)
            Field("export", wrapper_ng_show="!_edit_obj.only_webfrontend", ng_options="value.idx as get_home_info_string(value) for value in get_export_list()"),
            HTML("""
<div class='form-group' ng-show="!_edit_obj.only_webfrontend'>
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
            "Quota settings",
            HTML("""
<div class='form-group'>
    <div class='col-sm-12'>
        <quotasettings object='_edit_obj' type='user'></quotasettings>
    </div>
</div>
            """),
            ng_show="_edit_obj.user_quota_setting_set.length && !_edit_obj.only_webfrontend",
        ),
        Fieldset(
            "/home scan settings",
            HTML("""
<div class='form-group'>
    <label class='control-label col-sm-2'>Scan Home dir</label>
    <div class='controls col-sm-8'>
        <input type='button'
            ng-class='_edit_obj.scan_user_home && "btn btn-sm btn-success" || "btn btn-sm"'
            ng-click='_edit_obj.scan_user_home = !_edit_obj.scan_user_home' ng-value='_edit_obj.scan_user_home && "yes" || "no"'>
        </input>
    </div>
</div>
            """),
            Field("scan_depth", min=1, max=5, wrapper_ng_show="_edit_obj.scan_user_home"),
        ),
        Fieldset(
            "Permissions",
            Field(
                "allowed_device_groups",
                repeat="value.idx as value in valid_device_groups()",
                # repeat="value.idx as value in valid_group_csw_perms(_edit_obj)",
                placeholder="Select one or more device groups",
                display="name",
                filter="{name:$select.search}",
            ),
            Field(
                "permission",
                repeat="value.idx as value in valid_user_csw_perms()",
                placeholder="Select a permission",
                display="info",
                groupby="'model_name'",
                filter="{info:$select.search}",
                wrapper_ng_show="!create_mode",
                null=True,
            ),
            Field(
                "object",
                wrapper_ng_show="!create_mode && _edit_obj.permission",
                repeat="value.idx as value in object_list()",
                placeholder="Select an object",
                display="name",
                groupby="'group'",
                filter="{name:$select.search}",
                null=True,
            ),
            Field(
                "permission_level",
                wrapper_ng_show="!create_mode",
                repeat="value.level as value in ac_levels",
                placeholder="Select a permission mode",
                display="info",
            ),
            # Field(
            #    "permission",
            #    wrapper_ng_show="!create_mode",
            #    ng_options="value.idx as value.info group by value.content_type.model for value in valid_user_csw_perms()",
            # ),
            # Field(
            #    "object",
            #    wrapper_ng_show="!create_mode && _edit_obj.permission",
            #    ng_options="value.idx as value.name group by value.group for value in object_list()",
            # ),
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
            HTML("<div class='col-sm-12'><div permissions ng_if='!create_mode' object='_edit_obj' type='user' action='true'></div></div>"),
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
            "scan_depth",
            "aliases", "db_is_auth_for_password", "export", "group"
        ]
        widgets = {
            "secondary_groups": ui_select_multiple_widget(),
            "allowed_device_groups": ui_select_multiple_widget(),
        }


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
