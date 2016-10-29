# Copyright (C) 2012-2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of webfrontend
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

angular.module(
    "icsw.system.license",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "angularFileUpload", "gettext",
        "icsw.backend.system.license",
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.syslicenseoverview")
]).controller("icswSystemLicenseCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$timeout", "$uibModal",
    "ICSW_URLS", 'FileUploader', "icswCSRFService", "blockUI", "icswParseXMLResponseService",
    "icswSystemLicenseDataService", "icswAcessLevelService", "icswSystemOvaCounterService",
(
    $scope, $compile, $filter, $templateCache, Restangular, $q, $timeout, $uibModal,
    ICSW_URLS, FileUploader, icswCSRFService, blockUI, icswParseXMLResponseService,
    icswSystemLicenseDataService, icswAcessLevelService, icswSystemOvaCounterService,
) ->
    $scope.struct = {
        # data valid
        data_valid: false
        # license tree
        license_tree: undefined
        # license tab open
        your_licenses_open: false
        # lic_packs open
        lic_packs_open: false
        # lic_upload open
        lic_upload_open: true
        # ova graph open
        ova_graph_open: false
    }

    load = () ->
        $q.all(
            [
                icswSystemLicenseDataService.load($scope.$id)
                icswSystemOvaCounterService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.license_tree = data[0]
                $scope.struct.data_valid = true
        )

    load()
    
    $scope.uploader = new FileUploader(
        scope: $scope
        url: ICSW_URLS.ICSW_LIC_UPLOAD_LICENSE_FILE
        queueLimit: 1
        alias: "license_file"
        formData: []
        removeAfterUpload: true
    )

    icswCSRFService.get_token().then(
        (token) ->
            $scope.uploader.formData.push({"csrfmiddlewaretoken": token})
    )
    $scope.upload_list = []

    $scope.uploader.onBeforeUploadItem = () ->
        blockUI.start()

    $scope.uploader.onCompleteItem = (item, response, status, headers) ->
        # must not give direct response to the parse service
        response = "<document>" + response + "</document>"
        icswParseXMLResponseService(response)
        icswSystemLicenseDataService.reload()
        icswAcessLevelService.reload()

    $scope.uploader.onCompleteAll = () ->
        blockUI.stop()
        $scope.uploader.clearQueue()

]).directive("icswSystemLicenseOverview",
[
    "$q",
(
    $q,
) ->
    return {
        restrict : "EA"
        controller: 'icswSystemLicenseCtrl'
        templateUrl : "icsw.system.license.overview"
    }
]).directive("icswSystemLicenseLocalLicenses",
[
    "$q",
 (
     $q,
 ) ->
        return {
            restrict : "EA"
            templateUrl : "icsw.system.license.local.licenses"
            scope: {
                license_tree: "=icswLicenseTree"
            }
            controller: "icswSystemLicenseLocalLicensesCtrl"
        }
]).controller("icswSystemLicenseLocalLicensesCtrl", [
    "$scope",
(
    $scope,
) ->
    # console.log "$scope=", $scope, $scope.license_tree

    $scope.get_merged_key_list = (a, b) ->
        if !a?
            a = {}
        if !b?
            b = {}
        return _.uniq(Object.keys(a).concat(Object.keys(b)))

    $scope.undefined_to_zero = (x) ->
        return if x? then x else 0
]).directive("icswSystemLicensePackages",
[
    "icswSimpleAjaxCall", "ICSW_URLS",
(
    icswSimpleAjaxCall, ICSW_URLS,
) ->
    return {
        restrict : "EA"
        controller: 'icswSystemLicenseCtrl'
        templateUrl : "icsw.system.license.packages"
        link: (scope, el, attrs) ->
            scope.cluster_accordion_open = {
                0: true  # show first accordion which is the cluster id of this cluster by the ordering below
            }
            scope.package_order_fun = (pack) ->
                return moment(pack.date).unix()

            scope.cluster_order_fun = (data) ->
                # order by is_this_cluster, cluster_id
                prio = 0
                if data[0] == scope.struct.license_tree.cluster_info.CLUSTER_ID
                    prio -= 1
                return [prio, data[0]]

            scope.get_list = (obj) ->
                if !obj.__transformed_list?
                    # cluster-id, license
                    obj.__transformed_list = ([k, v] for k, v of obj)
                return obj.__transformed_list

            scope.get_cluster_title = (cluster_id) ->
                if cluster_id == scope.struct.license_tree.cluster_info.CLUSTER_ID
                    return "Current cluster (#{cluster_id})"
                else
                    return "Cluster #{cluster_id}"
    }
]).directive("icswSystemOvaDisplay",
[
    "$templateCache", "$q",
(
    $templateCache, $q,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.system.ova.display")
        controller: "icswOvaDisplayCtrl"
        replace: true
    }
]).service("icswReactOvaDisplayFactory",
[
    "$q", "$timeout", "icswSystemOvaCounterService", "$state",
(
    $q, $timeout, icswSystemOvaCounterService, $state,
) ->
    {ul, li, a, span, div, p, strong, h3, hr} = React.DOM
    return React.createClass(
        displayName: "icswOvaDisplay"

        getInitialState: () ->
            return {
                counter: 0
            }

        force_redraw: () ->
            @setState({counter: @state.counter + 1})

        componentWillMount: () ->
            @struct = {
                # data present
                data_ok: false
                # ova counter service
                ocs: null
                # timeout
                timeout: null
                # load id
                load_id: "ova_react"
            }
            load = () =>
                if @struct.data_ok
                    _w_list = [icswSystemOvaCounterService.reload(@struct.load_id)]
                else
                    _w_list = [icswSystemOvaCounterService.load(@struct.load_id)]
                $q.all(_w_list).then(
                    (data) =>
                        @struct.ocs = data[0]
                        @struct.data_ok = true
                        @force_redraw()
                )
                @struct.timeout = $timeout(
                    () =>
                        load()
                    20000
                )

            load()

        componentWillUnmount: () ->
            if @struct.timeout
                $timeout.cancel(@struct.timeout)
            console.log "stop ovadisplay"

        render: () ->
            if @struct.data_ok
                return li(
                    {}
                    a(
                        {}
                        span(
                            {
                                className: "cursorpointer #{@struct.ocs.info_class}"
                                title: "Ova usage counter"
                                onClick: (event) ->
                                    $state.go("main.syslicenseoverview")
                            }
                            @struct.ocs.info_str
                        )
                    )
                )
            else
                return li(
                    {}
                    a(
                        {}
                        span(
                            {}
                            "N/A"
                        )
                    )
                )
    )

]).directive("icswOvaDisplayGraph",
[
    "$q", "$templateCache",
(
    $q, $templateCache,
) ->
    return {
        restrict: "E"
        controller: "icswOvaDisplayGraphCtrl"
        template: $templateCache.get("icsw.system.ova.graph")
        scope: true
    }
]).controller("icswOvaDisplayGraphCtrl",
[
    "$scope", "icswRRDGraphUserSettingService", "icswRRDGraphBasicSetting", "$q", "icswAcessLevelService"
    "icswDeviceTreeService", "$rootScope", "ICSW_SIGNALS",
(
    $scope, icswRRDGraphUserSettingService, icswRRDGraphBasicSetting, $q, icswAcessLevelService,
    icswDeviceTreeService, $rootScope, ICSW_SIGNALS,
) ->
    # ???
    moment().utc()
    $scope.struct = {
        # base data set
        base_data_set: false
        # base settings
        base_setting: undefined
        # graph setting
        local_setting: undefined
        # from and to date
        from_date: undefined
        to_date: undefined
        # devices
        devices: []
        # load_called
        load_called: false
    }
    _load = () ->
        $scope.struct.load_called = true
        $q.all(
            [
                icswRRDGraphUserSettingService.load($scope.$id)
                icswDeviceTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                _user_setting = data[0]
                local_setting = _user_setting.get_default()
                _user_setting.set_custom_size(local_setting, 1024, 400)
                _dt = data[1]
                base_setting = new icswRRDGraphBasicSetting()
                base_setting.draw_on_init = true
                base_setting.show_tree = false
                base_setting.show_settings = false
                base_setting.display_tree_switch = false
                base_setting.auto_select_keys = [
                    "icsw.ova"
                ]
                $scope.struct.local_setting = local_setting
                $scope.struct.base_setting = base_setting
                $scope.struct.base_data_set = true
                _routes = icswAcessLevelService.get_routing_info().routing
                $scope.struct.to_date = moment()
                $scope.struct.from_date = moment().subtract(moment.duration(4, "week"))
                if "rms_server" of _routes
                    _server = _routes["rms_server"][0]
                    _device = _dt.all_lut[_server[2]]
                    if _device?
                        $scope.struct.devices.push(_device)
        )
    _load()
    # $rootScope.$on(ICSW_SIGNALS("ICSW_RMS_FAIR_SHARE_TREE_SELECTED"), () ->
    #     if not $scope.struct.load_called
    #       _load()
    # )
])
