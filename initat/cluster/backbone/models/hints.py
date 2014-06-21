#!/usr/bin/python-init

from django.db import models
from django.db.models import Q, signals, get_model
from django.dispatch import receiver
from rest_framework import serializers

__all__ = [
    "config_hint", "config_hint_serializer",
    "config_var_hint", "config_var_hint_serializer",
    "config_script_hint", "config_script_hint_serializer",
]

class config_hint(models.Model):
    idx = models.AutoField(primary_key=True)
    # config
    config_name = models.CharField(max_length=192, blank=False, unique=True)
    config_description = models.CharField(max_length=192, default="")
    valid_for_meta = models.BooleanField(default=True)
    exact_match = models.BooleanField(default=True)
    # short and long help text
    help_text_short = models.TextField(default="")
    help_text_html = models.TextField(default="")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = "backbone"

class config_var_hint(models.Model):
    idx = models.AutoField(primary_key=True)
    # config hint
    config_hint = models.ForeignKey("backbone.config_hint")
    var_name = models.CharField(max_length=192, default="")
    # short and long help text
    help_text_short = models.TextField(default="")
    help_text_html = models.TextField(default="")
    # should the var be created automatically ?
    ac_flag = models.BooleanField(default=False)
    ac_type = models.CharField(default="str", max_length=64, choices=[
        ("str", "string var"),
        ("int", "int var"),
        ("bool", "bool var")])
    ac_description = models.CharField(default="description", max_length=128)
    # will be casted to int, bool
    ac_value = models.TextField(default="")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = "backbone"

class config_script_hint(models.Model):
    idx = models.AutoField(primary_key=True)
    # config hint
    config_hint = models.ForeignKey("backbone.config_hint")
    script_name = models.CharField(max_length=192, default="")
    # short and long help text
    help_text_short = models.TextField(default="")
    help_text_html = models.TextField(default="")
    # should the var be created automatically ?
    ac_flag = models.BooleanField(default=False)
    ac_description = models.CharField(default="description", max_length=128)
    # will be casted to int, bool
    ac_value = models.TextField(default="")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        app_label = "backbone"

class config_var_hint_serializer(serializers.ModelSerializer):
    class Meta:
        model = config_var_hint

class config_script_hint_serializer(serializers.ModelSerializer):
    class Meta:
        model = config_script_hint

class config_hint_serializer(serializers.ModelSerializer):
    config_var_hint_set = config_var_hint_serializer(many=True)
    config_script_hint_set = config_script_hint_serializer(many=True)
    class Meta:
        model = config_hint


