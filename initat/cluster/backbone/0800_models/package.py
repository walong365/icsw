#!/usr/bin/python-init

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
from lxml import etree  # @UnresolvedImport
from lxml.builder import E  # @UnresolvedImport

__all__ = [
    "package_repo",
    "package_search",
    "package_search_result",
    "package",  # "package_serializer",
    "package_device_connection",  # "package_device_connection_serializer",
    "package_service",
]


class package_service(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(unique=True, max_length=128, blank=False)
    enabled = models.BooleanField(default=True)
    alias = models.CharField(max_length=128, default=True)
    autorefresh = models.BooleanField(default=True)
    url = models.CharField(max_length=256, default="")
    type = models.CharField(max_length=64, default="ris")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)
        app_label = "backbone"


# package related models
class package_repo(models.Model):
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=128, default="", unique=True)
    alias = models.CharField(max_length=128, default="")
    repo_type = models.CharField(max_length=128, default="")
    enabled = models.BooleanField(default=True)
    autorefresh = models.BooleanField(default=True)
    gpg_check = models.BooleanField(default=True)
    url = models.CharField(max_length=384, default="")
    created = models.DateTimeField(auto_now_add=True)
    service = models.ForeignKey(package_service, null=True, blank=True)
    publish_to_nodes = models.BooleanField(default=False, verbose_name="PublishFlag")
    priority = models.IntegerField(default=99)
    system_type = models.CharField(max_length=64, choices=[
        ("zypper", "zypper (suse)"),
        ("yum", "yum (redhat)"),
        ], default="zypper")
    # service = models.CharField(max_length=128, default="")

    class Meta:
        ordering = ("name",)
        app_label = "backbone"


class package_search(models.Model):
    idx = models.AutoField(primary_key=True)
    search_string = models.CharField(max_length=128, default="")
    # search string for latest search result
    last_search_string = models.CharField(max_length=128, default="", blank=True)
    user = models.ForeignKey("user")
    num_searches = models.IntegerField(default=0)
    # state diagramm ini (new) -> run -> done -> wait (search again pressed) -> run -> done -> ...
    current_state = models.CharField(
        max_length=6,
        choices=(
            ("ini", "initialised"),
            ("wait", "waiting"),
            ("run", "search running"),
            ("done", "search done")
        ),
        default="ini"
    )
    deleted = models.BooleanField(default=False)
    # number of results for the last search
    results = models.IntegerField(default=0)
    last_search = models.DateTimeField(null=True, auto_now_add=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        app_label = "backbone"
        ordering = ("search_string", "results",)


class package_search_result(models.Model):
    idx = models.AutoField(primary_key=True)
    package_search = models.ForeignKey(package_search)
    name = models.CharField(max_length=128, default="")
    kind = models.CharField(max_length=16, default="package", choices=(
        ("package", "Package"),
        ("patch", "Patch"),
    ))
    arch = models.CharField(max_length=32, default="")
    # version w. release
    version = models.CharField(max_length=128, default="")
    copied = models.BooleanField(default=False)
    package_repo = models.ForeignKey("backbone.package_repo", null=True)
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name", "arch", "version",)
        app_label = "backbone"


class package(models.Model):
    idx = models.AutoField(db_column="package_idx", primary_key=True)
    name = models.CharField(max_length=128)
    version = models.CharField(max_length=128)
    kind = models.CharField(max_length=16, default="package", choices=(
        ("package", "Package"),
        ("patch", "Patch"),
    ))
    always_latest = models.BooleanField(default=False)
    arch = models.CharField(max_length=32, default="")
    # hard to determine ...
    size = models.IntegerField(default=0)
    package_repo = models.ForeignKey("backbone.package_repo", null=True)
    target_repo = models.ForeignKey("backbone.package_repo", null=True, related_name="target_repo_package")
    created = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = u'package'
        unique_together = (("name", "version", "arch", "kind", "target_repo",),)
        app_label = "backbone"


class package_device_connection(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("backbone.device")
    package = models.ForeignKey("backbone.package")
    # target state

    target_state = models.CharField(max_length=8, choices=(
        ("keep", "keep"),
        ("install", "install"),
        ("upgrade", "upgrade"),
        ("erase", "erase")), default="keep")
    installed = models.CharField(max_length=8, choices=(
        ("u", "unknown"),
        ("y", "yes"),
        ("n", "no")), default="u")
    force_flag = models.BooleanField(default=False)
    nodeps_flag = models.BooleanField(default=False)
    created = models.DateTimeField(auto_now_add=True)
    response_type = models.CharField(max_length=16, choices=(
        ("zypper_xml", "zypper_xml"),
        ("yum_flat", "yum_flat"),
        ("unknown", "unknown"),
        ), default="zypper_xml")
    response_str = models.TextField(max_length=65535, default="")
    # install time of package
    install_time = models.IntegerField(default=0)
    # version / release information
    installed_name = models.CharField(max_length=255, default="")
    installed_version = models.CharField(max_length=255, default="")
    installed_release = models.CharField(max_length=255, default="")
    # dependencies
    image_dep = models.BooleanField(default=False)
    image_list = models.ManyToManyField("backbone.image", blank=True)
    kernel_dep = models.BooleanField(default=False)
    kernel_list = models.ManyToManyField("backbone.kernel", blank=True)
