# -*- coding: utf-8 -*-
""" extra tags and filters for django """

from django import template
from django.utils.safestring import mark_safe
from django.template.defaultfilters import stringfilter
import django.core.urlresolvers
import django.utils.http
import django.forms.forms
from django.db.models import Q
import datetime
import logging_tools
from django.conf import settings
from django.utils.functional import memoize
import lxml.etree

register = template.Library()

@register.filter(name="nl_to_br")
@stringfilter
def nl_to_br(value):
    return mark_safe(value.replace("\n", "<br>"))

@register.filter(name="to_nbsp")
@stringfilter
def to_nbsp(value):
    return mark_safe(value.replace(" ", "&nbsp;"))

@register.filter("validate_language_code")
def validate_language_code(lang_code):
    s_code = lang_code.split(".")[0].split("_")[0].split("-")[0]
    return s_code if s_code in ["en", "de", "it", "fr"] else "en"

@register.filter(name="first_character")
def first_character(cur_str):
    return cur_str[0] if cur_str else ""

@register.tag("render_rms_tag")
def render_rms_tag(parser, token):
    try:
        tag_name, cust_obj = token.split_contents()
    except:
        raise template.TemplateSyntaxError, "%r tag requires one argument" % (token.contents.split()[0])
    else:
        return rms_render_node(cust_obj)
    
class rms_render_node(template.Node):
    def __init__(self, cust_obj):
        self.cust_obj = template.Variable(cust_obj)
    def render(self, context):
        cust_obj = self.cust_obj.resolve(context)
        if cust_obj.tag in ["load"]:
            try:
                load = float(cust_obj.text)
            except:
                return cust_obj.text
            else:
                max_load = 16.
            load = min(load, max_load)
            return "<div style=\"float:left;\">%.2f</div>%s" % (
                load,
                "\n".join([
                    "<div style=\"width:100px ; height:10px; text-align:center; border:1px solid black; float:left;\">"
                    "<div style=\"width:%dpx ; height:10px; text-align:center; background-color:#ff4444;\"></div>" % (98 * load / max_load),
                    "</div>"]))
        else:
            return cust_obj.text
        