from django.conf.urls import patterns, include, url
from django.conf import settings
import sys
import os
import process_tools
from initat.cluster.frontend import rest_views
from rest_framework.urlpatterns import format_suffix_patterns

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

session_patterns = patterns(
    "initat.cluster.frontend",
    url(r"logout", "session_views.sess_logout", name="logout"),
    url(r"login" , "session_views.sess_login" , name="login" ),
)

rms_patterns = patterns(
    "initat.cluster.rms",
    url(r"overview"     , "rms_views.overview"         , name="overview"         ),
    url(r"get_node_xml" , "rms_views.get_node_xml"     , name="get_node_xml"     ),
    url(r"get_run_xml"  , "rms_views.get_run_jobs_xml" , name="get_run_jobs_xml" ),
    url(r"get_wait_xml" , "rms_views.get_wait_jobs_xml", name="get_wait_jobs_xml"),
)

base_patterns = patterns(
    "initat.cluster.setup",
    url("^change_xml_entry$"                  , "base_views.change_xml_entry", name="change_xml_entry"  ),
    url("^xml/create_object/(?P<obj_name>.*)$", "base_views.create_object"   , name="create_object"),
    url("^xml/delete_object/(?P<obj_name>.*)$", "base_views.delete_object"   , name="delete_object"),
    url("^get_gauge_info$"                    , "base_views.get_gauge_info"  , name="get_gauge_info"),
)

setup_patterns = patterns(
    "initat.cluster.setup",
    url(r"p_overview"         , "setup_views.partition_overview"        , name="partition_overview"),
    url(r"xml/create_newd"    , "setup_views.create_part_disc"          , name="create_part_disc"  ),
    url(r"xml/delete_disc"    , "setup_views.delete_part_disc"          , name="delete_part_disc"  ),
    url(r"xml/create_part"    , "setup_views.create_partition"          , name="create_partition"  ),
    url(r"xml/delete_part"    , "setup_views.delete_partition"          , name="delete_partition"  ),
    url(r"xml/validate"       , "setup_views.validate_partition"        , name="validate_partition"),
    url(r"i_overview"         , "setup_views.image_overview"            , name="image_overview"    ),
    url(r"k_overview"         , "setup_views.kernel_overview"           , name="kernel_overview"   ),
    url(r"xml/scan_for_images", "setup_views.scan_for_images"           , name="scan_for_images"   ),
    url(r"xml/use_image"      , "setup_views.use_image"                 , name="use_image"         ),
    url(r"xml/delete_image"   , "setup_views.delete_image"              , name="delete_image"      ),
    url(r"xml/show_devloccl"  , "setup_views.show_device_class_location", name="show_device_class_location"),
)

config_patterns = patterns(
    "initat.cluster.frontend",
    url("^config_types$"        , "config_views.show_config_types"       , name="show_config_types" ),
    url("^show_config$"         , "config_views.show_configs"            , name="show_configs"      ),
    url("^get_dev_confs_xml$"   , "config_views.get_device_configs"      , name="get_device_configs"),
    url("^create_config$"       , "config_views.create_config"           , name="create_config"     ),
    url("^delete_config$"       , "config_views.delete_config"           , name="delete_config"     ),
    url("^create_var$"          , "config_views.create_var"              , name="create_var"        ),
    url("^delete_var$"          , "config_views.delete_var"              , name="delete_var"        ),
    url("^create_script$"       , "config_views.create_script"           , name="create_script"     ),
    url("^delete_script$"       , "config_views.delete_script"           , name="delete_script"     ),
    url("^set_config_cb$"       , "config_views.alter_config_cb"         , name="alter_config_cb"   ),
    url("^generate_config$"     , "config_views.generate_config"         , name="generate_config"   ),
    url("^download_hash$"       , "config_views.download_hash"           , name="download_hash"     ),
    url("^download_config/(?P<hash>.*)$", "config_views.download_configs", name="download_configs"  ),
    url("^upload_config$"       , "config_views.upload_config"           , name="upload_config"     ),
)

boot_patterns = patterns(
    "initat.cluster.frontend",
    url("^show_boot$"          , "boot_views.show_boot"       , name="show_boot"),
    url("^xml/get_options"     , "boot_views.get_html_options", name="get_html_options"),
    url("^xml/get_addon_info$" , "boot_views.get_addon_info"  , name="get_addon_info"),
    url("^xml/get_boot_info$"  , "boot_views.get_boot_info"   , name="get_boot_info"),
    url("^xml/get_devlog_info$", "boot_views.get_devlog_info" , name="get_devlog_info"),
    url("^xml/set_kernel"      , "boot_views.set_kernel"      , name="set_kernel"),
    url("^xml/set_target_state", "boot_views.set_target_state", name="set_target_state"),
    url("^xml/set_boot"        , "boot_views.set_boot"        , name="set_boot"),
    url("^xml/set_part"        , "boot_views.set_partition"   , name="set_partition"),
    url("^xml/set_image"       , "boot_views.set_image"       , name="set_image"),
    url("^soft_control$"       , "boot_views.soft_control"    , name="soft_control"       ),
    url("^hard_control$"       , "boot_views.hard_control"    , name="hard_control"       ),
)

device_patterns = patterns(
    "initat.cluster.frontend",
    url("^device_tree$"       , "device_views.device_tree"        , name="tree"               ),
    url("^get_xml_tree$"      , "device_views.get_xml_tree"       , name="get_xml_tree"       ), 
    url("^add_selection$"     , "device_views.add_selection"      , name="add_selection"      ),
    url("^clear_selection$"   , "device_views.clear_selection"    , name="clear_selection"    ),
    url("^config$"            , "device_views.show_configs"       , name="show_configs"       ),
    url("^get_group_tree$"    , "device_views.get_group_tree"     , name="get_group_tree"     ),
    url("^connections"        , "device_views.connections"        , name="connections"        ),
    url("^xml/create_connect" , "device_views.create_connection"  , name="create_connection"  ),
    url("^xml/delete_connect" , "device_views.delete_connection"  , name="delete_connection"  ),
    url("manual_connection"   , "device_views.manual_connection"  , name="manual_connection"  ),
    url("variables$"          , "device_views.variables"          , name="variables"          ),
    url("variables/create$"   , "device_views.create_variable"    , name="create_variable"    ),
    url("variables/delete$"   , "device_views.delete_variable"    , name="delete_variable"    ),
    url("dev_info$"           , "device_views.device_info"        , name="device_info"        ),
)

network_patterns = patterns(
    "initat.cluster.frontend",
    url("^network$"           , "network_views.show_cluster_networks" , name="show_networks"        ),
    url("^netw_t_dt$"         , "network_views.show_network_d_types"  , name="show_network_d_types" ),
    url("^dev_network$"       , "network_views.device_network"        , name="network"              ),
    url("^get_network_tree$"  , "network_views.get_network_tree"      , name="get_network_tree"     ), 
    url("^create_netdevice$"  , "network_views.create_netdevice"      , name="create_netdevice"     ),
    url("^delete_netdevice$"  , "network_views.delete_netdevice"      , name="delete_netdevice"     ),
    url("^create_net_ip$"     , "network_views.create_net_ip"         , name="create_net_ip"        ),
    url("^delete_net_ip$"     , "network_views.delete_net_ip"         , name="delete_net_ip"        ),
    url("^create_new_peer$"   , "network_views.create_new_peer"       , name="create_new_peer"      ),
    url("^delete_peer$"       , "network_views.delete_peer"           , name="delete_peer"          ),
    url("^get_valid_peers$"   , "network_views.get_valid_peers"       , name="get_valid_peers"      ),
    url("^copy_network$"      , "network_views.copy_network"          , name="copy_network"         ),
    url("^json_network$"      , "network_views.json_network"          , name="json_network"         ),
)

monitoring_patterns = patterns(
    "initat.cluster.frontend",
    url("^setup$"              , "monitoring_views.setup"            , name="setup"            ),
    url("^extsetup$"           , "monitoring_views.extended_setup"   , name="extended_setup"   ),
    url("^create_command$"     , "monitoring_views.create_command"   , name="create_command"   ),
    url("^delete_command$"     , "monitoring_views.delete_command"   , name="delete_command"   ),
    url("^xml/dev_config$"     , "monitoring_views.device_config"    , name="device_config"    ),
    url("^create_config$"      , "monitoring_views.create_config"    , name="create_config"    ),
    url("^to_icinga$"          , "monitoring_views.call_icinga"      , name="call_icinga"      ),
    url("^xml/read_part$"      , "monitoring_views.fetch_partition"  , name="fetch_partition"  ),
)

user_patterns = patterns(
    "initat.cluster.frontend",
    url("overview/(?P<mode>.*)$"      , "user_views.overview"   , name="overview"),
    url("sync$"                       , "user_views.sync_users" , name="sync_users"),
)

if settings.CLUSTER_LICENSE["rest"]:
    rpl = []
    for obj_name in ["user", "group", "device_group"]:
        rpl.extend([
            url("^%s/$" % (obj_name), getattr(rest_views, "%s_list" % (obj_name)).as_view(), name="%s_list" % (obj_name)),
            url("^%s/(?P<pk>[0-9]+)/$" % (obj_name), getattr(rest_views, "%s_detail" % (obj_name)).as_view(), name="%s_detail" % (obj_name)),
        ])
    rest_patterns = patterns(
        "initat.cluster.frontend",
        url("^api/$"                     , "rest_views.api_root"              , name="root"),
        url("^api/user/$"                , rest_views.user_list_h.as_view()   , name="user_list_h"),
        url("^api/user/(?P<pk>[0-9]+)/$" , rest_views.user_detail_h.as_view() , name="user_detail_h"),
        url("^api/group/$"               , rest_views.group_list_h.as_view()  , name="group_list_h"),
        url("^api/group/(?P<pk>[0-9]+)/$", rest_views.group_detail_h.as_view(), name="group_detail_h"),
        *rpl
    )
    rest_patterns = format_suffix_patterns(rest_patterns)

pack_patterns = patterns(
    "initat.cluster.frontend",
    url("overview/repo$"       , "pack_views.repo_overview"      , name="repo_overview"      ),
    url("search/repo$"         , "pack_views.search_package"     , name="search_package"     ),
    url("search/create"        , "pack_views.create_search"      , name="create_search"      ),
    url("search/delete"        , "pack_views.delete_search"      , name="delete_search"      ),
    url("search/retry"         , "pack_views.retry_search"       , name="retry_search"       ),
    url("search/search_result" , "pack_views.get_search_result"  , name="get_search_result"  ),
    url("search/use_package"   , "pack_views.use_package"        , name="use_package"        ),
    url("search/unuse_package" , "pack_views.unuse_package"      , name="unuse_package"      ),
    url("install"              , "pack_views.install"            , name="install"            ),
    url("refresh"              , "pack_views.refresh"            , name="refresh"            ),
    url("pack/add"             , "pack_views.add_package"        , name="add_package"        ),
    url("pack/remove"          , "pack_views.remove_package"     , name="remove_package"     ),
    url("pack/change_tstate"   , "pack_views.change_target_state", name="change_target_state"),
    url("pack/change_pflag"    , "pack_views.change_package_flag", name="change_package_flag"),
    url("pack/sync"            , "pack_views.synchronize"        , name="synchronize"        ),
)

main_patterns = patterns(
    "initat.cluster.frontend",
    url(r"index$" , "main_views.index", name="index"),
)

rrd_patterns = patterns(
    "initat.cluster.frontend",
    url(r"class$", "rrd_views.class_overview", name="class_overview"),
)

doc_patterns = patterns(
    "",
    url(r"^%s/(?P<path>.*)$" % (settings.REL_SITE_ROOT)    ,
        "django.views.static.serve", {
            "document_root" : os.path.join(settings.FILE_ROOT, "doc", "build", "html")
            }, name="show"),
)

my_url_patterns = patterns(
    "",
    #url(r"static/(?P<path>.*)$"        , "django.views.static.serve", {"document_root" : settings.MEDIA_ROOT}),
    url(r"^$"         , "initat.cluster.frontend.session_views.redirect_to_main"),
    url(r"^base/"     , include(base_patterns      , namespace="base"    )),
    url(r"^session/"  , include(session_patterns   , namespace="session" )),
    url(r"^config/"   , include(config_patterns    , namespace="config"  )),
    url(r"^rms/"      , include(rms_patterns       , namespace="rms"     )),
    url(r"^main/"     , include(main_patterns      , namespace="main"    )),
    url(r"^device/"   , include(device_patterns    , namespace="device"  )),
    url(r"^network/"  , include(network_patterns   , namespace="network" )),
    url(r"^nagios/"   , include(monitoring_patterns, namespace="mon"     )),
    url(r"^boot/"     , include(boot_patterns      , namespace="boot"    )),
    url(r"^setup/"    , include(setup_patterns     , namespace="setup"   )),
    url(r"^user/"     , include(user_patterns      , namespace="user"    )),
    url(r"^pack/"     , include(pack_patterns      , namespace="pack"    )),
    url(r"^rrd/"      , include(rrd_patterns       , namespace="rrd"     )),
    url(r"^doc/"      , include(doc_patterns       , namespace="doc"     )),
)

if settings.CLUSTER_LICENSE["rest"]:
    my_url_patterns += patterns(
        "",
        url(r"^rest/"     , include(rest_patterns      , namespace="rest"    )),
    )

url_patterns = patterns(
    "",
    url(r"^%s/media/frontend/(?P<path>.*)$" % (settings.REL_SITE_ROOT)    ,
        "django.views.static.serve", {
            "document_root" : os.path.join(settings.FILE_ROOT, "frontend", "media")
            }),
    url(r"^%s/static/initat/core/(?P<path>.*)$" % (settings.REL_SITE_ROOT),
        "django.views.static.serve", {
            "document_root" : os.path.join(settings.FILE_ROOT, "..", "core")
            }),
    url(r"^%s/static/rest_framework/(?P<path>.*)$" % (settings.REL_SITE_ROOT),
        "django.views.static.serve", {
            "document_root" : "/opt/python-init/lib/python/site-packages/rest_framework/static/rest_framework"
            }),
    url(r"^%s/media/uni_form/(?P<path>.*)$" % (settings.REL_SITE_ROOT),
        "django.views.static.serve", {
            "document_root" : "/opt/python-init/lib/python/site-packages/crispy_forms/static/uni_form"
            }),
    url(r"^%s/" % (settings.REL_SITE_ROOT)                                , include(my_url_patterns)),
    url(r"^$", "initat.cluster.frontend.session_views.redirect_to_main"),
)
