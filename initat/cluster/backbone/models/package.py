#!/usr/bin/python-init

from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, signals
from django.dispatch import receiver
from initat.cluster.backbone.models.license import LicenseUsage, LicenseParameterTypeEnum, LicenseEnum, \
    LicenseLockListDeviceService
from initat.cluster.backbone.models.functions import _check_empty_string
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

    def __unicode__(self):
        return self.name

    @property
    def distributable(self):
        is_d = False
        if self.publish_to_nodes:
            is_d = True if not self.url.startswith("dir:") else False
        return is_d

    def get_xml(self):
        return E.package_repo(
            unicode(self),
            pk="{:d}".format(self.pk),
            key="pr__{:d}".format(self.pk),
            name=self.name,
            alias=self.alias,
            repo_type=self.repo_type,
            enabled="1" if self.enabled else "0",
            autorefresh="1" if self.autorefresh else "0",
            gpg_check="1" if self.gpg_check else "0",
            publish_to_nodes="1" if self.publish_to_nodes else "0",
            url=self.url)

    def get_service_name(self):
        if self.service_id:
            return self.service.name
        else:
            return ""

    def repo_str(self):
        _vf = [
            "[{}]".format(self.alias),
            "name={}".format(self.name),
            "enabled={:d}".format(1 if self.enabled else 0),
            "autorefresh={:d}".format(1 if self.autorefresh else 0),
            "baseurl={}".format(self.url),
            "type={}".format(self.repo_type),
            "keeppackages=0",
            "priority={:d}".format(self.priority),
            "",
        ]
        if self.service_id:
            _vf.append("service={}".format(self.service.name))
        return "\n".join(_vf)

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

    def __unicode__(self):
        return self.search_string

    class CSW_Meta:
        fk_ignore_list = ["package_search_result"]

    class Meta:
        app_label = "backbone"
        ordering = ("search_string", "results",)


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
        ("patch", "Patch"),
    ))
    arch = models.CharField(max_length=32, default="")
    # version w. release
    version = models.CharField(max_length=128, default="")
    copied = models.BooleanField(default=False)
    package_repo = models.ForeignKey("backbone.package_repo", null=True)
    created = models.DateTimeField(auto_now_add=True)

    def create_package(self, exact=True, target_repo=None):
        new_p = package(
            name=self.name,
            # set empty version in case of always latest (== not exact)
            version=self.version if exact else "",
            kind=self.kind,
            arch=self.arch,
            package_repo=self.package_repo,
            always_latest=not exact,
            target_repo=target_repo,
            )
        try:
            new_p.save()
        except:
            raise
        else:
            self.copied = True
            self.save()
        return new_p

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

    def get_xml(self):
        return E.package(
            unicode(self),
            pk="{:d}".format(self.pk),
            key="pack__{:d}".format(self.pk),
            name=self.name,
            version=self.version,
            kind=self.kind,
            arch=self.arch,
            size="{:d}".format(self.size),
            package_repo="{:d}".format(self.package_repo_id or 0),
            always_latest="{:d}".format(1 if self.always_latest else 0),
        )

    def __unicode__(self):
        if self.always_latest:
            return u"{}-LATEST".format(self.name)
        else:
            return u"{}-{}".format(self.name, self.version)

    class CSW_Meta:
        permissions = (
            ("package_install", "access package install site", False),
        )

    def target_repo_name(self):
        if self.target_repo_id:
            return self.target_repo.name
        else:
            return ""

    class Meta:
        db_table = u'package'
        unique_together = (("name", "version", "arch", "kind", "target_repo",),)
        app_label = "backbone"


@receiver(signals.pre_save, sender=package)
def package_pre_save(sender, **kwargs):
    return
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        cur_pack = package.objects.exclude(Q(pk=cur_inst.pk)).filter(
            Q(name=cur_inst.name) &
            Q(always_latest=cur_inst.always_latest) &
            Q(version=cur_inst.version) &
            Q(arch=cur_inst.arch))
        if len(cur_pack):
            raise ValidationError("Package already exists")


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

    def get_xml(self, with_package=False, pre_delete=False):
        pdc_xml = E.package_device_connection(
            pk="{:d}".format(self.pk),
            key="pdc__{:d}".format(self.pk),
            device="{:d}".format(self.device_id),
            package="{:d}".format(self.package_id),
            target_state="{}".format(self.target_state),
            installed="{}".format(self.installed),
            force_flag="1" if self.force_flag else "0",
            nodeps_flag="1" if self.nodeps_flag else "0",
            pre_delete="1" if pre_delete else "0",
        )
        if with_package:
            pdc_xml.append(self.package.get_xml())
        return pdc_xml

    def interpret_response(self):
        if self.response_type == "zypper_xml":
            # print "..", self.response_str
            xml = etree.fromstring(self.response_str)
            if xml.find("post_result/stdout") is not None:
                pp_src, pp_text = ("post", xml.findtext("post_result/stdout"))
            elif xml.find("pre_result/stdout") is not None:
                pp_src, pp_text = ("pre", xml.findtext("pre_result/stdout"))
            else:
                pp_src, pp_text = ("main", None)
            if pp_src == "main":
                if xml[0].tag == "info":
                    # short when target_state ="keep"
                    self.installed = "u"
                else:
                    # full stream
                    install_summary = xml.xpath(".//install-summary", smart_strings=False)
                    if len(install_summary):
                        install_summary = install_summary[0]
                        if not len(install_summary):
                            # nohting to do, set according to target state
                            self.installed = {
                                "keep": "u",
                                "install": "y",
                                "upgrade": "y",
                                "erase": "n",
                            }[self.target_state]
                        else:
                            if len(install_summary.xpath(".//to-install", smart_strings=False)):
                                self.installed = "y"
                            elif len(install_summary.xpath(".//to-reinstall", smart_strings=False)):
                                self.installed = "y"
                            elif len(install_summary.xpath(".//to-upgrade", smart_strings=False)):
                                self.installed = "y"
                            elif len(install_summary.xpath(".//to-remove", smart_strings=False)):
                                self.installed = "n"
                            else:
                                self.installed = "u"
                    else:
                        stdout_el = xml.xpath(".//stdout", smart_strings=False)
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
            else:
                pp_lines = pp_text.split("\n")
                self.installed_name, self.installed_release, self.installed_version = ("", "", "")
                if pp_lines[0].count("not installed"):
                    self.installed = "n"
                    self.install_time = 0
                elif len(pp_lines) > 1 and pp_lines[1].isdigit():
                    self.installed = "y"
                    self.install_time = int(pp_lines[1])
                    self.installed_name = pp_lines[0]
                    if len(pp_lines) > 3:
                        self.installed_version = pp_lines[2]
                        self.installed_release = pp_lines[3]
                else:
                    self.installed = "u"
                    self.install_time = 0
        elif self.response_type == "yum_flat":
            xml = etree.fromstring(self.response_str)
            if xml.find("post_result/stdout") is not None:
                pp_src, pp_text = ("post", xml.findtext("post_result/stdout"))
            elif xml.find("pre_result/stdout") is not None:
                pp_src, pp_text = ("pre", xml.findtext("pre_result/stdout"))
            else:
                pp_src = "main"
            if pp_src == "main":
                yum_stdout = xml.findtext("stdout")
                if yum_stdout is not None:
                    lines = xml.findtext("stdout").strip().split("\n")
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
            else:
                pp_lines = pp_text.split("\n")
                self.installed_name, self.installed_release, self.installed_version = ("", "", "")
                if pp_lines[0].count("not installed"):
                    self.installed = "n"
                    self.install_time = 0
                elif len(pp_lines) > 1 and pp_lines[1].isdigit():
                    self.installed = "y"
                    self.install_time = int(pp_lines[1])
                    self.installed_name = pp_lines[0]
                    if len(pp_lines) > 3:
                        self.installed_version = pp_lines[2]
                        self.installed_release = pp_lines[3]
                else:
                    self.installed = "u"
                    self.install_time = 0
        else:
            self.installed = "u"

    class Meta:
        app_label = "backbone"


@receiver(signals.pre_save, sender=package_device_connection)
def package_device_connection_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        if cur_inst.target_state == "install" and cur_inst.package.always_latest:
            # rewrite t oupgrade
            cur_inst.target_state = "upgrade"
        if cur_inst.target_state not in ["upgrade", "keep", "install", "erase"]:
            raise ValidationError("unknown target state '{}'".format(cur_inst.target_state))

        if LicenseLockListDeviceService.objects.is_device_locked(LicenseEnum.package_install, cur_inst.device):
            raise ValidationError(
                u"Device {} is locked from accessing the license package install.".format(cur_inst.device)
            )


@receiver(signals.post_save, sender=package_device_connection)
def package_device_connection_post_save(sender, instance, raw, **kwargs):
    if not raw:
        LicenseUsage.log_usage(LicenseEnum.package_install, LicenseParameterTypeEnum.device, instance.device)
