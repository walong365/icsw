from django.conf.urls import patterns, include, url
from django.conf import settings
import sys

from django.contrib import admin
admin.autodiscover()

import init.cluster.sub_urls

urlpatterns = init.cluster.sub_urls.sub_patterns

urlpatterns += patterns('',
    (r'^cluster/admin/', include(admin.site.urls)),
)
