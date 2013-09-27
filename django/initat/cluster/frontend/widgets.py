#!/usr/bin/python-init -Otu
""" widgets for django """

from django.db.models import Q
from django.forms import widgets
from django.forms.util import flatatt, to_current_timezone
from django.utils.encoding import smart_unicode, smart_text, force_text, python_2_unicode_compatible
from django.utils.html import conditional_escape, format_html, format_html_join
from django.utils.safestring import mark_safe

from initat.cluster.backbone.models import domain_name_tree, domain_tree_node
from itertools import chain
from lxml import etree # @UnresolvedImports
from lxml.builder import E # @UnresolvedImports

class domain_name_tree_widget(widgets.TextInput):
    def _iterate_tree(self, top_node):
        # cur_a = E.a(top_node.full_name or "[TLN]") # , href="#")
        r_list = [E.li(top_node.full_name or "[TLN]")]
        if top_node._sub_tree and top_node.depth < 2:
            sub_node = E.ul()
            # cur_a.append(sub_node)
            r_list[0].append(sub_node)
            for key in sorted(top_node._sub_tree.iterkeys()):
                for entry in top_node._sub_tree[key]:
                    sub_node.extend(self._iterate_tree(entry))
        return r_list
    def render(self, name, value, attrs=None):
        if value is None:
            value = ""
        print "***", name, value, attrs
        value = smart_unicode(value)
        final_attrs = self.build_attrs(attrs, name=name)
        cur_dtn = domain_tree_node.objects.get(Q(pk=value))
        return etree.tostring(E.input(value=cur_dtn.full_name, **final_attrs))
        print final_attrs
        # return "<input >"
        cur_tree = domain_name_tree()
        top_node = cur_tree.get_domain_tree_node("")[0]
        cur_s = E.div(id="dnt")
        top_ul = E.ul()
        cur_s.append(top_ul)
        top_ul.extend(self._iterate_tree(top_node))
        print etree.tostring(cur_s, pretty_print=True)
        return etree.tostring(cur_s, pretty_print=True)

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

