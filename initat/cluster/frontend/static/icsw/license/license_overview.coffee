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

# NOTE: ui.bootstrap and angular-dimple both define a bar directive and therefore can not be used in the same module

class license_overview
    constructor: (@xml) ->
        for _sa in ["name", "attribute"]
            @[_sa] = @xml.attr(_sa)
        @license_stack = []
        @update(@xml)

    update: (xml) =>
        for _si in [
            "sge_used_issued", "external_used", "used",
            "reserved", "in_use", "free", "limit", "sge_used_requested",
            "total", "sge_used"
        ]
            @[_si] = parseInt(xml.attr(_si))
        @is_used = if parseInt(xml.attr("in_use")) then true else false
        @show = if parseInt(xml.attr("show")) then true else false

class license_server
    constructor: (@xml) ->
        @info = @xml.attr("info")
        @port = parseInt(@xml.attr("port"))
        @address = @xml.attr("address")
        @license_file = @xml.find("license_file").text()

class license
    constructor: (@xml) ->
        @open = false
        @name = @xml.attr("name")
        @key = @name
        # link to overview object
        @overview = null
        @all_usages = []
        @versions = []
        @update(@)

    update: (other) =>
        for _lc in ["used", "reserved", "free", "issued"]
            @[_lc] = parseInt(other.xml.attr(_lc))
        @versions.length = 0
        for sub_xml in other.xml.find("version")
            @versions.push(new license_version($(sub_xml), @))
        @all_usages.length = 0
        @versions = (new license_version($(sub_xml), @) for sub_xml in other.xml.find("version"))
        for version in @versions
            for usage in version.usages
                @all_usages.push(usage)
        usercount = {}
        for usage in @all_usages
            if usage.user not of usercount
                usercount[usage.user] = 0
            usercount[usage.user] += usage.num
        for usage in @all_usages
            usage.user_usage = usercount[usage.user]
        @num_users = _.keys(usercount).length
        # console.log @num_users
        @all_usages = _.sortBy(usage for usage in @all_usages, (entry) -> return entry.user)


class license_version
    constructor: (@xml, @license) ->
        @vendor = @xml.attr("vendor")
        @version = @xml.attr("version")
        @key = @license.key + "." + @version
        @usages = _.sortBy(
            new license_usage($(sub_xml), @) for sub_xml in @xml.find("usages > usage")
            (entry) ->
                return entry.user
        )

class license_usage
    constructor: (@xml, @version) ->
        for _ta in ["client_long", "client_short", "user", "client_version", "server_info"]
            @[_ta] = @xml.attr(_ta)
        @num = parseInt(@xml.attr("num"))
        @checkout_time = moment.unix(parseInt(@xml.attr("checkout_time")))
        @absolute_co = @checkout_time.format("dd, Do MM YYYY, hh:mm:ss")
        @relative_co = @checkout_time.fromNow()


lic_module = angular.module("icsw.license.overview",
    [
        "ngResource", "ngCookies", "ngSanitize", "init.csw.filters", "ui.bootstrap", "icsw.d3", "icsw.dimple",
        "icsw.tools.angular-dimple-init", "ui.bootstrap.datetimepicker", "restangular", "icsw.tools"
    ]
).config(["icswRouteExtensionProvider", (icswRouteExtensionProvider) ->
    icswRouteExtensionProvider.add_route("main.licoverview")
]).directive("icswLicenseLiveView",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        controller: "icswRMSLicenseLiveviewCtrl"
        template: $templateCache.get("icsw.license.liveview")
    }
]).controller("icswRMSLicenseLiveviewCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$log",
    "$uibModal", "icswAccessLevelService", "$timeout", "ICSW_URLS", "icswSimpleAjaxCall",
(
    $scope, $compile, $filter, $templateCache, Restangular, $q, $log,
    $uibModal, icswAccessLevelService, $timeout, ICSW_URLS, icswSimpleAjaxCall
) ->
    $scope.struct = {
        # license servers
        servers: []
        # license
        licenses: []
        lic_overview: []
        # current timeout
        cur_timeout: undefined
    }
    $scope.server_open = false
    $scope.overview_open = true

    $scope.update = () ->
        icswSimpleAjaxCall(
            url: ICSW_URLS.LIC_LICENSE_LIVEVIEW
            dataType: "xml"
        ).then(
            (xml) ->
                _ov_lut = {}
                for entry in $scope.struct.lic_overview
                    _ov_lut[entry.name] = entry
                _open_list = (_license.name for _license in $scope.struct.licenses when _license.open)
                $scope.struct.servers.length = 0
                for entry in $(xml).find("ms_license_info > license_servers > server")
                    $scope.struct.servers.push(new license_server($(entry)))
                _lic_lut = _.keyBy($scope.struct.licenses, (entry) -> return entry.name)
                # $scope.struct.licenses.length = 0
                for entry in $(xml).find("ms_license_info > licenses > license")
                    new_lic = new license($(entry))
                    if new_lic.name of _lic_lut
                        _lic_lut[new_lic.name].update(new_lic)
                    else
                        $scope.struct.licenses.push(new_lic)
                        if new_lic.name in _open_list
                            new_lic.open = true
                _updated = []
                for entry in $(xml).find("license_overview > licenses > license")
                    _name = $(entry).attr("name")
                    if _name of _ov_lut
                        # update
                        _ov_lut[_name].update($(entry))
                        _updated.push(_name)
                    else
                        # new entry
                        new_ov = new license_overview($(entry))
                        _ov_lut[_name] = new_ov
                        $scope.struct.lic_overview.push(new_ov)
                        _updated.push(_name)
                # link license-overview object with license
                for entry in $scope.struct.licenses
                    if entry.name of _ov_lut
                        entry.overview = _ov_lut[entry.name]
                # check to remove
                _to_remove = _.difference(_.keys(_ov_lut), _updated)
                # console.log _.keys(_ov_lut), _updated, _to_remove
                _.remove($scope.struct.lic_overview, (entry) -> return entry.name in _to_remove)
                for _ov in $scope.struct.lic_overview
                    $scope.build_stack(_ov)
                $scope.struct.cur_timeout = $timeout($scope.update, 3000)
            (error) ->
                $scope.struct.cur_timeout = $timeout($scope.update, 30000)
        )

    $scope.build_stack = (lic) ->
        total = lic.total
        [_to_add, _to_modify, _to_remove] = [[], [], []]
        if lic.license_stack.length == 0
            lic.license_stack = [
                {
                    type: "primary"
                }
                {
                    type: "warning"
                }
                {
                    type: "success"
                }
            ]
        _lut = _.keyBy(lic.license_stack, (entry) -> return entry.type)
        for [_key, _value, _info] in _.zip(
            ["primary", "warning", "success"]
            [lic.sge_used, lic.external_used, lic.free]
            ["used on cluster", "used external", "free"]
        )
            _lut[_key].value = parseInt(_value * 1000 / total)
            _lut[_key].out = "#{_value}"
            _lut[_key].title = "#{_value} #{_info}"
    $scope.update()
    $scope.$on("$destroy", () ->
        if $scope.struct.cur_timeout?
            $timeout.cancel($scope.struct.cur_timeout)
            $scope.struct.cur_timeout = undefined
    )
]).directive("icswRmsLicenseGraph",
[
    "$compile", "$templateCache",
(
    $compile, $templateCache
) ->
    return {
        restrict : "EA"
        scope: {
            license: "=icswLicense"
        }
        template : $templateCache.get("icsw.rms.license.graph")
    }
]).controller("icswLicenseOverviewCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "$q", "$uibModal", "icswAccessLevelService",
     "$timeout", "$sce", "d3_service", "dimple_service", "ICSW_URLS", "icswLicenseUsageTools",
(
    $scope, $compile, $filter, $templateCache, $q, $uibModal, icswAccessLevelService,
    $timeout, $sce, d3_service, dimple_service, ICSW_URLS, icswLicenseUsageTools,
) ->
    wait_list = restDataSource.add_sources([
        [ICSW_URLS.REST_DEVICE_LIST, {}],
        [ICSW_URLS.REST_EXT_LICENSE_LIST, {}],
    ])
    $q.all(wait_list).then(
        (data) ->
            $scope.device_list = data[0]
            $scope.ext_license_list = data[1]
    
            # for testing:
            # $scope.ext_license_list[1].selected = true
            # $scope.license_select_change()
    
            $scope.update_lic_overview_data()
    )

    $scope.$watch('timerange', (unused) -> $scope.update_lic_overview_data())
    $scope.$watch('licdaterangestart', (unused) -> $scope.update_lic_overview_data())
    $scope.$watch('multi_view', (unused) -> $scope.update_lic_overview_data())

    $scope.view_mode = 'default'

    $scope.set_view_mode = (mode) ->
        if mode == $scope.view_mode
            $scope.view_mode = 'default'
        else
            $scope.view_mode = mode

    $scope.update_lic_overview_data = () ->
        if $scope.ext_license_list
            for lic in $scope.ext_license_list
                if $scope.multi_view
                    lic.usage = ""
                else
                    do (lic) ->
                        icswLicenseUsageTools.get_lic_data('default', lic.idx, $scope.timerange, $scope.licdaterangestart, (new_data) ->
                            if new_data.length > 0
                                lic.usage = "(" + icswLicenseUsageTools.calc_avg_usage(new_data) + "%)"
                            else
                                lic.usage = ""
                        )
    $scope.dimpleloaded = false
    d3_service.d3().then(
        (d3) ->
            dimple_service.dimple().then(
                (dimple) ->
                    $scope.dimpleloaded = true
            )
    )
    $scope.license_select_change = () ->
        $scope.ext_license_selected = []
        if $scope.ext_license_list
            for lic in $scope.ext_license_list
                if lic.selected
                    $scope.ext_license_selected.push(lic)
    $scope.license_select_change()  # init by empty list

    $scope.get_li_sel_class = (li) ->
        if li.selected
            return "btn btn-xs btn-success"
        else
            return "btn btn-xs btn-default"
    $scope.toggle_li_sel = (li) ->
        li.selected = !li.selected
        $scope.license_select_change()

    $scope.set_timerange = (tr) ->
        $scope.timerange = tr
    $scope.set_timerange("week")
    $scope.licdaterangestart = moment().startOf("day")
    $scope.multi_view = false
    $scope.cur_time = moment().format()
    # for testing:
    $scope.licdaterangestart = moment("Tue Oct 07 2014 00:00:00 GMT+0200 (CEST)")

]).directive("icswLicenseOverview",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        templateUrl: "icsw.license.overview"
    }
]).service("icswLicenseUsageTools",
[
    "ICSW_URLS", "$resource",
(
    ICSW_URLS, $resource,
) ->
    
    get_lic_data: (viewmode, lic_id, timerange, start_date, cont) ->
        lic_resource = switch
            when viewmode == "show_version" then $resource(ICSW_URLS.LIC_LICENSE_VERSION_STATE_COARSE_LIST, {})
            when viewmode == "show_user" then $resource(ICSW_URLS.LIC_LICENSE_USER_COARSE_LIST, {})
            when viewmode == "show_device" then $resource(ICSW_URLS.LIC_LICENSE_DEVICE_COARSE_LIST, {})
            else $resource(ICSW_URLS.LIC_LICENSE_STATE_COARSE_LIST, {})  # this is default and min_max
        query_data = {
            'lic_id': lic_id
            'duration_type' : timerange
            'date' : moment(start_date).unix()  # ask server in utc
        }
        lic_resource.query(query_data, (new_data) ->
            cont(new_data)
        )

    calc_avg_usage: (new_data) ->
        sum_used = 0
        sum_issued = 0
        for entry in new_data
            sum_used += entry.used
            sum_issued += entry.issued
        return Math.round( 100 * (sum_used / sum_issued) )

    return {
        get_lic_data: get_lic_data
        calc_avg_usage: calc_avg_usage
    }
]).directive("icswLicenseGraph",
[
    "$templateCache", "ICSW_URLS", "icswSimpleAjaxCall", "icswLicenseUsageTools",
(
    $templateCache, ICSW_URLS, icswSimpleAjaxCall, icswLicenseUsageTools,
) ->
    return {
        restrict : "EA"
        template : """
<div ng-if="dimpleloaded">
    <div ng-if="!fixed_range">
        <h3>License: {{ lic_name }} {{ header_addition }}</h3>
    </div>
    <div ng-if="lic_data_show.length > 0">
        <graph data="lic_data_show" width="{{lic_graph_width}}" height="{{lic_graph_height}}">
            <x field="date" order-by="full_date" title="null"></x>
            <y field="value" title="License usage"></y>
            <stacked-area field="type"/>
            <!--
            the data is meant differently than displayed in legend currently
            -->
            <legend></legend>
        </graph>
    </div>
    <div ng-if="lic_data_show.length == 0">
        no data available
    </div>
</div>
"""
        scope : {
            timerange: '='
            dimpleloaded: '='
            licdaterangestart: '='
            viewmode: '='
        }
        link : (scope, el, attrs) ->
            # can't reuse other attributes as they are shared with parent scope
            scope.fixed_range = attrs.fixedtimerange? && attrs.fixedlicdaterangestart?
            scope.lic_id = attrs.lic
            scope.lic_name = attrs.licname
    
            scope.set_lic_data = () ->
                # we get lic_data and lic_data_min_max by default
                list = switch
                    when scope.viewmode == "show_min_max" then "lic_data_min_max"
                    when scope.viewmode == "show_user"    then "lic_data_user"
                    when scope.viewmode == "show_device"  then "lic_data_device"
                    when scope.viewmode == "show_version" then "lic_data_version"
                    else "lic_data"
    
                # set or retrieve
                if scope[list]
                    console.log "use data", list, scope[list]
                    console.log _.map(scope[list], (x) -> x.full_date)
    
                    # this is not nice, but we sometimes need apply, and finding out whether we are in an apply is an anti-pattern
                    scope.lic_data_show = scope[list]
    
                    scope.$apply(
                            scope.lic_data_show = scope[list]
                    )
                else
                    console.log "retrieve data", list, scope.viewmode
                    scope.update_lic_data(scope.viewmode)
    
            scope.update_lic_data = (viewmode, reset=false) ->
                if reset
                    scope.lic_data = null
                    scope.lic_data_min_max = null
                    scope.lic_data_version = null
                    scope.lic_data_user = null
                    scope.lic_data_device = null
    
                # call with argument to allow obtaining general data when in view mode
                tr = if scope.fixed_range then attrs.fixedtimerange else scope.timerange
                start_date = if scope.fixed_range then attrs.fixedlicdaterangestart else scope.licdaterangestart
    
                # prepare data for dimple
                # only define continuation function per mode
                create_common = (entry) ->
                    return {"date": entry.display_date, "full_date": entry.full_start_date}

                scope.lic_graph_width = 500
                scope.lic_graph_height = 300
                if viewmode == 'default' || viewmode == "show_min_max"
                    cont = (new_data, dates) ->
                        console.log "calc default data"
                        scope.lic_data = []
                        scope.lic_data_min_max = []
                        for entry in new_data
                            common = create_common(entry)
    
                            # we have an entry for this
                            _.remove(dates, (elem) -> elem.date == common.date)
    
                            scope.lic_data.push(_.merge({ "type" : "used", "value": entry.used, "order": 1 }, common))
                            scope.lic_data.push(_.merge({ "type" : "unused", "value": entry.issued - entry.used, "order": 2 }, common))
    
                            scope.lic_data_min_max.push(_.merge({ "type": "min used", "value": entry.used_min, "order": 1 }, common))
                            scope.lic_data_min_max.push(_.merge({ "type": "avg used", "value": entry.used - entry.used_min, "order": 2 }, common))
                            scope.lic_data_min_max.push(_.merge({ "type": "max used", "value": entry.used_max - entry.used, "order": 3 }, common))
                            scope.lic_data_min_max.push(_.merge({ "type": "unused", "value": entry.issued_max - entry.used_max, "order": 4 }, common))  # use issued_max as used_max can be greater than issued
    
                        if new_data.length != 0  # we have got data, add missing ones
                            for date in dates
                                scope.lic_data.push({ "type" : "used",   "date": date.date, "full_date": date.full_date, "value" : 0,  "order" : 1 })
                                scope.lic_data.push({ "type" : "unused", "date": date.date, "full_date": date.full_date, "value" : 0,  "order" : 2 })
    
                                scope.lic_data_min_max.push({ "type" : "min used", "date" : date.date, "full_date": date.full_date, "value" : 0,  "order" : 1 })
                                scope.lic_data_min_max.push({ "type" : "avg used", "date" : date.date, "full_date": date.full_date, "value" : 0,  "order" : 2 })
                                scope.lic_data_min_max.push({ "type" : "max used", "date" : date.date, "full_date": date.full_date, "value" : 0,  "order" : 3 })
                                scope.lic_data_min_max.push({ "type" : "unused",   "date" : date.date, "full_date": date.full_date, "value" : 0,  "order" : 4 })
    
                        if new_data.length > 0
                            scope.header_addition = "(" + lic_utils.calc_avg_usage(new_data) + "% usage)"
                else if viewmode == 'show_version'
                    cont = (new_data, dates) ->
                        console.log "calc version data"
                        scope.lic_data_version = []
                        types = []
                        for entry in new_data
                            common = create_common(entry)
    
                            type = "#{entry.ext_license_version_name} (#{entry.vendor_name})"
                            types.push type
                            scope.lic_data_version.push(_.merge({ "type" : type, "value" : entry.frequency, "order" : 0}, common))
    
                        if new_data.length != 0  # we have got some data, add missing ones
                            for type in _.uniq(types)
                                for date in dates
                                    if _.find(scope.lic_data_version, (elem) -> elem.date == date.date && elem.type == type) == undefined
                                        scope.lic_data_version.push({ "type" : type, "date": date.date, "full_date": date.full_date, "value" : 0, "order" : 0 })
                else if viewmode == 'show_user' || viewmode == 'show_device'
                    list = switch
                        when viewmode == 'show_user' then "lic_data_user"
                        else "lic_data_device"
                    cont = (new_data, dates) ->
                        console.log "calc version "+viewmode
                        scope[list] = []
                        types = []
                        for entry in new_data
                            types.push entry.type
                            common = create_common(entry)
                            scope[list].push(_.merge({ "type" : entry.type, "value" : entry.val, "order" : 0}, common))
    
    
                        # TODO: this does not work yet, the angular-dimple directive does not care about changes after initialisation
                        if types.length > 6
                            scope.lic_graph_width = 800
                            scope.lic_graph_height = 600
                        else
                            scope.lic_graph_width = 500
                            scope.lic_graph_height = 300
    
                        # TODO: extract into function together with code above
                        if new_data.length != 0  # we have got some data, add missing ones
                            for type in _.uniq(types)
                                for date in dates
                                    if _.find(scope[list], (elem) -> elem.date == date.date && elem.type == type) == undefined
                                        scope[list].push({ "type" : type, "date": date.date, "full_date": date.full_date, "value" : 0, "order" : 0 })
    
                icswLicenseUsageTools.get_lic_data(viewmode, scope.lic_id, tr, start_date, (new_data) ->
                    # also query all possible dates to check for missing ones (dimple needs all of them)
                    icswSimpleAjaxCall(
                        url: ICSW_URLS.LIC_GET_LICENSE_OVERVIEW_STEPS
                        data:
                            "date": moment(start_date).unix()  # ask server in utc
                            "duration_type" : tr
                        dataType : "json"
                    ).then(
                        (steps_json) ->
                            cont(new_data, steps_json)
                            scope.set_lic_data()
                    )
                )
    
            if !scope.fixed_range
                # need to watch by string and not by var, probably because var originates from parent scope
                scope.$watch('timerange', (unused) -> scope.update_lic_data(scope.viewmode, true))
                scope.$watch('licdaterangestart', (unused) -> scope.update_lic_data(scope.viewmode, true))
            else
                # no updates for fixed range
                scope.update_lic_data(scope.viewmode)
            scope.$watch('viewmode', (unused) -> scope.set_lic_data())
    }
])

