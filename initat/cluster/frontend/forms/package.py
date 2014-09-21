# -*- coding: utf-8 -*-

""" formulars for the package installation """

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Fieldset, HTML
from django.forms import Form, ModelForm, ModelMultipleChoiceField, ChoiceField, BooleanField
from initat.cluster.backbone.models import package_search


__all__ = [
    "package_search_form",
    "package_action_form",
]


# empty query set
class empty_query_set(object):
    def all(self):
        raise StopIteration


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
