from django.conf import settings
from django.conf.urls import patterns, include

from django.contrib import admin
admin.autodiscover()

import initat.cluster.sub_urls

urlpatterns = initat.cluster.sub_urls.sub_patterns

urlpatterns += patterns(
    "",
    (r"^%s/admin/" % (settings.REL_SITE_ROOT), include(admin.site.urls)),
)
