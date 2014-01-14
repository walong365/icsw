#!/usr/bin/python-init -Otu
""" widgets for django """

from django.forms import widgets
from django.forms.util import flatatt
from django.utils.encoding import smart_text, force_text
from django.utils.html import format_html
from django.utils.safestring import mark_safe

class device_tree_widget(widgets.SelectMultiple):
    def render_options(self, selected_choices):
        # Normalize to strings.
        selected_choices = set(force_text(v) for v in selected_choices)
        output = []
        cur_group_name = ""
        for option_value, (group_name, option_label) in self.choices:
            if group_name != cur_group_name:
                if cur_group_name:
                    output.append("</optgroup>")
                output.append(format_html('<optgroup label="{0}">', force_text(group_name)))
                cur_group_name = group_name
            output.append(self.render_option(selected_choices, option_value, option_label))
        if cur_group_name:
            output.append("</optgroup>")
        return output
    def render_option(self, selected_choices, option_value, option_label):
        option_value = force_text(option_value)
        if option_value in selected_choices:
            selected_html = mark_safe(' selected="selected"')
        else:
            selected_html = ""
        return format_html(
            u'<option value="{0}"{1}>{2}</option>',
                option_value,
                selected_html,
                smart_text(option_label)
        )
    def render(self, name, value, attrs=None):
        final_attrs = self.build_attrs(attrs, name=name)
        output = [format_html('<select multiple="multiple"{0}>', flatatt(final_attrs))]
        output.extend(self.render_options(value))
        output.append('</select>')
        return mark_safe('\n'.join(output))
