""" widgets for django """

import copy
from itertools import chain
import process_tools
import pprint
from django.conf import settings
from django.db.models import Q
from django.forms import widgets
from django.forms.models import ModelChoiceIterator
from django.forms.util import flatatt
from django.forms.widgets import CheckboxInput
from django.utils.datastructures import MultiValueDict, MergeDict
from django.utils.encoding import force_unicode, smart_unicode
from django.utils.safestring import mark_safe
from django.utils.translation import ugettext_lazy as _
from initat.cluster.backbone.models import domain_name_tree, domain_tree_node
from lxml import etree
from lxml.builder import E

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
