from django.conf import settings
from django.conf.urls import patterns, include, url
from django.conf.urls.static import static

from initat.cluster.frontend import session_views_test

# handler404 = main_views.index.as_view()

session_patterns = patterns(
    "initat.cluster.frontend",
    url(r"login", session_views_test.sess_login.as_view(), name="login"),
)
my_url_patterns = patterns(
    "",
    url(r"^session/", include(session_patterns, namespace="session")),
)

url_patterns = patterns(
    "",
    url(r"^%s/" % (settings.REL_SITE_ROOT), include(my_url_patterns)),
)

url_patterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
url_patterns += patterns(
    'django.contrib.staticfiles.views',
    url(r'^{}/static/(?P<path>.*)$'.format(settings.REL_SITE_ROOT), 'serve'),
)
