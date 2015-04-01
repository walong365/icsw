# -*- coding: utf-8 -*-

""" formulars for the NOCTUA / CORVUS webfrontend """

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Fieldset, Div, HTML
from django.forms import ModelForm
from initat.cluster.backbone.models import partition_table, partition, partition_disc, sys_partition
from initat.cluster.frontend.widgets import ui_select_widget


__all__ = [
    "partition_table_form",
    "partition_disc_form",
    "partition_form",
    "partition_sys_form",
]


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
                Field("label_type", ng_options="value.label as value.info_string for value in valid_label_types"),
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
                    repeat="value.idx as value in edit_obj.partition_disc_set | orderBy:'disc'",
                    placeholder="select the disc",
                    display="disc",
                    readonly=True,
                ),
                Field("pnum", placeholder="partition", min=1, max=16),
                Field(
                    "partition_fs",
                    repeat="value.idx as value in this.get_partition_fs() | orderBy:'name'",
                    placeholder="partition filesystem",
                    display="full_info",
                ),
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

    class Meta:
        model = partition
        fields = [
            "mountpoint", "partition_hex", "partition_disc", "size", "mount_options", "pnum",
            "bootable", "fs_freq", "fs_passno", "warn_threshold", "crit_threshold", "partition_fs"
        ]
        widgets = {
            "partition_disc": ui_select_widget(),
            "partition_fs": ui_select_widget(),
        }


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
