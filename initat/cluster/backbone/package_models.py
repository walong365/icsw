#!/usr/bin/python-init

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.db import models
from django.db.models import Q, signals, get_model
from django.dispatch import receiver
from django.forms import Textarea
from django.utils.functional import memoize
from initat.cluster.backbone.model_functions import _check_empty_string, _check_float, _check_integer, _check_non_empty_string, to_system_tz
from lxml import etree # @UnresolvedImport
from lxml.builder import E # @UnresolvedImport
from rest_framework import serializers

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
    publish_to_nodes = models.BooleanField(default=False, verbose_name="PublishFlag")
    def get_xml(self):
        return E.package_repo(
            unicode(self),
            pk="%d" % (self.pk),
            key="pr__%d" % (self.pk),
            name=self.name,
            alias=self.alias,
            repo_type=self.repo_type,
            enabled="1" if self.enabled else "0",
            autorefresh="1" if self.autorefresh else "0",
            gpg_check="1" if self.gpg_check else "0",
            publish_to_nodes="1" if self.publish_to_nodes else "0",
            url=self.url)
    def __unicode__(self):
        return self.name
    @property
    def distributable(self):
        is_d = False
        if self.publish_to_nodes:
            is_d = True if not self.url.startswith("dir:") else False
        return is_d
    def repo_str(self):
        return "\n".join([
            "[%s]" % (self.alias),
            "name=%s" % (self.name),
            "enabled=%d" % (1 if self.enabled else 0),
            "autorefresh=%d" % (1 if self.autorefresh else 0),
            "baseurl=%s" % (self.url),
            "type=%s" % (self.repo_type),
            "keeppackages=0",
            "",
        ])
    class Meta:
        ordering = ("name",)

class package_repo_serializer(serializers.ModelSerializer):
    class Meta:
        model = package_repo

class package_search(models.Model):
    idx = models.AutoField(primary_key=True)
    search_string = models.CharField(max_length=128, default="")
    # search string for latest search result
    last_search_string = models.CharField(max_length=128, default="")
    user = models.ForeignKey("user")
    num_searches = models.IntegerField(default=0)
    # state diagramm ini (new) -> run -> done -> wait (search again pressed) -> run -> done -> ...
    current_state = models.CharField(max_length=6, choices=(
        ("ini" , "initialised"),
        ("wait", "waiting"),
        ("run" , "search running"),
        ("done", "search done")), default="ini")
    deleted = models.BooleanField(default=False)
    # number of results for the last search
    results = models.IntegerField(default=0)
    last_search = models.DateTimeField(null=True)
    created = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.package_search(
            unicode(self),
            pk="%d" % (self.pk),
            key="ps__%d" % (self.pk),
            search_string=self.search_string,
            current_state=self.current_state,
            num_searches="%d" % (self.num_searches),
            last_search_string="%s" % (self.last_search_string),
            last_search=unicode(to_system_tz(self.last_search)) if self.last_search else "never",
            results="%d" % (self.results))
    def __unicode__(self):
        return self.search_string

@receiver(signals.pre_save, sender=package_search)
def package_search_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "search_string")
        if not cur_inst.deleted:
            num_ss = package_search.objects.exclude(Q(pk=cur_inst.pk)).filter(Q(search_string=cur_inst.search_string) & Q(deleted=False)).count()
            if num_ss:
                raise ValidationError("search_string already used")

class package_search_result(models.Model):
    idx = models.AutoField(primary_key=True)
    package_search = models.ForeignKey(package_search)
    name = models.CharField(max_length=128, default="")
    kind = models.CharField(max_length=16, default="package", choices=(
        ("package", "Package"),
        ("patch"  , "Patch"),
    ))
    arch = models.CharField(max_length=32, default="")
    # version w. release
    version = models.CharField(max_length=128, default="")
    copied = models.BooleanField(default=False)
    package_repo = models.ForeignKey(package_repo, null=True)
    created = models.DateTimeField(auto_now_add=True)
    def create_package(self):
        new_p = package(
            name=self.name,
            version=self.version,
            kind=self.kind,
            arch=self.arch,
            package_repo=self.package_repo)
        try:
            new_p.save()
        except:
            raise
        else:
            self.copied = True
            self.save()
        return new_p
    def get_xml(self):
        return E.package_search_result(
            unicode(self),
            pk="%d" % (self.pk),
            key="psr__%d" % (self.pk),
            name=self.name,
            kind=self.kind,
            arch=self.arch,
            version=self.version,
            copied="1" if self.copied else "0",
            package_repo="%d" % (self.package_repo_id or 0)
        )
    class Meta:
        ordering = ("name", "arch", "version",)

class package(models.Model):
    idx = models.AutoField(db_column="package_idx", primary_key=True)
    name = models.CharField(max_length=128)
    version = models.CharField(max_length=128)
    kind = models.CharField(max_length=16, default="package", choices=(
        ("package", "Package"),
        ("patch"  , "Patch"),
    ))
    arch = models.CharField(max_length=32, default="")
    # hard to determine ...
    size = models.IntegerField(default=0)
    package_repo = models.ForeignKey(package_repo, null=True)
# #    pgroup = models.TextField()
# #    summary = models.TextField()
# #    distribution = models.ForeignKey("distribution")
# #    vendor = models.ForeignKey("vendor")
# #    buildtime = models.IntegerField(null=True, blank=True)
# #    buildhost = models.CharField(max_length=765, blank=True)
# #    packager = models.CharField(max_length=765, blank=True)
# #    date = models.DateTimeField(auto_now_add=True)
    created = models.DateTimeField(auto_now_add=True)
    def get_xml(self):
        return E.package(
            unicode(self),
            pk="%d" % (self.pk),
            key="pack__%d" % (self.pk),
            name=self.name,
            version=self.version,
            kind=self.kind,
            arch=self.arch,
            size="%d" % (self.size),
            package_repo="%d" % (self.package_repo_id or 0)
        )
    def __unicode__(self):
        return "%s-%s" % (self.name, self.version)
    class Meta:
        db_table = u'package'
        unique_together = (("name", "version", "arch", "kind",),)

class package_device_connection(models.Model):
    idx = models.AutoField(primary_key=True)
    device = models.ForeignKey("device")
    package = models.ForeignKey(package)
    # target state
    target_state = models.CharField(max_length=8, choices=(
        ("keep"   , "keep"),
        ("install", "install"),
        ("upgrade", "upgrade"),
        ("erase"  , "erase")), default="keep")
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
        ("unknown"   , "unknown"),
        ), default="zypper_xml")
    response_str = models.TextField(max_length=65535, default="")
    def get_xml(self, with_package=False):
        pdc_xml = E.package_device_connection(
            pk="%d" % (self.pk),
            key="pdc__%d" % (self.pk),
            device="%d" % (self.device_id),
            package="%d" % (self.package_id),
            target_state="%s" % (self.target_state),
            installed="%s" % (self.installed),
            force_flag="1" if self.force_flag else "0",
            nodeps_flag="1" if self.nodeps_flag else "0",
        )
        if with_package:
            pdc_xml.append(self.package.get_xml())
        return pdc_xml
    def interpret_response(self):
        if self.response_type == "zypper_xml":
            xml = etree.fromstring(self.response_str)
            if xml[0].tag == "info":
                # short when target_state ="keep"
                self.installed = "u"
            else:
                # full stream
                install_summary = xml.xpath(".//install-summary")
                if len(install_summary):
                    install_summary = install_summary[0]
                    if not len(install_summary):
                        # nohting to do, set according to target state
                        self.installed = {"keep"    : "u",
                                          "install" : "y",
                                          "upgrade" : "y",
                                          "erase"   : "n"}[self.target_state]
                    else:
                        if len(install_summary.xpath(".//to-install")):
                            self.installed = "y"
                        elif len(install_summary.xpath(".//to-reinstall")):
                            self.installed = "y"
                        elif len(install_summary.xpath(".//to-remove")):
                            self.installed = "n"
                        else:
                            self.installed = "u"
                else:
                    stdout_el = xml.xpath(".//stdout")
                    if len(stdout_el):
                        line = stdout_el[0].text.strip()
                        if line.startswith("package") and line.endswith("installed"):
                            if line.count("not installed"):
                                self.installed = "n"
                            else:
                                self.installed = "y"
                        else:
                            # unsure
                            self.installed = "u"
                    else:
                        self.installed = "u"
                        print "*** interpret_response (package) ***", etree.tostring(xml, pretty_print=True)
        elif self.response_type == "yum_flat":
            lines = etree.fromstring(self.response_str).findtext("stdout").strip().split("\n")
            if len(lines) == 1:
                line = lines[0]
                if line.startswith("package") and line.endswith("installed"):
                    if line.count("not installed"):
                        self.installed = "n"
                    else:
                        self.installed = "y"
                else:
                    # unsure
                    self.installed = "u"
            else:
                self.installed = "u"
                cur_mode = 0
                for _line_num, line in enumerate(lines):
                    if line.startswith("Installed:"):
                        cur_mode = 1
                    elif line.startswith("Removed:"):
                        cur_mode = 2
                    elif not line.strip():
                        cur_mode = 0
                    else:
                        if cur_mode:
                            if line.startswith(" ") and line.count(self.package.name):
                                self.installed = "y" if cur_mode == 1 else "n"
        else:
            self.installed = "u"
    class Meta:
        pass

