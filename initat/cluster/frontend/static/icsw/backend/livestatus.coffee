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

    # livestatus helper functions

    "icsw.backend.livestatus",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap",
        "init.csw.filters", "restangular", "noVNC", "ui.select", "icsw.tools",
        "icsw.device.info", "icsw.user",
    ]
).service("icswLivestatusPipeSpecTree",
[
    "$q", "icswSimpleAjaxCall", "ICSW_URLS", "Restangular", "icswUserGroupRoleTools",
    "icswTools",
(
    $q, icswSimpleAjaxCall, ICSW_URLS, Restangular, icswUserGroupRoleTools,
    icswTools,
) ->
    class icswLivestatusPipeSpecTree
        constructor: (list) ->
            # total list
            @list = []
            # list valid for user
            @user_list = []
            @current_user = null
            @update(list)

        update: (list) =>
            @list.length = 0
            for entry in list
                @list.push(@seed_entry(entry))
            @build_luts()

        seed_entry: (entry) ->
            entry.$$deletable = false
            entry.$$editable = false
            if not entry.$$default_vars?
                entry.$$default_vars = []
            else
                entry.$$default_vars.length = 0
            return entry

        build_luts: () =>
            @lut = _.keyBy(@list, "idx")
            @name_lut = _.keyBy(@list, "name")
            icswTools.order_in_place(
                @list
                ["system_pipe", "public_pipe", "name"]
                ["desc", "asc", "desc"]
            )
            @salt_list()
            @apply_user_filter()

        apply_user_filter: () ->
            @user_list.length = 0
            @current_var_setting = {}
            if @current_user
                _user_idx = @current_user.user.idx
                for entry in @list
                    if entry.public_pipe or entry.create_user == _user_idx
                        @user_list.push(entry)
                    if not entry.system_pipe and entry.create_user == _user_idx
                        entry.$$deletable = true
                        entry.$$editable = true
                    # just to be sure ...
                    entry.$$default_vars.length = 0
                    for _vn in icswUserGroupRoleTools.pipe_spec_var_names()
                        if @current_user.get_var(_vn).value == entry.name
                            # console.log "V", _vn, entry
                            entry.$$default_vars.push(_vn)
                            @current_var_setting[_vn] = entry.name
                    if entry.$$default_vars.length
                        entry.$$default_var_info = entry.$$default_vars.join(", ")
                    else
                        entry.$$default_var_info = "no default"

        ensure_defaults: () =>
            # check user variables for sane defaults
            _names = (entry.name for entry in @list)
            q = $q.defer()
            for entry in @list
                if entry.def_user_var_name
                    _var = @current_user.get_var(entry.def_user_var_name)
                    if _var.value not in _names
                        console.error entry.def_user_var_name, _var.value
            q.resolve("done")
            return q.promise

        get_default_layout: (vn) =>
            return (entry for entry in @list when entry.def_user_var_name == vn)[0].name

        _create_user_vars: () =>
            user = @current_user
            defer = $q.defer()
            _c_list = []
            for entry in @list
                if entry.def_user_var_name
                    _c_list.push(
                        user.get_or_create(entry.def_user_var_name, entry.name, "s")
                    )
            if _c_list.length
                $q.all(_c_list).then(
                    (done) ->
                        defer.resolve("ok")
                )
            else
                defer.resolve("ok")
            return defer.promise

        spec_name_defined: (name) =>
            return if name of @name_lut then true else false

        get_spec: (name) =>
            return @name_lut[name]

        set_user: (user) =>
            # set current user
            @current_user = user
            @apply_user_filter()
            return @_create_user_vars()

        salt_list: () =>
            _count_elements = (el_struct) ->
                _num = 0
                _iterate = (in_obj) ->
                    _num++
                    for key, value of in_obj
                        (_iterate(_el) for _el in value)
                _iterate(el_struct)
                return _num

            for entry in @list
                _el = angular.fromJson(entry.json_spec)
                entry.$$number_of_elements = _count_elements(_el)

        duplicate_spec: (spec) ->
            q = $q.defer()
            icswSimpleAjaxCall(
                url: ICSW_URLS.MON_DUPLICATE_DP_SPEC
                data:
                    spec_id: spec.idx
            ).then(
                (data) =>
                    _new_id = parseInt($(data).find("value[name='new_spec']").text())
                    Restangular.one(ICSW_URLS.REST_MON_DISPLAY_PIPE_SPEC_LIST.slice(1)).get({idx: _new_id}).then(
                        (new_obj) =>
                            new_obj = new_obj.plain()[0]
                            @list.push(@seed_entry(new_obj))
                            @build_luts()
                            q.resolve("copied")
                    )
                (error) ->
                    q.reject("error")
            )
            return q.promise

        delete_spec: (spec) =>
            q = $q.defer()
            Restangular.restangularizeElement(null, spec, ICSW_URLS.REST_MON_DISPLAY_PIPE_SPEC_DETAIL.slice(1).slice(0, -2))
            spec.remove().then(
                (ok) =>
                    _.remove(@list, (entry) -> return entry.idx == spec.idx)
                    @build_luts()
                    q.resolve("delete")
                (error) ->
                    q.reject("not deleted")
            )
            return q.promise

        modify_spec: (spec) =>
            q = $q.defer()
            Restangular.restangularizeElement(null, spec, ICSW_URLS.REST_MON_DISPLAY_PIPE_SPEC_DETAIL.slice(1).slice(0, -2))
            spec.put().then(
                (data) =>
                    # much better then remove / push
                    _.assignIn(spec, data.plain())
                    @seed_entry(spec)
                    @build_luts()
                    q.resolve("modify")
                (error) ->
                    q.reject("not modified")
            )

]).service("icswLivestatusPipeSpecTreeService",
[
    "$q", "Restangular", "ICSW_URLS", "icswTreeBase",
    "icswTools", "icswLivestatusPipeSpecTree",
(
    $q, Restangular, ICSW_URLS, icswTreeBase,
    icswTools, icswLivestatusPipeSpecTree,
) ->
    rest_map = [
        ICSW_URLS.REST_MON_DISPLAY_PIPE_SPEC_LIST
    ]
    return new icswTreeBase(
        "DeviceLivestatusPipeSpecTree"
        icswLivestatusPipeSpecTree
        rest_map
        ""
    )
])
