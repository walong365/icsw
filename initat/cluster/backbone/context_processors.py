#!/usr/bin/python-init -Otu

class csw_perm_lut(object):
    def __init__(self, user, module_name):
        self.user = user
        self.module_name = module_name
    def __getitem__(self, perm_name):
        return self.user.has_object_perm("%s.%s" % (self.module_name, perm_name))
    def __bool__(self):
        return self.user.has_module_perms(self.module_name)
    def __nonzero__(self):
        return self.user.has_module_perms(self.module_name)

class csw_perm_proxy(object):
    def __init__(self, request):
        if hasattr(request, "user"):
            self.user = request.user
        else:
            self.user = None
    def __getitem__(self, module_name):
        if self.user:
            return csw_perm_lut(self.user, module_name)
        else:
            return False
    def __contains__(self, perm_name):
        if "." not in perm_name:
            return bool(self[perm_name])
        module_name, perm_name = perm_name.split(".", 1)
        return self[module_name][perm_name]

def add_csw_permissions(request):
    return {"csw_perms" : csw_perm_proxy(request)}
