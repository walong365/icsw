#!/usr/bin/python-init

from django.conf import settings
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError, ImproperlyConfigured
from django.db import models
from django.db.models import Q, signals, get_model
from django.dispatch import receiver
from initat.cluster.backbone.models.functions import _check_empty_string, _check_integer
from lxml.builder import E # @UnresolvedImport
from rest_framework import serializers
import base64
import crypt
import hashlib
import inspect
import os
import random
import string

__all__ = [
    "csw_permission", "csw_permission_serializer",
    "csw_object_permission", "csw_object_permission_serializer",
    "user", "user_serializer", "user_serializer_h",
    "group", "group_serializer", "group_serializer_h",
    "user_device_login",
    "user_variable",
    ]

# auth_cache structure
class auth_cache(object):
    def __init__(self, auth_obj):
        self.auth_obj = auth_obj
        self.cache_key = u"auth_%s_%d" % (
            auth_obj._meta.object_name,
            auth_obj.pk,
            )
        self.__perms, self.__obj_perms = (set(), {})
        if self.auth_obj.__class__.__name__ == "user":
            self.has_all_perms = self.auth_obj.is_superuser
        else:
            self.has_all_perms = False
        # print self.cache_key
        self._from_db()
    def _from_db(self):
        self.__perm_dict = dict([("%s.%s" % (cur_perm.content_type.app_label, cur_perm.codename), cur_perm) for cur_perm in csw_permission.objects.all().select_related("content_type")])
        perms = self.auth_obj.permissions.all().select_related("content_type")
        for perm in perms:
            self.__perms.add(("%s.%s" % (perm.content_type.app_label, perm.codename)))
        obj_perms = self.auth_obj.object_permissions.all().select_related("csw_permission__content_type")
        for obj_perm in obj_perms:
            perm_key = "%s.%s" % (obj_perm.csw_permission.content_type.app_label, obj_perm.csw_permission.codename)
            self.__obj_perms.setdefault(perm_key, []).append(obj_perm.object_pk)
        # pprint.pprint(self.__obj_perms)
    def _get_code_key(self, app_label, code_name):
        code_key = "%s.%s" % (app_label, code_name)
        if code_key not in self.__perm_dict:
            raise ValueError("wrong permission name %s" % (code_key))
        return code_key
    def has_permission(self, app_label, code_name):
        code_key = self._get_code_key(app_label, code_name)
        return code_key in self.__perms
    def has_object_permission(self, app_label, code_name, obj=None):
        code_key = self._get_code_key(app_label, code_name)
        if self.has_permission(app_label, code_name):
            # at fist check global permission
            return True
        elif code_key in self.__obj_perms:
            if obj:
                if app_label == obj._meta.app_label:
                    return obj.pk in self.__obj_perms.get(code_key, [])
                else:
                    return False
            else:
                # no obj given so if the key is found in obj_perms it means that at least we have one object set
                return True
        else:
            return False
    def get_allowed_object_list(self, app_label, code_name):
        code_key = self._get_code_key(app_label, code_name)
        if self.has_permission(app_label, code_name) or getattr(self.auth_obj, "is_superuser", False):
            # at fist check global permission
            return set(get_model(app_label, self.__perm_dict[code_key].content_type.name).objects.all().values_list("pk", flat=True))
        elif code_key in self.__obj_perms:
            return set(self.__obj_perms[code_key])
        else:
            return set()
    def get_all_object_perms(self, obj):
        obj_ct = ContentType.objects.get_for_model(obj)
        # which permissions are valid for this object ?
        obj_perms = set([key for key, value in self.__perm_dict.iteritems() if value.content_type == obj_ct])
        if self.has_all_perms:
            return obj_perms
        else:
            # which permissions are global set ?
            global_perms = obj_perms & self.__perms
            # local permissions
            local_perms = set([key for key in obj_perms if obj.pk in self.__obj_perms.get(key, [])])
            return global_perms | local_perms

class csw_permission(models.Model):
    """
    ClusterSoftware permissions
    - global permissions
    """
    idx = models.AutoField(primary_key=True)
    name = models.CharField(max_length=150)
    codename = models.CharField(max_length=150)
    content_type = models.ForeignKey(ContentType)
    # true if this right can be used for object-level permissions
    valid_for_object_level = models.BooleanField(default=True)
    class Meta:
        unique_together = (("content_type", "codename"),)
        ordering = ("content_type__app_label", "content_type__name", "name",)
        app_label = "backbone"
    # def get_xml(self):
    #    r_xml = E.csw_permission(
    #        pk="%d" % (self.pk),
    #        key="cswp__%d" % (self.pk),
    #        name=self.name or "",
    #        codename=self.codename or "",
    #        valid_for_object_level="1" if self.valid_for_object_level else "0",
    #        content_type="%d" % (self.content_type_id),
    #        )
    #    return r_xml
    @staticmethod
    def get_permission(in_object, code_name):
        ct = ContentType.objects.get_for_model(in_object)
        cur_pk = in_object.pk
        return csw_object_permission.objects.create(
            csw_permission=csw_permission.objects.get(Q(content_type=ct) & Q(codename=code_name)),
            object_pk=cur_pk
            )
    def __unicode__(self):
        return u"%s | %s | %s | %s" % (
            self.content_type.app_label,
            self.content_type,
            self.name,
            "G/O" if self.valid_for_object_level else "G",
            )

class content_type_serializer(serializers.ModelSerializer):
    class Meta:
        model = ContentType

class csw_permission_serializer(serializers.ModelSerializer):
    content_type = content_type_serializer()
    class Meta:
        model = csw_permission

class csw_object_permission(models.Model):
    """
    ClusterSoftware object permissions
    - local permissions
    - only allowed on the correct content_type
    """
    idx = models.AutoField(primary_key=True)
    csw_permission = models.ForeignKey(csw_permission)
    object_pk = models.IntegerField(default=0)
    def __unicode__(self):
        return "%s | %d" % (unicode(self.csw_permission), self.object_pk)
    class Meta:
        app_label = "backbone"

class csw_object_permission_serializer(serializers.ModelSerializer):
    class Meta:
        model = csw_object_permission

def get_label_codename(perm):
    app_label, codename = (None, None)
    if type(perm) in [str, unicode]:
        if perm.count(".") == 1:
            app_label, codename = perm.split(".")
        else:
            raise ImproperlyConfigured("Unknown permission format '%s'" % (perm))
    elif isinstance(perm, csw_permission):
        app_label, codename = (perm.content_type.app_label, perm.codename)
    elif isinstance(perm, csw_object_permission):
        app_label, codename = (perm.csw_permission.content_type.app_label, perm.csw_permission.codename)
    else:
        raise ImproperlyConfigured("Unknown perm '%s'" % (unicode(perm)))
    return (app_label, codename)

def check_app_permission(auth_obj, app_label):
    if auth_obj.permissions.filter(Q(content_type__app_label=app_label)).count():
        return True
    elif auth_obj.object_permissions.filter(Q(csw_permission__content_type__app_label=app_label)).count():
        return True
    else:
        return False

def check_permission(auth_obj, perm):
    if not hasattr(auth_obj, "_auth_cache"):
        auth_obj._auth_cache = auth_cache(auth_obj)
    app_label, codename = get_label_codename(perm)
    if app_label and codename:
        # caching code
        return auth_obj._auth_cache.has_permission(app_label, codename)
        # old code
        # try:
        #    auth_obj.permissions.get(
        #        Q(codename=codename) &
        #        Q(content_type__app_label=app_label)
        #        )
        # except csw_permission.DoesNotExist:
        #    return False
        # else:
        #    return True
    else:
        return False

def check_object_permission(auth_obj, perm, obj):
    if not hasattr(auth_obj, "_auth_cache"):
        auth_obj._auth_cache = auth_cache(auth_obj)
    app_label, code_name = get_label_codename(perm)
    # print "* cop", auth_obj, perm, obj, app_label, codename
    if app_label and code_name:
        if obj is None:
            # caching code
            return auth_obj._auth_cache.has_object_permission(app_label, code_name)
        else:
            if app_label == obj._meta.app_label:
                # caching code
                return auth_obj._auth_cache.has_object_permission(app_label, code_name, obj)
            else:
                return False
    else:
        return False

def get_all_object_perms(auth_obj, obj):
    # return all allowed permissions for a given object
    if not hasattr(auth_obj, "_auth_cache"):
        auth_obj._auth_cache = auth_cache(auth_obj)
    return auth_obj._auth_cache.get_all_object_perms(obj)

def get_allowed_object_list(auth_obj, perm):
    # return all allowed objects for a given permissions
    if not hasattr(auth_obj, "_auth_cache"):
        auth_obj._auth_cache = auth_cache(auth_obj)
    app_label, code_name = get_label_codename(perm)
    return auth_obj._auth_cache.get_allowed_object_list(app_label, code_name)

class user_manager(models.Manager):
    def get_by_natural_key(self, login):
        return super(user_manager, self).get(Q(login=login))
    def create_superuser(self, login, email, password):
        # create group
        user_group = group.objects.create(
            groupname="%sgrp" % (login),
            gid=max(list(group.objects.all().values_list("gid", flat=True)) + [665]) + 1,
            group_comment="auto create group for admin %s" % (login),
        )
        new_admin = self.create(
            login=login,
            email=email,
            uid=max(list(user.objects.all().values_list("uid", flat=True)) + [665]) + 1,
            group=user_group,
            comment="admin create by createsuperuser",
            password=password,
            is_superuser=True)
        return new_admin

class user(models.Model):
    objects = user_manager()
    USERNAME_FIELD = "login"
    REQUIRED_FIELDS = ["email", ]
    idx = models.AutoField(db_column="user_idx", primary_key=True)
    active = models.BooleanField(default=True)
    login = models.CharField(unique=True, max_length=255)
    uid = models.IntegerField(unique=True)
    group = models.ForeignKey("group")
    aliases = models.TextField(blank=True, null=True)
    export = models.ForeignKey("device_config", null=True, related_name="export", blank=True)
    home = models.TextField(blank=True, null=True)
    shell = models.CharField(max_length=765, blank=True, default="/bin/bash")
    # SHA encrypted
    password = models.CharField(max_length=48, blank=True)
    password_ssha = models.CharField(max_length=64, blank=True, default="")
    # cluster_contact = models.BooleanField()
    first_name = models.CharField(max_length=765, blank=True, default="")
    last_name = models.CharField(max_length=765, blank=True, default="")
    title = models.CharField(max_length=765, blank=True, default="")
    email = models.CharField(max_length=765, blank=True, default="")
    pager = models.CharField(max_length=765, blank=True, default="")
    tel = models.CharField(max_length=765, blank=True, default="")
    comment = models.CharField(max_length=765, blank=True, default="")
    nt_password = models.CharField(max_length=255, blank=True, default="")
    lm_password = models.CharField(max_length=255, blank=True, default="")
    date = models.DateTimeField(auto_now_add=True)
    allowed_device_groups = models.ManyToManyField("device_group", blank=True)
    home_dir_created = models.BooleanField(default=False)
    secondary_groups = models.ManyToManyField("group", related_name="secondary", blank=True)
    last_login = models.DateTimeField(null=True)
    permissions = models.ManyToManyField(csw_permission, related_name="db_user_permissions", blank=True)
    object_permissions = models.ManyToManyField(csw_object_permission, related_name="db_user_permissions", blank=True)
    is_superuser = models.BooleanField(default=False)
    db_is_auth_for_password = models.BooleanField(default=False)
    def __setattr__(self, key, value):
        # catch clearing of export entry via empty ("" or '') key
        if key == "export" and type(value) in [str, unicode]:
            value = None
        super(user, self).__setattr__(key, value)
    def is_authenticated(self):
        return True
    def has_perms(self, perms):
        # check if user has all of the perms
        return all([self.has_perm(perm) for perm in perms])
    def has_any_perms(self, perms):
        # check if user has any of the perms
        return any([self.has_perm(perm) for perm in perms])
    def has_perm(self, perm, ask_parent=True):
        # only check global permissions
        if not (self.active and self.group.active):
            return False
        elif self.is_superuser:
            return True
        res = check_permission(self, perm)
        if not res and ask_parent:
            res = check_permission(self.group, perm)
        return res
    @property
    def is_staff(self):
        return self.is_superuser
    @property
    def id(self):
        return self.pk
    def has_object_perm(self, perm, obj=None, ask_parent=True):
        if not (self.active and self.group.active):
            return False
        elif self.is_superuser:
            return True
        res = check_object_permission(self, perm, obj)
        if not res and ask_parent:
            res = check_object_permission(self.group, perm, obj)
        return res
    def get_all_object_perms(self, obj, ask_parent=True):
        # return all permissions we have for a given object
        if not (self.active and self.group.active):
            r_val = set()
        else:
            if ask_parent:
                r_val = get_all_object_perms(self, obj) | get_all_object_perms(self.group, obj)
            else:
                r_val = get_all_object_perms(self, obj)
        return r_val
    def get_all_object_perms_xml(self, obj, ask_parent=True):
        return E.permissions(
            *[E.permissions(cur_val, app=cur_val.split(".")[0], permission=cur_val.split(".")[1]) for cur_val in sorted(list(self.get_all_object_perms(obj, ask_parent)))]
        )
    def get_allowed_object_list(self, perm, ask_parent=True):
        # get all object pks we have an object permission for
        if ask_parent:
            return get_allowed_object_list(self, perm) | get_allowed_object_list(self.group, perm)
        else:
            return get_allowed_object_list(self, perm)
    def has_object_perms(self, perms, obj=None, ask_parent=True):
        # check if user has all of the object perms
        return all([self.has_object_perm(perm, obj, ask_parent=ask_parent) for perm in perms])
    def has_any_object_perms(self, perms, obj=None, ask_parent=True):
        # check if user has any of the object perms
        return any([self.has_object_perm(perm, obj, ask_parent=ask_parent) for perm in perms])
    def has_module_perms(self, module_name, ask_parent=True):
        if not (self.active and self.group.active):
            return False
        elif self.is_superuser:
            return True
        res = check_app_permission(self, module_name)
        if not res and ask_parent:
            res = self.group.has_module_perms(module_name)
        return res
    def get_is_active(self):
        return self.active
    is_active = property(get_is_active)
#     def get_xml(self, with_permissions=False, with_allowed_device_groups=True, user_perm_dict=None,
#                 allowed_device_group_dict=None):
#         user_xml = E.user(
#             unicode(self),
#             pk="%d" % (self.pk),
#             key="user__%d" % (self.pk),
#             login=self.login,
#             uid="%d" % (self.uid),
#             group="%d" % (self.group_id or 0),
#             aliases=self.aliases or "",
#             active="1" if self.active else "0",
#             export="%d" % (self.export_id or 0),
#             home_dir_created="1" if self.home_dir_created else "0",
#             first_name=self.first_name or "",
#             last_name=self.last_name or "",
#             title=self.title or "",
#             email=self.email or "",
#             pager=self.pager or "",
#             tel=self.tel or "",
#             comment=self.comment or "",
#             is_superuser="1" if self.is_superuser else "0",
#             secondary_groups="::".join(["%d" % (sec_group.pk) for sec_group in self.secondary_groups.all()]),
#             db_is_auth_for_password="1" if self.db_is_auth_for_password else "0"
#         )
#         if with_allowed_device_groups:
#             if allowed_device_group_dict:
#                 user_xml.attrib["allowed_device_groups"] = "::".join(["%d" % (cur_pk) for cur_pk in allowed_device_group_dict.get(self.login, [])])
#             else:
#                 user_xml.attrib["allowed_device_groups"] = "::".join(["%d" % (cur_pk) for cur_pk in self.allowed_device_groups.all().values_list("pk", flat=True)])
#         if with_permissions:
#             if user_perm_dict:
#                 user_xml.attrib["permissions"] = "::".join(["%d" % (cur_perm.pk) for cur_perm in user_perm_dict.get(self.login, [])])
#             else:
#                 user_xml.attrib["permissions"] = "::".join(["%d" % (cur_perm.pk) for cur_perm in csw_permission.objects.filter(Q(db_user_permissions=self))])
#         else:
#             # empty field
#             user_xml.attrib["permissions"] = ""
#         return user_xml
    class CSW_Meta:
        permissions = (
            ("admin"      , "Administrator", True),
            ("modify_tree", "modify device tree", False),
            ("modify_domain_name_tree", "modify domain name tree", False),
            ("modify_category_tree", "modify category tree", False),
        )
        # foreign keys to ignore
        fk_ignore_list = ["user_variable"]
    class Meta:
        db_table = u'user'
        ordering = ("login",)
        app_label = "backbone"
    def __unicode__(self):
        return u"%s (%d; %s, %s)" % (
            self.login,
            self.pk,
            self.first_name or "first",
            self.last_name or "last")

class user_serializer_h(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(format='api', view_name="rest:user_detail_h")
    group = serializers.HyperlinkedRelatedField(view_name="rest:group_detail_h")
    class Meta:
        model = user
        fields = ("url", "login", "uid", "group")

class user_serializer(serializers.ModelSerializer):
    object_permissions = csw_object_permission_serializer(many=True, read_only=True)
    class Meta:
        model = user
        fields = ("idx", "login", "uid", "group", "first_name", "last_name", "shell",
            "title", "email", "pager", "comment", "tel", "password", "active", "export",
            "permissions", "secondary_groups", "object_permissions",
            "allowed_device_groups", "aliases", "db_is_auth_for_password", "is_superuser",
            )

@receiver(signals.m2m_changed, sender=user.permissions.through)
def user_permissions_changed(sender, *args, **kwargs):
    if kwargs.get("action") == "pre_add" and "instance" in kwargs:
        cur_user = None
        try:
            # hack to get the current logged in user
            for frame_record in inspect.stack():
                if frame_record[3] == "get_response":
                    request = frame_record[0].f_locals["request"]
                    cur_user = request.user
        except:
            cur_user = None
        if cur_user:
            is_admin = cur_user.has_perm("backbone.admin")
            for add_pk in kwargs.get("pk_set"):
                # only admins can grant admin or group_admin rights
                if csw_permission.objects.get(Q(pk=add_pk)).codename in ["admin", "group_admin"] and not is_admin:
                    raise ValidationError("not enough rights")

@receiver(signals.pre_save, sender=user)
def user_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_integer(cur_inst, "uid", min_val=100, max_val=65535)
        _check_empty_string(cur_inst, "login")
        _check_empty_string(cur_inst, "password")
        if not cur_inst.home:
            cur_inst.home = cur_inst.login
        cur_pw = cur_inst.password
        if cur_pw.count(":"):
            cur_method, passwd = cur_pw.split(":", 1)
        else:
            cur_method, passwd = ("", cur_pw)
        if cur_method in ["SHA1", "CRYPT"]:
            # known hash, pass
            pass
        else:
            pw_gen_1 = settings.PASSWORD_HASH_FUNCTION
            if pw_gen_1 == "CRYPT":
                salt = "".join(random.choice(string.ascii_uppercase + string.digits) for _x in xrange(4))
                cur_pw = "%s:%s" % (pw_gen_1, crypt.crypt(passwd, salt))
                cur_inst.password = cur_pw
                cur_inst.password_ssha = ""
            else:
                salt = os.urandom(4)
                new_sh = hashlib.new(pw_gen_1)
                new_sh.update(passwd)
                cur_pw = "%s:%s" % (pw_gen_1, base64.b64encode(new_sh.digest()))
                cur_inst.password = cur_pw
                # ssha1
                new_sh.update(salt)
                # print base64.b64encode(new_sh.digest() +  salt)
                cur_inst.password_ssha = "%s:%s" % ("SSHA", base64.b64encode(new_sh.digest() + salt))

@receiver(signals.post_save, sender=user)
def user_post_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]

# @receiver(signals.post_delete, sender=user)
# def user_post_delete(sender, **kwargs):
#    if "instance" in kwargs:
#        cur_inst = kwargs["instance"]

class group(models.Model):
    idx = models.AutoField(db_column="ggroup_idx", primary_key=True)
    active = models.BooleanField(default=True)
    groupname = models.CharField(db_column="ggroupname", unique=True, max_length=48, blank=False)
    gid = models.IntegerField(unique=True)
    homestart = models.TextField(blank=True)
    group_comment = models.CharField(max_length=765, blank=True)
    first_name = models.CharField(max_length=765, blank=True)
    last_name = models.CharField(max_length=765, blank=True)
    title = models.CharField(max_length=765, blank=True)
    email = models.CharField(max_length=765, blank=True, default="")
    pager = models.CharField(max_length=765, blank=True, default="")
    tel = models.CharField(max_length=765, blank=True, default="")
    comment = models.CharField(max_length=765, blank=True)
    date = models.DateTimeField(auto_now_add=True)
    # not implemented right now in md-config-server
    allowed_device_groups = models.ManyToManyField("device_group", blank=True)
    # parent group
    parent_group = models.ForeignKey("self", null=True, blank=True)
    permissions = models.ManyToManyField(csw_permission, related_name="db_group_permissions", blank=True)
    object_permissions = models.ManyToManyField(csw_object_permission, related_name="db_group_permissions")
    def has_perms(self, perms):
        # check if group has all of the perms
        return all([self.has_perm(perm) for perm in perms])
    def has_any_perms(self, perms):
        # check if group has any of the perms
        return any([self.has_perm(perm) for perm in perms])
    def has_perm(self, perm):
        if not self.active:
            return False
        return check_permission(self, perm)
    def has_object_perm(self, perm, obj=None, ask_parent=True):
        if not self.active:
            return False
        return check_object_permission(self, perm, obj)
    def has_object_perms(self, perms, obj=None, ask_parent=True):
        # check if group has all of the object perms
        return all([self.has_object_perm(perm, obj) for perm in perms])
    def has_any_object_perms(self, perms, obj=None, ask_parent=True):
        # check if group has any of the object perms
        return any([self.has_object_perm(perm, obj) for perm in perms])
    def get_allowed_object_list(self, perm, ask_parent=True):
        # get all object pks we have an object permission for
        return get_allowed_object_list(self, perm)
    def has_module_perms(self, module_name):
        if not (self.active):
            return False
        return check_app_permission(self, module_name)
    def get_is_active(self):
        return self.active
    is_active = property(get_is_active)
#     def get_xml(self, with_permissions=False, group_perm_dict=None, with_allowed_device_groups=False,
#                 allowed_device_group_dict=None):
#         group_xml = E.group(
#             unicode(self),
#             pk="%d" % (self.pk),
#             key="group__%d" % (self.pk),
#             groupname=unicode(self.groupname),
#             gid="%d" % (self.gid),
#             homestart=self.homestart or "",
#             active="1" if self.active else "0",
#             parent_group="%d" % (self.parent_group_id or 0),
#         )
#         for attr_name in [
#             "first_name", "last_name", "group_comment",
#             "title", "email", "pager", "tel", "comment"]:
#             group_xml.attrib[attr_name] = getattr(self, attr_name)
#         if with_allowed_device_groups:
#             if allowed_device_group_dict:
#                 group_xml.attrib["allowed_device_groups"] = "::".join(["%d" % (cur_pk) for cur_pk in allowed_device_group_dict.get(self.groupname, [])])
#             else:
#                 group_xml.attrib["allowed_device_groups"] = "::".join(["%d" % (cur_pk) for cur_pk in self.allowed_device_groups.all().values_list("pk", flat=True)])
#         if with_permissions:
#             if group_perm_dict is not None:
#                 group_xml.attrib["permissions"] = "::".join(["%d" % (cur_perm.pk) for cur_perm in group_perm_dict.get(self.groupname, [])])
#             else:
#                 group_xml.attrib["permissions"] = "::".join(["%d" % (cur_perm.pk) for cur_perm in csw_permission.objects.filter(Q(db_group_permissions=self))])
#         else:
#             # empty field
#             group_xml.attrib["permissions"] = ""
#         return group_xml
    class CSW_Meta:
        permissions = (
            ("group_admin", "Group administrator", True),
        )
    class Meta:
        db_table = u'ggroup'
        ordering = ("groupname",)
        app_label = "backbone"
    def __unicode__(self):
        return "%s (gid=%d)" % (
            self.groupname,
            self.gid)

class group_serializer_h(serializers.HyperlinkedModelSerializer):
    url = serializers.HyperlinkedIdentityField(format='api', view_name="rest:group_detail_h")
    class Meta:
        model = group
        fields = ("url", "groupname", "active", "gid")

class group_serializer(serializers.ModelSerializer):
    object_permissions = csw_object_permission_serializer(many=True, read_only=True)
    class Meta:
        model = group
        fields = ("groupname", "active", "gid", "idx", "parent_group",
            "homestart", "tel", "title", "email", "pager", "comment",
            "allowed_device_groups", "permissions", "object_permissions",
            )

@receiver(signals.pre_save, sender=group)
def group_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "groupname")
        _check_integer(cur_inst, "gid", min_val=100, max_val=65535)
        if cur_inst.homestart and not cur_inst.homestart.startswith("/"):
            raise ValidationError("homestart has to start with '/'")
        my_pk = cur_inst.pk
        if cur_inst.parent_group_id:
            # while true
            if cur_inst.parent_group_id == my_pk:
                raise ValidationError("cannot be own parentgroup")
            # check for ring dependency
            cur_parent = cur_inst.parent_group
            while cur_parent is not None:
                if cur_parent.pk == my_pk:
                    raise ValidationError("ring dependency detected in groups")
                cur_parent = cur_parent.parent_group

@receiver(signals.post_save, sender=group)
def group_post_save(sender, **kwargs):
    if not kwargs["raw"] and "instance" in kwargs:
        _cur_inst = kwargs["instance"]

@receiver(signals.post_delete, sender=group)
def group_post_delete(sender, **kwargs):
    if "instance" in kwargs:
        _cur_inst = kwargs["instance"]

@receiver(signals.m2m_changed, sender=group.permissions.through)
def group_permissions_changed(sender, *args, **kwargs):
    if kwargs.get("action") == "pre_add" and "instance" in kwargs:
        for add_pk in kwargs.get("pk_set"):
            if csw_permission.objects.get(Q(pk=add_pk)).codename in ["admin", "group_admin"]:
                raise ValidationError("right not allowed for group")

class user_device_login(models.Model):
    idx = models.AutoField(db_column="user_device_login_idx", primary_key=True)
    user = models.ForeignKey("backbone.user")
    device = models.ForeignKey("backbone.device")
    date = models.DateTimeField(auto_now_add=True)
    class Meta:
        db_table = u'user_device_login'
        app_label = "backbone"

class user_variable(models.Model):
    idx = models.AutoField(primary_key=True)
    user = models.ForeignKey("backbone.user")
    var_type = models.CharField(max_length=2, choices=[
        ("s", "string"),
        ("i", "integer"),
        ("b", "boolean"),
        ("n", "none")])
    name = models.CharField(max_length=189)
    value = models.CharField(max_length=64, default="")
    date = models.DateTimeField(auto_now_add=True)
    def to_db_format(self):
        cur_val = self.value
        if type(cur_val) in [str, unicode]:
            self.var_type = "s"
        elif type(cur_val) in [int, long]:
            self.var_type = "i"
            self.value = "%d" % (self.value)
        elif type(cur_val) in [bool]:
            self.var_type = "b"
            self.value = "1" if cur_val else "0"
        elif cur_val is None:
            self.var_type = "n"
            self.value = "None"
    def from_db_format(self):
        if self.var_type == "b":
            if self.value.lower() in ["true", "t"]:
                self.value = True
            elif self.value.lower() in ["false", "f"]:
                self.value = False
            else:
                self.value = True if int(self.value) else False
        elif self.var_type == "i":
            self.value = int(self.value)
        elif self.var_type == "n":
            self.value = None
    class Meta:
        unique_together = [("name", "user"), ]
        app_label = "backbone"

@receiver(signals.pre_save, sender=user_variable)
def user_variable_pre_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        _check_empty_string(cur_inst, "name")
        cur_inst.to_db_format()

@receiver(signals.post_init, sender=user_variable)
def user_variable_post_init(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        cur_inst.from_db_format()

@receiver(signals.post_save, sender=user_variable)
def user_variable_post_save(sender, **kwargs):
    if "instance" in kwargs:
        cur_inst = kwargs["instance"]
        cur_inst.from_db_format()
