# Copyright (C) 2012-2015 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License Version 2 as
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
{% load staticfiles %}

# Naming conventions
#
#- where possible use CamelCase
#- controllers end with "Ctrl"
#- module names start with "icsw.", separation with dots (no CamelCase)
#- second part is the name of the directory
#- then the (optional) functionality (for example icsw.device.network)
#- directives use '-' as separator, CamelCase in code
#- service, provider and factory names end with service, provider, factory and also use CamelCase
#
#Directory setup
#
#- below templates
#- top level equals the second part of the module name
#- second level (optional) for functionality (icsw.device.network -> templates/device/network/ )
#- shared functions in utils.{function} (app icsw.utils) [init.csw.filters -> icsw.utils.filters]
#
#File separation inside directories
#
#- one or more file(s) for HTML and cs / js code
#- no templates in coffeescript files
#- templates in .html via script type=ng-template/script
#- name of templates start with the name of the module with underscores, ending is ".html"
#- no root. bindings

ics_app = angular.module(
    "icsw.app",
    [
        "ngResource",
        "ngCookies",
        "ngSanitize",
        "ui.bootstrap",
        "ui.router",
        "restangular",
        "blockUI",
        "toaster",
        "init.csw.filters",
        "icsw.tools.tree",
        "icsw.layout.menu",
        "icsw.layout.sidebar",
        "icsw.network",
        "icsw.tools",
        "icsw.login",
        "icsw.layout.routing",
        "icsw.user",
        "icsw.user.password",
        "icsw.user.dashboard",
        "icsw.user.settings",
        "icsw.rrd.graph",
        "icsw.info.background",
        "icsw.server.info",
        "icsw.config.config",
        "icsw.config.generate",
        "icsw.device.variables",
        "icsw.device.info",
        "icsw.device.tree",
        "icsw.config.category_tree",
        "icsw.config.domain_name_tree",
        "icsw.device.network",
        "icsw.device.configuration",
        "icsw.device.connection",
        "icsw.device.category",
        "icsw.device.livestatus",
        "icsw.device.monconfig",
        "icsw.device.location",
        "icsw.device.status_history",
        "icsw.device.partition",
        "icsw.license.overview"
        "icsw.monitoring.overview",
        "icsw.monitoring.monitoring_basic",
        "icsw.monitoring.device",
        "icsw.monitoring.cluster",
        "icsw.monitoring.escalation",
        "icsw.monitoring.build_info",
        "icsw.package.install",
        "icsw.device.boot",
        "icsw.device.create",
        "icsw.config.kernel",
        "icsw.config.kpi",
        "icsw.config.image",
        "icsw.config.partition_table",
        "icsw.rms",
        {% for app in ADDITIONAL_ANGULAR_APPS %}
        "{{ app }}",
        {% endfor %}
    ]
).config(() ->
    # console.log "config"
).config(["blockUIConfig", (blockUIConfig) ->
    blockUIConfig.delay = 0
    blockUIConfig.message = "Loading, please wait ..."
    blockUIConfig.autoBlock = false
    blockUIConfig.autoInjectBodyBlock = false
]).constant("ICSW_URLS", {
    {% with "images/product/"|add:settings.INIT_PRODUCT_NAME|lower|add:"-flat-trans.png" as gfx_name %}
    "MENU_GFX_URL": "{% static gfx_name %}"
    {% endwith %}
    {% with "images/product/"|add:settings.INIT_PRODUCT_NAME|lower|add:"-trans.png" as gfx_name %}
    "MENU_GFX_BIG_URL": "{% static gfx_name %}"
    {% endwith %}
    "D3_MIN_JS": "{% static 'js/d3js/d3.min.js' %}"
    "DIMPLE_MIN_JS": "{% static 'js/dimple.v2.1.0.min.js' %}"
    "ADMIN_INDEX": "{% url 'admin:index' %}"
    "BASE_CATEGORY_TREE": "{% url 'base:category_tree' %}"
    "BASE_CHANGE_CATEGORY": "{% url 'base:change_category' %}"
    "BASE_GET_GAUGE_INFO": "{% url 'base:get_gauge_info' %}"
    "BASE_MODIFY_LOCATION_GFX": "{% url 'base:modify_location_gfx' %}"
    "BASE_PRUNE_CATEGORIES": "{% url 'base:prune_categories' %}"
    "BASE_UPLOAD_LOCATION_GFX": "{% url 'base:upload_location_gfx' %}"
    "BOOT_GET_BOOT_INFO_JSON": "{% url 'boot:get_boot_info_json' %}"
    "BOOT_GET_DEVLOG_INFO": "{% url 'boot:get_devlog_info' %}"
    "BOOT_HARD_CONTROL": "{% url 'boot:hard_control' %}"
    "BOOT_SHOW_BOOT": "{% url 'boot:show_boot' %}"
    "BOOT_SOFT_CONTROL": "{% url 'boot:soft_control' %}"
    "BOOT_UPDATE_DEVICE": "{% url 'boot:update_device' 1 %}"
    "CONFIG_COPY_MON": "{% url 'config:copy_mon' %}"
    "CONFIG_ALTER_CONFIG_CB": "{% url 'config:alter_config_cb' %}"
    "CONFIG_DELETE_OBJECTS": "{% url 'config:delete_objects' %}"
    "CONFIG_DOWNLOAD_CONFIGS": "{% url 'config:download_configs' 1 %}"
    "CONFIG_GENERATE_CONFIG": "{% url 'config:generate_config' %}"
    "CONFIG_GET_CACHED_UPLOADS": "{% url 'config:get_cached_uploads' %}"
    "CONFIG_GET_DEVICE_CVARS": "{% url 'config:get_device_cvars' %}"
    "CONFIG_HANDLE_CACHED_CONFIG": "{% url 'config:handle_cached_config' %}"
    "CONFIG_KPI": "{% url 'config:kpi' %}"
    "CONFIG_SHOW_CONFIGS": "{% url 'config:show_configs' %}"
    "CONFIG_UPLOAD_CONFIG": "{% url 'config:upload_config' %}"
    "DEVICE_CHANGE_DEVICES": "{% url 'device:change_devices' %}"
    "DEVICE_CONNECTIONS": "{% url 'device:connections' %}"
    "DEVICE_GET_DEVICE_LOCATION": "{% url 'device:get_device_location' %}"
    "DEVICE_MANUAL_CONNECTION": "{% url 'device:manual_connection' %}"
    "DEVICE_SCAN_DEVICE_NETWORK": "{% url 'device:scan_device_network' %}"
    "DEVICE_SET_SELECTION": "{% url 'device:set_selection' %}"
    "DEVICE_SHOW_CONFIGS": "{% url 'device:show_configs' %}"
    "DEVICE_TREE_SMART": "{% url 'device:tree_smart' %}"
    "DEVICE_VARIABLES": "{% url 'device:variables' %}"
    "DYNDOC_PAGE_X": "{% url 'dyndoc:doc_page' 'x' %}"
    "INFO_PAGE": "{% url 'main:info_page' %}"
    "LIC_GET_LICENSE_OVERVIEW_STEPS": "{% url 'lic:get_license_overview_steps' %}"
    "LIC_LICENSE_DEVICE_COARSE_LIST": "{% url 'lic:license_device_coarse_list' %}"
    "LIC_LICENSE_LIVEVIEW": "{% url 'lic:license_liveview' %}"
    "LIC_LICENSE_STATE_COARSE_LIST": "{% url 'lic:license_state_coarse_list' %}"
    "LIC_LICENSE_USER_COARSE_LIST": "{% url 'lic:license_user_coarse_list' %}"
    "LIC_LICENSE_VERSION_STATE_COARSE_LIST": "{% url 'lic:license_version_state_coarse_list' %}"
    "LIC_OVERVIEW": "{% url 'lic:overview' %}"
    "MAIN_GET_SERVER_INFO": "{% url 'main:get_server_info' %}"
    "MAIN_INDEX":  "{% url 'main:index' %}"
    "MAIN_SERVER_CONTROL": "{% url 'main:server_control' %}"
    "MAIN_VIRTUAL_DESKTOP_VIEWER": "{% url 'main:virtual_desktop_viewer' %}"
    "MON_BUILD_INFO": "{% url 'mon:build_info' %}"
    "MON_CALL_ICINGA": "{% url 'mon:call_icinga' %}"
    "MON_CLEAR_PARTITION": "{% url 'mon:clear_partition' %}"
    "MON_CREATE_CONFIG": "{% url 'mon:create_config' %}"
    "MON_CREATE_DEVICE": "{% url 'mon:create_device' %}"
    "MON_DELETE_HINT": "{% url 'mon:delete_hint' %}"
    "MON_DEVICE_CONFIG": "{% url 'mon:device_config' %}"
    "MON_FETCH_PARTITION": "{% url 'mon:fetch_partition' %}"
    "MON_FETCH_PNG_FROM_CACHE": "{% url 'mon:fetch_png_from_cache' 0 %}"
    "MON_GET_HIST_DEVICE_DATA": "{% url 'mon:get_hist_device_data' %}"
    "MON_GET_HIST_SERVICE_DATA": "{% url 'mon:get_hist_service_data' %}"
    "MON_GET_HIST_SERVICE_LINE_GRAPH_DATA": "{% url 'mon:get_hist_service_line_graph_data' %}"
    "MON_GET_HIST_DEVICE_LINE_GRAPH_DATA": "{% url 'mon:get_hist_device_line_graph_data' %}"
    "MON_GET_HIST_TIMESPAN": "{% url 'mon:get_hist_timespan' %}"
    "MON_GET_MON_VARS": "{% url 'mon:get_mon_vars' %}"
    "MON_GET_NODE_CONFIG": "{% url 'mon:get_node_config' %}"
    "MON_GET_NODE_STATUS": "{% url 'mon:get_node_status' %}"
    "MON_LIVESTATUS": "{% url 'mon:livestatus' %}"
    "MON_OVERVIEW": "{% url 'mon:overview' %}"
    "MON_RESOLVE_NAME": "{% url 'mon:resolve_name' %}"
    "MON_SETUP_CLUSTER": "{% url 'mon:setup_cluster' %}"
    "MON_SETUP_ESCALATION": "{% url 'mon:setup_escalation' %}"
    "MON_SETUP": "{% url 'mon:setup' %}"
    "MON_SVG_TO_PNG": "{% url 'mon:svg_to_png' %}"
    "MON_USE_PARTITION": "{% url 'mon:use_partition' %}"
    "NETWORK_COPY_NETWORK": "{% url 'network:copy_network' %}"
    "NETWORK_DEVICE_NETWORK": "{% url 'network:device_network' %}"
    "NETWORK_DOMAIN_NAME_TREE": "{% url 'network:domain_name_tree' %}"
    "NETWORK_GET_ACTIVE_SCANS": "{% url 'network:get_active_scans' %}"
    "NETWORK_GET_CLUSTERS": "{% url 'network:get_clusters' %}"
    "NETWORK_JSON_NETWORK": "{% url 'network:json_network' %}"
    "NETWORK_SHOW_NETWORKS": "{% url 'network:show_networks' %}"
    "PACK_ADD_PACKAGE": "{% url 'pack:add_package' %}"
    "PACK_CHANGE_PDC": "{% url 'pack:change_pdc' %}"
    "PACK_REMOVE_PACKAGE": "{% url 'pack:remove_package' %}"
    "PACK_REPO_OVERVIEW": "{% url 'pack:repo_overview' %}"
    "PACK_RETRY_SEARCH": "{% url 'pack:retry_search' %}"
    "PACK_USE_PACKAGE": "{% url 'pack:use_package' %}"
    "REST_ARCHITECTURE_LIST": "{% url 'rest:architecture_list' %}"
    "REST_BACKGROUND_JOB_LIST": "{% url 'rest:background_job_list' %}"
    "REST_CATEGORY_DETAIL": "{% url 'rest:category_detail' 1 %}"
    "REST_CATEGORY_LIST": "{% url 'rest:category_list' %}"
    "REST_CD_CONNECTION_DETAIL": "{% url 'rest:cd_connection_detail' 1 %}"
    "REST_CD_CONNECTION_LIST": "{% url 'rest:cd_connection_list' %}"
    "REST_CLUSTER_LICENSE_DETAIL": "{% url 'rest:cluster_license_detail' 1 %}"
    "REST_CLUSTER_LICENSE_LIST": "{% url 'rest:cluster_license_list' %}"
    "REST_CONFIG_BLOB_DETAIL": "{% url 'rest:config_blob_detail' 1 %}"
    "REST_CONFIG_BOOL_DETAIL": "{% url 'rest:config_bool_detail' 1 %}"
    "REST_CONFIG_BOOL_LIST": "{% url 'rest:config_bool_list'%}"
    "REST_CONFIG_CATALOG_DETAIL": "{% url 'rest:config_catalog_detail' 1 %}"
    "REST_CONFIG_CATALOG_LIST": "{% url 'rest:config_catalog_list' %}"
    "REST_CONFIG_DETAIL": "{% url 'rest:config_detail' 1 %}"
    "REST_CONFIG_HINT_LIST": "{% url 'rest:config_hint_list' %}"
    "REST_CONFIG_INT_DETAIL": "{% url 'rest:config_int_detail' 1 %}"
    "REST_CONFIG_INT_LIST": "{% url 'rest:config_int_list'%}"
    "REST_CONFIG_LIST": "{% url 'rest:config_list' %}"
    "REST_CONFIG_SCRIPT_DETAIL": "{% url 'rest:config_script_detail' 1 %}"
    "REST_CONFIG_SCRIPT_LIST": "{% url 'rest:config_script_list'%}"
    "REST_CONFIG_STR_DETAIL": "{% url 'rest:config_str_detail' 1 %}"
    "REST_CONFIG_STR_LIST": "{% url 'rest:config_str_list'%}"
    "REST_CSW_OBJECT_LIST": "{% url 'rest:csw_object_list' %}"
    "REST_CSW_PERMISSION_LIST": "{% url 'rest:csw_permission_list' %}"
    "REST_DEVICE_GROUP_LIST": "{% url 'rest:device_group_list' %}"
    "REST_DEVICE_DETAIL": "{% url 'rest:device_detail' 1 %}"
    "REST_DEVICE_LIST": "{% url 'rest:device_list' %}"
    "REST_DEVICE_MON_LOCATION_DETAIL": "{% url 'rest:device_mon_location_detail' 1 %}"
    "REST_DEVICE_MON_LOCATION_LIST": "{% url 'rest:device_mon_location_list' %}"
    "REST_DEVICE_SELECTION_LIST": "{% url 'rest:device_selection_list' %}"
    "REST_DEVICE_TREE_LIST": "{% url 'rest:device_tree_list' %}"
    "REST_DEVICE_TREE_DETAIL": "{% url 'rest:device_tree_detail' 1 %}"
    "REST_DEVICE_TYPE_LIST": "{% url 'rest:device_type_list' %}"
    "REST_DEVICE_VARIABLE_DETAIL": "{% url 'rest:device_variable_detail' 1 %}"
    "REST_DEVICE_VARIABLE_LIST": "{% url 'rest:device_variable_list' %}"
    "REST_DOMAIN_TREE_NODE_DETAIL": "{% url 'rest:domain_tree_node_detail' 1 %}"
    "REST_DOMAIN_TREE_NODE_LIST": "{% url 'rest:domain_tree_node_list' %}"
    "REST_EXT_LICENSE_LIST": "{% url 'rest:ext_license_list' %}"
    "REST_GROUP_DETAIL": "{% url 'rest:group_detail' 1 %}"
    "REST_GROUP_LIST": "{% url 'rest:group_list' %}"
    "REST_GROUP_OBJECT_PERMISSION_DETAIL": "{% url 'rest:group_object_permission_detail' 1 %}"
    "REST_GROUP_PERMISSION_DETAIL": "{% url 'rest:group_permission_detail' 1 %}"
    "REST_GROUP_PERMISSION_LIST": "{% url 'rest:group_permission_list' %}"
    "REST_HOME_EXPORT_LIST": "{% url 'rest:home_export_list' %}"
    "REST_HOST_CHECK_COMMAND_LIST": "{% url 'rest:host_check_command_list' %}"
    "REST_QUOTA_CAPABLE_BLOCKDEVICE_LIST": "{% url 'rest:quota_capable_blockdevice_list' %}"
    "REST_IMAGE_LIST": "{% url 'rest:image_list' %}"
    "REST_KERNEL_LIST": "{% url 'rest:kernel_list' %}"
    "REST_KPI_LIST": "{% url 'rest:kpi_list' %}"
    "REST_KPI_SELECTED_DEVICE_MONITORING_CATEGORY_TUPLE": "{% url 'rest:kpi_selected_device_monitoring_category_tuple_list' %}"
    "REST_LOCATION_GFX_DETAIL": "{% url 'rest:location_gfx_detail' 1 %}"
    "REST_LOCATION_GFX_LIST": "{% url 'rest:location_gfx_list' %}"
    "REST_LOG_SOURCE_LIST": "{% url 'rest:LogSourceList' %}"
    "REST_LOG_LEVEL_LIST": "{% url 'rest:LogLevelList' %}"
    "REST_MACBOOTLOG_LIST": "{% url 'rest:macbootlog_list' %}"
    "REST_MIN_ACCESS_LEVELS": "{% url 'rest:min_access_levels' %}"
    "REST_MON_CHECK_COMMAND_DETAIL": "{% url 'rest:mon_check_command_detail' 1 %}"
    "REST_MON_CHECK_COMMAND_LIST": "{% url 'rest:mon_check_command_list'%}"
    "REST_MON_CHECK_COMMAND_SPECIAL_LIST": "{% url 'rest:mon_check_command_special_list' %}"
    "REST_MON_CONTACT_LIST": "{% url 'rest:mon_contact_list' %}"
    "REST_MON_CONTACTGROUP_LIST": "{% url 'rest:mon_contactgroup_list' %}"
    "REST_MON_DEVICE_ESC_TEMPL_LIST": "{% url 'rest:mon_device_esc_templ_list' %}"
    "REST_MON_DEVICE_TEMPL_LIST": "{% url 'rest:mon_device_templ_list' %}"
    "REST_MON_DIST_MASTER_LIST": "{% url 'rest:mon_dist_master_list' %}"
    "REST_MON_DIST_SLAVE_LIST": "{% url 'rest:mon_dist_slave_list' %}"
    "REST_MON_EXT_HOST_LIST": "{% url 'rest:mon_ext_host_list' %}"
    "REST_MON_HOST_CLUSTER_LIST": "{% url 'rest:mon_host_cluster_list' %}"
    "REST_MON_HOST_DEPENDENCY_LIST": "{% url 'rest:mon_host_dependency_list' %}"
    "REST_MON_HOST_DEPENDENCY_TEMPL_LIST": "{% url 'rest:mon_host_dependency_templ_list' %}"
    "REST_MON_NOTIFICATION_LIST": "{% url 'rest:mon_notification_list' %}"
    "REST_MON_PERIOD_LIST": "{% url 'rest:mon_period_list' %}"
    "REST_MON_SERVICE_TEMPL_LIST": "{% url 'rest:mon_service_templ_list' %}"
    "REST_MON_SERVICE_CLUSTER_LIST": "{% url 'rest:mon_service_cluster_list' %}"
    "REST_MON_SERVICE_DEPENDENCY_LIST": "{% url 'rest:mon_service_dependency_list' %}"
    "REST_MON_SERVICE_DEPENDENCY_TEMPL_LIST": "{% url 'rest:mon_service_dependency_templ_list' %}"
    "REST_MON_SERVICE_ESC_TEMPL_LIST": "{% url 'rest:mon_service_esc_templ_list' %}"
    "REST_MONITORING_HINT_DETAIL": "{% url 'rest:monitoring_hint_detail' 1 %}"
    "REST_NETDEVICE_LIST": "{% url 'rest:netdevice_list' %}"
    "REST_NET_IP_DETAIL": "{% url 'rest:net_ip_detail' 1 %}"
    "REST_NET_IP_LIST": "{% url 'rest:net_ip_list' %}"
    "REST_NETDEVICE_DETAIL": "{% url 'rest:netdevice_detail' 1 %}"
    "REST_NETDEVICE_LIST": "{% url 'rest:netdevice_list' %}"
    "REST_NETDEVICE_PEER_LIST": "{% url 'rest:netdevice_peer_list' %}"
    "REST_NETDEVICE_SPEED_LIST": "{% url 'rest:netdevice_speed_list' %}"
    "REST_NETWORK_DEVICE_TYPE_LIST": "{% url 'rest:network_device_type_list' %}"
    "REST_NETWORK_LIST": "{% url 'rest:network_list' %}"
    "REST_NETWORK_TYPE_LIST": "{% url 'rest:network_type_list' %}"
    "REST_PACKAGE_LIST": "{% url 'rest:package_list' %}"
    "REST_PACKAGE_REPO_LIST": "{% url 'rest:package_repo_list' %}"
    "REST_PACKAGE_SEARCH_LIST": "{% url 'rest:package_search_list' %}"
    "REST_PACKAGE_SEARCH_RESULT_LIST": "{% url 'rest:package_search_result_list' %}"
    "REST_PACKAGE_SERVICE_LIST": "{% url 'rest:package_service_list' %}"
    "REST_PARTITION_DETAIL": "{% url 'rest:partition_detail' 1 %}"
    "REST_PARTITION_DISC_DETAIL": "{% url 'rest:partition_disc_detail' 1 %}"
    "REST_PARTITION_DISC_LIST": "{% url 'rest:partition_disc_list' %}"
    "REST_PARTITION_FS_LIST": "{% url 'rest:partition_fs_list' %}"
    "REST_PARTITION_LIST": "{% url 'rest:partition_list' %}"
    "REST_PARTITION_TABLE_LIST": "{% url 'rest:partition_table_list' %}"
    "REST_PEER_INFORMATION_DETAIL": "{% url 'rest:peer_information_detail' 1 %}"
    "REST_PEER_INFORMATION_LIST": "{% url 'rest:peer_information_list' %}"
    "REST_QUOTA_CAPABLE_BLOCKDEVICE_LIST": "{% url 'rest:quota_capable_blockdevice_list' %}"
    "REST_SNMP_NETWORK_TYPE_LIST": "{% url 'rest:snmp_network_type_list' %}"
    "REST_STATUS_LIST": "{% url 'rest:status_list' %}"
    "REST_SYS_PARTITION_DETAIL": "{% url 'rest:sys_partition_detail' 1 %}"
    "REST_SYS_PARTITION_LIST": "{% url 'rest:sys_partition_list'%}"
    "REST_USER_DETAIL": "{% url 'rest:user_detail' 1 %}"
    "REST_USER_LIST": "{% url 'rest:user_list' %}"
    "REST_USER_OBJECT_PERMISSION_DETAIL": "{% url 'rest:user_object_permission_detail' 1 %}"
    "REST_USER_PERMISSION_DETAIL": "{% url 'rest:user_permission_detail' 1 %}"
    "REST_USER_PERMISSION_LIST": "{% url 'rest:user_permission_list' %}"
    "REST_VIRTUAL_DESKTOP_PROTOCOL_LIST": "{% url 'rest:virtual_desktop_protocol_list' %}"
    "REST_VIRTUAL_DESKTOP_USER_SETTING_LIST": "{% url 'rest:virtual_desktop_user_setting_list' %}"
    "REST_WINDOW_MANAGER_LIST": "{% url 'rest:window_manager_list' %}"
    "RMS_CHANGE_JOB_PRIORITY": "{% url 'rms:change_job_priority' %}"
    "RMS_CONTROL_JOB": "{% url 'rms:control_job' %}"
    "RMS_CONTROL_QUEUE": "{% url 'rms:control_queue' %}"
    "RMS_GET_FILE_CONTENT": "{% url 'rms:get_file_content' %}"
    "RMS_GET_NODE_INFO": "{% url 'rms:get_node_info' %}"
    "RMS_GET_RMS_JOBINFO": "{% url 'rms:get_rms_jobinfo' %}"
    "RMS_GET_RMS_JSON": "{% url 'rms:get_rms_json' %}"
    "RMS_GET_USER_SETTING": "{% url 'rms:get_user_setting' %}"
    "RMS_OVERVIEW": "{% url 'rms:overview' %}"
    "RMS_SET_USER_SETTING": "{% url 'rms:set_user_setting' %}"
    "RRD_DEVICE_RRDS": "{% url 'rrd:device_rrds' %}"
    "RRD_GRAPH_RRDS": "{% url 'rrd:graph_rrds' %}"
    "RRD_MERGE_CDS": "{% url 'rrd:merge_cds' %}"
    "SESSION_LOGOUT": "{% url 'session:logout' %}"
    "SESSION_LOGIN": "{% url 'session:login' %}"
    "SETUP_IMAGE_OVERVIEW": "{% url 'setup:image_overview' %}"
    "SETUP_KERNEL_OVERVIEW": "{% url 'setup:kernel_overview' %}"
    "SETUP_PARTITION_OVERVIEW": "{% url 'setup:partition_overview' %}"
    "SETUP_RESCAN_IMAGES": "{% url 'setup:rescan_images' %}"
    "SETUP_RESCAN_KERNELS": "{% url 'setup:rescan_kernels' %}"
    "SETUP_USE_IMAGE": "{% url 'setup:use_image' %}"
    "SETUP_VALIDATE_PARTITION": "{% url 'setup:validate_partition' %}"
    "USER_ACCOUNT_INFO": "{% url 'user:account_info' %}"
    "USER_BACKGROUND_JOB_INFO": "{% url 'user:background_job_info' %}"
    "USER_CHANGE_OBJECT_PERMISSION": "{% url 'user:change_object_permission' %}"
    "USER_CLEAR_HOME_DIR_CREATED": "{% url 'user:clear_home_dir_created' %}"
    "USER_GET_DEVICE_IP": "{% url 'user:get_device_ip' %}"
    "USER_GLOBAL_SETTINGS": "{% url 'user:global_settings' %}"
    "USER_OVERVIEW": "{% url 'user:overview' %}"
    "USER_SET_USER_VAR": "{% url 'user:set_user_var' %}"
    "USER_SYNC_USERS": "{% url 'user:sync_users' %}"
    {% for name, url in ADDITIONAL_URLS %}
    "{{ name }}": "{{ url }}"
    {% endfor %}
})
