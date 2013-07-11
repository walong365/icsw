# session views

""" basic session views """

import sys
import os
import logging

from django.contrib.auth import login, logout
from django.core.urlresolvers import reverse
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.generic import View

from initat.core.render import render_me
from initat.cluster.frontend.helper_functions import update_session_object
from initat.cluster.frontend.forms import authentication_form
from initat.cluster.backbone.models import user, user_variable, group

logger = logging.getLogger("cluster.setup")

### correct path to import session_handler
##if "cluster-backbone-sql" in __file__:
##    # local run
##    OLD_DIR = os.path.dirname(__file__).replace(
##        "/cluster-backbone-sql/initat/cluster/frontend",
##        "/webfrontend/htdocs/python")
##else:
##    OLD_DIR = "/srv/www/htdocs/python"
##
##if not OLD_DIR in sys.path:
##    sys.path.append(OLD_DIR)

class redirect_to_main(View):
    @method_decorator(never_cache)
    def get(self, request):
        return HttpResponseRedirect(reverse("session:login"))

class sess_logout(View):
    def get(self, request):
        from_logout = request.user.is_authenticated()
        logout(request)
        login_form = authentication_form()
        return render_me(request, "login.html", {
            "login_form"  : login_form,
            "from_logout" : from_logout,
            "app_path"    : reverse("session:login")})()

class sess_login(View):
    def get(self, request):
        return render_me(request, "login.html", {
            "login_form" : authentication_form(),
            "app_path"   : reverse("session:login")})()
    def post(self, request):
        _post = request.POST
        login_form = authentication_form(data=_post)
        if login_form.is_valid():
            django_user = login_form.get_user()
            try:
                db_user = user.objects.get(Q(login=django_user.username))
            except user.DoesNotExist:
                db_user = None
                logger.warning("no db_user defined")
                if not user.objects.all().count() and not group.objects.all().count():
                    logger.warning("creating default user")
                    # create standard user
                    new_group = group.objects.create(
                        groupname="%sgrp" % (django_user.username),
                        gid=666,
                    )
                    new_user = user.objects.create(
                        login=django_user.username,
                        group=new_group,
                        uid=666,
                        password=login_form.cleaned_data.get("password"),
                    )
                    db_user = new_user
            else:
                pass
            login(request, django_user)
            request.session["db_user"] = db_user
            if db_user:
                request.session["user_vars"] = dict([(user_var.name, user_var) for user_var in db_user.user_variable_set.all()])
            else:
                request.session["user_vars"] = {}
            update_session_object(request)
            return HttpResponseRedirect(reverse("main:index"))
        return render_me(request, "login.html", {
            "login_form" : login_form,
            "app_path"   : reverse("session:login")})()
