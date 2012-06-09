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
