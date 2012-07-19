# session views

import sys
from django.shortcuts import render_to_response
from django.http import HttpResponse, HttpResponseRedirect
import os
from django.core.urlresolvers import reverse
from django.contrib.auth import authenticate, login, logout
import pprint
from init.cluster.backbone.models import user
from django.db.models import Q
import random
from init.cluster.frontend import render_tools
from django.conf import settings
from init.cluster.frontend.forms import authentication_form

# correct path to import session_handler
if "cluster-backbone-sql" in __file__:
    # local run
    OLD_DIR = os.path.dirname(__file__).replace(
        "/cluster-backbone-sql/init/cluster/frontend",
        "/webfrontend/htdocs/python")
else:
    OLD_DIR = "/srv/www/htdocs/python"

if not OLD_DIR in sys.path:
    sys.path.append(OLD_DIR)

import session_handler

def sess_logout(request):
    # destroy old sessions stuff
    if "DB_SESSION_ID" in request.session.keys():
        #sess_data = session_handler.read_session(request, request.session["DB_SESSION_ID"])
        #session_handler.delete_session(sess_data)
        pass
    logout(request)
    login_form = authentication_form()
    return render_tools.render_me(request, "login.html", {"login_form"  : login_form,
                                                          "from_logout" : True,
                                                          "app_path"    : reverse("session:login")})()

def sess_login(request):
    if request.method == "POST":
        _post = request.POST
        login_form = authentication_form(data=_post)
        if login_form.is_valid():
            django_user = login_form.get_user()
            try:
                db_user = user.objects.get(Q(login=django_user.username))
            except user.DoesNotExist:
                return HttpResponseRedirect(reverse("transfer:main"))
            else:
                login(request, django_user)
                #print db_user
                sess_id = "".join([chr(random.randint(97, 122)) for x in range(16)])
                sess_dict = {"session_id" : sess_id}
                session_handler.init_session(request, sess_id, db_user, {"session_id" : sess_id})
                request.session["DB_SESSION_ID"] = sess_id
                # no need to use transfer_views
                return HttpResponseRedirect(reverse("main:index"))
                #return HttpResponseRedirect(reverse("transfer:main", args=["index.py?SID=%s" % (sess_id)]))
    else:
        login_form = authentication_form()
    return render_tools.render_me(request, "login.html", {"login_form" : login_form,
                                                          "app_path"   : reverse("session:login")})()
