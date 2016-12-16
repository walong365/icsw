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
    "icswSystemLicenseDataService", "icswAccessLevelService", "icswSystemOvaCounterService",
(
    $scope, $compile, $filter, $templateCache, Restangular, $q, $timeout, $uibModal,
    ICSW_URLS, FileUploader, icswCSRFService, blockUI, icswParseXMLResponseService,
    icswSystemLicenseDataService, icswAccessLevelService, icswSystemOvaCounterService,
) ->
    $scope.struct = {
        # data valid
        data_valid: false
        # ova service
        ova_service: null
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
                $scope.struct.ova_service = data[1]
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
        icswAccessLevelService.reload()

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
    "$q", "$timeout", "icswSystemOvaCounterService", "$state", "ICSW_URLS",
(
    $q, $timeout, icswSystemOvaCounterService, $state, ICSW_URLS,
) ->
    {ul, li, a, span, div, p, strong, h3, hr, img, button, table, tr, td, tbody} = React.DOM
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
                # load id
                load_id: "ova_react"
            }
            load = () =>
                _w_list = [icswSystemOvaCounterService.load(@struct.load_id)]
                $q.all(_w_list).then(
                    (data) =>
                        @struct.ocs = data[0]
                        @struct.data_ok = true
                        @force_redraw()
                        @struct.ocs.on_update.promise.then(
                            () ->
                            () ->
                            (new_data) =>
                                @force_redraw()
                        )
                )

            load()

        componentWillUnmount: () ->
            console.log "stop ovadisplay"

        render: () ->
            if @struct.data_ok
                return li(
                    {}
                    button(
                        {
                            type: "button"
                            className: "ova-statusbutton cursorpointer btn btn-xs btn-default"
                            onClick: (event) ->
                                $state.go("main.syslicenseoverview")
                            title: "Ova usage counter (#{@struct.ocs.system_cradle.available} available, #{@struct.ocs.system_cradle.installed} installed)"
                        }
                        table(
                            {
                            className: "condensed"
                            }
                            tbody(
                                {}
                                tr(
                                    {}
                                    td(
                                        {
                                            rowSpan: 2
                                        }
                                        img(
                                            {
                                                key: "ova"
                                                src: "#{ICSW_URLS.STATIC_URL}/egg_#{@struct.ocs.status_class}.svg"
                                                height: "30"
                                                className: "pull-left"
                                                style: { marginRight: 5}
                                            }
                                        )
                                    )
                                    td(
                                        {
                                            className: "text-right"
                                        }
                                        @struct.ocs.system_cradle.available
                                    )
                                )
                                tr(
                                    {}
                                    td(
                                        {
                                            className: "text-right"
                                            style: { borderTop: "1px solid #666666" }
                                        }
                                        @struct.ocs.system_cradle.installed
                                    )
                                )
                            )
                        )
                    )
                )
            else
                return li(
                    {}
                    a(
                        {
                            style: { paddingBottom: 0 }
                            className: "ovabutton-na"
                        }
                        img(
                            {
                                key: "ova"
                                src: "#{ICSW_URLS.STATIC_URL}/egg.svg"
                                height: "25"
                                className: "pull-left"
                                style: {
                                    marginRight: 5
                                    marginTop: -5
                                }
                            }
                        )
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
    "$scope", "icswRRDGraphUserSettingService", "icswRRDGraphBasicSetting", "$q", "icswAccessLevelService"
    "icswDeviceTreeService", "$rootScope", "ICSW_SIGNALS",
(
    $scope, icswRRDGraphUserSettingService, icswRRDGraphBasicSetting, $q, icswAccessLevelService,
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
        # graph errors
        graph_errors: ""
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
                base_setting.ordering = "AVERAGE"
                base_setting.auto_select_keys = [
                    "compound.icsw.ova"
                ]
                $scope.struct.local_setting = local_setting
                $scope.struct.base_setting = base_setting
                _routes = icswAccessLevelService.get_routing_info().routing
                # console.log _routes
                if "grapher_server" of _routes
                    $scope.struct.to_date = moment()
                    $scope.struct.from_date = moment().subtract(moment.duration(4, "week"))
                    $scope.struct.base_data_set = true
                    _server = _routes["grapher_server"][0]
                    _device = _dt.all_lut[_server[2]]
                    if _device?
                        $scope.struct.devices.push(_device)
                else
                    $scope.struct.graph_errors = "No graphing server defined"
        )
    _load()
    # $rootScope.$on(ICSW_SIGNALS("ICSW_RMS_FAIR_SHARE_TREE_SELECTED"), () ->
    #     if not $scope.struct.load_called
    #       _load()
    # )
])
