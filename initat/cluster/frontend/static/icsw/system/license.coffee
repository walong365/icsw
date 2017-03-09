# Copyright (C) 2012-2017 init.at
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
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$uibModal",
    "ICSW_URLS", 'FileUploader', "icswCSRFService", "blockUI", "icswParseXMLResponseService",
    "icswSystemLicenseDataService", "icswAccessLevelService", "icswSystemOvaCounterService",
(
    $scope, $compile, $filter, $templateCache, Restangular, $q, $uibModal,
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
    "icswSimpleAjaxCall", "ICSW_URLS", "$templateCache",
(
    icswSimpleAjaxCall, ICSW_URLS, $templateCache,
) ->
    return {
        restrict : "EA"
        # controller: 'icswSystemLicenseCtrl'
        scope: {
            license_tree: "=icswLicenseTree"
        }
        template : $templateCache.get("icsw.system.license.packages")
        controller: "icswSystemLicensePackagesCtrl"
        link: (scope, el, attrs) ->
            scope.set_license_tree(scope.license_tree)
    }
]).controller("icswSystemLicensePackagesCtrl",
[
    "$scope", "icswTools",
(
    $scope, icswTools,
) ->
    $scope.struct = {
        # set by link
        license_tree: null
        # ordered license list
        lic_list: []
    }
    $scope.cluster_accordion_open = {
        0: true
    }

    $scope.set_license_tree = (lic_tree) ->
        $scope.struct.license_tree = lic_tree
        $scope.struct.lic_list.length = 0
        for entry in $scope.struct.license_tree.pack_list
            entry.$$mom_date = moment(entry.date).unix()
            $scope.struct.lic_list.push(entry)
            entry.$$cluster_list = []
            for key, value of entry.lic_info
                value.$$cluster_id = key
                value.$$local_cluster = value.$$cluster_id == $scope.struct.license_tree.cluster_info.CLUSTER_ID
                if value.$$local_cluster
                    value.$$cluster_info = "Local cluster (#{value.$$cluster_id})"
                else
                    value.$$cluster_info = "Other cluster #{value.$$clustr_id}"
                entry.$$cluster_list.push(value)
            icswTools.order_in_place(entry.$$cluster_list, ["$$local_cluster"], ["asc"])
        icswTools.order_in_place($scope.struct.lic_list, ["$$mom_date"], ["asc"])

]).service("icswReactOvaDisplayFactory",
[
    "$q", "icswSystemOvaCounterService", "$state", "ICSW_URLS",
(
    $q, icswSystemOvaCounterService, $state, ICSW_URLS,
) ->
    {li, a, span, div, img, button, table, tr, td, tbody} = React.DOM

    eval_lics = (used_elements) ->
        style_classes = ["success", "warning", "danger"]
        titles = []
        _levels = []
        for ova in used_elements
            used_perc = 100.0 / ova.installed * ova.used
            lic_const = ova.license_data
            if used_perc >= lic_const.crit_percentage
                _levels.push(2) # error
            else if used_perc >= lic_const.warn_percentage
                _levels.push(1) # warning
            else
                _levels.push(0) # ok
            # variable expansion
            _title = "#{lic_const.description}, {used} used of {installed} installed"
            for _exp_name in ["used", "installed"]
                _title = _.replace(_title, "{#{_exp_name}}", ova[_exp_name])
            titles.push(_title)

        _create_tcf = (key, value) ->
            # style, use key to determine final style
            _style = {}
            if _.startsWith(key, "l2")
                _style.borderTop = "1px solid #666666"
            if _.endsWith(key, "pr")
                _style.paddingRight = 5
            if _.endsWith(key, "w")
                _style.width = 10
            return td(
                {
                    key: key
                    className: "text-right"
                    style: _style
                }
                value
            )

        # the following lines are still not optimal
        if used_elements.length == 1  # one pool (pure noctua or nestor)
            line_data = [
                [
                    _create_tcf("l1", "#{used_elements[0].used}")
                ]
                [
                    _create_tcf("l2", "#{used_elements[0].installed}")
                ]
            ]
        else if used_elements.length == 2  # CORVUS

            line_data = (
                [
                    _create_tcf("l#{_idx}pr", "#{used_elements[_idx - 1].license_data.ova_repr}: ")
                    _create_tcf("l#{_idx}v", "#{used_elements[_idx - 1].used} / #{used_elements[_idx - 1].installed}")
                ] for _idx in [1, 2]
            )
        else
            _idx = 0
            line_data = [[], []]
            for ova in used_elements
                if _idx
                    line_data[0].push(
                        _create_tcf("sl#{_idx}w", "")
                    )
                    line_data[1].push(
                        _create_tcf("sl#{_idx}w", "")
                    )
                _idx++
                line_data[0].push(
                    _create_tcf("l1#{_idx}", "#{ova.used}")
                )
                line_data[1].push(
                    _create_tcf("l2#{_idx}", "#{ova.installed}")
                )

        return {
            titles: titles
            styleclass: style_classes[_.max(_levels)]
            line_data: line_data
        }


    # build button with egg symbol
    egg_display = React.createFactory(
        React.createClass(
            propTypes: {
                used_licenses: React.PropTypes.array
            }

            render: () ->
                lic_data = eval_lics(@props.used_licenses)
                return button(
                    {
                        type: "button"
                        className: "ova-statusbutton cursorpointer btn btn-xs btn-default"
                        onClick: (event) ->
                            $state.go("main.syslicenseoverview")
                        title: lic_data.titles.join("\n")
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
                                            src: "#{ICSW_URLS.STATIC_URL}/egg_#{lic_data.styleclass}.svg"
                                            height: "30"
                                            className: "pull-left"
                                            style: { marginRight: 5}
                                        }
                                    )
                                )
                                lic_data.line_data[0]
                            )
                            tr(
                                {}
                                lic_data.line_data[1]
                            )
                        )
                    )
                )
        )
    )

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
            if @struct.data_ok and @struct.ocs.license_list.length
                used_lics = (
                    lic for lic in @struct.ocs.license_list when lic.license_data
                )
            else
                used_lics = []
            if used_lics.length
                return li(
                    {}
                    div(
                        {}
                        (
                            egg_display(
                                {
                                    key: "lic.button"
                                    used_licenses: used_lics
                                }
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
    "$scope", "icswGraphUserSettingService", "icswGraphBasicSetting", "$q", "icswAccessLevelService"
    "icswDeviceTreeService", "$rootScope", "ICSW_SIGNALS",
(
    $scope, icswGraphUserSettingService, icswGraphBasicSetting, $q, icswAccessLevelService,
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
                icswGraphUserSettingService.load($scope.$id)
                icswDeviceTreeService.load($scope.$id)
            ]
        ).then(
            (data) ->
                _user_setting = data[0]
                local_setting = _user_setting.get_default()
                _user_setting.set_custom_size(local_setting, 1024, 400)
                local_setting.hide_empty = false
                _dt = data[1]
                base_setting = new icswGraphBasicSetting()
                base_setting.draw_on_init = true
                base_setting.show_tree = false
                base_setting.show_settings = false
                base_setting.display_tree_switch = false
                base_setting.ordering = "AVERAGE"
                base_setting.auto_select_keys = [
                    "compound.icsw.ova.consume"
                    "compound.icsw.ova.license"
                ]
                $scope.struct.local_setting = local_setting
                $scope.struct.base_setting = base_setting
                _routes = icswAccessLevelService.get_routing_info().routing
                # console.log _routes
                if _routes? and "grapher_server" of _routes
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
