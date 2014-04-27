#!/usr/bin/python-init

from django.db import models
from django.db.models import Q, signals, get_model
from django.dispatch import receiver
from rest_framework import serializers

__all__ = [
    "config_hint", "config_hint_serializer",
    "config_var_hint", "config_var_hint_serializer",
]

class config_hint(object):
    idx = models.AutoField(primary_key=True)
    # config
    config_name = models.CharField(max_length=192, blank=False, unique=True)
    # short and long help text
    help_text_short = models.TextField(default="")
    help_text_long = models.TextField(default="")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = "backbone"

class config_var_hint(object):
    idx = models.AutoField(primary_key=True)
    # config hint
    config_hint = models.ForeignKey("backbone.config_hint")
    var_name = models.CharField(max_length=192, default="")
    # short and long help text
    help_text_short = models.TextField(default="")
    help_text_long = models.TextField(default="")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = "backbone"

class config_hint_serializer(serializers.ModelSerializer):
    class Meta:
        model = config_hint

class config_var_hint_serializer(serializers.ModelSerializer):
    class Meta:
        model = config_var_hint

