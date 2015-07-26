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

angular.module(
    "icsw.user.license",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "angularFileUpload", "gettext",
    ]
).controller("icswUserLicenseCtrl",
    ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "restDataSource", "$q", "$timeout", "$modal",
     "$window", "ICSW_URLS", 'FileUploader', 'blockUI', 'icswParseXMLResponseService', 'icswUserLicenseDataService',
     "access_level_service",
    ($scope, $compile, $filter, $templateCache, Restangular, restDataSource, $q, $timeout, $modal,
     $window, ICSW_URLS, FileUploader, blockUI, icswParseXMLResponseService, icswUserLicenseDataService,
     access_level_service) ->
        $scope.uploader = new FileUploader(
                scope : $scope
                url : ICSW_URLS.USER_UPLOAD_LICENSE_FILE
                queueLimit : 1
                alias : "license_file"
                formData : [
                     "csrfmiddlewaretoken" : $window.CSRF_TOKEN
                ]
                removeAfterUpload : true
        )
        $scope.upload_list = []
        $scope.uploader.onBeforeUploadItem = () ->
            blockUI.start()
        $scope.uploader.onCompleteItem = (item, response, status, headers) ->
            # must not give direct response to the parse service
            response = "<document>" + response + "</document>"
            icswParseXMLResponseService(response)
            icswUserLicenseDataService.reload_data()
            access_level_service.reload()
        $scope.uploader.onCompleteAll = () ->
            blockUI.stop()
            $scope.uploader.clearQueue()
]).directive("icswUserLicenseOverview", ["icswUserLicenseDataService", "$window", (icswUserLicenseDataService, $window) ->
    return {
        restrict : "EA"
        controller: 'icswUserLicenseCtrl'
        templateUrl : "icsw.user.license.overview"
        link: (scope, el, attrs) ->
            scope.CLUSTER_ID = $window.CLUSTER_ID
            scope.your_licenses_open = false
            scope.lic_packs_open = false
            scope.lic_upload_open = true
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
]).directive("icswUserLicenseYourLicenses",
    ["icswUserLicenseDataService", "$window",
     (icswUserLicenseDataService, $window) ->
        return {
            restrict : "EA"
            templateUrl : "icsw.user.license.your_licenses"
            scope: true
            link: (scope, el, attrs) ->
                icswUserLicenseDataService.add_to_scope(scope)
                scope.get_merged_key_list = (a, b) ->
                    if !a?
                        a = {}
                    if !b?
                        b = {}
                    return _.unique(Object.keys(a).concat(Object.keys(b)))
                scope._state = icswUserLicenseDataService.calculate_effective_license_state
                scope.undefined_to_zero = (x) ->
                    return if x? then x else 0
        }
]).directive("icswUserLicensePackages", ["icswUserLicenseDataService", "$window", (icswUserLicenseDataService, $window) ->
    return {
        restrict : "EA"
        controller: 'icswUserLicenseCtrl'
        templateUrl : "icsw.user.license.packages"
        link: (scope, el, attrs) ->
            icswUserLicenseDataService.add_to_scope(scope)
            scope.cluster_accordion_open = {
                0: true  # show first accordion which is the cluster id of this cluster by the ordering below
            }
            scope.package_order_fun = (pack) ->
                return moment(pack.date).unix()
            scope.cluster_order_fun = (data) ->
                # order by is_this_cluster, cluster_id
                prio = 0
                if data[0] == $window.CLUSTER_ID
                    prio -= 1
                return [prio, data[0]]
            scope.get_list = (obj) ->
                if !obj.__transformed_list?
                    obj.__transformed_list = ([k, v] for k, v of obj)
                return obj.__transformed_list

            scope.get_cluster_title = (cluster_id) ->
                if cluster_id == $window.CLUSTER_ID
                    return "Current cluster (#{cluster_id})"
                else
                    return "Cluster #{cluster_id}"
    }
]).service("icswUserLicenseDataService", ["Restangular", "ICSW_URLS", "gettextCatalog", "$window", "$q", (Restangular, ICSW_URLS, gettextCatalog, $window, $q) ->
    data = {
        state_valid: false
        all_licenses: []
        license_packages: []
        # no reload:
        license_violations: Restangular.all(ICSW_URLS.ICSW_LIC_GET_LICENSE_VIOLATIONS.slice(1)).customGET().$object
    }

    reload_data = () ->
        promises = [
            Restangular.all(ICSW_URLS.ICSW_LIC_GET_ALL_LICENSES.slice(1)).getList(),
            Restangular.all(ICSW_URLS.ICSW_LIC_GET_LICENSE_PACKAGES.slice(1)).getList(),
        ]
        $q.all(promises).then((new_lists) ->
            data.state_valid = true
            data.all_licenses.length = 0
            for entry in new_lists[0]
                data.all_licenses.push(entry)
            data.license_packages.length = 0
            for entry in new_lists[1]
                data.license_packages.push(entry)
        )

    reload_data()

    data.reload_data = reload_data

    data.get_license_by_id = (id) ->
        return _.find(data.all_licenses, (elem) -> return elem.id == id)

    data.add_to_scope = (scope) ->
        for k, v of data
            if k != 'add_to_scope'
                scope[k] = v


    # NOTE: code below here is just utils, but we can't have it in a proper service since that would create a circular dependency
    _get_license_state_internal = (issued_lic) ->
        # add this such that licenses with higher parameters have priority if state is equal
        parameters_sortable = _.sum(_.values(issued_lic.parameters))
        if moment(issued_lic.valid_from) < moment() and moment() < add_grace_period(moment(issued_lic.valid_to))
            if moment() < moment(issued_lic.valid_to)
                return ([0, parameters_sortable, 0, {
                    state_id: 'valid'
                    state_str: gettextCatalog.getString('Valid')
                    date_info: gettextCatalog.getString('until') + ' ' + moment(issued_lic.valid_to).format("YYYY-MM-DD")
                }])
            else
                return ([3, parameters_sortable, 0,  {
                    state_id: 'grace'
                    state_str: gettextCatalog.getString('In grace period')
                    date_info: gettextCatalog.getString('since') + ' ' + moment(issued_lic.valid_to).format("YYYY-MM-DD")
                }])
        else if moment(issued_lic.valid_from) < moment()
            return ([5, parameters_sortable, moment(issued_lic.valid_to), {
                state_id: 'expired'
                state_str: gettextCatalog.getString('Expired')
                date_info: gettextCatalog.getString('since') + ' ' + moment(issued_lic.valid_to).format("YYYY-MM-DD")
            }])
        else
            return ([8, parameters_sortable, moment(issued_lic.valid_from), {
                state_id: 'valid_in_future'
                state_str: gettextCatalog.getString('Will be valid')
                date_info: gettextCatalog.getString('on') + ' ' + moment(issued_lic.valid_from).format("YYYY-MM-DD")
            }])
    get_license_state_bootstrap_class = (state) ->
        if state?
            return {'valid': 'success', 'expired': 'danger', 'grace': 'warning', 'valid_in_future': 'warning',
            'parameter_violated': 'danger'}[state]
        else
            return ""
    get_license_state_icon_class = (state) ->
        if state?
            return {'valid': 'fa fa-check', 'expired': 'fa fa-times', 'grace': 'fa fa-clock-o', 'valid_in_future': 'fa fa-clock-o',
            'parameter_violated': 'fa fa-times'}[state]
        else
            return ""
    get_license_state = (issued_lic) ->
        state =  _get_license_state_internal(issued_lic)
        return if state? then state[3] else undefined

    calculate_license_state = (packages, license_id=undefined, cluster_id=undefined) ->
        # calculate the current state of either all licenses in a package or of a certain one for a given cluster_id or all cluster_ids
        state = undefined
        if packages.length
            states = []
            # build list [priority, data] in states
            for pack in packages
                check_licenses = (lic_list) ->
                    for pack_lic in lic_list
                        if !license_id? or pack_lic.id == license_id
                            lic_state = _get_license_state_internal(pack_lic)
                            lic_state[3].package = pack
                            lic_state[3].lic = pack_lic
                            states.push(lic_state)

                # has dict of cluster_licenses (get_license_packages django view)
                for cluster_id_iter, cluster_lic_list of pack.cluster_licenses
                    # cluster_id is string (actual cluster id)
                    if cluster_id_iter == cluster_id
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

        if data.license_violations[license_id]? and data.license_violations[license_id].type == 'hard'
            if !state?
                state = {}
            state.state_id = "parameter_violated"
            state.state_str = gettextCatalog.getString('License parameter violated')
        return state

    calculate_effective_license_state = (license_id) -> return calculate_license_state(data.license_packages, license_id, $window.CLUSTER_ID)

    add_grace_period = (date) ->
        # NOTE: keep grace period in sync with py
        return date.add(2, 'weeks')

    angular.extend(data, {
        get_license_bootstrap_class : (issued_lic) ->
            state = get_license_state(issued_lic)
            return if state? then get_license_state_bootstrap_class(state.state_id) else undefined
        get_license_state : get_license_state
        get_license_state_bootstrap_class : get_license_state_bootstrap_class
        get_license_state_icon_class: get_license_state_icon_class
        _get_license_state_internal: _get_license_state_internal  # expose for licadmin
        calculate_effective_license_state: calculate_effective_license_state
        calculate_license_state: calculate_license_state
        get_license_warning: (issued_license) ->
            warnings = []
            if data.license_violations[issued_license.id]?
                violation = data.license_violations[issued_license.id]
                revocation_date = moment(violation['revocation_date'])
                date_str = revocation_date.format("YYYY-MM-DD HH:mm")

                msg =  "Your license for #{violation['name']} is violated and "
                if revocation_date > moment()
                    msg += "will be revoked on <strong>#{date_str}</strong>."
                else
                    msg += "has been revoked on <strong>#{date_str}</strong>."

                warnings.push [violation['revocation_date'], msg]

            lic_state = calculate_effective_license_state(issued_license.id)
            if lic_state? and lic_state.state_id == "grace"
                expiration = add_grace_period(moment(lic_state.lic.valid_to))
                date_str = expiration.format("YYYY-MM-DD HH:mm")
                msg = "Your license for #{issued_license.name} is in the grace period and "
                msg += "will be revoked on <strong>#{date_str}</strong>."

                warnings.push [expiration, msg]

            if warnings.length
                warnings.sort()
                return warnings[0][1]
    })

    return data
]).run(["toaster", "icswUserLicenseDataService", "$rootScope", (toaster, icswUserLicenseDataService, $rootScope) ->
    $rootScope.$watch(
        () -> return Object.keys(icswUserLicenseDataService.license_violations).length + Object.keys(icswUserLicenseDataService.license_packages).length
        () ->
            if icswUserLicenseDataService.license_violations? and icswUserLicenseDataService.license_violations.plain? and
                    Object.keys(icswUserLicenseDataService.all_licenses).length > 0
                for license in icswUserLicenseDataService.all_licenses
                    msg = icswUserLicenseDataService.get_license_warning(license)
                    if msg?
                        toaster.pop("warning", "License warning", msg, 10000, 'trustedHtml')
    )
])
