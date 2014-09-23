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
    domain_name_tree, device_group, home_export_list, device_config, TOP_LOCATIONS, \
    csw_permission, kernel, network, network_type, network_device_type, image, partition_table, \
    mon_period, mon_notification, mon_contact, host_check_command, \
    device_variable, config, config_str, config_int, config_bool, \
    config_script, netdevice, net_ip, peer_information, config_catalog, cd_connection, \
    cluster_setting, location_gfx

from initat.cluster.frontend.forms.boot import *
from initat.cluster.frontend.forms.config import *
from initat.cluster.frontend.forms.monitoring import *
from initat.cluster.frontend.forms.package import *
from initat.cluster.frontend.forms.partition import *
from initat.cluster.frontend.forms.user import *
from initat.cluster.frontend.forms.network import *


# empty query set
class empty_query_set(object):
    def all(self):
        raise StopIteration


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
                # Field("domain_tree_node", ng_options="value.idx as value.tree_info for value in domain_tree_node", ui_select=True),
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


class export_choice_field(ModelChoiceField):
    def reload(self):
        self.queryset = home_export_list()

    def label_from_instance(self, obj):
        return self.queryset.exp_dict[obj.pk]["info"]


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
