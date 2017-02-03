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
    "icsw.backend.system.license",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "angularFileUpload", "gettext",
    ]
).service("icswSystemOvaCounter",
[
    "Restangular", "ICSW_URLS", "$q", "icswWebSocketService", "$rootScope", "ICSW_SIGNALS",
    "icswUserService",
(
    Restangular, ICSW_URLS, $q, icswWebSocketService, $rootScope, ICSW_SIGNALS,
    icswUserService,
) ->
    class icswSystemOvaCounter
        constructor: (c_list) ->
            @counter = 0
            @system_cradle = null
            # usage per license
            @license_list = []
            # usage per license lut
            @license_lut = {}
            @on_update = $q.defer()
            @update(c_list)

            @ws = undefined
            @setup_web_socket()

            $rootScope.$on(ICSW_SIGNALS("ICSW_USER_LOGGEDIN"), () =>
                @setup_web_socket()
            )

        update: (c_list) ->
            @counter++
            _c = c_list.plain()[0]
            @update_plain(_c)

        update_plain: (cradle) =>
            @system_cradle = cradle
            @license_list.length = 0
            @license_lut = {}
            for basket in cradle.icsweggbasket_set
                _ln = basket.license_id_name or "global"
                if _ln not of @license_lut
                    new_usage = {
                        name: _ln
                        installed: 0
                        available: 0
                        available_ghost: 0
                    }
                    @license_lut[_ln] = new_usage
                    @license_list.push(new_usage)
                _usage = @license_lut[_ln]
                for _attr in ["installed", "available", "available_ghost"]
                    _usage[_attr] += basket[_attr]
            for _usage in @license_list
                _usage.used = _usage.installed - _usage.available
                _usage.used_ghost = _usage.installed - _usage.available_ghost
                @build_info_str(_usage)
            @any_used = _.some(usage.any_used for usage in @license_list)
            @system_cradle.used = @system_cradle.installed - @system_cradle.available

        build_info_str: (usage) ->
            usage.any_used = usage.installed != usage.available
            _in = usage.installed
            _av = usage.available
            _used = _in - _av
            _perc = parseInt(100 * _used / _av)
            @info_str = "#{_used} / #{_in}"
            if _perc > 90
                _class = "danger"
            else if _perc > 80
                _class = "warning"
            else
                _class = "success"
            usage.info_class = "label label-#{_class}"
            usage.status_class = _class

        close_web_socket: () =>
            if @ws? and @ws
                @ws.close()

        setup_web_socket: () ->
            @close_web_socket()
            if icswUserService.user_present() and icswUserService.get().is_authenticated()
                icswWebSocketService.get_ws(
                    "ova_counter"
                    (data) =>
                        @update_plain(data)
                        @on_update.notify(@system_cradle)
                ).then(
                    (ws) ->
                        @ws = ws
                )

]).service("icswSystemOvaCounterService",
[
    "ICSW_URLS", "icswTreeBase", "icswSystemOvaCounter",
(
    ICSW_URLS, icswTreeBase, icswSystemOvaCounter,
) ->
    rest_map = [
        ICSW_URLS.ICSW_LIC_GET_OVA_COUNTER
    ]
    return new icswTreeBase(
        "SysOvaCounter"
        icswSystemOvaCounter
        rest_map
        ""
    )
]).service("icswSystemLicenseDataTree",
[
    "Restangular", "ICSW_URLS", "icswSimpleAjaxCall", "$q",
    "icswSystemLicenseFunctions",
(
    Restangular, ICSW_URLS, icswSimpleAjaxCall, $q,
    icswSystemLicenseFunctions,
) ->
    class icswSystemLicenseDataTree
        constructor: (list, pack_list, violation_list, @cluster_info) ->
            @list = []
            @pack_list = []
            @violation_list = []
            @update(list, pack_list, violation_list)

        update: (list, pack_list, violation_list) =>
            @list.length = 0
            for entry in list
                @list.push(entry.plain())
            @pack_list.length = 0
            for entry in pack_list
                @pack_list.push(entry.plain())
            @violation_list.length = 0
            for entry in violation_list
                @violation_list.push(entry.plain())
            if @violation_list.length
                console.error "add license_violation test", @violation_list
            @build_luts()
        
        build_luts: () =>
            # @lut = _.keyBy(@list, "idx")
            @lut_by_id = _.keyBy(@list, "id")
            @pack_lut = _.keyBy(@pack_list, "idx")
            @link()

        link: () =>
            # salt lists
            for lic in @list
                @calculate_license_state(lic)
                @set_warning(lic)
            for pack in @pack_list
                for c_id, lic_struct of pack.lic_info
                    for lic in lic_struct.licenses
                        if lic.id of @lut_by_id
                            lic.$$license = @lut_by_id[lic.id]
                            lic.$$state = icswSystemLicenseFunctions.get_license_state_internal(lic)[3]
                            # console.log "s=", lic.id, lic.$$state
                            if lic.$$state?
                                lic.$$bootstrap_class = icswSystemLicenseFunctions.get_license_state_bootstrap_class(lic.$$state.state_id)
                                lic.$$icon_class = icswSystemLicenseFunctions.get_license_state_icon_class(lic.$$state.state_id)
                            else
                                lic.$$bootstrap_class = ""
                                lic.$$icon_class = ""
                        else
                            lic.$$license = {name: "License with id '#{lic.id}' not known"}
                            lic.$$state = {state_str: "N/A"}
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
                                lic_state = icswSystemLicenseFunctions.get_license_state_internal(pack_lic)
                                lic_state[3].package = pack
                                lic_state[3].lic = pack_lic
                                states.push(lic_state)

                    # has dict of cluster_licenses (get_license_packages django view)
                    for cluster_id_iter, lic_struct of pack.lic_info
                        # cluster_id is string (actual cluster id)
                        # console.log cluster_id_iter, @cluster_info.CLUSTER_ID
                        if cluster_id_iter == @cluster_info.CLUSTER_ID
                            check_licenses(lic_struct.licenses)

                if states.length
                    # NOTE: duplicated in license admin
                    states.sort(
                        (a, b) ->
                            if a[0] != b[0]
                                # lower state id is better
                                return if a[0] > b[0] then 1 else -1
                            else
                                # for parameters, we want higher values
                                return if a[1] < b[1] then 1 else -1
                    )
                    state = states[0][3]

            # if @violation_list.length
            #     # FIXME, ToDo
            #     console.error "add license_violation test", @violation_list
            #if data.license_violations[license_id]? and data.license_violations[license_id].type == 'hard'
            #    if !state?
            #        state = {}
            #    state.state_id = "parameter_violated"
            #    state.state_str = gettextCatalog.getString('License parameter violated')
            license.$$state = state
            if license.$$state?
                license.$$bootstrap_class = icswSystemLicenseFunctions.get_license_state_bootstrap_class(license.$$state.state_id)
                license.$$icon_class = icswSystemLicenseFunctions.get_license_state_icon_class(license.$$state.state_id)
            else
                license.$$bootstrap_class = ""
                license.$$icon_class = ""
            [license.$$fp_bootstrap_class, license.$$fp_icon_class] =  icswSystemLicenseFunctions.get_license_fp_state(license.fp_state)

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
                expiration = icswSystemLicenseFunctions.add_grace_period(moment(lic_state.lic.valid_to))
                date_str = expiration.format("YYYY-MM-DD HH:mm")
                msg = "Your license for #{license.name} is in the grace period and "
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
            return @license_is_valid("fast_frontend")

        license_is_valid: (lic_name) =>
            _valid = false
            if lic_name of @lut_by_id
                _lic = @lut_by_id[lic_name]
                if _lic.$$state?
                    _valid = _lic.$$state.use
            # console.log "lic_check", lic_name, @lut_by_id, _valid
            return _valid

]).service("icswSystemLicenseDataService",
[
    "Restangular", "ICSW_URLS", "gettextCatalog", "icswSimpleAjaxCall", "$q",
    "icswSystemLicenseDataTree", "$rootScope", "ICSW_SIGNALS",
    "icswTreeBase",
(
    Restangular, ICSW_URLS, gettextCatalog, icswSimpleAjaxCall, $q,
    icswSystemLicenseDataTree, $rootScope, ICSW_SIGNALS,
    icswTreeBase,
) ->
    rest_map = [
        ICSW_URLS.ICSW_LIC_GET_ALL_LICENSES
        ICSW_URLS.ICSW_LIC_GET_LICENSE_PACKAGES
        ICSW_URLS.ICSW_LIC_GET_LICENSE_VIOLATIONS
    ]
    class icswSystemLicenseTree extends icswTreeBase
        extra_calls: () =>
            return [
                icswSimpleAjaxCall(
                    {
                        url: ICSW_URLS.MAIN_GET_CLUSTER_INFO
                        dataType: "json"
                    }
                )
            ]

        fx_mode: () =>
            # return true if fx_mode (== fast frontend) is enabled
            if @is_valid()
                _fx_mode = @get_result().fx_mode()
            else
                _fx_mode = false
            return _fx_mode

    return new icswSystemLicenseTree(
        "SysLicenseTree"
        icswSystemLicenseDataTree
        rest_map
        "ICSW_LICENSE_DATA_LOADED"
    )
]).service("icswSystemLicenseFunctions", [
    "$q", "gettextCatalog",
(
    $q, gettextCatalog,
) ->

    add_grace_period = (date) ->
        # NOTE: keep grace period in sync with py, see license.py line 295
        return date.add(2, 'weeks')

    get_license_state_internal = (issued_lic) ->
        # console.log "*", issued_lic
        # add this such that licenses with higher parameters have priority if state is equal
        parameters_sortable = _.sum(_.values(issued_lic.parameters))
        # console.log "*", issued_lic.state
        # console.log "*", issued_lic
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

    get_license_fp_state = (fp_state) ->
        if fp_state?
            if fp_state
                return ["success", "fa fa-check"]
            else
                return ["danger", "fa fa-times"]
        else
            return ["warning", "fa fa-times"]

    return {
        get_license_state_bootstrap_class : get_license_state_bootstrap_class
        get_license_state_icon_class: get_license_state_icon_class
        get_license_state_internal: get_license_state_internal
        add_grace_period: add_grace_period
        get_license_fp_state: get_license_fp_state
    }
])
