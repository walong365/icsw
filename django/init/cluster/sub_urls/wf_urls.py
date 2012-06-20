from django.conf.urls import patterns, include, url
from django.conf import settings
import sys

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

transfer_patterns = patterns(
    "init.cluster.transfer",
    url(r"^$", "transfer_views.redirect_to_main"),
    url(r"transfer/"    , "transfer_views.transfer", name="main"),
    url(r"transfer/(.*)", "transfer_views.transfer", name="main")
)

session_patterns = patterns(
    "init.cluster.frontend",
    url(r"logout", "session_views.sess_logout", name="logout"),
    url(r"login" , "session_views.sess_login" , name="login" ),
)

rms_patterns = patterns(
    "init.cluster.rms",
    url(r"overview", "rms_views.overview", name="overview"),
)

config_patterns = patterns(
    ""
)

my_url_patterns = patterns(
    "",
    url(r"static/(?P<path>.*)$"        , "django.views.static.serve", {"document_root" : settings.MEDIA_ROOT}),
    url(r"^"        , include(transfer_patterns, namespace="transfer")),
    url(r"^session/", include(session_patterns , namespace="session" )),
    url(r"^config/" , include(config_patterns  , namespace="config"  )),
    url(r"^rms/"    , include(rms_patterns     , namespace="rms"     )),
)

url_patterns = patterns(
    "",
    # hack for icons
    url(r"^%s/frontend/media/(?P<path>.*)$" % (settings.REL_SITE_ROOT), "django.views.static.serve", {"document_root" : settings.MEDIA_ROOT}, name="media"),
    url(r"icons-init/(?P<path>.*)$"                                   , "django.views.static.serve", {"document_root" : settings.MEDIA_ROOT[:-14] + "/icons"}),
    url(r"^%s/" % (settings.REL_SITE_ROOT)                            , include(my_url_patterns)),
)
