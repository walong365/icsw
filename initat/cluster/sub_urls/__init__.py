#!/usr/bin/python-init -Otu

import sys
import os
from django.conf.urls import patterns, include, url
from django.conf import settings
import pprint

path_name = os.path.dirname(__file__)

sub_patterns = patterns("")

for entry in os.listdir(path_name):
    if entry.endswith(".py") and entry.count("url"):
        new_mod = __import__(entry.split(".")[0], globals(), locals())
        sub_patterns += new_mod.url_patterns
