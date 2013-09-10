# session views

""" basic session views """

import base64
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
            db_user = login_form.get_user()
            login(request, db_user)
            request.session["password"] = base64.b64encode(login_form.cleaned_data.get("password").decode("utf-8"))
            # for alias logins login_name != login
            request.session["login_name"] = login_form.get_login_name()
            update_session_object(request)
            return HttpResponseRedirect(reverse("main:index"))
        return render_me(request, "login.html", {
            "login_form" : login_form,
            "app_path"   : reverse("session:login")})()
