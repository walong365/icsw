from django.conf.urls import patterns, include, url
from django.conf import settings
import sys
import process_tools

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

transfer_patterns = patterns(
    "initat.cluster.transfer",
    url(r"^$", "transfer_views.redirect_to_main"),
    url(r"transfer/"    , "transfer_views.transfer", name="main"),
    url(r"transfer/(.*)", "transfer_views.transfer", name="main")
)

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
)

setup_patterns = patterns(
    "initat.cluster.setup",
    url(r"p_overview"         , "setup_views.partition_overview"        , name="partition_overview"),
    url(r"xml/get_parts"      , "setup_views.get_all_partitions"        , name="get_all_partitions"),
    url(r"xml/create_newpt"   , "setup_views.create_new_partition_table", name="create_new_partition_table"),
    url(r"xml/create_newd"    , "setup_views.create_part_disc"          , name="create_part_disc"),
    url(r"xml/delete_disc"    , "setup_views.delete_part_disc"          , name="delete_part_disc"),
    url(r"xml/create_part"    , "setup_views.create_partition"          , name="create_partition"),
    url(r"xml/delete_part"    , "setup_views.delete_partition"          , name="delete_partition"),
    url(r"i_overview"         , "setup_views.image_overview"            , name="image_overview"),
    url(r"xml/get_images"     , "setup_views.get_all_images"            , name="get_all_images"),
    url(r"xml/scan_for_images", "setup_views.scan_for_images"           , name="scan_for_images"),
    url(r"xml/take_image"     , "setup_views.take_image"                , name="take_image"),
    url(r"xml/show_devloccl"  , "setup_views.show_device_class_location", name="show_device_class_location"),
)

config_patterns = patterns(
    "initat.cluster.frontend",
    url("^config_types$"     , "config_views.show_config_types"       , name="show_config_types" ),
    url("^show_config$"      , "config_views.show_configs"            , name="show_configs"      ),
    url("^get_configs_xml$"  , "config_views.get_configs"             , name="get_configs"       ),
    url("^get_dev_confs_xml$", "config_views.get_device_configs"      , name="get_device_configs"),
    url("^create_config$"    , "config_views.create_config"           , name="create_config"     ),
    url("^delete_config$"    , "config_views.delete_config"           , name="delete_config"     ),
    url("^create_var$"       , "config_views.create_var"              , name="create_var"        ),
    url("^delete_var$"       , "config_views.delete_var"              , name="delete_var"        ),
    url("^create_script$"    , "config_views.create_script"           , name="create_script"     ),
    url("^delete_script$"    , "config_views.delete_script"           , name="delete_script"     ),
    url("^set_config_cb$"    , "config_views.alter_config_cb"         , name="alter_config_cb"   ),
    url("^generate_config$"  , "config_views.generate_config"         , name="generate_config"   ),
)

boot_patterns = patterns(
    "initat.cluster.frontend",
    url("^show_boot$"          , "boot_views.show_boot"       , name="show_boot"),
    url("^xml/get_options"     , "boot_views.get_html_options", name="get_html_options"),
    url("^xml/get_addon_info$" , "boot_views.get_addon_info"  , name="get_addon_info"),
    url("^xml/get_boot_info$"  , "boot_views.get_boot_info"   , name="get_boot_info"),
    url("^xml/set_kernel"      , "boot_views.set_kernel"      , name="set_kernel"),
    url("^xml/set_target_state", "boot_views.set_target_state", name="set_target_state"),
    url("^xml/set_boot"        , "boot_views.set_boot"        , name="set_boot"),
    url("^xml/set_part"        , "boot_views.set_partition"   , name="set_partition"),
    url("^xml/set_iamge"       , "boot_views.set_image"       , name="set_image"),
)

device_patterns = patterns(
    "initat.cluster.frontend",
    url("^device_tree$"       , "device_views.device_tree"        , name="tree"               ),
    url("^get_json_tree$"     , "device_views.get_json_tree"      , name="get_json_tree"      ), 
    url("^get_xml_tree$"      , "device_views.get_xml_tree"       , name="get_xml_tree"       ), 
    url("^create_devg$"       , "device_views.create_device_group", name="create_device_group"),
    url("^create_device$"     , "device_views.create_device"      , name="create_device"      ),
    url("^delete_devg$"       , "device_views.delete_device_group", name="delete_device_group"),
    url("^delete_device$"     , "device_views.delete_device"      , name="delete_device"      ),
    url("^add_selection$"     , "device_views.add_selection"      , name="add_selection"      ),
    url("^clear_selection$"   , "device_views.clear_selection"    , name="clear_selection"    ),
    url("^config$"            , "device_views.show_configs"       , name="show_configs"       ),
    url("^get_group_tree$"    , "device_views.get_group_tree"     , name="get_group_tree"     ),
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
    url("^get_hopcount_state$", "network_views.get_hopcount_state"    , name="get_hopcount_state"   ),
    url("^trigger_hc_rebuild$", "network_views.rebuild_hopcount"      , name="rebuild_hopcount"     ),
)

monitoring_patterns = patterns(
    "initat.cluster.frontend",
    url("^setup$"            , "monitoring_views.setup"            , name="setup"),
    url("^xml/get_config"    , "monitoring_views.get_config"       , name="get_config"),
    url("^create_command$"   , "monitoring_views.create_command"   , name="create_command"),
    url("^delete_command$"   , "monitoring_views.delete_command"   , name="delete_command"),
    url("xml/dev_config$"    , "monitoring_views.device_config"    , name="device_config"),
    url("create_config$"     , "monitoring_views.create_config"    , name="create_config"),
)

main_patterns = patterns(
    "initat.cluster.frontend",
    url(r"index$" , "main_views.index", name="index"),
)

my_url_patterns = patterns(
    "",
    url(r"static/(?P<path>.*)$"        , "django.views.static.serve", {"document_root" : settings.MEDIA_ROOT}),
    url(r"^"          , include(transfer_patterns  , namespace="transfer")),
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
)

url_patterns = patterns(
    "",
    # hack for icons
    url(r"^%s/frontend/media/(?P<path>.*)$" % (settings.REL_SITE_ROOT), "django.views.static.serve", {"document_root" : settings.MEDIA_ROOT}, name="media"),
    url(r"icons-init/(?P<path>.*)$"                                   , "django.views.static.serve", {"document_root" : settings.MEDIA_ROOT[:-14] + "/icons"}),
    url(r"^%s/initat/(?P<path>.*)$" % (settings.REL_SITE_ROOT)        , "django.views.static.serve", {"document_root" : settings.MEDIA_ROOT[:-22]}),
    url(r"^%s/icinga/(?P<path>.*)$" % (settings.REL_SITE_ROOT)        , "django.views.static.serve", {"document_root" : "/opt/icinga"}),
    url(r"^%s/" % (settings.REL_SITE_ROOT)                            , include(my_url_patterns)),
)
