# -*- coding: utf-8 -*-

""" formulars for the NOCTUA / CORVUS webfrontend """

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Button, Fieldset, Div, HTML
from django.forms import ModelForm, CharField, ModelChoiceField, ChoiceField
from django.forms.widgets import Textarea
from initat.cluster.backbone.models import device, mon_check_command, mon_service_templ, mon_period, \
    mon_notification, mon_contact, host_check_command, mon_contactgroup, mon_device_templ, \
    mon_host_cluster, mon_service_cluster, mon_host_dependency_templ, mon_service_esc_templ, \
    mon_device_esc_templ, mon_service_dependency_templ, mon_service_dependency, mon_host_dependency


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
