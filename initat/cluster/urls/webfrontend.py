#!/usr/bin/python-init -Otu

from django.conf.urls import patterns, include, url
from django.conf import settings
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
import os
from initat.cluster.frontend import rest_views, device_views, main_views, network_views, \
    monitoring_views, user_views, package_views, config_views, boot_views, session_views, rrd_views, \
    base_views, setup_views, doc_views
from initat.cluster.rms import rms_views, lic_views
# from rest_framework.urlpatterns import format_suffix_patterns
from django.conf.urls.static import static

handler404 = main_views.index.as_view()

# Uncomment the next two lines to enable the admin:
# from django.contrib import admin
# admin.autodiscover()

session_patterns = patterns(
    "initat.cluster.frontend",
    url(r"logout", session_views.sess_logout.as_view(), name="logout"),
    url(r"login", session_views.sess_login.as_view(), name="login"),
)

rms_patterns = patterns(
    "initat.cluster.rms",
    url(r"overview", rms_views.overview.as_view(), name="overview"),
    url(r"get_header_xml", rms_views.get_header_xml.as_view(), name="get_header_xml"),
    url(r"get_rms_json", rms_views.get_rms_json.as_view(), name="get_rms_json"),
    url(r"get_rms_jobinfo", rms_views.get_rms_jobinfo.as_view(), name="get_rms_jobinfo"),
    url(r"get_node_info", rms_views.get_node_info.as_view(), name="get_node_info"),
    url(r"control_job", rms_views.control_job.as_view(), name="control_job"),
    url(r"control_queue", rms_views.control_queue.as_view(), name="control_queue"),
    url(r"get_file_content", rms_views.get_file_content.as_view(), name="get_file_content"),
    url(r"set_user_setting", rms_views.set_user_setting.as_view(), name="set_user_setting"),
    url(r"get_user_setting", rms_views.get_user_setting.as_view(), name="get_user_setting"),
    url(r"change_job_pri$", rms_views.change_job_priority.as_view(), name="change_job_priority"),
)

# license overview
lic_patterns = patterns(
    "initat.cluster.rms",
    url(r"overview$", lic_views.overview.as_view(), name="overview"),
    url(r"license_liveview$", lic_views.license_liveview.as_view(), name="license_liveview"),
    url(r"get_license_overview_steps$", lic_views.get_license_overview_steps.as_view(), name="get_license_overview_steps"),
    url("^license_state_coarse_list$", lic_views.license_state_coarse_list.as_view(), name="license_state_coarse_list"),
    url("^license_version_state_coarse_list$", lic_views.license_version_state_coarse_list.as_view(), name="license_version_state_coarse_list"),
    url("^license_user_coarse_list$", lic_views.license_user_coarse_list.as_view(), name="license_user_coarse_list"),
    url("^license_device_coarse_list$", lic_views.license_device_coarse_list.as_view(), name="license_device_coarse_list"),
)


base_patterns = patterns(
    "initat.cluster.setup",
    url("^get_gauge_info$", base_views.get_gauge_info.as_view(), name="get_gauge_info"),
    url("^get_cat_tree$", base_views.get_category_tree.as_view(), name="category_tree"),
    url("^upload_loc_gfx$", base_views.upload_location_gfx.as_view(), name="upload_location_gfx"),
    url("^loc_gfx_thumbnail/(?P<id>\d+)/(?P<image_count>\d+)$", base_views.location_gfx_icon.as_view(), name="location_gfx_icon"),
    url("^loc_gfx_image/(?P<id>\d+)/(?P<image_count>\d+)$", base_views.location_gfx_image.as_view(), name="location_gfx_image"),
    url("^modify_loc_gfx$", base_views.modify_location_gfx.as_view(), name="modify_location_gfx"),
    url("^change_category", base_views.change_category.as_view(), name="change_category"),
    url("^prune_cat_tree", base_views.prune_category_tree.as_view(), name="prune_categories"),
)

setup_patterns = patterns(
    "initat.cluster.setup",
    url(r"p_overview", setup_views.partition_overview.as_view(), name="partition_overview"),
    url(r"xml/validate", setup_views.validate_partition.as_view(), name="validate_partition"),
    url(r"i_overview", setup_views.image_overview.as_view(), name="image_overview"),
    url(r"k_overview", setup_views.kernel_overview.as_view(), name="kernel_overview"),
    url(r"xml/rescan_images", setup_views.scan_for_images.as_view(), name="rescan_images"),
    url(r"xml/use_image", setup_views.use_image.as_view(), name="use_image"),
    url(r"xml/rescan_kernels", setup_views.rescan_kernels.as_view(), name="rescan_kernels"),
)

config_patterns = patterns(
    "initat.cluster.frontend",
    url("^show_config$", config_views.show_configs.as_view(), name="show_configs"),
    url("^set_config_cb$", config_views.alter_config_cb.as_view(), name="alter_config_cb"),
    url("^generate_config$", config_views.generate_config.as_view(), name="generate_config"),
    url("^download_config/(?P<hash>.*)$", config_views.download_configs.as_view(), name="download_configs"),
    url("^upload_config$", config_views.upload_config.as_view(), name="upload_config"),
    url("^xml/show_dev_vars", config_views.get_device_cvars.as_view(), name="get_device_cvars"),
    url("^xml/copy_mon$", config_views.copy_mon.as_view(), name="copy_mon"),
    url("^xml/delete_objects$", config_views.delete_objects.as_view(), name="delete_objects"),
    url("^get_cached_uploads$", config_views.get_cached_uploads.as_view(), name="get_cached_uploads"),
    url("^handle_cached_config$", config_views.handle_cached_config.as_view(), name="handle_cached_config"),
)

boot_patterns = patterns(
    "initat.cluster.frontend",
    url("^show_boot$", boot_views.show_boot.as_view(), name="show_boot"),
    url("^xml/get_boot_infojs$", boot_views.get_boot_info_json.as_view(), name="get_boot_info_json"),
    url("^xml/get_devlog_info$", boot_views.get_devlog_info.as_view(), name="get_devlog_info"),
    url("^soft_control$", boot_views.soft_control.as_view(), name="soft_control"),
    url("^hard_control$", boot_views.hard_control.as_view(), name="hard_control"),
    url("^update_device/(\d+)$", boot_views.update_device.as_view(), name="update_device"),
)

device_patterns = patterns(
    "initat.cluster.frontend",
    # url("^device_tree$", device_views.device_tree.as_view(), name="tree"),
    url("^device_tree_smart$", device_views.device_tree_smart.as_view(), name="tree_smart"),
    url("^set_selection$", device_views.set_selection.as_view(), name="set_selection"),
    url("^config$", device_views.show_configs.as_view(), name="show_configs"),
    url("^connections", device_views.connections.as_view(), name="connections"),
    url("^manual_connection", device_views.manual_connection.as_view(), name="manual_connection"),
    url("^variables$", device_views.variables.as_view(), name="variables"),
    url("^change_devices$", device_views.change_devices.as_view(), name="change_devices"),
    url("^scan_device_network$", device_views.scan_device_network.as_view(), name="scan_device_network"),
    url("^device_info/(?P<device_pk>\d+)/(?P<mode>\S+)$", device_views.device_info.as_view(), name="device_info"),
    url("^get_device_locations$", device_views.get_device_location.as_view(), name="get_device_location"),
)

network_patterns = patterns(
    "initat.cluster.frontend",
    url("^network$", network_views.show_cluster_networks.as_view(), name="show_networks"),
    url("^dev_network$", network_views.device_network.as_view(), name="device_network"),
    url("^copy_network$", network_views.copy_network.as_view(), name="copy_network"),
    url("^json_network$", network_views.json_network.as_view(), name="json_network"),
    url("^cdnt$", network_views.get_domain_name_tree.as_view(), name="domain_name_tree"),
    url("^get_clusters$", network_views.get_network_clusters.as_view(), name="get_clusters"),
    url("^get_scans", network_views.get_active_scans.as_view(), name="get_active_scans"),
)

monitoring_patterns = patterns(
    "initat.cluster.frontend",
    url("^create_config$", monitoring_views.create_config.as_view(), name="create_config"),
    url("^setup$", monitoring_views.setup.as_view(), name="setup"),
    url("^extsetupc$", monitoring_views.setup_cluster.as_view(), name="setup_cluster"),
    url("^extsetupe$", monitoring_views.setup_escalation.as_view(), name="setup_escalation"),
    url("^xml/dev_config$", monitoring_views.device_config.as_view(), name="device_config"),
    url("^to_icinga$", monitoring_views.call_icinga.as_view(), name="call_icinga"),
    url("^xml/read_part$", monitoring_views.fetch_partition.as_view(), name="fetch_partition"),
    url("^xml/clear_part$", monitoring_views.clear_partition.as_view(), name="clear_partition"),
    url("^xml/use_part$", monitoring_views.use_partition.as_view(), name="use_partition"),
    url("^get_node_status", monitoring_views.get_node_status.as_view(), name="get_node_status"),
    url("^get_node_config", monitoring_views.get_node_config.as_view(), name="get_node_config"),
    url("^build_info$", monitoring_views.build_info.as_view(), name="build_info"),
    url("^livestatus$", monitoring_views.livestatus.as_view(), name="livestatus"),
    url("^overview$", monitoring_views.overview.as_view(), name="overview"),
    url("^create_device$", monitoring_views.create_device.as_view(), name="create_device"),
    url("^resolve_name$", monitoring_views.resolve_name.as_view(), name="resolve_name"),
    url("^delete_hint$", monitoring_views.delete_hint.as_view(), name="delete_hint"),
    url("^get_mon_vars$", monitoring_views.get_mon_vars.as_view(), name="get_mon_vars"),
    url("^get_hist_timespan$", monitoring_views.get_hist_timespan.as_view(), name="get_hist_timespan"),
    url("^get_hist_device_data$", monitoring_views.get_hist_device_data.as_view(), name="get_hist_device_data"),
    url("^get_hist_service_data$", monitoring_views.get_hist_service_data.as_view(), name="get_hist_service_data"),
    url("^get_hist_service_line_graph_data$", monitoring_views.get_hist_service_line_graph_data.as_view(),
        name="get_hist_service_line_graph_data"),
    url("^get_hist_device_line_graph_data$", monitoring_views.get_hist_device_line_graph_data.as_view(),
        name="get_hist_device_line_graph_data"),
    url("^svg_to_png$", monitoring_views.svg_to_png.as_view(), name="svg_to_png"),
    url("^fetch_png/(?P<cache_key>\S+)$", monitoring_views.fetch_png_from_cache.as_view(), name="fetch_png_from_cache"),

)

user_patterns = patterns(
    "initat.cluster.frontend",
    url("overview/$", user_views.overview.as_view(), name="overview"),
    url("sync$", user_views.sync_users.as_view(), name="sync_users"),
    url("^set_user_var$", user_views.set_user_var.as_view(), name="set_user_var"),
    url("^get_user_var$", user_views.get_user_var.as_view(), name="get_user_var"),
    url("^change_obj_perm$", user_views.change_object_permission.as_view(), name="change_object_permission"),
    url("^account_info$", user_views.account_info.as_view(), name="account_info"),
    url("^global_settings$", user_views.global_settings.as_view(), name="global_settings"),
    url("^background_info$", user_views.background_job_info.as_view(), name="background_job_info"),
    url("^chdc$", user_views.clear_home_dir_created.as_view(), name="clear_home_dir_created"),
    url("^get_device_ip$", user_views.get_device_ip.as_view(), name="get_device_ip"),
    url("^get_historic_user$", user_views.get_historic_user.as_view(), name="get_historic_user"),
)

pack_patterns = patterns(
    "initat.cluster.frontend",
    url("overview/repo$", package_views.repo_overview.as_view(), name="repo_overview"),
    url("search/retry", package_views.retry_search.as_view(), name="retry_search"),
    url("search/use_package", package_views.use_package.as_view(), name="use_package"),
    url("search/unuse_package", package_views.unuse_package.as_view(), name="unuse_package"),
    # url("install"              , package_views.install.as_view()            , name="install"),
    # url("refresh"              , package_views.refresh.as_view()            , name="refresh"),
    url("pack/add", package_views.add_package.as_view(), name="add_package"),
    url("pack/remove", package_views.remove_package.as_view(), name="remove_package"),
    url("pack/change", package_views.change_package.as_view(), name="change_pdc"),
    url("pack/change_tstate", package_views.change_target_state.as_view(), name="change_target_state"),
    url("pack/change_pflag", package_views.change_package_flag.as_view(), name="change_package_flag"),
    url("pack/sync", package_views.synchronize.as_view(), name="synchronize"),
    url("pack/get_status", package_views.get_pdc_status.as_view(), name="get_pdc_status"),
)

main_patterns = patterns(
    "initat.cluster.frontend",
    url(r"^index$", main_views.index.as_view(), name="index"),
    url(r"^permission$", main_views.permissions_denied.as_view(), name="permission_denied"),
    url(r"^info$", main_views.info_page.as_view(), name="info_page"),
    url(r"^server_info$", main_views.get_server_info.as_view(), name="get_server_info"),
    url(r"^server_control$", main_views.server_control.as_view(), name="server_control"),
    url(r"^virtual_desktop_viewer$", main_views.virtual_desktop_viewer.as_view(), name="virtual_desktop_viewer"),
)

rrd_patterns = patterns(
    "initat.cluster.frontend",
    url(r"^dev_rrds$", rrd_views.device_rrds.as_view(), name="device_rrds"),
    url(r"^graph_rrd$", rrd_views.graph_rrds.as_view(), name="graph_rrds"),
    url(r"^merge_cd$", rrd_views.merge_cds.as_view(), name="merge_cds"),
)

rpl = []
for src_mod, obj_name in rest_views.REST_LIST:
    is_camelcase = obj_name[0].lower() != obj_name[0]

    list_postfix = "List" if is_camelcase else "_list"
    detail_postfix = "Detail" if is_camelcase else "_detail"

    list_obj_name = "{}{}".format(obj_name, list_postfix)
    detail_obj_name = "{}{}".format(obj_name, detail_postfix)

    rpl.extend([
        url("^%s$" % (obj_name), getattr(rest_views, list_obj_name).as_view(), name=list_obj_name),
        url("^%s/(?P<pk>[0-9]+)$" % (obj_name), getattr(rest_views, detail_obj_name).as_view(), name=detail_obj_name),
    ])
rpl.extend([
    url("^device_tree$", rest_views.device_tree_list.as_view(), name="device_tree_list"),
    url("^device_tree/(?P<pk>[0-9]+)$", rest_views.device_tree_detail.as_view(), name="device_tree_detail"),
    url("^device_selection$", rest_views.device_selection_list.as_view(), name="device_selection_list"),
    url("^home_export_list$", rest_views.rest_home_export_list.as_view(), name="home_export_list"),
    url("^csw_object_list$", rest_views.csw_object_list.as_view({"get": "list"}), name="csw_object_list"),
    url("^netdevice_peer_list$", rest_views.netdevice_peer_list.as_view({"get": "list"}), name="netdevice_peer_list"),
    url("^min_access_levels$", rest_views.min_access_levels.as_view({"get": "list"}), name="min_access_levels"),
])

rest_patterns = patterns(
    "initat.cluster.frontend",
    *rpl
)
# rest_patterns = format_suffix_patterns(rest_patterns)

dyndoc_patterns = patterns(
    "initat.cluster.frontend",
    url(r"^hb/root$", doc_views.test_page.as_view(), name="doc_root"),
    url(r"^hb/(?P<page>.*)$", doc_views.doc_page.as_view(), name="doc_page"),
)

doc_patterns = patterns(
    "",
    url(r"^{}/(?P<path>.*)$".format(settings.REL_SITE_ROOT),
        "django.views.static.serve", {
            "document_root": os.path.join(settings.FILE_ROOT, "doc", "build", "html")
        }, name="show"),
)

system_patterns = patterns(
    "initat.cluster.frontend",
    url(r"^history_overview$", user_views.history_overview.as_view(), name="history_overview"),
    url(r"^get_historical_data$", user_views.get_historical_data.as_view(), name="get_historical_data"),
)

my_url_patterns = patterns(
    "",
    url(r"^$", session_views.redirect_to_main.as_view()),
    # redirect old entry point
    url(r"^main.py$", session_views.redirect_to_main.as_view()),
    url(r"^base/", include(base_patterns, namespace="base")),
    url(r"^session/", include(session_patterns, namespace="session")),
    url(r"^config/", include(config_patterns, namespace="config")),
    url(r"^rms/", include(rms_patterns, namespace="rms")),
    url(r"^lic/", include(lic_patterns, namespace="lic")),
    url(r"^main/", include(main_patterns, namespace="main")),
    url(r"^device/", include(device_patterns, namespace="device")),
    url(r"^network/", include(network_patterns, namespace="network")),
    url(r"^mon/", include(monitoring_patterns, namespace="mon")),
    url(r"^boot/", include(boot_patterns, namespace="boot")),
    url(r"^setup/", include(setup_patterns, namespace="setup")),
    url(r"^user/", include(user_patterns, namespace="user")),
    url(r"^pack/", include(pack_patterns, namespace="pack")),
    url(r"^rrd/", include(rrd_patterns, namespace="rrd")),
    url(r"^doc/", include(doc_patterns, namespace="doc")),
    url(r"^dyndoc/", include(dyndoc_patterns, namespace="dyndoc")),
    url(r"^rest/", include(rest_patterns, namespace="rest")),
    url(r"^system/", include(system_patterns, namespace="system")),
)

url_patterns = patterns(
    "",
    url(r"^%s/" % (settings.REL_SITE_ROOT), include(my_url_patterns)),
    url(r"^$", session_views.redirect_to_main.as_view()),
)

url_patterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
url_patterns += patterns(
    'django.contrib.staticfiles.views',
    url(r'^{}/static/(?P<path>.*)$'.format(settings.REL_SITE_ROOT), 'serve'),
)
