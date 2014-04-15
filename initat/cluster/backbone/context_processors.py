#!/usr/bin/env python

from django.core.exceptions import ImproperlyConfigured
from initat.cluster.backbone.models import AC_MASK_DICT

class csw_obj_lut(object):
    __slots__ = ["user", "module_name", "content_name", "perm_name"]
    def __init__(self, user, module_name, content_name, perm_name):
        self.user = user
        self.module_name = module_name
        self.content_name = content_name
        self.perm_name = perm_name
    @property
    def key(self):
        return "{}.{}.{}".format(self.module_name, self.content_name, self.perm_name)
    def __getitem__(self, obj_name):
        key = self.key
        if obj_name.count("."):
            raise ImproperlyConfigured("dot found in obj_name '{}' (key={})".format(obj_name, key))
        if obj_name == "ANY__":
            print "cfo", key
            return self.user.has_object_perm(key)
        elif obj_name in AC_MASK_DICT:
            _level = self.user.get_object_perm_level(key)
            if _level >= 0:
                return _level & AC_MASK_DICT[obj_name]
            else:
                return False
        else:
            raise ImproperlyConfigured("Unknown object level accesscode '{}' (key '{}')".format(obj_name, key))
    def __bool__(self):
        return self.user.has_object_perm(self.key)
    def __nonzero__(self):
        return self.user.has_object_perm(self.key)

class csw_perm_lut(object):
    __slots__ = ["user", "module_name", "content_name"]
    def __init__(self, user, module_name, content_name):
        self.user = user
        self.module_name = module_name
        self.content_name = content_name
    def __getitem__(self, perm_name):
        return csw_obj_lut(self.user, self.module_name, self.content_name, perm_name)
    def __bool__(self):
        return self.user.has_content_perms(self.module_name, self.content_name)
    def __nonzero__(self):
        return self.user.has_content_perms(self.module_name, self.content_name)

class csw_content_lut(object):
    __slots__ = ["user", "module_name"]
    def __init__(self, user, module_name):
        self.user = user
        self.module_name = module_name
    def __getitem__(self, content_name):
        return csw_perm_lut(self.user, self.module_name, content_name)
    def __bool__(self):
        return self.user.has_module_perms(self.module_name)
    def __nonzero__(self):
        return self.user.has_module_perms(self.module_name)

class csw_perm_proxy(object):
    __slots__ = ["user"]
    def __init__(self, request):
        if hasattr(request, "user"):
            self.user = request.user
        else:
            self.user = None
    def __getitem__(self, module_name):
        if self.user:
            return csw_content_lut(self.user, module_name)
        else:
            return False
    def __contains__(self, perm_name):
        if "." not in perm_name:
            return bool(self[perm_name])
        module_name, perm_name = perm_name.split(".", 1)
        return self[module_name][perm_name]

def add_csw_permissions(request):
    return {
        "csw_perms" : csw_perm_proxy(request),
    }
