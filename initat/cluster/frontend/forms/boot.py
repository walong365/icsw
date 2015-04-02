# -*- coding: utf-8 -*-

""" formulars for the NOCTUA / CORVUS webfrontend """

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Fieldset, Div, HTML
from django.forms import Form, ModelForm, CharField, ModelChoiceField, \
    ModelMultipleChoiceField, BooleanField
from initat.cluster.backbone.models import device
from initat.cluster.frontend.widgets import ui_select_widget
from initat.cluster.frontend.forms.form_models import empty_query_set


__all__ = [
    "device_boot_form",
    "boot_form",
    "boot_single_form",
    "boot_many_form",
]


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
    new_kernel = ModelChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_widget)
    new_image = ModelChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_widget)
    stage1_flavour = ModelChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_widget)
    partition_table = ModelChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_widget)
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
        <ui-select ng-model="_edit_obj.target_state">
            <ui-select-match placeholder="target state">{{$select.selected.info}}</ui-select-match>
            <ui-select-choices repeat="value.idx as value in netstate.states">
                <div ng-bind-html='value.info'></div>
            </ui-select-choices>
        </ui-select>
    </div>
</div>
<div class='form-group' ng-show="bo_enabled['t']">
    <label class='control-label col-sm-4'>
        special state
    </label>
    <div class='col-sm-7'>
        <ui-select ng-model="_edit_obj.target_state">
            <ui-select-match placeholder="special target state">{{$select.selected.info}}</ui-select-match>
            <ui-select-choices repeat="value.idx as value in special_states">
                <div ng-bind-html='value.info'></div>
            </ui-select-choices>
        </ui-select>
    </div>
</div>
{% endverbatim %}
            """),
            Field(
                "new_kernel",
                repeat="value.idx as value in kernels",
                display="name",
                placeholder="kernel",
                filter="{name:$select.search}",
                wrapper_ng_show="bo_enabled['k']",
            ),
            Field(
                "stage1_flavour",
                repeat="value.val as value in stage1_flavours",
                display="name",
                placeholder="stage1 flavour",
                filter="{name:$select.search}",
                wrapper_ng_show="bo_enabled['k']",
            ),
            Field("kernel_append", wrapper_ng_show="bo_enabled['k']"),
            Field(
                "new_image",
                repeat="value.idx as value in images",
                display="name",
                placeholder="image",
                filter="{name:$select.search}",
                wrapper_ng_show="bo_enabled['i']",
            ),
            Field(
                "partition_table",
                repeat="value.idx as value in partitions",
                display="name",
                placeholder="partition table",
                filter="{name:$select.search}",
                wrapper_ng_show="bo_enabled['p']",
            ),
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


class boot_many_form(Form):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-4'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    target_state = ModelChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_widget)
    new_kernel = ModelChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_widget)
    new_image = ModelChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_widget)
    stage1_flavour = ModelChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_widget)
    partition_table = ModelChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_widget)
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
        <ui-select ng-model="_edit_obj.target_state">
            <ui-select-match placeholder="target state">{{$select.selected.info}}</ui-select-match>
            <ui-select-choices repeat="value.idx as value in netstate.states">
                <div ng-bind-html='value.info'></div>
            </ui-select-choices>
        </ui-select>
    </div>
</div>
<div class='form-group' ng-show="bo_enabled['t'] && _edit_obj.change_target_state">
    <label class='control-label col-sm-4'>
        special state
    </label>
    <div class='col-sm-7'>
        <ui-select ng-model="_edit_obj.target_state">
            <ui-select-match placeholder="special target state">{{$select.selected.info}}</ui-select-match>
            <ui-select-choices repeat="value.idx as value in special_states">
                <div ng-bind-html='value.info'></div>
            </ui-select-choices>
        </ui-select>
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
                (
                    "new_kernel",
                    {
                        "repeat": "value.idx as value in kernels",
                        "display": "name",
                        "placeholder": "kernel",
                        "filter": "{name:$select.search}",
                    },
                    "k",
                    "new_kernel"
                ),
                (
                    "stage1_flavour",
                    {
                        "repeat": "value.val as value in stage1_flavours",
                        "display": "name",
                        "placeholder": "stage1 flavour",
                        "filter": "{name:$select.search}",
                    },
                    "k",
                    ""
                ),
                ("kernel_append", {}, "k", ""),
                (
                    "new_image",
                    {
                        "repeat": "value.idx as value in images",
                        "display": "name",
                        "placeholder": "image",
                        "filter": "{name:$select.search}",
                    },
                    "i",
                    "new_image"
                ),
                (
                    "partition_table",
                    {
                        "repeat": "value.idx as value in partitions",
                        "display": "name",
                        "placeholder": "partition table",
                        "filter": "{name:$select.search}",
                    },
                    "p",
                    "partition_table"
                ),
                ("dhcp_mac", {}, "b", "dhcp_mac"),
                ("dhcp_write", {}, "b", ""),
                ("macaddr", {}, "b", ""),
                ("driver", {}, "b", ""),
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
                                **f_options),
                            css_class="col-md-9",
                        ),
                        css_class="row",
                    ) for f_name, f_options, en_flag, en_field in el_list
                ]
            )
        )
    helper.layout.append(
        FormActions(
            Submit("submit", "Modify many", css_class="primaryAction"),
        ),
    )
