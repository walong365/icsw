# -*- coding: utf-8 -*-

""" formulars for the package installation """

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Fieldset, HTML
from django.forms import Form, ModelForm, ChoiceField, BooleanField
from initat.cluster.backbone.models import package_search
from initat.cluster.frontend.widgets import ui_select_widget, ui_select_multiple_widget


__all__ = [
    "package_search_form",
    "package_action_form",
]


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
    target_state = ChoiceField(required=False, widget=ui_select_widget)
    nodeps_flag = ChoiceField(required=False, widget=ui_select_widget)
    force_flag = ChoiceField(required=False, widget=ui_select_widget)
    image_dep = ChoiceField(required=False, widget=ui_select_widget)
    image_change = BooleanField(label="change image list", required=False)
    image_list = ChoiceField(required=False, widget=ui_select_multiple_widget)
    # ModelMultipleChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_multiple_widget)
    kernel_dep = ChoiceField(required=False, widget=ui_select_widget)
    kernel_change = BooleanField(label="change kernel list", required=False)
    kernel_list = ChoiceField(required=False, widget=ui_select_multiple_widget)
    # ModelMultipleChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_multiple_widget)
    helper.layout = Layout(
        HTML("<h2>PDC action</h2>"),
        Fieldset(
            "Base data",
            Field(
                "target_state",
                repeat="value.state as value in target_states",
                placeholder="select a target state",
                display="info",
            ),
        ),
        Fieldset(
            "Flags",
            Field(
                "nodeps_flag",
                repeat="value.idx as value in flag_states",
                placeholder="select the nodeps flag",
                display="info",
                null=True,
            ),
            Field(
                "force_flag",
                repeat="value.idx as value in flag_states",
                placeholder="select the force flag",
                display="info",
                null=True,
            ),
        ),
        Fieldset(
            "Image Dependency",
            Field(
                "image_dep",
                repeat="value.idx as value in dep_states",
                placeholder="select image dependency",
                display="info",
                null=True,
            ),
            Field("image_change"),
            Field(
                "image_list",
                repeat="value.idx as value in srv_image_list",
                placeholder="select one or more images",
                display="name",
                wrapper_ng_show="edit_obj.image_change",
            ),
        ),
        Fieldset(
            "Kernel Dependency",
            Field(
                "kernel_dep",
                repeat="value.idx as value in dep_states",
                placeholder="select kernel dependency",
                display="info",
                null=True,
            ),
            Field("kernel_change"),
            Field(
                "kernel_list",
                repeat="value.idx as value in srv_kernel_list",
                display="name",
                placeholder="select one or more kernels",
                wrapper_ng_show="edit_obj.kernel_change",
            ),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="submit"),
        ),
    )
