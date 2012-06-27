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
    url(r"overview"     , "rms_views.overview"         , name="overview"         ),
    url(r"get_node_xml" , "rms_views.get_node_xml"     , name="get_node_xml"     ),
    url(r"get_run_xml"  , "rms_views.get_run_jobs_xml" , name="get_run_jobs_xml" ),
    url(r"get_wait_xml" , "rms_views.get_wait_jobs_xml", name="get_wait_jobs_xml"),
)

config_patterns = patterns(
    "init.cluster.frontend",
    url("^config_types$", "config_views.show_config_type_options", name="config_types"),
)

device_patterns = patterns(
    "init.cluster.frontend",
    url("^device_tree$"     , "device_views.device_tree"        , name="tree"               ),
    url("^get_json_tree$"   , "device_views.get_json_tree"      , name="get_json_tree"      ), 
    url("^get_json_devlist$", "device_views.get_json_devlist"   , name="get_json_devlist"   ),
    url("^get_xml_tree$"    , "device_views.get_xml_tree"       , name="get_xml_tree"       ), 
    url("^get_network_tree$", "device_views.get_network_tree"   , name="get_network_tree"   ), 
    url("^change_xml_entry$", "device_views.change_xml_entry"   , name="change_xml_entry"   ),
    url("^create_devg$"     , "device_views.create_device_group", name="create_device_group"),
    url("^create_device$"   , "device_views.create_device"      , name="create_device"      ),
    url("^delete_devg$"     , "device_views.delete_device_group", name="delete_device_group"),
    url("^delete_device$"   , "device_views.delete_device"      , name="delete_device"      ),
    url("^add_selection$"   , "device_views.add_selection"      , name="add_selection"      ),
    url("^clear_selection$" , "device_views.clear_selection"    , name="clear_selection"    ),
    url("^network$"         , "device_views.network"            , name="network"            ),
    url("^create_netdevice$", "device_views.create_netdevice"   , name="create_netdevice"   ),
    
)

network_patterns = patterns(
    "init.cluster.frontend",
    url("^network$"          , "network_views.show_cluster_networks" , name="networks"),
    url("^netdevice_classes$", "network_views.show_netdevice_classes", name="netdevice_classes"),
)

main_patterns = patterns(
    "init.cluster.frontend",
    url(r"index$" , "main_views.index", name="index"),
)

my_url_patterns = patterns(
    "",
    url(r"static/(?P<path>.*)$"        , "django.views.static.serve", {"document_root" : settings.MEDIA_ROOT}),
    url(r"^"        , include(transfer_patterns, namespace="transfer")),
    url(r"^session/", include(session_patterns , namespace="session" )),
    url(r"^config/" , include(config_patterns  , namespace="config"  )),
    url(r"^rms/"    , include(rms_patterns     , namespace="rms"     )),
    url(r"^main/"   , include(main_patterns    , namespace="main"    )),
    url(r"^device/" , include(device_patterns  , namespace="device"  )),
    url(r"^network/", include(network_patterns , namespace="network" )),
)

url_patterns = patterns(
    "",
    # hack for icons
    url(r"^%s/frontend/media/(?P<path>.*)$" % (settings.REL_SITE_ROOT), "django.views.static.serve", {"document_root" : settings.MEDIA_ROOT}, name="media"),
    url(r"icons-init/(?P<path>.*)$"                                   , "django.views.static.serve", {"document_root" : settings.MEDIA_ROOT[:-14] + "/icons"}),
    url(r"^%s/" % (settings.REL_SITE_ROOT)                            , include(my_url_patterns)),
)
