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


root = exports ? this

ics_app = angular.module(
    "icsw.app",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular",
        "blockUI",
        "icsw.tools.tree",
        "icsw.layout.menu",
        "icsw.layout.sidebar",
        "icsw.network",
        "icsw.tools",
        "icsw.login",
        "icsw.user",
        "icsw.user.password",
        "icsw.user.dashboard",
        "icsw.user.settings",
        "icsw.rrd.graph",
        "icsw.info.background",
        "icsw.server.info",
        "icsw.config",
        "icsw.config.gen",
        "icsw.device.variables",
        "icsw.device.info",
        "icsw.device",
        "icsw.config.category_tree",
        "icsw.config.domain_name_tree",
        "icsw.network.device",
        "icsw.device.config",
        "icsw.device.connection",
        "icsw.device.livestatus",
        "icsw.device.status_history",
        # "icsw.lic"
        # "icsw.monitoring.create",
        # "icsw.monitoring_build_info",
        # "icsw.monitoring.device",
        # "icsw.monitoring_overview",
        # "icsw.monitoring_basic",
        # "icsw.monitoring_extended",
        "icsw.package.install",
        "icsw.device.boot",
        "icsw.kernel",
        "icsw.image",
        "icsw.partition_table",
        "icsw.rms",
    ]
)

ics_app.config(() ->
    console.log "config"
).config(["blockUIConfig", (blockUIConfig) ->
    blockUIConfig.delay = 0
    blockUIConfig.message = "Loading, please wait ..."
    blockUIConfig.autoBlock = false
    blockUIConfig.autoInjectBodyBlock = false
]).constant("ICSW_URLS", {
    {% with "images/product/"|add:settings.INIT_PRODUCT_NAME|lower|add:"-flat-trans.png" as gfx_name %}
    "MENU_GFX_URL": "{% static gfx_name %}"
    {% endwith %}
    "ADMIN_INDEX": "{% url 'admin:index' %}"
    "BASE_CATEGORY_TREE": "{% url 'base:category_tree' %}"
    "BASE_GET_GAUGE_INFO": "{% url 'base:get_gauge_info' %}"
    "BASE_MODIFY_LOCATION_GFX": "{% url 'base:modify_location_gfx' %}"
    "BASE_PRUNE_CATEGORIES": "{% url 'base:prune_categories' %}"
    "BASE_UPLOAD_LOCATION_GFX": "{% url 'base:upload_location_gfx' %}"
    "BOOT_SHOW_BOOT": "{% url 'boot:show_boot' %}"
    "CONFIG_SHOW_CONFIGS": "{% url 'config:show_configs' %}"
    "DEVICE_CONNECTIONS": "{% url 'device:connections' %}"
    "DEVICE_SHOW_CONFIGS": "{% url 'device:show_configs' %}"
    "DEVICE_SET_SELECTION": "{% url 'device:set_selection' %}"
    "DEVICE_TREE_SMART": "{% url 'device:tree_smart' %}"
    "DEVICE_VARIABLES": "{% url 'device:variables' %}"
    "DOC_PAGE": "/cluster/doc/main.pdf"
    "DYNDOC_PAGE_X": "{% url 'dyndoc:doc_page' 'x' %}"
    "INFO_PAGE": "{% url 'main:info_page' %}"
    "LIC_LICENSE_LIVEVIEW": "{% url 'lic:license_liveview' %}"
    "LIC_OVERVIEW": "{% url 'lic:overview' %}"
    "MAIN_GET_SERVER_INFO": "{% url 'main:get_server_info' %}"
    "MAIN_SERVER_CONTROL": "{% url 'main:server_control' %}"
    "MAIN_INDEX":  "{% url 'main:index' %}"
    "MAIN_VIRTUAL_DESKTOP_VIEWER": "{% url 'main:virtual_desktop_viewer' %}"
    "MON_BUILD_INFO": "{% url 'mon:build_info' %}"
    "MON_CALL_ICINGA": "{% url 'mon:call_icinga' %}"
    "MON_CREATE_DEVICE": "{% url 'mon:create_device' %}"
    "MON_CREATE_CONFIG": "{% url 'mon:create_config' %}"
    "MON_DELETE_HINT": "{% url 'mon:delete_hint' %}"
    "MON_DEVICE_CONFIG": "{% url 'mon:device_config' %}"
    "MON_GET_NODE_CONFIG": "{% url 'mon:get_node_config' %}"
    "MON_GET_NODE_STATUS": "{% url 'mon:get_node_status' %}"
    "MON_LIVESTATUS": "{% url 'mon:livestatus' %}"
    "MON_OVERVIEW": "{% url 'mon:overview' %}"
    "MON_SETUP_CLUSTER": "{% url 'mon:setup_cluster' %}"
    "MON_SETUP_ESCALATION": "{% url 'mon:setup_escalation' %}"
    "MON_SETUP": "{% url 'mon:setup' %}"
    "NETWORK_DEVICE_NETWORK": "{% url 'network:device_network' %}"
    "NETWORK_DOMAIN_NAME_TREE": "{% url 'network:domain_name_tree' %}"
    "NETWORK_SHOW_NETWORKS": "{% url 'network:show_networks' %}"
    "PACK_ADD_PACKAGE": "{% url 'pack:add_package' %}"
    "PACK_CHANGE_PDC": "{% url 'pack:change_pdc' %}"
    "PACK_REMOVE_PACKAGE": "{% url 'pack:remove_package' %}"
    "PACK_REPO_OVERVIEW": "{% url 'pack:repo_overview' %}"
    "PACK_RETRY_SEARCH": "{% url 'pack:retry_search' %}"
    "PACK_USE_PACKAGE": "{% url 'pack:use_package' %}"
    "REST_BACKGROUND_JOB_LIST": "{% url 'rest:background_job_list' %}"
    "REST_CATEGORY_DETAIL": "{% url 'rest:category_detail' 1 %}"
    "REST_CATEGORY_LIST": "{% url 'rest:category_list' %}"
    "REST_CLUSTER_LICENSE_DETAIL": "{% url 'rest:cluster_license_detail' 1 %}"
    "REST_CLUSTER_SETTING_LIST": "{% url 'rest:cluster_setting_list' %}"
    "REST_CSW_OBJECT_LIST": "{% url 'rest:csw_object_list' %}"
    "REST_CSW_PERMISSION_LIST": "{% url 'rest:csw_permission_list' %}"
    "REST_DEVICE_GROUP_LIST": "{% url 'rest:device_group_list' %}"
    "REST_DEVICE_LIST": "{% url 'rest:device_list' %}"
    "REST_DEVICE_MON_LOCATION_LIST": "{% url 'rest:device_mon_location_list' %}"
    "REST_DEVICE_SELECTION_LIST": "{% url 'rest:device_selection_list' %}"
    "REST_DEVICE_TREE_LIST": "{% url 'rest:device_tree_list' %}"
    "REST_DOMAIN_TREE_NODE_DETAIL": "{% url 'rest:domain_tree_node_detail' 1 %}"
    "REST_DOMAIN_TREE_NODE_LIST": "{% url 'rest:domain_tree_node_list' %}"
    "REST_FETCH_FORMS": "{% url 'rest:fetch_forms' %}"
    "REST_GROUP_DETAIL": "{% url 'rest:group_detail' 1 %}"
    "REST_GROUP_LIST": "{% url 'rest:group_list' %}"
    "REST_GROUP_OBJECT_PERMISSION_DETAIL": "{% url 'rest:group_object_permission_detail' 1 %}"
    "REST_GROUP_PERMISSION_DETAIL": "{% url 'rest:group_permission_detail' 1 %}"
    "REST_GROUP_PERMISSION_LIST": "{% url 'rest:group_permission_list' %}"
    "REST_HOME_EXPORT_LIST": "{% url 'rest:home_export_list' %}"
    "REST_QUOTA_CAPABLE_BLOCKDEVICE_LIST": "{% url 'rest:quota_capable_blockdevice_list' %}"
    "REST_KERNEL_LIST": "{% url 'rest:kernel_list' %}"
    "REST_IMAGE_LIST": "{% url 'rest:image_list' %}"
    "REST_LOCATION_GFX_DETAIL": "{% url 'rest:location_gfx_detail' 1 %}"
    "REST_LOCATION_GFX_LIST": "{% url 'rest:location_gfx_list' %}"
    "REST_MONITORING_HINT_DETAIL": "{% url 'rest:monitoring_hint_detail' 1 %}"
    "REST_NETDEVICE_LIST": "{% url 'rest:netdevice_list' %}"
    "REST_NET_IP_LIST": "{% url 'rest:net_ip_list' %}"
    "REST_NETWORK_DEVICE_TYPE_LIST": "{% url 'rest:network_device_type_list' %}"
    "REST_NETWORK_LIST": "{% url 'rest:network_list' %}"
    "REST_NETWORK_TYPE_LIST": "{% url 'rest:network_type_list' %}"
    "REST_PACKAGE_LIST": "{% url 'rest:package_list' %}"
    "REST_PACKAGE_REPO_LIST": "{% url 'rest:package_repo_list' %}"
    "REST_PACKAGE_SEARCH_LIST": "{% url 'rest:package_search_list' %}"
    "REST_PACKAGE_SEARCH_RESULT_LIST": "{% url 'rest:package_search_result_list' %}"
    "REST_PACKAGE_SERVICE_LIST": "{% url 'rest:package_service_list' %}"
    "REST_USER_DETAIL": "{% url 'rest:user_detail' 1 %}"
    "REST_USER_LIST": "{% url 'rest:user_list' %}"
    "REST_USER_OBJECT_PERMISSION_DETAIL": "{% url 'rest:user_object_permission_detail' 1 %}"
    "REST_USER_PERMISSION_DETAIL": "{% url 'rest:user_permission_detail' 1 %}"
    "REST_USER_PERMISSION_LIST": "{% url 'rest:user_permission_list' %}"
    "REST_VIRTUAL_DESKTOP_PROTOCOL_LIST": "{% url 'rest:virtual_desktop_protocol_list' %}"
    "REST_VIRTUAL_DESKTOP_USER_SETTING_LIST": "{% url 'rest:virtual_desktop_user_setting_list' %}"
    "REST_WINDOW_MANAGER_LIST": "{% url 'rest:window_manager_list' %}"
    "RMS_GET_RMS_JOBINFO": "{% url 'rms:get_rms_jobinfo' %}"
    "RMS_OVERVIEW": "{% url 'rms:overview' %}"
    "RRD_DEVICE_RRDS": "{% url 'rrd:device_rrds' %}"
    "RRD_GRAPH_RRDS": "{% url 'rrd:graph_rrds' %}"
    "RRD_MERGE_CDS": "{% url 'rrd:merge_cds' %}"
    "SESSION_LOGOUT": "{% url 'session:logout' %}"
    "SETUP_IMAGE_OVERVIEW": "{% url 'setup:image_overview' %}"
    "SETUP_KERNEL_OVERVIEW": "{% url 'setup:kernel_overview' %}"
    "SETUP_PARTITION_OVERVIEW": "{% url 'setup:partition_overview' %}"
    "USER_ACCOUNT_INFO": "{% url 'user:account_info' %}"
    "USER_BACKGROUND_JOB_INFO": "{% url 'user:background_job_info' %}"
    "USER_CHANGE_OBJECT_PERMISSION": "{% url 'user:change_object_permission' %}"
    "USER_CLEAR_HOME_DIR_CREATED": "{% url 'user:clear_home_dir_created' %}"
    "USER_GET_DEVICE_IP": "{% url 'user:get_device_ip' %}"
    "USER_GLOBAL_SETTINGS": "{% url 'user:global_settings' %}"
    "USER_OVERVIEW": "{% url 'user:overview' %}"
    "USER_SET_USER_VAR": "{% url 'user:set_user_var' %}"
    "USER_SYNC_USERS": "{% url 'user:sync_users' %}"
})

root.ics_app = ics_app

create_module = angular.module("icsw.monitoring.create", ["ngSanitize", "ui.bootstrap", "restangular"])

create_controller = create_module.controller("create_base", ["$scope", "$timeout", "$window", "$templateCache", "restDataSource", "$q", "blockUI",
    ($scope, $timeout, $window, $templateCache, restDataSource, $q, blockUI) ->
        $scope.base_open = true
        $scope.resolve_pending = false
        $scope.device_data = {
            full_name        : ""
            comment          : "new device"
            device_group     : "newgroup"
            ip               : ""
            resolve_via_ip   : true
            routing_capable  : false
            peer             : 0
            icon_name        : "linux40"
        }
        $scope.peers = []
        $scope.rest_map = [
            {"short" : "device_group", "url" : "{% url 'rest:device_group_list' %}"}
            {"short" : "device_type", "url" : "{% url 'rest:device_type_list' %}"}
            {"short" : "mother_server", "url" : "{% url 'rest:device_tree_list' %}", "options" : {"all_mother_servers" : true}}
            {"short" : "monitor_server", "url" : "{% url 'rest:device_tree_list' %}", "options" : {"monitor_server_type" : true}}
            {"short" : "domain_tree_node", "url" : "{% url 'rest:domain_tree_node_list' %}"}
            {"short" : "peers", "url" : "{% url 'rest:netdevice_peer_list' %}" },
            {"short" : "mon_ext_host", "url" : "{% url 'rest:mon_ext_host_list' %}"}
        ]
        $scope.rest_data = {}
        $scope.all_peers = [{"idx" : 0, "info" : "no peering", "device group name" : "---"}]
        $scope.reload = () ->
            blockUI.start()
            wait_list = []
            for value, idx in $scope.rest_map
                $scope.rest_data[value.short] = restDataSource.reload([value.url, value.options])
                wait_list.push($scope.rest_data[value.short])
            $q.all(wait_list).then((data) ->
                for value, idx in data
                    $scope.rest_data[$scope.rest_map[idx].short] = value
                # build image lut
                $scope.img_lut = {}
                for value in $scope.rest_data.mon_ext_host
                    $scope.img_lut[value.name] = value.data_image
                # create info strings
                for entry in $scope.rest_data.peers
                    entry.info = "#{entry.devname} on #{entry.device_name}"
                $scope.peers = (entry for entry in $scope.rest_data.peers when entry.routing)
                r_list = [{"idx" : 0, "info" : "no peering", "device group name" : "---"}]
                for entry in $scope.peers 
                    r_list.push(entry)
                $scope.all_peers = r_list
                blockUI.stop()
            )
        $scope.get_image_src = () ->
            img_url = ""
            if $scope.img_lut?
                if $scope.device_data.icon_name of $scope.img_lut
                    img_url = $scope.img_lut[$scope.device_data.icon_name]
            return img_url
        $scope.device_name_changed = () ->
            if not $scope.resolve_pending and $scope.device_data.full_name and not $scope.device_data.ip
                $scope.resolve_name()
        $scope.resolve_name = () ->
            # clear ip
            $scope.device_data.ip = ""
            $scope.resolve_pending = true
            call_ajax
                url  : "{% url 'mon:resolve_name' %}"
                data : {
                    "fqdn" : $scope.device_data.full_name
                }
                success : (xml) =>
                    $scope.$apply(
                        $scope.resolve_pending = false
                    )
                    if parse_xml_response(xml)
                        if $(xml).find("value[name='ip']").length and not $scope.device_data.ip
                            $scope.$apply(
                                $scope.device_data.ip = $(xml).find("value[name='ip']").text()
                            )
        $scope.device_groups = () ->
            return (entry.name for entry in $scope.rest_data.device_group when entry.cluster_device_group == false and entry.enabled)
        $scope.any_peers = () ->
            return if $scope.peers.length > 0 then true else false
        $scope.build_device_dict = () ->
            return {
                "full_name" : $scope.full_name
                "comment"   : $scope.comment
                "device_group" : $scope.device_group
                "ip"           : $scope.ip
            }
        $scope.create_device = () ->
            d_dict = $scope.device_data
            blockUI.start()
            call_ajax
                url  : "{% url 'mon:create_device' %}"
                data : {
                    "device_data" : angular.toJson(d_dict)
                }
                success : (xml) =>
                    parse_xml_response(xml)
                    reload_sidebar_tree()
                    blockUI.stop()
                    $scope.reload()
        $scope.reload()

]).controller("form_ctrl", ["$scope",
    ($scope) ->
])
