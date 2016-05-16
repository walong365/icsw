# Copyright (C) 2012-2016 init.at
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

angular.module(
    "icsw.user.license",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "angularFileUpload", "gettext",
    ]
).config(["$stateProvider", ($stateProvider) ->
    $stateProvider.state(
        "main.licenseoverview", {
            url: "/licenseoverview"
            templateUrl: "icsw/main/license/overview.html"
            icswData:
                pageTitle: "License information"
                rights: (user, acls) ->
                    if user.is_superuser
                        return true
                    else
                        return false
                menuEntry:
                    menukey: "sys"
                    name: "License"
                    icon: "fa-key"
                    ordering: 20
        }
    )
]).controller("icswUserLicenseCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$timeout", "$uibModal",
    "ICSW_URLS", 'FileUploader', "icswCSRFService", "blockUI", "icswParseXMLResponseService",
    "icswUserLicenseDataService", "icswAcessLevelService",
(
    $scope, $compile, $filter, $templateCache, Restangular, $q, $timeout, $uibModal,
    ICSW_URLS, FileUploader, icswCSRFService, blockUI, icswParseXMLResponseService,
    icswUserLicenseDataService, icswAcessLevelService,
) ->
    $scope.struct = {
        # data valid
        data_valid: false
        # license tree
        license_tree: undefined
    }
    load = () ->
        $q.all(
            [
                icswUserLicenseDataService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.license_tree = data[0]
                $scope.struct.data_valid = true
        )
    load()
    
    $scope.uploader = new FileUploader(
        scope: $scope
        url: ICSW_URLS.USER_UPLOAD_LICENSE_FILE
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
        icswUserLicenseDataService.reload_data()
        icswAcessLevelService.reload()

    $scope.uploader.onCompleteAll = () ->
        blockUI.stop()
        $scope.uploader.clearQueue()

]).directive("icswUserLicenseOverview",
[
    "$q",
(
    $q,
) ->
    return {
        restrict : "EA"
        controller: 'icswUserLicenseCtrl'
        templateUrl : "icsw.user.license.overview"
        link: (scope, el, attrs) ->
            scope.your_licenses_open = false
            scope.lic_packs_open = false
            scope.lic_upload_open = true
            if false
                scope.$watch(
                    () -> icswUserLicenseDataService.license_packages.length
                    (new_val, old_val) ->
                        scope.license_views_disabled = new_val == 0
                        # only change accordion states on actual change
                        if old_val == 0 and new_val > 0
                            scope.your_licenses_open = true
                            scope.lic_packs_open = true
                        if old_val > 1 and new_val == 0
                            scope.your_licenses_open = false
                            scope.lic_packs_open = false
                )
    }
]).directive("icswUserLicenseLocalLicenses",
[
    "$q",
 (
     $q,
 ) ->
        return {
            restrict : "EA"
            templateUrl : "icsw.user.license.local.licenses"
            scope: {
                license_tree: "=icswLicenseTree"
            }
            controller: "icswUserLicenseLocalLicensesCtrl"
        }
]).controller("icswUserLicenseLocalLicensesCtrl", [
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
]).directive("icswUserLicensePackages",
[
    "icswSimpleAjaxCall", "ICSW_URLS",
(
    icswSimpleAjaxCall, ICSW_URLS,
) ->
    return {
        restrict : "EA"
        controller: 'icswUserLicenseCtrl'
        templateUrl : "icsw.user.license.packages"
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
]).service("icswUserLicenseDataTree",
[
    "Restangular", "ICSW_URLS", "icswSimpleAjaxCall", "$q",
    "icswUserLicenseFunctions",
(
    Restangular, ICSW_URLS, icswSimpleAjaxCall, $q,
    icswUserLicenseFunctions,
) ->
    class icswUserLicenseDataTree
        constructor: (list, pack_list, violation_list, @cluster_info) ->
            @list = []
            @pack_list = []
            @violation_list = []
            @update(list, pack_list, violation_list)

        update: (list, pack_list, violation_list) =>
            @list.length = 0
            for entry in list
                @list.push(entry)
            @pack_list.length = 0
            for entry in pack_list
                @pack_list.push(entry)
            @violation_list.length = 0
            for entry in violation_list
                @violation_list.push(entry)
            @build_luts()
        
        build_luts: () =>
            @lut = _.keyBy(@list, "idx")
            @lut_by_id = _.keyBy(@list, "id")
            @pack_lut = _.keyBy(@pack_list, "idx")
            @link()

        link: () =>
            # salt lists
            for lic in @list
                @calculate_license_state(lic)
                @set_warning(lic)
            for pack in @pack_list
                for c_id, lic_list of pack.cluster_licenses
                    for lic in lic_list
                        lic.$$license = @lut_by_id[lic.id]
                        lic.$$state = icswUserLicenseFunctions.get_license_state_internal(lic)[3]
                        if lic.$$state?
                            lic.$$bootstrap_class = icswUserLicenseFunctions.get_license_state_bootstrap_class(lic.$$state.state_id)
                            lic.$$icon_class = icswUserLicenseFunctions.get_license_state_icon_class(lic.$$state.state_id)
                        else
                            lic.$$bootstrap_class = ""
                            lic.$$icon_class = ""

        # calculate_license_state: (packages, license_id=undefined, cluster_id=undefined) ->
        calculate_license_state: (license) =>
            # calculate the current state of either all licenses in a package or of a certain one for a given cluster_id or all cluster_ids
            state = undefined
            if @pack_list.length
                states = []
                # build list [priority, data] in states
                for pack in @pack_list
                    check_licenses = (lic_list) ->
                        for pack_lic in lic_list
                            if !license? or pack_lic.id == license.id
                                lic_state = icswUserLicenseFunctions.get_license_state_internal(pack_lic)
                                lic_state[3].package = pack
                                lic_state[3].lic = pack_lic
                                states.push(lic_state)

                    # has dict of cluster_licenses (get_license_packages django view)
                    for cluster_id_iter, cluster_lic_list of pack.cluster_licenses
                        # cluster_id is string (actual cluster id)
                        # console.log cluster_id_iter, @cluster_info.CLUSTER_ID
                        if cluster_id_iter == @cluster_info.CLUSTER_ID
                            check_licenses(cluster_lic_list)

                if states.length
                    # NOTE: duplicated in license admin
                    states.sort((a, b) ->
                        if a[0] != b[0]
                            # lower state id is better
                            return if a[0] > b[0] then 1 else -1
                        else
                            # for parameters, we want higher values
                            return if a[1] < b[1] then 1 else -1
                    )
                    state = states[0][3]

            if @violation_list.length
                # FIXME, ToDo
                console.error "add license_violation test"
            #if data.license_violations[license_id]? and data.license_violations[license_id].type == 'hard'
            #    if !state?
            #        state = {}
            #    state.state_id = "parameter_violated"
            #    state.state_str = gettextCatalog.getString('License parameter violated')
            license.$$state = state
            if license.$$state?
                license.$$bootstrap_class = icswUserLicenseFunctions.get_license_state_bootstrap_class(license.$$state.state_id)
                license.$$icon_class = icswUserLicenseFunctions.get_license_state_icon_class(license.$$state.state_id)
            else
                license.$$bootstrap_class = ""
                license.$$icon_class = ""

        set_warning: (license) =>
            warnings = []
            if false
                if @license_violations[issued_license.id]?
                    violation = data.license_violations[issued_license.id]
                    revocation_date = moment(violation['revocation_date'])
                    date_str = revocation_date.format("YYYY-MM-DD HH:mm")

                    msg =  "Your license for #{violation['name']} is violated and "
                    if revocation_date > moment()
                        msg += "will be revoked on <strong>#{date_str}</strong>."
                    else
                        msg += "has been revoked on <strong>#{date_str}</strong>."

                    warnings.push [violation['revocation_date'], msg]

            lic_state = license.$$state
            if lic_state? and lic_state.state_id == "grace"
                expiration = icswUserLicenseFunctions.add_grace_period(moment(lic_state.lic.valid_to))
                date_str = expiration.format("YYYY-MM-DD HH:mm")
                msg = "Your license for #{issued_license.name} is in the grace period and "
                msg += "will be revoked on <strong>#{date_str}</strong>."

                warnings.push [expiration, msg]

            license.$$warnings = warnings
            if warnings.length
                warnings.sort()
                license.$$warning_info = warnings[0][1]
                license.$$in_warning = true
            else
                license.$$warning_info = ""
                license.$$in_warning = false

        # fx mode activated ?
        fx_mode: () =>
            if "fast_frontend" of @lut_by_id
                _state = @lut_by_id["fast_frontend"]
                _fx_mode = _state.$$state.use
            else
                _fx_mode = false
            return _fx_mode

        license_is_valid: (lic_name) =>
            _valid = false
            if lic_name of @lut_by_id
                _valid = @lut_by_id[lic_name].$$state.use
            # console.log "lic_check", lic_name, @lut_by_id, _valid
            return _valid

]).service("icswUserLicenseDataService",
[
    "Restangular", "ICSW_URLS", "gettextCatalog", "icswSimpleAjaxCall", "$q",
    "icswUserLicenseDataTree", "icswCachingCall",
(
    Restangular, ICSW_URLS, gettextCatalog, icswSimpleAjaxCall, $q,
    icswUserLicenseDataTree, icswCachingCall,
) ->
    rest_map = [
        [
            ICSW_URLS.ICSW_LIC_GET_ALL_LICENSES, {}
        ]
        [
            ICSW_URLS.ICSW_LIC_GET_LICENSE_PACKAGES, {}
        ]
        [
            ICSW_URLS.ICSW_LIC_GET_LICENSE_VIOLATIONS, {}
        ]
    ]

    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false

    load_data = (client) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _wait_list.push(
            icswSimpleAjaxCall(
                {
                    url: ICSW_URLS.MAIN_GET_CLUSTER_INFO
                    dataType: "json"
                }
            )
        )
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** license tree loaded ***"
                _result = new icswUserLicenseDataTree(data[0], data[1], data[2], data[3])
                _defer.resolve(_result)
                for client of _fetch_dict
                    # resolve clients
                    _fetch_dict[client].resolve(_result)
                # reset fetch_dict
                _fetch_dict = {}
        )
        return _defer

    fetch_data = (client) ->
        if client not of _fetch_dict
            # register client
            _defer = $q.defer()
            _fetch_dict[client] = _defer
        if _result
            # resolve immediately
            _fetch_dict[client].resolve(_result)
        return _fetch_dict[client]

    # data.get_license_by_id = (id) ->
    #     return _.find(data.all_licenses, (elem) -> return elem.id == id)

    # NOTE: code below here is just utils, but we can't have it in a proper service since that would create a circular dependency
    # get_license_state = (issued_lic) ->
    #     state =  _get_license_state_internal(issued_lic)
    #     return if state? then state[3] else undefined

    return {
        load: (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise

        is_valid: () ->
            return if _result? then true else false

        fx_mode: () ->
            # return true if fx_mode (== fast frontend) is enabled
            if _result?
                _fx_mode = _result.fx_mode()
            else
                _fx_mode = false
            return _fx_mode
                
    }
]).service("icswUserLicenseFunctions", [
    "$q", "gettextCatalog",
(
    $q, gettextCatalog,
) ->

    add_grace_period = (date) ->
        # NOTE: keep grace period in sync with py
        return date.add(2, 'weeks')

    get_license_state_internal = (issued_lic) ->
        # console.log "*", issued_lic
        # add this such that licenses with higher parameters have priority if state is equal
        parameters_sortable = _.sum(_.values(issued_lic.parameters))
        if moment(issued_lic.valid_from) < moment() and moment() < add_grace_period(moment(issued_lic.valid_to))
            if moment() < moment(issued_lic.valid_to)
                return (
                    [
                        0
                        parameters_sortable
                        0
                        {
                            state_id: 'valid'
                            use: true
                            state_str: gettextCatalog.getString('Valid')
                            date_info: gettextCatalog.getString('until') + ' ' + moment(issued_lic.valid_to).format("YYYY-MM-DD")
                        }
                    ]
                )
            else
                return (
                    [
                        3
                        parameters_sortable
                        0
                        {
                            state_id: 'grace'
                            use: true
                            state_str: gettextCatalog.getString('In grace period')
                            date_info: gettextCatalog.getString('since') + ' ' + moment(issued_lic.valid_to).format("YYYY-MM-DD")
                        }
                    ]
                )
        else if moment(issued_lic.valid_from) < moment()
            return (
                [
                    5
                    parameters_sortable
                    moment(issued_lic.valid_to)
                    {
                        state_id: 'expired'
                        use: false
                        state_str: gettextCatalog.getString('Expired')
                        date_info: gettextCatalog.getString('since') + ' ' + moment(issued_lic.valid_to).format("YYYY-MM-DD")
                    }
                ]
            )
        else
            return (
                [
                    8
                    parameters_sortable
                    moment(issued_lic.valid_from)
                    {
                        state_id: 'valid_in_future'
                        use: false
                        state_str: gettextCatalog.getString('Will be valid')
                        date_info: gettextCatalog.getString('on') + ' ' + moment(issued_lic.valid_from).format("YYYY-MM-DD")
                    }
                ]
            )

    get_license_state_bootstrap_class = (state) ->
        if state?
            return {
                valid: 'success'
                expired: 'danger'
                grace: 'warning'
                valid_in_future: 'warning'
                parameter_violated: 'danger'
            }[state]
        else
            return ""

    get_license_state_icon_class = (state) ->
        if state?
            return {
                valid: 'fa fa-check'
                expired: 'fa fa-times'
                grace: 'fa fa-clock-o'
                valid_in_future: 'fa fa-clock-o'
                parameter_violated: 'fa fa-times'
            }[state]
        else
            return ""

    return {
        get_license_state_bootstrap_class : get_license_state_bootstrap_class
        get_license_state_icon_class: get_license_state_icon_class
        get_license_state_internal: get_license_state_internal
        add_grace_period: add_grace_period
    }
])
# FIXME
#.run([
##    "toaster", "icswUserLicenseDataService", "$rootScope",
#(
#    toaster, icswUserLicenseDataService, $rootScope
#) ->
#    $rootScope.$watch(
#        () -> return Object.keys(icswUserLicenseDataService.license_violations).length + Object.keys(icswUserLicenseDataService.license_packages).length
#        () ->
#            if icswUserLicenseDataService.license_violations? and icswUserLicenseDataService.license_violations.plain? and
#                    Object.keys(icswUserLicenseDataService.all_licenses).length > 0
#                for license in icswUserLicenseDataService.all_licenses
#                    msg = icswUserLicenseDataService.get_license_warning(license)
#                    if msg?
#                        toaster.pop("warning", "License warning", msg, 10000, 'trustedHtml')
#    )
#])
