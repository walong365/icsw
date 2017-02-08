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

]).constant("RELEVANT_OVA_LICS"
    # FIXME - MOVE OBJECT
    "netboot":
        "name": "Nodes"
        "warnperc": 0.9
        "title": "OVA for booting Nodes used:{used} installed:{installed}"
    "md_config_server":
        "name": "Checks"
        "warnperc": 0.8
        "title": "OVA for assigning Service Checks used:{used} installed:{installed}"
    "global-dev":
        "name": "Global"
        "warnperc": 0.8
        "title": "{used} global OVA of {installed} used"

).controller("icswSystemLicenseCtrl",
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
    "$q", "icswSystemOvaCounterService", "$state", "ICSW_URLS", "RELEVANT_OVA_LICS",
(
    $q, icswSystemOvaCounterService, $state, ICSW_URLS, RELEVANT_OVA_LICS
) ->
    {ul, li, a, span, div, p, strong, h3, hr, img, button, table, tr, td, tbody} = React.DOM

    # BUILD BUTTON WITH EGG SYMBOL
    egg_display = React.createFactory(
        React.createClass(
            propTypes: {
                elements: React.PropTypes.array
            }

            render: () ->
                lic_data = eval_lics(@props.elements)
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
                                lic_data.line_1
                            )
                            tr(
                                {}
                                lic_data.line_2
                            )
                        )
                    )
                )
        )
    )

    get_table_cell = React.createFactory(
        React.createClass(
            propTypes: {
                value: React.PropTypes.string
                style: React.PropTypes.object
            }
            render: () ->
                td(
                    {
                        className: "text-right"
                        style: @props.style
                    }
                    @props.value
                )
        )
    )

    eval_lics = (lic_elements) ->
        lic_keys = Object.keys(RELEVANT_OVA_LICS)
        used_elements = lic_elements.filter (lic) -> lic.name in lic_keys

        style_classes = ["success", "warning", "danger"]
        current_level = 0  # success
        titles = []
        line_1_data = []
        line_2_data = []
        for ova in used_elements when ova.name in lic_keys
            used_perc = 1 / ova.installed * ova.used
            lic_const = RELEVANT_OVA_LICS[ova.name]
            if used_perc == 1.0
                _lvl = 2  # error
            else if used_perc >= lic_const.warnperc
                _lvl = 1  # warning
            else
                _lvl = 0
            current_level = if current_level < _lvl then _lvl else current_level
            _title = lic_const.title.replace /{used}/, ova.used
            _title = _title.replace /{installed}/, ova.installed
            titles.push(_title)

        if used_elements.length == 1  # ONE OVA POOL (NOCUTA / NESTOR)
            line_1_data.push(get_table_cell({
                key: "lic_btt_l1"
                value: "#{used_elements[0].used}"
                style: {}
            }))
            line_2_data.push(get_table_cell({
                key: "lic_btt_l2"
                value: "#{used_elements[0].installed}"
                style: {borderTop: "1px solid #666666"}
            }))
        else if used_elements.length == 2  # CORVUS
            line_1_data.push(get_table_cell({
                key: "lic_btt_l1-name"
                value: "#{RELEVANT_OVA_LICS[used_elements[0].name].name}: "
                style: {paddingRight: 5}
            }))
            line_1_data.push(get_table_cell({
                key: "lic_btt_l1"
                value: "#{used_elements[0].used} / #{used_elements[0].installed}"
                style: {}
            }))
            line_2_data.push(get_table_cell({
                key: "lic_btt_l2-name"
                value: "#{RELEVANT_OVA_LICS[used_elements[1].name].name}: "
                style: {paddingRight: 5}
            }))
            line_2_data.push(get_table_cell({
                key: "lic_btt_l2"
                value: "#{used_elements[1].used} / #{used_elements[1].installed}"
                style: {}
            }))
        else
            for idx in [0...used_elements.length] by 1
                line_1_data.push(get_table_cell({
                    key: "lic_btt_l1-#{idx}"
                    value: "#{used_elements[idx].used}"
                    style: {}
                }))
                line_2_data.push(get_table_cell({
                    key: "lic_btt_l2-#{idx}"
                    value: "#{used_elements[idx].installed}"
                    style: {borderTop: "1px solid #666666"}
                }))
                if idx < used_elements.length - 1
                    line_1_data.push(get_table_cell({
                        key: "lic_btt_l1m-#{idx}"
                        value: ""
                        style: { width:10 }
                    }))
                    line_2_data.push(get_table_cell({
                        key: "lic_btt_l2m-#{idx}"
                        value: ""
                        style: { width:10 }
                    }))

        return {
            "titles": titles
            "styleclass": style_classes[current_level]
            "line_1" : line_1_data
            "line_2" : line_2_data
        }


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
            lic_keys = Object.keys(RELEVANT_OVA_LICS)
            if @struct.data_ok and @struct.ocs.license_list.length
                used_elements = @struct.ocs.license_list.filter (lic) -> lic.name in lic_keys
            else
                used_elements = []
            if used_elements.length
                return li(
                    {}
                    div(
                        {}
                        (
                            egg_display(
                                {
                                    key: "lic.button"
                                    elements: @struct.ocs.license_list
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
                local_setting.hide_empty = false
                _dt = data[1]
                base_setting = new icswRRDGraphBasicSetting()
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
