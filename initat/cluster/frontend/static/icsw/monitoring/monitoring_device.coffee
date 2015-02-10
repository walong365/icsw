
monitoring_device_module = angular.module("icsw.monitoring.device",
        ["ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.select", "icsw.tools.table", "icsw.tools.button"])


monitoring_device_module.directive('icswMonitoringDevice', ["ICSW_URLS", "Restangular", (ICSW_URLS, Restangular) ->
    return {
        restrict     : "EA"
        templateUrl  : "icsw.monitoring.device"
    }
]).service('icswMonitoringDeviceService', ["ICSW_URLS", "Restangular", "msgbus", (ICSW_URLS, Restangular, msgbus) ->
    get_rest = (url, opts={}) -> return Restangular.all(url).getList(opts).$object
    data = {
        mon_device_templ   : get_rest(ICSW_URLS.REST_MON_DEVICE_TEMPL_LIST.slice(1))
        mon_ext_host       : get_rest(ICSW_URLS.REST_MON_EXT_HOST_LIST.slice(1))
        mon_server         : get_rest(ICSW_URLS.REST_DEVICE_TREE_LIST.slice(1), {"monitor_server_type" : true})
    }

    ret = {
        rest_url            : ICSW_URLS.REST_DEVICE_TREE_LIST
        rest_options        : {"ignore_meta_devices" : true, "olp" : "backbone.device.change_monitoring"}
        edit_template       : "device.monitoring.form"
        md_cache_modes : [
            {"idx" : 1, "name" : "automatic (server)"}
            {"idx" : 2, "name" : "never use cache"}
            {"idx" : 3, "name" : "once (until successful)"}
        ]
        init_fn: ($scope) ->
            msgbus.emit("devselreceiver")
            msgbus.receive("devicelist", $scope, (name, args) ->
                $scope.reload(args[1])
            )
        fetch : (edit_obj) ->
            # $.blockUI()
            call_ajax
                url     : ICSW_URLS.MON_FETCH_PARTITION
                data    : {
                    "pk" : edit_obj.idx
                }
                success : (xml) ->
                    # $.unblockUI()
                    parse_xml_response(xml)
    }
    for k, v of data  # shallow copy
        ret[k] = v
    return ret
])
