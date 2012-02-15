""" initcore tags and filters for django """
# -*- coding: utf-8 -*-

import datetime
import logging_tools
import codecs

from lxml.builder import E
from lxml import etree

import django.core.urlresolvers
import django.utils.http
import django.forms.forms

from django import template
from django.utils.safestring import mark_safe
from django.template.defaultfilters import stringfilter
from django.db.models import Q
from django.conf import settings
from django.utils.functional import memoize
from django.conf import settings

from initcore import menu_tools

register = template.Library()

@register.filter(name="nl_to_br")
@stringfilter
def nl_to_br(value):
    """ Convert a \n to <br> """
    return mark_safe(value.replace("\n", "<br>"))

@register.filter(name="to_nbsp")
@stringfilter
def to_nbsp(value):
    """ Convert a ' ' to &nbsp; """
    return mark_safe(value.replace(" ", "&nbsp;"))

@register.filter(name="relative_date")
def relative_date(value):
    if type(value) == datetime.datetime:
        value = logging_tools.get_relative_dt(value)
    return mark_safe(value)

@register.filter(name="getattr")
def getattribute(value, arg):
    if hasattr(value, str(arg)):
        return getattr(value, arg)
    elif hasattr(value, "has_key") and value.has_key(arg):
        return value[arg]
    else:
        return settings.TEMPLATE_STRING_IF_INVALID

@register.filter(name="in_list")
def is_in_list(value, arg):
    if type(arg) == type([]):
        return value in arg
    else:
        return False

@register.filter(name="lookup")
def lookup(in_dict, index):
    return in_dict[index] if index in in_dict else u""

@register.filter(name="get_flavour_list")
def get_flavour_list(docx_obj, flav_list):
    return docx_obj.get_flavour_list(flav_list)

@register.filter(name="get_unset_flavour_list")
def get_unset_flavour_list(docx_obj, flav_list):
    return docx_obj.get_unset_flavour_list(flav_list)

@register.filter(name="get_upload_list")
def get_upload_list(docx_obj, flavour):
    return docx_obj.get_upload_list(flavour)

@register.filter(name="get_doc_request")
def get_doc_request(order_obj, ref_id):
    return order_obj.get_doc_request(int(ref_id))

@register.filter(name="get_doc_request_a")
def get_doc_request_a(order_obj, ref_id):
    return order_obj.get_doc_request_a(int(ref_id))

@register.filter(name="get_doc_request_k")
def get_doc_request_k(order_obj, ref_id):
    return order_obj.get_doc_request_k(int(ref_id))

@register.filter(name="get_doc_request_m")
def get_doc_request_m(order_obj, ref_id):
    return order_obj.get_doc_request_m(int(ref_id))

@register.filter(name="get_doc_request_ac")
def get_doc_request_ac(order_obj, ref_id):
    return order_obj.get_doc_request_ac(int(ref_id))

@register.filter(name="get_doc_request_az")
def get_doc_request_az(order_obj, ref_id):
    return order_obj.get_doc_request_az(int(ref_id))

@register.filter(name="get_order_az_ids")
def get_order_az_ids(order_obj):
    return order_obj.get_order_az_ids()

@register.filter(name='class_name')
def class_name(ob):
    return ob.__class__.__name__

@register.tag("get_menu")
def get_menu(parser, token):
    return init_menu()

class init_menu(template.Node):
    def render(self, context):
        request = context["request"]
        is_mobile = request.session.get("is_mobile", False)
        return mark_safe(menu_tools.get_menu_html(request, is_mobile, False))

@register.filter(name="modulo")
def modulo(v, arg):
    return not bool(v % arg)    

@register.filter(name="divide")
def divide(v, arg):
    return v / int(arg)
