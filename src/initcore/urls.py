""" These urls have to be registered in a
namespace called 'session' """

from django.conf.urls.defaults import url, patterns, include
from django.conf import settings

urlpatterns = patterns(
    "initcore.views",
    url(r"^login/$", "login", name="login"),
    url(r"^logout/$", "logout", name="logout"),
    url(r"^change_password/$", "change_password", name="change_password"),
    url(r"^set_mobile/$", "set_mobile", name="set_mobile"),
    url(r"^user_config/$", "user_config", name="user_config"),
    url(r"^get_menu/(.*)$", "get_menu", name="get_menu"),
    url(r"^switch_ua/$", "switch_useragent", name="switch_useragent"),
    url(r"^set_colorscheme/(\S+)/$", "set_color_scheme", name="set_color_scheme"),
    url(r"^menu_folder/(\S+)/$", "menu_folder", name="menu_folder"),
    url(r"^layout/set_state/$", "save_layout_state", name="save_layout_state"),
)
