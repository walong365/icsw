#!/usr/bin/python-init -Otu
# -*- coding: utf-8 -*-

""" initcore views """

import base64
import codecs
import os
import colorsys
import datetime
import logging_tools
from lxml import etree
from lxml.builder import E

from django.http import HttpResponse, HttpResponseRedirect
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST
from django.conf import settings
from django.core.urlresolvers import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import auth
from django.contrib.auth.models import User
from django.db.models import Q

from initcore import menu_tools
from initcore.render_tools import render_me
from initcore.helper_functions import init_logging
from initcore.forms import authentication_form, user_config_form, change_password_form
from initcore.models import user_variable

from edmdb.models import olimhcm_oetiperson, olimhcm_oetirole, olimhcm_oetipersonoetirole, olimcrm_person

session_history = None

@login_required
def logout(request):
    """ Log a User out, and record action """
    # generate login history entry
    if request.user:
        try:
            act_she = session_history.objects.get(Q(session_id=request.session._session_key) & Q(user=request.user))
        except:
            print "No session_history found"
        else:
            act_she.logout_time = datetime.datetime.now()
            act_she.save()
    auth.logout(request)
    return render_me(request, "initcore/login.html", {"login_form": authentication_form(),
                                             "next"        : settings.SITE_ROOT,
                                             "from_logout" : True,
                                             "app_path"    : reverse("session:login")})()

#@init_logging
@never_cache
def login(request, template_name="initcore/login.html", redirect_field_name="next"):
    redirect_to = request.REQUEST.get(redirect_field_name, settings.SITE_ROOT)
    if request.method == "POST":
        form = authentication_form(data=request.POST)
        if form.is_valid():
            # Light security check -- make sure redirect_to isn't garbage.
            auth.login(request, form.get_user())
            request.session.update(get_user_variables(request))
            request.session.update(set_css_values(request))
            request.session.update(get_user_role(request, form.get_user()))
            request.session.save()
            return HttpResponseRedirect(redirect_to)
        else:
            form = authentication_form(data=dict([(key, value) for key, value in request.POST.iteritems() if key not in ["password"]]))
    else:
        form = authentication_form(request)
    request.session.set_test_cookie()
    return render_me(request, template_name, {"login_form" : form,
                                              "next"       : redirect_to,
                                              "app_path"   : reverse("session:login")})()

@init_logging
@login_required
def change_password(request):
    if request.method == "POST":
        # check
        _post = request.POST
        cur_form = change_password_form(_post, username=request.user.username)
        if cur_form.is_valid():
            request.user.set_password(cur_form.cleaned_data["password_1"])
            request.user.save()
            return HttpResponseRedirect(settings.SITE_ROOT)
    else:
        cur_form = change_password_form(username=request.user.username)
    return render_me(request, "initcore/change_password.html",
                     {"password_form" : cur_form,
                      }).render()

@init_logging
def menu_folder(request, *args):
    args = base64.b64decode(args[0])
    xml_doc = menu_tools.olim_menu(settings.MENU_XML_DIR).process(codecs.open(settings.MENU_XML_PATH, "r", "utf-8").read(), transform=False)
    parent_node = xml_doc.xpath(args)[0]
    request.session.update({"menu_xpath" : args})
    request.session.save()
    return render_me(request, "initcore/main.html")()

@init_logging
@login_required
def get_menu(request, *args):
    request.META["HTTP_X_REQUESTED_WITH"] = "HttpRequest"
    is_mobile = request.session.get("is_mobile", False)
    for_dynatree = "dynatree" in args
    menu_html = menu_tools.get_menu_html(request, is_mobile, for_dynatree)
    return HttpResponse(menu_html, mimetype="text/html")

@init_logging
@login_required
def switch_useragent(request):
    redirect_to = settings.SITE_ROOT
    user_vars = get_user_variables(request, "is_mobile")
    if "is_mobile" in user_vars:
        store_user_variable(request, "is_mobile", not user_vars["is_mobile"])
    else:
        store_user_variable(request, "is_mobile", False)
    request.session.update(get_user_variables(request))
    request.session.save()
    return HttpResponseRedirect(redirect_to)

@init_logging
@login_required
def set_color_scheme(request, *args):
    redirect_to = settings.SITE_ROOT
    store_user_variable(request, "css_theme", args[0])
    request.session.update(get_user_variables(request))
    request.session.update(set_css_values(request))
    request.session.save()
    return HttpResponseRedirect(redirect_to)

@init_logging
@login_required
def set_mobile(request):
    redirect_to = settings.SITE_ROOT
    if request.method == "POST":
        redirect_to = request.POST.get("next", settings.SITE_ROOT)
        # First time
        user_vars = get_user_variables(request, "is_mobile")
        if user_vars == {}:
            store_user_variable(request, "is_mobile", var_value=True, default=False)
            user_vars = get_user_variables(request, "is_mobile")
        else:
            if user_vars["is_mobile"]:
                store_user_variable(request, "is_mobile", False)
            else:
                store_user_variable(request, "is_mobile", True)
    return HttpResponseRedirect(redirect_to)

@init_logging
def save_layout_state(request):
    my_dict = {}
    for key in request.POST.iterkeys():
        if key.startswith("a[") and key.endswith("]"):
            s_key = key[2:-1].split("][")
            if len(s_key) == 2:
                cur_val = request.POST[key].lower()
                if cur_val.isdigit():
                    cur_val = int(cur_val)
                elif cur_val == "false":
                    cur_val = False
                elif cur_val == "true":
                    cur_val = True
                my_dict.setdefault(s_key[0], {})[s_key[1]] = cur_val
    if "west" in my_dict:
        # save west-closed flag in session
        request.session["west_closed"] = my_dict["west"].get("isClosed", False)
        request.session.save()
    return HttpResponse(etree.tostring(E.retval("OK saved state")),
                        mimetype="application/xml")

@login_required
def user_config(request):
    # modify session object if necessary
    def_dict = {"css_theme"  : settings.DEFAULT_CSS_THEME,
                "font_scale" : "27"}
    for cv_name, cv_default in def_dict.iteritems():
        if not request.session.has_key(cv_name):
            request.session[cv_name] = cv_default
    stored = False
    if request.method == "POST":
        config_form = user_config_form(request.POST, initial=dict([(key, request.session[key]) for key in def_dict.keys()]))
        if config_form.is_valid():
            stored = True
            for key in def_dict.keys():
                store_user_variable(request, key, config_form.cleaned_data[key])
    else:
        config_form = user_config_form(initial=dict([(key, request.session.get(key, value)) for key, value in def_dict.iteritems()]))
    # set colors according to selected css
    request.session.update(get_user_variables(request))
    request.session.update(set_css_values(request))
    request.session.save()
    if stored:
        return HttpResponseRedirect(settings.SITE_ROOT)
    else:
        return render_me(request, "initcore/user_config.html", {"css_form" : config_form})()

@login_required
def set_css_values(request):
    css_name = request.session.get("css_theme", settings.DEFAULT_CSS_THEME)
    font_scale = request.session.get("font_scale", "27")
    upd_dict = {"background_color_top"  : "#ffda88",
                "background_color_west" : "#ffeaa8"}
    css_dir = os.path.join(settings.MEDIA_ROOT, "initcore/css", "%s%s" % (css_name, font_scale))
    if os.path.isdir(css_dir):
        css_file = [f_name for f_name in os.listdir(css_dir) if f_name.endswith(".css")]
        #print css_dir, css_file
        if css_file:
            css_file = css_file[0]
            request.session["css_file"] = css_file
            try:
                css_lines = [line for line in file(os.path.join(css_dir, css_file), "r").read().split("\n") if line.strip().startswith(".ui-widget-content {")]
            except:
                pass
            else:
                if css_lines:
                    css_line = css_lines[0]
                    css_color = css_line[css_line.find("background:"):].split(None, 1)[1].split()[0][1:]
                    css_r_g_b = (int(css_color[0:2], 16),
                                 int(css_color[2:4], 16),
                                 int(css_color[4:6], 16))
                    css_h_s_v = colorsys.rgb_to_hsv(*css_r_g_b)
                    upd_dict = {"background_color_top"  : "#%02x%02x%02x" % (scale_rgb(css_r_g_b, 1.0, -20)),
                                "background_color_west" : "#%02x%02x%02x" % (scale_rgb(css_r_g_b, 1.02, 0))}
    return upd_dict

def scale_rgb(rgb_specs, fact, diff):
    ret_val = tuple([min(max(val * fact + diff * val * val / (255 * 255), 0), 255) for val in rgb_specs])
    return ret_val

def get_user_role(request, user):
    try:
        oetiperson = olimhcm_oetiperson.objects.get(username=request.user.username)
    except olimhcm_oetiperson.DoesNotExist:
        res =  {"OLIM_ROLE": ()}
    else:
        person2role = olimhcm_oetipersonoetirole.objects.filter(rf_oetiperson=oetiperson.pk)
        roles = []
        for i in person2role:
            role = olimhcm_oetirole.objects.get(pk=i.rf_oetirole)
            roles.append(role.rolename)
        res = {"OLIM_ROLE": roles}
    return res

@login_required
def get_user_variables(request, var_name=None):
    if type(request) == User:
        # we got an user, no traversing needed
        edm_user = request
    else:
        edm_user = request.user
    # the vars belong to the oekotex user, not the django user
    query = Q(user=edm_user)
    if var_name:
        query &= Q(name=var_name)
    all_vars = user_variable.objects.filter(query)
    var_dict = dict([(act_var.name, act_var.load()) for act_var in all_vars])
    return var_dict

@login_required
def store_user_variable(request, var_name, var_value=None, default=None):
    edm_user = request.user
    cur_value = var_value if var_value is not None else request.session.get(var_name, default)
    try:
        act_var = user_variable.objects.get(Q(user=edm_user) & Q(name=var_name))
    except user_variable.DoesNotExist:
        act_var = user_variable(user=edm_user,
                                name=var_name)
    except user_variable.MultipleObjectsReturned:
        request.log("more than one user_variable '%s' defined, deleting them all ..." % (var_name),
                    logging_tools.LOG_LEVEL_ERROR)
        user_variable.objects.filter(Q(user=edm_user) & Q(name=var_name)).delete()
        act_var = user_variable(user=edm_user,
                                name=var_name)
    else:
        pass
    act_var.store(cur_value)
    request.session[var_name] = act_var.load()
    return act_var

@login_required
def overview(request, first_char=""):
    return render_me(request, "initcore/welcome_page.html")()

@login_required
def admin(request, first_char=""):
    return render_me(request, "initcore/admin_page.html")()
