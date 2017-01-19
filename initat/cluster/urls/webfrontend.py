# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2017 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#
""" url definitions for ICSW """

import os

import django.contrib.staticfiles.views
from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static

# from utkik.dispatch import url, include

from initat.cluster.frontend import rest_views, device_views, main_views, network_views, \
    monitoring_views, user_views, package_views, config_views, boot_views, session_views, rrd_views, \
    base_views, setup_views, doc_views, license_views, model_history_views, discovery_views, rms_views, \
    lic_views, auth_views, asset_views, report_views

# handler404 = main_views.index.as_view()
report_patterns = [
    url("^upload_report_gfx$", report_views.UploadReportGfx.as_view(), name="upload_report_gfx"),
    url("^get_report_gfx$", report_views.GetReportGfx.as_view(), name="get_report_gfx"),
    url("^generate_report_pdf$", report_views.GenerateReportPdf.as_view(), name="generate_report_pdf"),
    url("^get_progress$", report_views.GetProgress.as_view(), name="get_progress"),
    url("^get_report_data$", report_views.GetReportData.as_view(), name="get_report_data"),
    url("^report_data_available$", report_views.ReportDataAvailable.as_view(), name="report_data_available"),
    url("^generate_report_xlsx$", report_views.GenerateReportXlsx.as_view(), name="generate_report_xlsx"),
    url("^report_history_available$", report_views.ReportHistoryAvailable.as_view(), name="report_history_available"),
    url("^update_download_count$", report_views.UpdateDownloadCount.as_view(), name="update_download_count"),
]

asset_patterns = [
    url("^hidden_static_asset_template_type_manager$", asset_views.HiddenStaticAssetTemplateTypesManager.as_view(), name="hidden_static_asset_template_type_manager"),
    url("^asset_package_loader$", asset_views.AssetPackageLoader.as_view(), name="asset_package_loader"),
    url("^asset_batch_deleter$", asset_views.AssetBatchDeleter.as_view(), name="asset_batch_deleter"),
    url("^get_fieldvalues_for_template$", asset_views.GetFieldvaluesForTemplate.as_view(), name="get_fieldvalues_for_template"),
    url("^simple_asset_batch_loader$", asset_views.SimpleAssetBatchLoader.as_view(), name="simple_asset_batch_loader"),
    url("^get_assetbatch_list$", asset_views.AssetBatchViewSet.as_view({"get": "list"}), name="get_assetbatch_list"),
    url("^run_assetrun_for_device_now$", asset_views.AssetScanRunner.as_view(), name="run_assetrun_for_device_now"),
    url("^get_schedule_list$", asset_views.ScheduledRunViewSet.as_view({"get": "list"}), name="get_schedule_list"),
    url("^get_static_templates$", asset_views.StaticAssetTemplateViewSet.as_view({"get": "get_all"}), name="get_static_templates"),
    url("^get_static_template_refs$", asset_views.StaticAssetTemplateViewSet.as_view({"get": "get_refs"}), name="get_static_template_references"),
    url("^reorder_template_field$", asset_views.StaticAssetTemplateViewSet.as_view({"post": "reorder_fields"}), name="reorder_template_fields"),
    url("^copy_static_template$", asset_views.CopyStaticTemplate.as_view(), name="copy_static_template"),
    url(
        "^create_static_template$",
        asset_views.StaticAssetTemplateViewSet.as_view({"post": "create_template"}),
        name="create_static_asset_template"
    ),
    url(
        "^static_template/(?P<pk>[0-9]+$)",
        asset_views.StaticAssetTemplateViewSet.as_view({"delete": "delete_template"}),
        name="static_asset_template_detail"
    ),
    url(
        "^static_asset_template_field/(?P<pk>[0-9]+)$",
        asset_views.StaticAssetTemplateViewSet.as_view({"delete": "delete_field", "put": "store_field"}),
        name="static_asset_template_field_detail",
    ),
    url(
        "^static_asset_template_field$",
        asset_views.StaticAssetTemplateViewSet.as_view({"post": "create_field"}),
        name="static_asset_template_field_call",
    ),
    url(
        "^device_asset$",
        asset_views.DeviceStaticAssetViewSet.as_view({"post": "create_asset"}),
        name="device_asset_call",
    ),
    url(
        "^device_asset/(?P<pk>[0-9]+$)",
        asset_views.DeviceStaticAssetViewSet.as_view({"delete": "delete_asset"}),
        name="device_asset_detail"
    ),
    url(
        "^device_asset_field/(?P<pk>[0-9]+$)",
        asset_views.DeviceStaticAssetViewSet.as_view({"delete": "delete_field"}),
        name="device_asset_field_detail"
    ),
    url(
        "device_asset_post$", asset_views.DeviceAssetPost.as_view(), name="device_asset_post",
    ),
    url(
        "device_asset_add_unused$", asset_views.DeviceStaticAssetViewSet.as_view({"post": "add_unused"}),
        name="device_asset_add_unused",
    ),
]

session_patterns = [
    url(r"logout", session_views.session_logout.as_view(), name="logout"),
    url(r"login", session_views.session_login.as_view(), name="login"),
    url(r"expel", session_views.session_expel.as_view(), name="expel"),
    url(r"log_addons$", session_views.login_addons.as_view(), name="login_addons"),
    url(r"change_database$", session_views.change_database.as_view(), name="change_database"),
    url(r"get_authenticated_user$", session_views.UserView.as_view({"get": "get_user"}), name="get_authenticated_user"),
    url(r"get_csrf_token$", session_views.get_csrf_token.as_view(), name="get_csrf_token"),
    url(r"get_background_jobs$", session_views.BackgroundJobViewSet.as_view({"get": "get_bg_jobs"}), name="background_jobs"),
    url(r"get_theme_setup$", session_views.ThemeViewSet.as_view({"get": "get_all_themes"}), name="get_theme_setup"),
    url(r"register_rc$", session_views.RouteViewSet.as_view({"post": "register"}), name="register_rc"),
]

rms_patterns = [
    url(r"get_header_dict", rms_views.get_header_dict.as_view(), name="get_header_dict"),
    url(r"get_header_xml", rms_views.get_header_xml.as_view(), name="get_header_xml"),
    url(r"get_rms_current_json", rms_views.get_rms_current_json.as_view(), name="get_rms_current_json"),
    url(r"get_rms_done_json", rms_views.get_rms_done_json.as_view(), name="get_rms_done_json"),
    url(r"get_rms_jobinfo", rms_views.get_rms_jobinfo.as_view(), name="get_rms_jobinfo"),
    url(r"control_job", rms_views.control_job.as_view(), name="control_job"),
    url(r"control_queue", rms_views.control_queue.as_view(), name="control_queue"),
    url(r"get_file_content", rms_views.get_file_content.as_view(), name="get_file_content"),
    url(r"change_job_pri$", rms_views.change_job_priority.as_view(), name="change_job_priority"),
    # for liebherr
    url(r"job_list$", rms_views.RmsJobViewSet.as_view({"get": "simple_get"}), name="job_list"),
]

# license overview
lic_patterns = [
    url(r"license_liveview$", lic_views.license_liveview.as_view(), name="license_liveview"),
    url(r"get_license_overview_steps$", lic_views.get_license_overview_steps.as_view(),
        name="get_license_overview_steps"),
    url("^license_state_coarse_list$", lic_views.license_state_coarse_list.as_view(), name="license_state_coarse_list"),
    url("^license_version_state_coarse_list$", lic_views.license_version_state_coarse_list.as_view(),
        name="license_version_state_coarse_list"),
    url("^license_user_coarse_list$", lic_views.license_user_coarse_list.as_view(), name="license_user_coarse_list"),
    url("^license_device_coarse_list$", lic_views.license_device_coarse_list.as_view(),
        name="license_device_coarse_list"),
]


base_patterns = [
    url("^propagate_channel_message$", base_views.propagate_channel_message, name="propagate_channel_message"),
    url("^upload_loc_gfx$", base_views.upload_location_gfx.as_view(), name="upload_location_gfx"),
    url("^loc_gfx_thumbnail/(?P<id>\d+)/(?P<image_count>\d+)$", base_views.location_gfx_icon.as_view(),
        name="location_gfx_icon"),
    url("^loc_gfx_image/(?P<id>\d+)/(?P<image_count>\d+)$", base_views.location_gfx_image.as_view(),
        name="location_gfx_image"),
    url("^modify_loc_gfx$", base_views.modify_location_gfx.as_view(), name="modify_location_gfx"),
    url("^change_category", base_views.change_category.as_view(), name="change_category"),
    url("^prune_category_tree$", base_views.prune_category_tree.as_view(), name="prune_category_tree"),
    url("^check_delete_object$", base_views.CheckDeleteObject.as_view(), name="check_delete_object"),
    url("^add_delete_request$", base_views.AddDeleteRequest.as_view(), name="add_delete_request"),
    url("^check_deletion_status$", base_views.CheckDeletionStatus.as_view(), name="check_deletion_status"),
    url("^GetKpiSourceData$", base_views.GetKpiSourceData.as_view(), name="GetKpiSourceData"),
    url("^CalculateKpiPreview$", base_views.CalculateKpiPreview.as_view(), name="CalculateKpiPreview"),
    url("^CategoryReferences", base_views.CategoryReferences.as_view(), name="CategoryReferences"),
]

setup_patterns = [
    url(r"xml/validate", setup_views.validate_partition.as_view(), name="validate_partition"),
    url(r"xml/rescan_images", setup_views.scan_for_images.as_view(), name="rescan_images"),
    url(r"xml/use_image", setup_views.use_image.as_view(), name="use_image"),
    url(r"xml/rescan_kernels", setup_views.rescan_kernels.as_view(), name="rescan_kernels"),
    url(r"BuildImage", setup_views.BuildImage.as_view(), name="BuildImage"),
]

config_patterns = [
    url("^set_config$", config_views.alter_config.as_view(), name="alter_config"),
    url("^generate_config$", config_views.generate_config.as_view(), name="generate_config"),
    url("^download_config/(?P<hash>.*)$", config_views.download_configs.as_view(), name="download_configs"),
    url("^upload_config$", config_views.upload_config.as_view(), name="upload_config"),
    url("^xml/show_dev_vars", config_views.get_device_cvars.as_view(), name="get_device_cvars"),
    url("^xml/copy_mon$", config_views.copy_mon.as_view(), name="copy_mon"),
    url("^xml/delete_objects$", config_views.delete_objects.as_view(), name="delete_objects"),
    url("^get_cached_uploads$", config_views.get_cached_uploads.as_view(), name="get_cached_uploads"),
    url("^handle_cached_config$", config_views.handle_cached_config.as_view(), name="handle_cached_config"),
]

boot_patterns = [
    url("^xml/get_boot_infojs$", boot_views.get_boot_info_json.as_view(), name="get_boot_info_json"),
    url("^xml/get_devlog_info$", boot_views.get_devlog_info.as_view(), name="get_devlog_info"),
    url("^soft_control$", boot_views.soft_control.as_view(), name="soft_control"),
    url("^hard_control$", boot_views.hard_control.as_view(), name="hard_control"),
    url("^update_device$", boot_views.update_device.as_view(), name="update_device"),
    url("^update_device_settings/boot/(\d+)$", boot_views.update_device_bootsettings.as_view(), name="update_device_settings"),
    url("^modify_mbl$", boot_views.modify_mbl.as_view(), name="modify_mbl"),
]

device_patterns = [
    url("^device_task_ignore_toggle$", device_views.DeviceTaskIgnoreToggle.as_view(), name="device_task_ignore_toggle"),
    url("^device_log_entry_loader$", device_views.DeviceLogEntryLoader.as_view(), name="device_log_entry_loader"),
    url("^device_log_entry_count$", device_views.DeviceLogEntryCount.as_view(), name="device_log_entry_count"),
    url("^system_completion_ignore_toggle$", device_views.SystemCompletionIgnoreToggle.as_view(), name="system_completion_ignore_toggle"),
    url("^system_completion$", device_views.SystemCompletion.as_view(), name="system_completion"),
    url("^device_completion$", device_views.DeviceCompletion.as_view(), name="device_completion"),
    url("^simple_graph_setup$", device_views.SimpleGraphSetup.as_view(), name="simple_graph_setup"),
    # url("^device_tree$", device_views.device_tree.as_view(), name="tree"),
    # url("^device_tree_smart$", device_views.device_tree_smart.as_view(), name="tree_smart"),
    url("^select_parents$", device_views.select_parents.as_view(), name="select_parents"),
    url("^enrich_devices$", device_views.EnrichDevices.as_view(), name="enrich_devices"),
    url("^manual_connection", device_views.manual_connection.as_view(), name="manual_connection"),
    url("^change_devices$", device_views.change_devices.as_view(), name="change_devices"),
    url("^scan_device_network$", device_views.scan_device_network.as_view(), name="scan_device_network"),
    url("^get_device_locations$", device_views.get_device_location.as_view(), name="get_device_location"),
    url("^GetMatchingDevices$", device_views.GetMatchingDevices.as_view(), name="GetMatchingDevices"),
    url("^create_device", device_views.create_device.as_view(), name="create_device"),
    url("^device_list_info$", device_views.DeviceListInfo.as_view(), name="device_list_info"),
    url(
        "^device_variable_call$",
        device_views.DeviceVariableViewSet.as_view({"post": "create", "get": "get"}),
        name="device_variable_list",
    ),
    url(
        "^device_variable_call/(?P<pk>[0-9]+)$",
        device_views.DeviceVariableViewSet.as_view({"delete": "delete", "put": "store"}),
        name="device_variable_detail",
    ),
    url(
        "^device_variable_scope_call$",
        device_views.DeviceVariableScopeViewSet.as_view(
            {
                "get": "list",
                "post": "create_var_scope",
            }
        ),
        name="device_variable_scope_list",
    ),
    url(
        "^device_variable_scope_detail/(?P<pk>[0-9]+)$",
        device_views.DeviceVariableScopeViewSet.as_view(
            {
                "put": "update_var_scope",
            }
        ),
        name="device_variable_scope_detail",
    ),
    url(
        "^device_variable_scope_entry$",
        device_views.DeviceVariableScopeViewSet.as_view({"post": "create_entry"}),
        name="device_variable_scope_entry_list",
    ),
    url(
        "^device_variable_scope_dvs_detail/(?P<pk>[0-9]+)$",
        device_views.DeviceVariableScopeViewSet.as_view({"delete": "delete_entry", "put": "store_entry"}),
        name="device_variable_scope_entry_detail",
    ),
    url(
        "^device_class_call$",
        device_views.DeviceClassViewSet.as_view({"get": "list"}),
        name="device_class_list",
    ),
]


icsw_lic_patterns = [
    url("^get_all_licenses$", license_views.LicenseViewSet.as_view({"get": "get_all_licenses"}), name="get_all_licenses"),
    url("^get_ova_counter", license_views.LicenseViewSet.as_view({"get": "get_ova_counter"}), name="get_ova_counter"),
    url("^get_license_packages$", license_views.get_license_packages.as_view(), name="get_license_packages"),
    url("^GetLicenseViolations$", license_views.GetLicenseViolations.as_view(), name="GetLicenseViolations"),
    url("^GetValidLicenses$", license_views.GetValidLicenses.as_view(), name="GetValidLicenses"),
    url("^upload_license_file$", license_views.upload_license_file.as_view(), name="upload_license_file"),
]

network_patterns = [
    # url("^network$", network_views.show_cluster_networks.as_view(), name="show_networks"),
    # url("^dev_network$", network_views.device_network.as_view(), name="device_network"),
    url("^copy_network$", network_views.CopyNetwork.as_view(), name="copy_network"),
    url("^json_network$", network_views.JsonNetwork.as_view(), name="json_network"),
    # url("^cdnt$", network_views.get_domain_name_tree.as_view(), name="domain_name_tree"),
    url("^get_clusters$", network_views.GetNetworkClusters.as_view(), name="get_clusters"),
    url("^get_free_ip$", network_views.GetFreeIp.as_view(), name="get_free_ip"),
    url("^rescan_networks$", network_views.RescanNetworks.as_view(), name="rescan_networks"),
    url("^nmap_scan_data_loader$", network_views.NmapScanDataLoader.as_view(), name="nmap_scan_data_loader"),
    url("^nmap_scan_deleter$", network_views.NmapScanDeleter.as_view(), name="nmap_scan_deleter"),
    url("^nmap_scan_diff$", network_views.NmapScanDiffer.as_view(), name="nmap_scan_diff"),
    url("^handle_nmap_scan_device$", network_views.HandleNmapScanDevice.as_view(), name="handle_nmap_scan_device"),
]

monitoring_patterns = [
    url("^create_config$", monitoring_views.create_config.as_view(), name="create_config"),
    url("^fetch_dyn_config$", monitoring_views.fetch_dyn_config.as_view(), name="fetch_dyn_config"),
    # url("^setup$", monitoring_views.setup.as_view(), name="setup"),
    # url("^extsetupc$", monitoring_views.setup_cluster.as_view(), name="setup_cluster"),
    # url("^extsetupe$", monitoring_views.setup_escalation.as_view(), name="setup_escalation"),
    # url("^MonitoringHints$", monitoring_views.MonitoringHints.as_view(), name="MonitoringHints"),
    # url("^MonitoringDisk$", monitoring_views.MonitoringDisk.as_view(), name="MonitoringDisk"),
    # url("^xml/dev_config$", monitoring_views.device_config.as_view(), name="device_config"),
    url("^to_icinga$", monitoring_views.call_icinga.as_view(), name="call_icinga"),
    url("^xml/read_part$", monitoring_views.fetch_partition.as_view(), name="fetch_partition"),
    url("^xml/clear_part$", monitoring_views.clear_partition.as_view(), name="clear_partition"),
    url("^xml/use_part$", monitoring_views.use_partition.as_view(), name="use_partition"),
    url("^get_node_status", monitoring_views.NodeStatusViewSet.as_view({"post": "get_all"}), name="get_node_status"),
    url("^get_node_config", monitoring_views.get_node_config.as_view(), name="get_node_config"),
    # url("^build_info$", monitoring_views.build_info.as_view(), name="build_info"),
    # url("^overview$", monitoring_views.overview.as_view(), name="overview"),
    url("^resolve_name$", monitoring_views.resolve_name.as_view(), name="resolve_name"),
    url("^search_similar_name$", monitoring_views.search_similar_names.as_view(), name="search_similar_names"),
    url("^get_mon_vars$", monitoring_views.get_mon_vars.as_view(), name="get_mon_vars"),
    url("^get_hist_timespan$", monitoring_views.get_hist_timespan.as_view(), name="get_hist_timespan"),
    url("^get_hist_device_data$", monitoring_views.get_hist_device_data.as_view(), name="get_hist_device_data"),
    url("^get_hist_service_data$", monitoring_views.get_hist_service_data.as_view(), name="get_hist_service_data"),
    url("^get_hist_service_line_graph_data$", monitoring_views.get_hist_service_line_graph_data.as_view(),
        name="get_hist_service_line_graph_data"),
    url("^get_hist_device_line_graph_data$", monitoring_views.get_hist_device_line_graph_data.as_view(),
        name="get_hist_device_line_graph_data"),
    url("^get_mon_sys_info$", monitoring_views.SysInfoViewSet.as_view({"get": "get_all"}), name="get_mon_sys_info"),
    url("^get_build_info$", monitoring_views.BuildInfoViewSet.as_view({"get": "get_all"}), name="get_mon_build_info"),
    url("^toggle_sys_flag$", monitoring_views.toggle_sys_flag.as_view(), name="toggle_sys_flag"),
    url("^send_command$", monitoring_views.SendMonCommand.as_view(), name="send_mon_command"),
    url("^duplicate_dsspec$", monitoring_views.DuplicateDisplayPipe.as_view(), name="duplicate_dp_spec"),
    url("^all_icinga_cmds$", monitoring_views.AllIcingaCmds.as_view(), name="all_icinga_cmds"),
]

user_patterns = [
    url("sync$", user_views.sync_users.as_view(), name="sync_users"),
    url("^change_obj_perm$", user_views.change_object_permission.as_view(), name="change_object_permission"),
    url("^chdc$", user_views.clear_home_dir_created.as_view(), name="clear_home_dir_created"),
    url("^get_device_ip$", user_views.get_device_ip.as_view(), name="get_device_ip"),
    url("^GetGlobalPermissions$", user_views.GetGlobalPermissions.as_view(), name="GetGlobalPermissions"),
    url("^GetObjectPermissions$", user_views.GetObjectPermissions.as_view(), name="GetObjectPermissions"),
    url("^GetInitProduct$", user_views.GetInitProduct.as_view(), name="GetInitProduct"),
    url("^GetNumQuotaServers$", user_views.get_num_quota_servers.as_view(), name="get_num_quota_servers"),
    # not really needed right now
    url("^", include(user_views.local_router.urls)),
]

pack_patterns = [
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
]

main_patterns = [
    # url(r"^permission$", main_views.permissions_denied.as_view(), name="permission_denied"),
    url(r"^server_info$", main_views.get_server_info.as_view(), name="get_server_info"),
    url(r"^server_control$", main_views.server_control.as_view(), name="server_control"),
    url(r"^virtual_desktop_viewer$", main_views.virtual_desktop_viewer.as_view(), name="virtual_desktop_viewer"),
    url(r"^num_background_jobs$", main_views.get_number_of_background_jobs.as_view(), name="get_number_of_background_jobs"),
    # url(r"^routing_info$", "main_views.get_routing_info", name="routing_info"),
    url(r"^routing_info$", main_views.get_routing_info.as_view(), name="routing_info"),
    url(r"^get_cluster_info$", main_views.get_cluster_info.as_view(), name="get_cluster_info"),
    url(r"^get_docu_info$", main_views.get_docu_info.as_view(), name="get_docu_info"),
    url(r"^get_overall_style", main_views.get_overall_style.as_view(), name="get_overall_style"),
]

rrd_patterns = [
    url(r"^dev_rrds$", rrd_views.device_rrds.as_view(), name="device_rrds"),
    url(r"^graph_rrd$", rrd_views.graph_rrds.as_view(), name="graph_rrds"),
    url(r"^trigger_threshold", rrd_views.trigger_sensor_threshold.as_view(), name="trigger_sensor_threshold"),
    url(r"^download_graph/(?P<hash>.*)$", rrd_views.download_rrd.as_view(), name="download_rrd")
]

discovery_patterns = [
    # url(r"^Overview$", discovery_views.DiscoveryOverview.as_view(), name="Overview"),
    # url(r"^EventLogOverview$", discovery_views.EventLogOverview.as_view(), name="EventLogOverview"),
    url(r"^GetEventLog$", discovery_views.GetEventLog.as_view(), name="GetEventLog"),
    url(r"^GetEventLogDeviceInfo$", discovery_views.GetEventLogDeviceInfo.as_view(), name="GetEventLogDeviceInfo"),
    url(r"^dispatcher_link_loader$", discovery_views.DispatcherLinkLoader.as_view(), name="dispatcher_link_loader"),
    url(r"^dispatcher_link_syncer$", discovery_views.DispatcherLinkSyncer.as_view(), name="dispatcher_link_syncer"),
    url(r"^create_schedule_item$", discovery_views.ScheduleItemCreator.as_view(), name="create_schedule_item"),
]

auth_patterns = [
    url(r"^test/auth_user$", auth_views.auth_user.as_view(), name="auth_test"),
    url(r"^auth/do_login$", auth_views.do_login.as_view(), name="do_login"),
]

rpl = []
for src_mod, obj_name in rest_views.REST_LIST:
    is_camelcase = obj_name[0].lower() != obj_name[0] or (obj_name.startswith("icsw") and obj_name.lower() != obj_name)

    list_postfix = "List" if is_camelcase else "_list"
    detail_postfix = "Detail" if is_camelcase else "_detail"

    list_obj_name = "{}{}".format(obj_name, list_postfix)
    detail_obj_name = "{}{}".format(obj_name, detail_postfix)

    rpl.extend(
        [
            url("^{}$".format(obj_name), getattr(rest_views, list_obj_name).as_view(), name=list_obj_name),
            url("^{}/(?P<pk>[0-9]+)$".format(obj_name), getattr(rest_views, detail_obj_name).as_view(), name=detail_obj_name),
        ]
    )

rpl.extend([
    url("^device_tree$", rest_views.device_tree_list.as_view(), name="device_tree_list"),
    url("^device_tree/(?P<pk>[0-9]+)$", rest_views.device_tree_detail.as_view(), name="device_tree_detail"),
    url("^device_com_cap_list$", rest_views.device_com_capabilities.as_view(), name="device_com_capabilities"),
    url("^home_export_list$", rest_views.rest_home_export_list.as_view(), name="home_export_list"),
    url("^csw_object_list$", rest_views.csw_object_list.as_view({"get": "list"}), name="csw_object_list"),
    url("^used_peer_list$", rest_views.used_peer_list.as_view({"get": "list"}), name="used_peer_list"),
    url("^peerable_netdevice_list$", rest_views.peerable_netdevice_list.as_view({"get": "list"}), name="peerable_netdevice_list"),
    url("^min_access_levels$", rest_views.min_access_levels.as_view({"get": "list"}), name="min_access_levels"),
])

rest_patterns = rpl

dyndoc_patterns = [
    # "initat.cluster.frontend",
    # url(r"^hb/root$", doc_views.test_page.as_view(), name="doc_root"),
    # TODO: fix handbook prefix in accordance with actual handbook html
    url(r"^(?P<page>.*)$", doc_views.doc_page.as_view(), name="doc_page"),
]

doc_patterns = [
    url(
        r"^{}/(?P<path>.*)$".format(settings.REL_SITE_ROOT),
        django.contrib.staticfiles.views.serve,
        {
            "document_root": os.path.join(settings.FILE_ROOT, "doc", "build", "html")
        },
        name="show"
    ),
]

system_patterns = [
    url(
        r"^get_historical_data$",
        model_history_views.get_historical_data.as_view(),
        name="get_historical_data"
    ),
    url(
        r"^get_models_with_history$",
        model_history_views.get_models_with_history.as_view(),
        name="get_models_with_history"
    ),
]

my_url_patterns = [
    # "",
    # url(r"^$", session_views.redirect_to_main.as_view()),
    # redirect old entry point
    # url(r"^main.py$", session_views.redirect_to_main.as_view()),
    url(r"^base/", include(base_patterns, namespace="base")),
    url(r"^session/", include(session_patterns, namespace="session")),
    url(r"^config/", include(config_patterns, namespace="config")),
    url(r"^rms/", include(rms_patterns, namespace="rms")),
    url(r"^lic/", include(lic_patterns, namespace="lic")),
    url(r"^icsw_lic/", include(icsw_lic_patterns, namespace="icsw_lic")),
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
    url(r"^discovery/", include(discovery_patterns, namespace="discovery")),
    url(r"^asset/", include(asset_patterns, namespace="asset")),
    url(r"^report/", include(report_patterns, namespace="report")),
]

urlpatterns = [
    url(r"^{}/".format(settings.REL_SITE_ROOT), include(my_url_patterns)),
] + [
    url(r"^auth/", include(auth_patterns, namespace="auth")),
]

# urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
