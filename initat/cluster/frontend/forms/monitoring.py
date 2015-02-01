# -*- coding: utf-8 -*-

""" formulars for the NOCTUA / CORVUS webfrontend """

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Button, Fieldset, Div, HTML
from django.forms import ModelForm, CharField, ModelChoiceField, ChoiceField
from django.forms.widgets import Textarea
from django.utils.safestring import mark_safe
from initat.cluster.backbone.models import device, mon_check_command, mon_service_templ, mon_period, \
    mon_notification, mon_contact, host_check_command, mon_contactgroup, mon_device_templ, \
    mon_host_cluster, mon_service_cluster, mon_host_dependency_templ, mon_service_esc_templ, \
    mon_device_esc_templ, mon_service_dependency_templ, mon_service_dependency, mon_host_dependency, monitoring_hint
from initat.cluster.frontend.widgets import ui_select_widget, ui_select_multiple_widget


__all__ = [
    "mon_period_form",
    "mon_notification_form",
    "mon_contact_form",
    "mon_service_templ_form",
    "mon_service_esc_templ_form",
    "host_check_command_form",
    "mon_contact_form",
    "mon_contactgroup_form",
    "mon_device_templ_form",
    "mon_device_esc_templ_form",
    "mon_host_cluster_form",
    "mon_service_cluster_form",
    "mon_host_dependency_templ_form",
    "mon_host_dependency_form",
    "mon_service_dependency_templ_form",
    "mon_service_dependency_form",
    "device_monitoring_form",
    "mon_check_command_form",
    "monitoring_hint_form",
]


# empty query set
class empty_query_set(object):
    def all(self):
        raise StopIteration


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
    not_type = ChoiceField(
        [
            ("host", "Host"),
            ("service", "Service")
        ],
        label="Notification type"
    )
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
                repeat="value.idx as value in rest_data.user | orderBy:'login'",
                display="info",
                filter="{info:$select.search}",
                placeholder="please select an user",
            ),
            Field(
                "notifications",
                repeat="value.idx as value in rest_data.mon_notification | orderBy:'name'",
                placeholder="Select one or more notifications",
                display="name",
                filter="{name:$select.search}",
            ),
            Field("mon_alias"),
        ),
        Fieldset(
            "Service settings",
            Field(
                "snperiod",
                repeat="value.idx as value in rest_data.mon_period | orderBy:'name'",
                display="name",
                placeholder="please select a time period",
                filter="{name:$select.search}",
            ),
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
            Field(
                "hnperiod",
                repeat="value.idx as value in rest_data.mon_period | orderBy:'name'",
                display="name",
                placeholder="please select a time period",
                filter="{name:$select.search}",
            ),
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

    class Meta:
        model = mon_contact
        fields = [
            "user", "snperiod", "hnperiod", "notifications", "mon_alias",
            "snrecovery", "sncritical", "snwarning", "snunknown", "sflapping", "splanned_downtime",
            "hnrecovery", "hndown", "hnunreachable", "hflapping", "hplanned_downtime",
        ]
        widgets = {
            "notifications": ui_select_multiple_widget(),
            "user": ui_select_widget(),
            "snperiod": ui_select_widget(),
            "hnperiod": ui_select_widget(),
        }


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
            Field(
                "nsc_period",
                repeat="value.idx as value in rest_data.mon_period | orderBy:'name'",
                display="name",
                placeholder="please select a time period",
                filter="{name:$select.search}",
            ),
        ),
        FormActions(
            Field("max_attempts", min=1, max=10),
            Field("check_interval", min=1, max=60),
            Field("retry_interval", min=1, max=60),
        ),
        Fieldset(
            "Notification",
            Field(
                "nsn_period",
                repeat="value.idx as value in rest_data.mon_period | orderBy:'name'",
                display="name",
                placeholder="please select a time period",
                filter="{name:$select.search}",
            ),
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

    class Meta:
        model = mon_service_templ
        widgets = {
            "nsc_period": ui_select_widget(),
            "nsn_period": ui_select_widget(),
        }


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
            Field(
                "esc_period",
                repeat="value.idx as value in rest_data.mon_period | orderBy:'name'",
                display="name",
                placeholder="please select a time period",
                filter="{name:$select.search}",
            ),
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

    class Meta:
        model = mon_service_esc_templ
        widgets = {
            "esc_period": ui_select_widget(),
        }


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
            Field(
                "members",
                repeat="value.idx as value in rest_data.mon_contact | orderBy:'user_name'",
                display="user_name",
                placeholder="please select one or more users",
                filter="{user_name:$select.search}",
            ),
            Field(
                "device_groups",
                repeat="value.idx as value in rest_data.device_group | orderBy:'name'",
                display="name",
                placeholder="please select one or more device groups",
                filter="{name:$select.search}",
            ),
            Field(
                "service_templates",
                repeat="value.idx as value in rest_data.mon_service_templ | orderBy:'name'",
                display="name",
                placeholder="please select one or more service templates",
                filter="{name:$select.search}",
            ),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
        ),
    )

    class Meta:
        model = mon_contactgroup
        widgets = {
            "members": ui_select_multiple_widget(),
            "device_groups": ui_select_multiple_widget(),
            "service_templates": ui_select_multiple_widget(),
        }


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
            Field(
                "mon_service_templ",
                repeat="value.idx as value in rest_data.mon_service_templ | orderBy:'name'",
                display="name",
                placeholder="please select a service template",
                filter="{name:$select.search}",
            ),
        ),
        Fieldset(
            "Check",
            Field(
                "host_check_command",
                repeat="value.idx as value in rest_data.host_check_command | orderBy:'name'",
                display="name",
                placeholder="please select a host check command",
                filter="{name:$select.search}",
            ),
            Field(
                "mon_period",
                repeat="value.idx as value in rest_data.mon_period | orderBy:'name'",
                display="name",
                placeholder="please select a time period",
                filter="{name:$select.search}",
            ),
        ),
        FormActions(
            Field("check_interval", min=1, max=60),
            Field("retry_interval", min=1, max=60),
            Field("max_attempts", min=1, max=10),
        ),
        Fieldset(
            "Notification",
            Field(
                "not_period",
                repeat="value.idx as value in rest_data.mon_period | orderBy:'name'",
                display="name",
                placeholder="please select a time period",
                filter="{name:$select.search}",
            ),
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

    class Meta:
        model = mon_device_templ
        widgets = {
            "mon_service_templ": ui_select_widget(),
            "host_check_command": ui_select_widget(),
            "mon_period": ui_select_widget(),
            "not_period": ui_select_widget(),
        }


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
            Field(
                "mon_service_esc_templ",
                repeat="value.idx as value in rest_data.mon_service_esc_templ | orderBy:'name'",
                display="name",
                placeholder="please select a service escalation template",
                filter="{name:$select.search}",
            ),
        ),
        Fieldset(
            "Notifications",
            Field("first_notification", min=1, max=10),
            Field("last_notification", min=1, max=10),
            Field(
                "esc_period",
                repeat="value.idx as value in rest_data.mon_period | orderBy:'name'",
                display="name",
                placeholder="please select a time period",
                filter="{name:$select.search}",
            ),
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

    class Meta:
        model = mon_device_esc_templ
        widgets = {
            "mon_service_esc_templ": ui_select_widget(),
            "esc_period": ui_select_widget(),
        }


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
            Field(
                "main_device",
                repeat="value.idx as value in rest_data.device | orderBy:'name'",
                display="name",
                placeholder="please select a device",
                filter="{name:$select.search}",
            ),
            Field(
                "devices",
                repeat="value.idx as value in rest_data.device | orderBy:'name'",
                display="name",
                placeholder="please select one ore more devices",
                filter="{name:$select.search}",
            ),
        ),
        Fieldset(
            "Service",
            Field(
                "mon_service_templ",
                repeat="value.idx as value in rest_data.mon_service_templ | orderBy:'name'",
                display="name",
                placeholder="please select a service template",
                filter="{name:$select.search}",
            ),
            Field("warn_value", min=0, max=128),
            Field("error_value", min=0, max=128),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
        ),
    )

    class Meta:
        model = mon_host_cluster
        widgets = {
            "main_device": ui_select_widget(),
            "mon_service_templ": ui_select_widget(),
            "devices": ui_select_multiple_widget(),
        }


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
            Field(
                "main_device",
                repeat="value.idx as value in rest_data.device | orderBy:'name'",
                display="name",
                placeholder="please select a device",
                filter="{name:$select.search}",
            ),
            Field(
                "devices",
                repeat="value.idx as value in rest_data.device | orderBy:'name'",
                display="name",
                placeholder="please select one ore more devices",
                filter="{name:$select.search}",
            ),
        ),
        Fieldset(
            "Service",
            Field(
                "mon_service_templ",
                repeat="value.idx as value in rest_data.mon_service_templ | orderBy:'name'",
                display="name",
                placeholder="please select a service template",
                filter="{name:$select.search}",
            ),
            Field(
                "mon_check_command",
                repeat="value.idx as value in rest_data.mon_check_command | orderBy:'name'",
                display="name",
                placeholder="please select a check command",
                filter="{name:$select.search}",
            ),
            Field("warn_value", min=0, max=128),
            Field("error_value", min=0, max=128),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
        ),
    )

    class Meta:
        model = mon_service_cluster
        widgets = {
            "main_device": ui_select_widget(),
            "mon_service_templ": ui_select_widget(),
            "mon_check_command": ui_select_widget(),
            "devices": ui_select_multiple_widget(),
        }


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
            Field(
                "dependency_period",
                repeat="value.idx as value in rest_data.mon_period | orderBy:'name'",
                display="name",
                placeholder="please select a period",
                filter="{name:$select.search}",
            ),
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

    class Meta:
        model = mon_host_dependency_templ
        widgets = {
            "dependency_period": ui_select_widget(),
        }


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
                repeat="value.idx as value in rest_data.mon_host_dependency_templ | orderBy:'name'",
                display="name",
                placeholder="please select a host dependency template",
                filter="{name:$select.search}",
            ),
        ),
        Fieldset(
            "Parent",
            Field(
                "devices",
                repeat="value.idx as value in rest_data.device | orderBy:'name'",
                display="name",
                placeholder="please select one or more devices",
                filter="{name:$select.search}",
            ),
        ),
        Fieldset(
            "Child",
            Field(
                "dependent_devices",
                repeat="value.idx as value in rest_data.device | orderBy:'name'",
                display="name",
                placeholder="please select one or more devices",
                filter="{name:$select.search}",
            ),
        ),
        Fieldset(
            "Cluster",
            Field(
                "mon_host_cluster",
                repeat="value.idx as value in rest_data.mon_host_cluster | orderBy:'name'",
                display="name",
                placeholder="please select a host cluster",
                filter="{name:$select.search}",
            ),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
        ),
    )

    class Meta:
        model = mon_host_dependency
        widgets = {
            "mon_host_dependency_templ": ui_select_widget(),
            "devices": ui_select_multiple_widget(),
            "dependent_devices": ui_select_multiple_widget(),
            "mon_host_cluster": ui_select_widget(),
        }


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
            Field(
                "dependency_period",
                repeat="value.idx as value in rest_data.mon_period | orderBy:'name'",
                display="name",
                placeholder="please select a period",
                filter="{name:$select.search}",
            ),
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

    class Meta:
        model = mon_service_dependency_templ
        widgets = {
            "dependency_period": ui_select_widget(),
        }


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
                repeat="value.idx as value in rest_data.mon_service_dependency_templ | orderBy:'name'",
                display="name",
                placeholder="please select a service dependency template",
                filter="{name:$select.search}",
            ),
        ),
        Fieldset(
            "Parent",
            Field(
                "devices",
                repeat="value.idx as value in rest_data.device | orderBy:'name'",
                display="name",
                placeholder="please select one or more devices",
                filter="{name:$select.search}",
            ),
            Field(
                "mon_check_command",
                repeat="value.idx as value in rest_data.mon_check_command | orderBy:'name'",
                display="name",
                placeholder="please select a check command",
                filter="{name:$select.search}",
            ),
        ),
        Fieldset(
            "Child",
            Field(
                "dependent_devices",
                repeat="value.idx as value in rest_data.device | orderBy:'name'",
                display="name",
                placeholder="please select one or more devices",
                filter="{name:$select.search}",
            ),
            Field(
                "dependent_mon_check_command",
                repeat="value.idx as value in rest_data.mon_check_command | orderBy:'name'",
                display="name",
                placeholder="please select a check command",
                filter="{name:$select.search}",
            ),
        ),
        Fieldset(
            "Cluster",
            Field(
                "mon_service_cluster",
                repeat="value.idx as value in rest_data.mon_service_cluster | orderBy:'name'",
                display="name",
                placeholder="please select a service cluster",
                filter="{name:$select.search}",
            ),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
        ),
    )

    class Meta:
        model = mon_service_dependency
        widgets = {
            "mon_service_dependency_templ": ui_select_widget(),
            "devices": ui_select_multiple_widget(),
            "dependent_devices": ui_select_multiple_widget(),
            "mon_service_cluster": ui_select_widget(),
            "mon_check_command": ui_select_widget(),
            "dependent_mon_check_command": ui_select_widget(),
        }


class device_monitoring_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    md_cache_mode = ChoiceField(widget=ui_select_widget)
    nagvis_parent = ModelChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_widget)
    helper.layout = Layout(
        HTML("<h2>Monitoring settings for {% verbatim %}{{ edit_obj.full_name }}{% endverbatim %}</h2>"),
        Fieldset(
            "Basic settings",
            Field(
                "md_cache_mode",
                repeat="value.idx as value in settings.md_cache_modes",
                display="name",
                placeholder="please select a cache mode",
                filter="{name:$select.search}",
                initial=1,
            ),
            Field(
                "mon_device_templ",
                repeat="value.idx as value in rest_data.mon_device_templ",
                display="name",
                placeholder="please select a device template",
                filter="{name:$select.search}",
                null=True,
            ),
            Field(
                "mon_ext_host",
                repeat="value.idx as value in rest_data.mon_ext_host",
                display="name",
                placeholder="please select an icon",
                filter="{name:$select.search}",
                listtemplate=mark_safe("<img ng-src='{{ value.data_image }}'></img><span ng-bind-html='value.name | highlight:$select.search'></span>"),
                null=True,
            ),
            Field(
                "monitor_server",
                repeat="value.idx as value in rest_data.mon_server",
                display="name",
                placeholder="please select a monitoring server",
                filter="{name:$select.search}",
                null=True,
            ),
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
                repeat="value.idx as value in entries | orderBy:'name'",
                display="name",
                placeholder="select a nagvis parent",
                filter="{name:$select.search, automap_root_nagvis:true}",
                null=True,
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
        widgets = {
            "mon_device_templ": ui_select_widget(),
            "mon_ext_host": ui_select_widget(),
            "monitor_server": ui_select_widget(),
        }


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
        HTML("<tabset><tab heading='basic setup'>"),
        Fieldset(
            "Basic settings",
            Field("name", wrapper_class="ng-class:form_error('name')"),
            Field("description"),
            Field(
                "mon_check_command_special",
                repeat="value.idx as value in mccs_list",
                display="info",
                placeholder="please select a special command",
                filter="{name:$select.search}",
                null=True,
                wrapper_ng_show="_edit_obj.is_active",
            ),
            Field("command_line", wrapper_ng_show="!_edit_obj.mon_check_command_special && _edit_obj.is_active"),
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
<div class='form-group' ng-show="!_edit_obj.mon_check_command_special && _edit_obj.is_active">
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
<div class='form-group' ng-show="!_edit_obj.mon_check_command_special && _edit_obj.is_active">
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
            Field(
                "mon_service_templ",
                repeat="value.idx as value in mon_service_templ | orderBy:'name'",
                display="name",
                placeholder="please select a service template",
                filter="{name:$select.search}",
                null=True,
            ),
            Field(
                "event_handler",
                repeat="value.idx as value in get_event_handlers(_edit_obj)",
                display="name",
                placeholder="please select an event handler",
                filter="{name:$select.search}",
                null=True,
                wrapper_ng_show="!_edit_obj.is_event_handler"
            ),
        ),
        Fieldset(
            "Active / passive settings",
            Field("is_active"),
            HTML("""
<div class='form-group col-sm-12' ng-show="!_edit_obj.is_active">
    <b>Set result via</b>
</div>
<div class='form-group col-sm-12' ng-show="!_edit_obj.is_active">
    <tt>
    {% verbatim %}
    /opt/cluster/bin/set_passive_checkresult.py --device &lt;FQDN&gt; --check {{ _edit_obj.name }} --state {OK|WARN|CRITICAL} --output &lt;OUTPUT&gt;
    {% endverbatim %}
    </tt>
</div>
"""),
            ng_show="!_edit_obj.mon_check_command_special",
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
        HTML("</tab><tab heading='Categories ({% verbatim %}{{ num_cats }}{% endverbatim %})' ng-show='num_cats'>"),
        Fieldset(
            "Categories",
            HTML("""
<div category edit_obj='{% verbatim %}{{_edit_obj }}{% endverbatim %}' mode='mon'>
</div>
            """),
        ),
        HTML("</tab></tabset>"),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        )
    )

    class Meta:
        model = mon_check_command
        fields = (
            "name", "mon_service_templ", "command_line",
            "description", "enable_perfdata", "volatile", "is_event_handler",
            "event_handler", "event_handler_enabled", "mon_check_command_special",
            "is_active",
        )
        widgets = {
            "mon_check_command_special": ui_select_widget(),
            "mon_service_templ": ui_select_widget(),
            "event_handler": ui_select_widget(),
        }


class monitoring_hint_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-9'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        HTML("<h2>Monitoring hint '{% verbatim %}{{ _edit_obj.m_type }} / {{ _edit_obj.key }}{% endverbatim %}'</h2>"),
        HTML("{% verbatim %}{{ _edit_obj }}{% endverbatim %}"),
        Fieldset(
            "lower bounds",
            HTML("""
<div class="form-group">
    <label class="control-label col-sm-4">Lower Critical</label>
    <div class="controls col-sm-8">
        <input class="form-control" ng-model="_edit_obj.lower_crit_float" required="True" type="number" step="any" ng-show="_edit_obj.v_type == 'f'"></input>
        <input class="form-control" ng-model="_edit_obj.lower_crit_int" required="True" type="number" ng-show="_edit_obj.v_type == 'i'"></input>
    </div>
</div>
<div class="form-group">
    <label class="control-label col-sm-4">Lower Warning</label>
    <div class="controls col-sm-8">
        <input class="form-control" ng-model="_edit_obj.lower_warn_float" required="True" type="number" step="any" ng-show="_edit_obj.v_type == 'f'"></input>
        <input class="form-control" ng-model="_edit_obj.lower_warn_int" required="True" type="number" ng-show="_edit_obj.v_type == 'i'"></input>
    </div>
</div>
"""),
        ),
        Fieldset(
            "upper bounds",
            HTML("""
<div class="form-group">
    <label class="control-label col-sm-4">Upper Warning</label>
    <div class="controls col-sm-8">
        <input class="form-control" ng-model="_edit_obj.upper_warn_float" required="True" type="number" step="any" ng-show="_edit_obj.v_type == 'f'"></input>
        <input class="form-control" ng-model="_edit_obj.upper_warn_int" required="True" type="number" ng-show="_edit_obj.v_type == 'i'"></input>
    </div>
</div>
<div class="form-group">
    <label class="control-label col-sm-4">Upper Critial</label>
    <div class="controls col-sm-8">
        <input class="form-control" ng-model="_edit_obj.upper_crit_float" required="True" type="number" step="any" ng-show="_edit_obj.v_type == 'f'"></input>
        <input class="form-control" ng-model="_edit_obj.upper_crit_int" required="True" type="number" ng-show="_edit_obj.v_type == 'i'"></input>
    </div>
</div>
"""),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        )
    )

    class Meta:
        model = monitoring_hint
