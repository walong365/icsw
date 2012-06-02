from django.conf.urls import patterns, include, url
from django.conf import settings
import sys

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

import init.cluster.sub_urls

urlpatterns = init.cluster.sub_urls.sub_patterns

