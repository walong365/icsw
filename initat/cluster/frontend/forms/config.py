# -*- coding: utf-8 -*-

""" formulars for the NOCTUA / CORVUS webfrontend """

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Fieldset, Div, HTML
from django.forms import ModelForm
from initat.cluster.backbone.models import config, config_str, config_int, config_bool, \
    config_script, config_catalog
from initat.cluster.frontend.widgets import ui_select_widget


__all__ = [
    "config_form",
    "config_catalog_form",
    "config_str_form",
    "config_int_form",
    "config_bool_form",
    "config_script_form",
]


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
                repeat="value.idx as value in this.get_valid_parents()",
                placeholder="select parent config",
                display="name",
                null=True,
                filter="{name:$select.search}",
                wrapper_ng_show="!_edit_obj.system_config && !_edit_obj.server_config",
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
            Field(
                "config_catalog",
                repeat="value.idx as value in this.config_catalogs",
                placeholder="select config catalog",
                display="name",
                filter="{name:$select.search}",
            ),
            HTML("<div icswConfigCategoryChoice edit_obj='{% verbatim %}{{_edit_obj }}{% endverbatim %}' mode='conf'></div>"),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        ),
    )

    class Meta:
        model = config
        fields = ("name", "description", "enabled", "priority", "parent_config", "config_catalog", "server_config",)
        widgets = {
            "parent_config": ui_select_widget(),
            "config_catalog": ui_select_widget(),
        }


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
