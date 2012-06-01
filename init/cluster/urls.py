from django.conf.urls import patterns, include, url
from django.conf import settings
import sys

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()
print type(__file__), __file__
sys.path.append("/usr/local/share/home/local/development/clustersoftware/build-extern/cluster-backbone-sql/cluster")

import cluster.sub_urls

urlpatterns = cluster.sub_urls.sub_patterns

##transfer_patterns = patterns(
##    "backbone.transfer",
##    url(r"(.*)/", "views.transfer", name="transfer")
##)
##
##my_url_patterns = patterns(
##    "",
##    url(r"static/(?P<path>.*)$", "django.views.static.serve", {"document_root" : settings.MEDIA_ROOT}),
##    url(r"^", include(transfer_patterns, namespace="transfer"))
##)
##
##urlpatterns = patterns(
##    "",
##    # hack for icons
##    url(r"icons-init/(?P<path>.*)$", "django.views.static.serve", {"document_root" : settings.MEDIA_ROOT[:-14] + "/icons"}),
##    url(r"^%s/" % (settings.REL_SITE_ROOT), include(my_url_patterns)),
##)
