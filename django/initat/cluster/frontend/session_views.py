# session views

import sys
import os
import pprint
import random
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
from django.core.urlresolvers import reverse
from django.contrib.auth import authenticate, login, logout
from initat.cluster.backbone.models import user
from django.db.models import Q
from initat.core.render import render_me
from django.conf import settings
from initat.cluster.frontend.forms import authentication_form
from initat.cluster.frontend.helper_functions import init_logging
from django.views.decorators.cache import never_cache

# correct path to import session_handler
if "cluster-backbone-sql" in __file__:
    # local run
    OLD_DIR = os.path.dirname(__file__).replace(
        "/cluster-backbone-sql/initat/cluster/frontend",
        "/webfrontend/htdocs/python")
else:
    OLD_DIR = "/srv/www/htdocs/python"

if not OLD_DIR in sys.path:
    sys.path.append(OLD_DIR)

@never_cache
def redirect_to_main(request):
    return HttpResponseRedirect(reverse("session:login"))

def sess_logout(request):
    from_logout = request.user.is_authenticated()
    logout(request)
    login_form = authentication_form()
    return render_me(request, "login.html", {
        "login_form"  : login_form,
        "from_logout" : from_logout,
        "app_path"    : reverse("session:login")})()

@init_logging
def sess_login(request):
    if request.method == "POST":
        _post = request.POST
        login_form = authentication_form(data=_post)
        if login_form.is_valid():
            django_user = login_form.get_user()
            try:
                db_user = user.objects.get(Q(login=django_user.username))
            except user.DoesNotExist:
                db_user = None
                request.log("no db_user defined")
            else:
                pass
            login(request, django_user)
            request.session["db_user"] = db_user
            return HttpResponseRedirect(reverse("main:index"))
    else:
        login_form = authentication_form()
    return render_me(request, "login.html", {
        "login_form" : login_form,
        "app_path"   : reverse("session:login")})()
