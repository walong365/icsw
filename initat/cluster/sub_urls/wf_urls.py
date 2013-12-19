#!/usr/bin/python-init -Otu

from django.conf.urls import patterns, include, url
from django.conf import settings
import os
from initat.cluster.frontend import rest_views, device_views, main_views, network_views, \
    monitoring_views, user_views, package_views, config_views, boot_views, session_views, rrd_views, \
    base_views, setup_views
from initat.cluster.rms import rms_views
from rest_framework.urlpatterns import format_suffix_patterns

handler404 = main_views.index.as_view()

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

session_patterns = patterns(
    "initat.cluster.frontend",
    url(r"logout", session_views.sess_logout.as_view(), name="logout"),
    url(r"login" , session_views.sess_login.as_view() , name="login"),
)

rms_patterns = patterns(
    "initat.cluster.rms",
    url(r"overview"        , rms_views.overview.as_view()         , name="overview"),
    url(r"get_header_xml"  , rms_views.get_header_xml.as_view()   , name="get_header_xml"),
    url(r"get_node_xml"    , rms_views.get_node_xml.as_view()     , name="get_node_xml"),
    url(r"get_run_xml"     , rms_views.get_run_jobs_xml.as_view() , name="get_run_jobs_xml"),
    url(r"get_wait_xml"    , rms_views.get_wait_jobs_xml.as_view(), name="get_wait_jobs_xml"),
    url(r"get_rms_json"    , rms_views.get_rms_json.as_view()     , name="get_rms_json"),
    url(r"control_job"     , rms_views.control_job.as_view()      , name="control_job"),
    url(r"get_file_content", rms_views.get_file_content.as_view() , name="get_file_content"),
)

base_patterns = patterns(
    "initat.cluster.setup",
    url("^change_xml_entry$"                  , base_views.change_xml_entry.as_view()   , name="change_xml_entry"),
    url("^xml/create_object/(?P<obj_name>.*)$", base_views.create_object.as_view()      , name="create_object"),
    url("^xml/delete_object/(?P<obj_name>.*)$", base_views.delete_object.as_view()      , name="delete_object"),
    url("^xml/get_object$"                    , base_views.get_object.as_view()         , name="get_object"),
    url("^get_gauge_info$"                    , base_views.get_gauge_info.as_view()     , name="get_gauge_info"),
    url("^get_cat_tree$"                      , base_views.get_category_tree.as_view()  , name="category_tree"),
    url("^cat_detail$"                        , base_views.category_detail.as_view()    , name="category_detail"),
    url("^cat_delete$"                        , base_views.delete_category.as_view()    , name="delete_category"),
    url("^cat_create$"                        , base_views.create_category.as_view()    , name="create_category"),
    url("^cat_move$"                          , base_views.move_category.as_view()      , name="move_category"),
    url("^cat_reference$"                     , base_views.get_cat_references.as_view() , name="get_cat_references"),
    url("^change_category"                    , base_views.change_category.as_view()    , name="change_category"),
    url("^prune_cat_tree"                     , base_views.prune_category_tree.as_view(), name="prune_categories"),
)

setup_patterns = patterns(
    "initat.cluster.setup",
    url(r"p_overview"         , setup_views.partition_overview.as_view()        , name="partition_overview"),
    url(r"xml/create_newd"    , setup_views.create_part_disc.as_view()          , name="create_part_disc"),
    url(r"xml/delete_disc"    , setup_views.delete_part_disc.as_view()          , name="delete_part_disc"),
    url(r"xml/create_part"    , setup_views.create_partition.as_view()          , name="create_partition"),
    url(r"xml/delete_part"    , setup_views.delete_partition.as_view()          , name="delete_partition"),
    url(r"xml/validate"       , setup_views.validate_partition.as_view()        , name="validate_partition"),
    url(r"i_overview"         , setup_views.image_overview.as_view()            , name="image_overview"),
    url(r"k_overview"         , setup_views.kernel_overview.as_view()           , name="kernel_overview"),
    url(r"xml/rescan_images"  , setup_views.scan_for_images.as_view()           , name="rescan_images"),
    url(r"xml/use_image"      , setup_views.use_image.as_view()                 , name="use_image"),
    url(r"xml/rescan_kernels" , setup_views.rescan_kernels.as_view()            , name="rescan_kernels"),
)

config_patterns = patterns(
    "initat.cluster.frontend",
    url("^show_config$"         , config_views.show_configs.as_view()            , name="show_configs"),
    url("^get_dev_confs_xml$"   , config_views.get_device_configs.as_view()      , name="get_device_configs"),
    url("^create_config$"       , config_views.create_config.as_view()           , name="create_config"),
    url("^delete_config$"       , config_views.delete_config.as_view()           , name="delete_config"),
    url("^create_var$"          , config_views.create_var.as_view()              , name="create_var"),
    url("^delete_var$"          , config_views.delete_var.as_view()              , name="delete_var"),
    url("^create_script$"       , config_views.create_script.as_view()           , name="create_script"),
    url("^delete_script$"       , config_views.delete_script.as_view()           , name="delete_script"),
    url("^set_config_cb$"       , config_views.alter_config_cb.as_view()         , name="alter_config_cb"),
    url("^generate_config$"     , config_views.generate_config.as_view()         , name="generate_config"),
    url("^download_hash$"       , config_views.download_hash.as_view()           , name="download_hash"),
    url("^download_config/(?P<hash>.*)$", config_views.download_configs.as_view(), name="download_configs"),
    url("^upload_config$"       , config_views.upload_config.as_view()           , name="upload_config"),
    url("^xml/show_dev_vars"    , config_views.get_device_cvars.as_view()        , name="get_device_cvars"),
)

boot_patterns = patterns(
    "initat.cluster.frontend",
    url("^show_boot$"          , boot_views.show_boot.as_view()       , name="show_boot"),
    url("^xml/get_options"     , boot_views.get_html_options.as_view(), name="get_html_options"),
    url("^xml/get_addon_info$" , boot_views.get_addon_info.as_view()  , name="get_addon_info"),
    url("^xml/get_boot_info$"  , boot_views.get_boot_info.as_view()   , name="get_boot_info"),
    url("^xml/get_devlog_info$", boot_views.get_devlog_info.as_view() , name="get_devlog_info"),
    url("^xml/set_kernel"      , boot_views.set_kernel.as_view()      , name="set_kernel"),
    url("^xml/set_target_state", boot_views.set_target_state.as_view(), name="set_target_state"),
    url("^xml/set_boot"        , boot_views.set_boot.as_view()        , name="set_boot"),
    url("^xml/set_part"        , boot_views.set_partition.as_view()   , name="set_partition"),
    url("^xml/set_image"       , boot_views.set_image.as_view()       , name="set_image"),
    url("^soft_control$"       , boot_views.soft_control.as_view()    , name="soft_control"),
    url("^hard_control$"       , boot_views.hard_control.as_view()    , name="hard_control"),
)

device_patterns = patterns(
    "initat.cluster.frontend",
    url("^device_tree$"       , device_views.device_tree.as_view()      , name="tree"),
    url("^get_xml_tree$"      , device_views.get_xml_tree.as_view()     , name="get_xml_tree"),
    url("^add_selection$"     , device_views.add_selection.as_view()    , name="add_selection"),
    url("^set_selection$"     , device_views.set_selection.as_view()    , name="set_selection"),
    url("^get_selection$"     , device_views.get_selection.as_view()    , name="get_selection"),
    url("^clear_selection$"   , device_views.clear_selection.as_view()  , name="clear_selection"),
    url("^config$"            , device_views.show_configs.as_view()     , name="show_configs"),
    url("^get_group_tree$"    , device_views.get_group_tree.as_view()   , name="get_group_tree"),
    url("^connections"        , device_views.connections.as_view()      , name="connections"),
    url("^xml/create_connect" , device_views.create_connection.as_view(), name="create_connection"),
    url("^xml/delete_connect" , device_views.delete_connection.as_view(), name="delete_connection"),
    url("manual_connection"   , device_views.manual_connection.as_view(), name="manual_connection"),
    url("variables$"          , device_views.variables.as_view()        , name="variables"),
    url("dev_info$"           , device_views.device_info.as_view()      , name="device_info"),
    url("change_devices$"     , device_views.change_devices.as_view()   , name="change_devices"),
)

network_patterns = patterns(
    "initat.cluster.frontend",
    url("^network$"           , network_views.show_cluster_networks.as_view() , name="show_networks"),
    url("^dev_network$"       , network_views.device_network.as_view()        , name="device_network"),
    url("^create_netdevice$"  , network_views.create_netdevice.as_view()      , name="create_netdevice"),
    url("^delete_netdevice$"  , network_views.delete_netdevice.as_view()      , name="delete_netdevice"),
    url("^create_net_ip$"     , network_views.create_net_ip.as_view()         , name="create_net_ip"),
    url("^delete_net_ip$"     , network_views.delete_net_ip.as_view()         , name="delete_net_ip"),
    url("^create_new_peer$"   , network_views.create_new_peer.as_view()       , name="create_new_peer"),
    url("^delete_peer$"       , network_views.delete_peer.as_view()           , name="delete_peer"),
    url("^get_valid_peers$"   , network_views.get_valid_peers.as_view()       , name="get_valid_peers"),
    url("^copy_network$"      , network_views.copy_network.as_view()          , name="copy_network"),
    url("^json_network$"      , network_views.json_network.as_view()          , name="json_network"),
    url("^cdnt$"              , network_views.get_domain_name_tree.as_view()  , name="domain_name_tree"),
    url("^mdtn$"              , network_views.move_domain_tree_node.as_view() , name="move_domain_tree_node"),
    url("^dtn_detail$"        , network_views.get_dtn_detail_form.as_view()   , name="dtn_detail_form"),
    url("^dtn_new$"           , network_views.create_new_dtn.as_view()        , name="create_new_dtn"),
    url("^delete_dtn$"        , network_views.delete_dtn.as_view()            , name="delete_dtn"),
)

monitoring_patterns = patterns(
    "initat.cluster.frontend",
    url("^setup$"              , monitoring_views.setup.as_view()            , name="setup"),
    url("^extsetupc$"          , monitoring_views.setup_cluster.as_view()    , name="setup_cluster"),
    url("^extsetupe$"          , monitoring_views.setup_escalation.as_view() , name="setup_escalation"),
    url("^create_command$"     , monitoring_views.create_command.as_view()   , name="create_command"),
    url("^delete_command$"     , monitoring_views.delete_command.as_view()   , name="delete_command"),
    url("^xml/dev_config$"     , monitoring_views.device_config.as_view()    , name="device_config"),
    url("^create_config$"      , monitoring_views.create_config.as_view()    , name="create_config"),
    url("^to_icinga$"          , monitoring_views.call_icinga.as_view()      , name="call_icinga"),
    url("^xml/read_part$"      , monitoring_views.fetch_partition.as_view()  , name="fetch_partition"),
    url("moncc_info$"          , monitoring_views.moncc_info.as_view()       , name="moncc_info"),
    url("^get_node_status"     , monitoring_views.get_node_status.as_view()  , name="get_node_status"),
    url("^get_node_config"     , monitoring_views.get_node_config.as_view()  , name="get_node_config"),
)

user_patterns = patterns(
    "initat.cluster.frontend",
    url("overview/$"                , user_views.overview.as_view()              , name="overview"),
    url("passwd/xml$"               , user_views.get_password_form.as_view()     , name="get_password_form"),
    url("sync$"                     , user_views.sync_users.as_view()            , name="sync_users"),
    url("^save_layout_state$"       , user_views.save_layout_state.as_view()     , name="save_layout_state"),
    url("^set_user_var$"            , user_views.set_user_var.as_view()          , name="set_user_var"),
    url("^get_user_var$"            , user_views.get_user_var.as_view()          , name="get_user_var"),
    url("^move_node$"               , user_views.move_node.as_view()             , name="move_node"),
    url("^group_detail$"            , user_views.group_detail.as_view()          , name="group_detail"),
    url("^user_detail$"             , user_views.user_detail.as_view()           , name="user_detail"),
    url("^get_object_permissions$"  , user_views.get_object_permissions.as_view(), name="get_object_permissions"),
    url("^change_obj_perm$"         , user_views.change_object_permission.as_view(), name="change_object_permission"),
    url("^account_info$"            , user_views.account_info.as_view()          , name="account_info"),
)

pack_patterns = patterns(
    "initat.cluster.frontend",
    url("overview/repo$"       , package_views.repo_overview.as_view()      , name="repo_overview"),
    # url("search/repo$"         , package_views.search_package.as_view()     , name="search_package"),
    # url("search/create"        , package_views.create_search.as_view()      , name="create_search"),
    # url("search/delete"        , package_views.delete_search.as_view()      , name="delete_search"),
    url("search/retry"         , package_views.retry_search.as_view()       , name="retry_search"),
    # url("search/search_result" , package_views.get_search_result.as_view()  , name="get_search_result"),
    url("search/use_package"   , package_views.use_package.as_view()        , name="use_package"),
    url("search/unuse_package" , package_views.unuse_package.as_view()      , name="unuse_package"),
    url("install"              , package_views.install.as_view()            , name="install"),
    url("refresh"              , package_views.refresh.as_view()            , name="refresh"),
    url("pack/add"             , package_views.add_package.as_view()        , name="add_package"),
    url("pack/remove"          , package_views.remove_package.as_view()     , name="remove_package"),
    url("pack/change"          , package_views.change_package.as_view()     , name="change_pdc"),
    url("pack/change_tstate"   , package_views.change_target_state.as_view(), name="change_target_state"),
    url("pack/change_pflag"    , package_views.change_package_flag.as_view(), name="change_package_flag"),
    url("pack/sync"            , package_views.synchronize.as_view()        , name="synchronize"),
    url("pack/get_status"      , package_views.get_pdc_status.as_view()     , name="get_pdc_status"),
)

main_patterns = patterns(
    "initat.cluster.frontend",
    url(r"index$" , main_views.index.as_view(), name="index"),
)

rrd_patterns = patterns(
    "initat.cluster.frontend",
    url(r"^dev_rrds$" , rrd_views.device_rrds.as_view(), name="device_rrds"),
    url(r"^graph_rrd$", rrd_views.graph_rrds.as_view() , name="graph_rrds"),
)

rpl = []
for obj_name in rest_views.REST_LIST:
    rpl.extend([
        url("^%s$" % (obj_name), getattr(rest_views, "%s_list" % (obj_name)).as_view(), name="%s_list" % (obj_name)),
        url("^%s/(?P<pk>[0-9]+)$" % (obj_name), getattr(rest_views, "%s_detail" % (obj_name)).as_view(), name="%s_detail" % (obj_name)),
    ])
rpl.extend([
    url("^device_tree$", rest_views.device_tree_list.as_view(), name="device_tree_list"),
    url("^device_tree/(?P<pk>[0-9]+)$", rest_views.device_tree_detail.as_view(), name="device_tree_detail"),
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
# rest_patterns = format_suffix_patterns(rest_patterns)

doc_patterns = patterns(
    "",
    url(r"^%s/(?P<path>.*)$" % (settings.REL_SITE_ROOT)    ,
        "django.views.static.serve", {
            "document_root" : os.path.join(settings.FILE_ROOT, "doc", "build", "html")
            }, name="show"),
)

my_url_patterns = patterns(
    "",
    # url(r"static/(?P<path>.*)$"        , "django.views.static.serve", {"document_root" : settings.MEDIA_ROOT}),
    url(r"^$"         , session_views.redirect_to_main.as_view()),
    url(r"^base/"     , include(base_patterns      , namespace="base")),
    url(r"^session/"  , include(session_patterns   , namespace="session")),
    url(r"^config/"   , include(config_patterns    , namespace="config")),
    url(r"^rms/"      , include(rms_patterns       , namespace="rms")),
    url(r"^main/"     , include(main_patterns      , namespace="main")),
    url(r"^device/"   , include(device_patterns    , namespace="device")),
    url(r"^network/"  , include(network_patterns   , namespace="network")),
    url(r"^nagios/"   , include(monitoring_patterns, namespace="mon")),
    url(r"^boot/"     , include(boot_patterns      , namespace="boot")),
    url(r"^setup/"    , include(setup_patterns     , namespace="setup")),
    url(r"^user/"     , include(user_patterns      , namespace="user")),
    url(r"^pack/"     , include(pack_patterns      , namespace="pack")),
    url(r"^rrd/"      , include(rrd_patterns       , namespace="rrd")),
    url(r"^doc/"      , include(doc_patterns       , namespace="doc")),
    url(r"^rest/"     , include(rest_patterns      , namespace="rest")),
)

url_patterns = patterns(
    "",
    # to show icinga logos in local debug mode
    url(r"icinga/images/logos/(?P<path>.*)$",
        "django.views.static.serve", {
            "document_root" : "/opt/icinga/share/images/logos",
            }
        ),
    url(r"^%s/media/frontend/(?P<path>.*)$" % (settings.REL_SITE_ROOT),
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
    url(r"^%s/graphs/(?P<path>.*)$" % (settings.REL_SITE_ROOT),
        "django.views.static.serve", {
            "document_root" : os.path.join(settings.FILE_ROOT, "graphs")
            }),
    url(r"^%s/" % (settings.REL_SITE_ROOT)                                , include(my_url_patterns)),
    url(r"^$", session_views.redirect_to_main.as_view()),
)
