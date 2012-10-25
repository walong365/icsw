# transfer views

import sys
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
import os
from django.core.urlresolvers import reverse

if "cluster-backbone-sql" in __file__:
    # local run
    OLD_DIR = os.path.dirname(__file__).replace(
        "/cluster-backbone-sql/initat/cluster/transfer",
        "/webfrontend/htdocs/python")
else:
    OLD_DIR = "/srv/www/htdocs/python"

if not OLD_DIR in sys.path:
    sys.path.append(OLD_DIR)

from django.views.decorators.cache import never_cache
import main
import pprint
import process_tools
from django.contrib.auth.decorators import login_required
from initat.cluster.frontend.helper_functions import init_logging

class request_object(object):
    def __init__(self, request, module_name):
        self.request = request
        self.environ = request.META
        self.environ["SCRIPT_FILENAME"] = os.path.join(OLD_DIR, "main.py")
        self.environ["SERVER_NAME"] = process_tools.get_machine_name()
        self.module_name = module_name
        self.title = module_name
        self._parse_args()
        self.output = []
    def _parse_args(self):
        self.sys_args = self.request.POST.copy()
        self.sys_args.update(self.request.GET)
        for key, value in self.sys_args.iteritems():
            if key.endswith("[]"):
                self.sys_args[key[:-2]] = [self.sys_args[key]]
                del self.sys_args[key]
            else:
                pass
        #for key, value in self.sys_args.iteritems():
        #    print key, value
        self.my_files = {}
    def write(self, what):
        self.output.append(what)
         
@login_required
@init_logging
def transfer(request, *args):
    #print request, args
    # rewrite for main.py
    #print args, request.META["PATH_INFO"]
    module_name = request.META["PATH_INFO"]
    if module_name.endswith("/"):
        module_name = module_name[:-1]
    module_name = module_name.split("/")[-1].split(".")[0]
    req = request_object(request, module_name)
    #print "module name: %s" % (module_name)
    result = main.handle_normal_module_call(req, module_name)
    if result is None:
        return HttpResponse("".join(req.output), content_type="text/html")
    else:
        return result

@never_cache
def redirect_to_main(request):
    return HttpResponseRedirect(reverse("transfer:main"))
