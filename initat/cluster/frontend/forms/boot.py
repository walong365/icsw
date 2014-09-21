# -*- coding: utf-8 -*-

""" formulars for the NOCTUA / CORVUS webfrontend """

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Fieldset, Div, HTML
from django.forms import Form, ModelForm, CharField, ModelChoiceField, \
    ModelMultipleChoiceField, BooleanField
from initat.cluster.backbone.models import device


__all__ = [
    "device_boot_form",
    "boot_form",
    "boot_single_form",
    "boot_many_form",
]


class empty_query_set(object):
    def all(self):
        raise StopIteration


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

