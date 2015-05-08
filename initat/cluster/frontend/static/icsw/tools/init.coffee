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

class paginator_root
    constructor: (@$filter) ->
        @dict = {}
    get_paginator: (name, $scope) =>
        if name not in @dict
            @dict[name] = new paginator_class(name, @$filter, $scope)
        return @dict[name]

class paginator_class
    constructor: (@name, @$filter, @$scope) ->
        @conf = {
            per_page         : 10
            filtered_len     : 0
            unfiltered_len   : 0
            # length currently shown in header
            shown_len        : 0
            num_pages        : 0
            start_idx        : 0
            end_idx          : 0
            act_page         : 0
            page_list        : []
            modify_epp       : false
            entries_per_page : []
            init             : false
            filter_changed   : false
            filter_mode      : false
            filter           : undefined
            filter_func      : undefined
        }
        if @$scope and @$scope.settings and @$scope.settings.filter_settings
            @conf.filter_settings = @$scope.settings.filter_settings
        else
            @conf.filter_settings = {}
    get_laquo_class : () =>
        if @conf.act_page == 1
            return "disabled"
        else
            return ""
    get_raquo_class : () =>
        if @conf.act_page == @conf.num_pages
            return "disabled"
        else
            return ""
    page_back: () =>
        if @conf.act_page > 1
            @conf.act_page--
            @activate_page()
    page_forward: () =>
        if @conf.act_page < @conf.num_pages
            @conf.act_page++
            @activate_page()
    get_filtered_pl: () =>
        # return a filtered page list around the current page
        s_page = @conf.act_page
        m_page = @conf.act_page
        e_page = @conf.act_page
        for idx in [1..10]
            if s_page > 1 and e_page - s_page < 10
                s_page--
            if e_page < @conf.num_pages and e_page - s_page < 10
                e_page++
        return (idx for idx in [s_page..e_page])
    get_range_info: (num) =>
        num = parseInt(num)
        s_val = (num - 1 ) * @conf.per_page + 1
        e_val = s_val + @conf.per_page - 1
        if e_val > @conf.filtered_len
            e_val = @conf.filtered_len
        return "page #{num} (#{s_val} - #{e_val})"
    activate_page: (num) =>
        if num != undefined
            @conf.act_page = parseInt(num)
        # indices start at zero
        pp = @conf.per_page
        @conf.start_idx = (@conf.act_page - 1 ) * pp
        @conf.end_idx = (@conf.act_page - 1) * pp + pp - 1
        if @conf.end_idx >= @conf.filtered_len
            @conf.end_idx = @conf.filtered_len - 1
    get_li_class: (num) =>
        if num == @conf.act_page
            return "active"
        else
            return ""
    set_epp: (in_str) =>
        @conf.modify_epp = true
        @conf.entries_per_page = (parseInt(entry) for entry in in_str.split(","))
    set_entries: (el_list) =>
        # can also be used to reapply the filter
        #@conf.unfiltered_len = el_list.length
        el_list = @apply_filter(el_list)
        #@filtered_list = el_list
        @conf.init = true
        @recalculate()
        #@conf.filtered_len = el_list.length
    recalculate: () =>
        pp = @conf.per_page
        @conf.shown_len = @conf.filtered_len
        @conf.num_pages = parseInt((@conf.filtered_len + pp - 1) / pp)
        if @conf.num_pages > 0
            @conf.page_list = (idx for idx in [1..@conf.num_pages])
        else
            @conf.page_list = []
        if @conf.act_page == 0
            @activate_page(1)
        else
            if @conf.act_page > @conf.page_list.length
                @activate_page(@conf.page_list.length)
            else
                @activate_page(@conf.act_page)
    simple_filter_mode: () =>
        return @conf.filter_mode == "simple"
    clear_filter: () =>
        if @conf.filter_mode
            @conf.filter = ""
    apply_filter: (el_list) =>
        @conf.unfiltered_len = el_list.length
        if @conf.filter_changed
            @conf.filter_changed(@)
        if @conf.filter_mode
            if @conf.filter_func
                el_list = (entry for entry in el_list when @conf.filter_func()(entry, @$scope))
            else
                el_list = @$filter("filter")(el_list, @conf.filter)
        @conf.filtered_len = el_list.length
        @filtered_list = el_list
        if @conf.filtered_len != @conf.shown_len
            # force recalculation of header
            @recalculate()
        return el_list


angular.module(
    "icsw.tools",
    [
        "toaster"
    ],
).config(["toasterConfig", (toasterConfig) ->
    # close on click
    toasterConfig["tap-to-dismiss"] = true
]).service("icswParseXMLResponseService", ["toaster", (toaster) ->
    return (xml, min_level, show_error=true) ->
        # use in combination with icswCallAjaxService, or otherwise make sure to wrap
        # the <response> from the server in some outer tag (similar to usage in license.coffee)

        success = false
        if $(xml).find("response header").length
            ret_state = $(xml).find("response header").attr("code")
            if parseInt(ret_state) < (if min_level then min_level else 40)
                success = true
            $(xml).find("response header messages message").each (idx, cur_mes) ->
                cur_mes = $(cur_mes)
                cur_level = parseInt(cur_mes.attr("log_level"))
                if cur_level < 30
                    toaster.pop("success", "", cur_mes.text())
                else if cur_level == 30
                    toaster.pop("warning", "", cur_mes.text())
                else
                    if show_error
                        toaster.pop("error", "An Error occured", cur_mes.text(), 0)
        else
            if xml != null
                toaster.pop("error", "A critical error occured", "error parsing response", 0)
        return success
]).factory("msgbus", ["$rootScope", ($rootScope) ->
    bus = {}
    bus.emit = (msg, data) ->
        # console.log "E", msg, "E", data
        $rootScope.$emit(msg, data)
    bus.receive = (msg, scope, func) ->
        unbind = $rootScope.$on(msg, func)
        scope.$on("$destroy", unbind)
    return bus
]).directive("icswSelMan", ["msgbus", (msgbus) ->
    # selection manager directive
    # selman=1 ... single device mode (==popup)
    # selman=0 ... single or multi device mode, depend on sidebar selection
    return {
        restrict: "A"
        priority: -100
        link: (scope, el, attrs) ->
            if parseInt(attrs.icswSelMan)
                # console.log "popup actsm", attrs
                scope.$watch(attrs["devicepk"], (new_val) ->
                    if new_val
                        if angular.isArray(new_val)
                            if new_val.length
                                scope.new_devsel(new_val)
                        else
                            # single device mode, for instance for deviceinfo
                            scope.new_devsel([new_val])
                )
            else
                # console.log "actsm", attrs
                # is there a devicepk in the attributes ?
                if attrs["devicepk"]?
                    # yes, watch for changes
                    scope.$watch(attrs["devicepk"], (new_val) ->
                        if new_val
                            if angular.isArray(new_val)
                                if new_val.length
                                    scope.new_devsel(new_val)
                            else
                                scope.new_devsel([new_val])
                    )
                else
                    # console.log "register on sidebar ?"
                    msgbus.emit("devselreceiver", "selman")
                    msgbus.receive("devicelist", scope, (name, args) ->
                        # check selman selection mode, can be
                        # d ... report all device pks
                        # D ... report all device pks with meta devices
                        # ....... more to come
                        selman_mode = attrs["icswSelManSelMode"]||"d"
                        if selman_mode == "d"
                            scope.new_devsel(args[1])
                        else if selman_mode == "D"
                            scope.new_devsel(args[0])
                        else
                            console.log "unknown selman selection mode '#{selman_mode}'"
                    )
    }
]).directive("icswElementSize", ["$parse", ($parse) ->
    # save size of element in scope (specified via icswElementSize)
    return (scope, element, attrs) ->
        fn = $parse(attrs["icswElementSize"])
        scope.$watch(
            ->
                return {
                    "width": element.width()
                    "height": element.height()
                }
            (new_val) ->
                fn.assign(scope, new_val)
            true
        )
]).factory("icswTools", ["icswParseXMLResponseService", (icwParseXMLResponseService) ->
    return {
        "get_size_str" : (size, factor, postfix) ->
            f_idx = 0
            while size > factor
                size = parseInt(size/factor)
                f_idx += 1
            factor = ["", "k", "M", "G", "T", "P", "E"][f_idx]
            return "#{size} #{factor}#{postfix}"
        "build_lut" : (in_list) ->
            lut = {}
            for value in in_list
                lut[value.idx] = value
            return lut
        "remove_by_idx" : (in_array, idx) ->
            for c_idx, val of in_array
                if val.idx == idx
                    c_idx = parseInt(c_idx)
                    rest = in_array.slice(c_idx + 1 || in_array.length)
                    in_array.length = if c_idx < 0 then in_array.length + c_idx else c_idx
                    in_array.push.apply(in_array, rest)
                    break
        "handle_reset" : (data, e_list, idx) ->
            # used to reset form fields when requested by server reply
            if data._reset_list
                if idx == null
                    # special case: e_list is the element to modify
                    scope_obj = e_list
                else
                    scope_obj = (entry for key, entry of e_list when key.match(/\d+/) and entry.idx == idx)[0]
                $(data._reset_list).each (idx, entry) ->
                    scope_obj[entry[0]] = entry[1]
                delete data._reset_list
    }
]).service("icswAjaxInfoService", ["$window", ($window) ->
    class ajax_struct
        constructor: (@top_div_name) ->
            @ajax_uuid = 0
            @ajax_dict = {}
            @top_div = undefined
        new_connection: (settings) =>
            cur_id = @ajax_uuid
            if not @top_div
                @top_div = $(@top_div_name)
            if not @top_div.find("ul").length
                @top_div.append($("<ul>"))
            ai_ul = @top_div.find("ul")
            title_str = settings.title or "pending..."
            if $window.DEBUG
                title_str = "(#{cur_id}) #{title_str}"
            ai_ul.append(
                $("<li>").attr({
                    "id" : cur_id
                }).text(title_str)
            )
            @ajax_dict[cur_id] = {
                "state" : "pending"
                "start" : new Date()
            }
            @ajax_uuid++
            return cur_id
        close_connection: (xhr_id) =>
            if xhr_id?
                @ajax_dict[xhr_id]["state"]   = "done"
                @ajax_dict[xhr_id]["runtime"] = new Date() - @ajax_dict[xhr_id]["start"]
                @top_div.find("li##{xhr_id}").remove()
]).service("icswCallAjaxService", ["icswAjaxInfoService", "$window", (icswAjaxInfoService, $window) ->
    local_ajax_info = new icswAjaxInfoService("div#ajax_info")
    default_ajax_dict =
        type       : "POST"
        timeout    : 50000
        dataType   : "xml"
        headers    : {"X-CSRFToken" : $window.CSRF_TOKEN}
        beforeSend : (xhr, settings) ->
            if not settings.hidden
                xhr.inituuid = local_ajax_info.new_connection(settings)
        complete   : (xhr, textstatus) ->
            local_ajax_info.close_connection(xhr.inituuid)
        dataFilter : (data, data_type) ->
            return data
        error      : (xhr, status, except) ->
            if status == "timeout"
                alert("timeout")
            else
                if xhr.status
                    # if status is != 0 an error has occured
                    alert("*** #{status} ***\nxhr.status : #{xhr.status}\nxhr.statusText : #{xhr.statusText}")
            return false
    return (in_dict) ->
        for key of default_ajax_dict
            if key not of in_dict
                in_dict[key] = default_ajax_dict[key]
        #if "success" of in_dict and in_dict["dataType"] == "xml"
        #    console.log "s", in_dict["success"]
        cur_xhr = $.ajax(in_dict)
        return cur_xhr
]).service("access_level_service", ["ICSW_URLS", "Restangular", (ICSW_URLS, Restangular) ->
    data = {}
    reload = () ->
        data.global_permissions = Restangular.all(ICSW_URLS.USER_GET_GLOBAL_PERMISSIONS.slice(1)).customGET().$object
        # these are not permissions for single objects, but the merged permission set of all objects
        data.object_permissions = Restangular.all(ICSW_URLS.USER_GET_OBJECT_PERMISSIONS.slice(1)).customGET().$object

        data.license_data = Restangular.all(ICSW_URLS.ICSW_LIC_GET_VALID_LICENSES.slice(1)).customGET().$object
    reload()

    # see lines 205 ff in backbone/models/user.py
    check_level = (obj, ac_name, mask, any) ->
        if ac_name.split(".").length != 3
            alert("illegal ac specifier '#{ac_name}'")
        #console.log ac_name, obj._GLOBAL_, obj.access_levels
        if obj and obj.access_levels?
            # object level permissions
            # no need to check for global permissions because those are mirrored down
            # to the object_level permission on the server
            if not obj._all
                obj._all = obj.access_levels
            if ac_name of obj._all
                if any
                    return if obj._all[ac_name] & mask then true else false
                else
                    return (obj._all[ac_name] & mask) == mask
            else
                return false
        else
            # check global permissions
            obj = data.global_permissions
            if ac_name of obj
                if any
                    if mask
                        return if obj[ac_name] & mask then true else false
                    else
                        return true
                else
                    return (obj[ac_name] & mask) == mask
            else
                return false
    has_menu_permission = (p_name) ->
        if angular.isArray(p_name)
            for p in p_name
                if has_menu_permission(p)
                    return true
            return false
        else
            if p_name.split(".").length == 2
                p_name = "backbone.#{p_name}"
            return p_name of data.global_permissions or p_name of data.object_permissions
    has_valid_license = (license) ->
        if Object.keys(data.license_data).length == 0
            # not loaded yet
            return false
        else
            if license not in data.license_data.all_licenses
                console.warn("Invalid license check for #{license}. Licenses are: #{data.license_data.all_licenses}")
            return license in data.license_data.valid_licenses
    func_dict = {
        # functions to check permissions for single objects
        "acl_delete" : (obj, ac_name) ->
            return check_level(obj, ac_name, 4, true)
        "acl_create" : (obj, ac_name) ->
            return check_level(obj, ac_name, 2, true)
        "acl_modify" : (obj, ac_name) ->
            return check_level(obj, ac_name, 1, true)
        "acl_read" : (obj, ac_name) ->
            return check_level(obj, ac_name, 0, true)
        "acl_any" : (obj, ac_name, mask) ->
            return check_level(obj, ac_name, mask, true)
        "acl_all" : (obj, ac_name, mask) ->
            return check_level(obj, ac_name, mask, false)

        # check if permission exists for any object (used for show/hide of entries of menu)
        has_menu_permission: has_menu_permission

        has_valid_license: has_valid_license
        has_any_valid_license: (licenses) ->
            for l in licenses
                if has_valid_license(l)
                    return true
            return false
    }
    return angular.extend({
        install: (scope) ->
            angular.extend(scope, func_dict)
        reload: reload
   }, func_dict)
]).service("initProduct", ["ICSW_URLS", "Restangular", (ICSW_URLS, Restangular) ->
    product = {}
    Restangular.all(ICSW_URLS.USER_GET_INIT_PRODUCT.slice(1)).customGET().then((new_data) ->
        product.name = new_data.name
        product.menu_gfx_url = "#{ICSW_URLS.STATIC_URL}/images/product/#{new_data.name.toLowerCase()}-flat-trans.png"
        product.menu_gfx_big_url = "#{ICSW_URLS.STATIC_URL}/images/product/#{new_data.name.toLowerCase()}-trans.png"
    )
    return product
]).config(['$httpProvider',
    ($httpProvider) ->
        $httpProvider.defaults.xsrfCookieName = 'csrftoken'
        $httpProvider.defaults.xsrfHeaderName = 'X-CSRFToken'
]).filter("paginator", ["$filter", ($filter) ->
    return (arr, scope, pagname) ->
        cur_ps = if pagname then scope.$eval(pagname) else scope.pagSettings
        if cur_ps.conf.init
            arr = cur_ps.apply_filter(arr)
            return arr.slice(cur_ps.conf.start_idx, cur_ps.conf.end_idx + 1)
        else
            return arr
]).filter("paginator2", ["$filter", ($filter) ->
    return (arr, pag_settings) ->
        if pag_settings.conf.init
            arr = pag_settings.apply_filter(arr)
            return arr.slice(pag_settings.conf.start_idx, pag_settings.conf.end_idx + 1)
        else
            return arr
]).filter("paginator_filter", ["$filter", ($filter) ->
    return (arr, scope) ->
        return scope.pagSettings.apply_filter(arr)
]).run(["Restangular", "toaster",
    (Restangular, toaster) ->
        Restangular.setRestangularFields({
            "id" : "idx"
        })
        Restangular.setResponseInterceptor((data, operation, what, url, response, deferred) ->
            if data.log_lines
                for entry in data.log_lines
                    toaster.pop(
                        {20 : "success", 30 : "warning", 40 : "error", 50 : "error"}[entry[0]]
                        entry[1]
                        ""
                    )
            if data._change_list
                $(data._change_list).each (idx, entry) ->
                    toaster.pop("success", "", entry[0] + " : " + entry[1])
                delete data._change_list
            if data._messages
                $(data._messages).each (idx, entry) ->
                    toaster.pop("success", "", entry)
            return data
        )
        Restangular.setErrorInterceptor((resp) ->
            error_list = []
            if typeof(resp.data) == "string"
                if resp.data
                    resp.data = {"error" : resp.data}
                else
                    resp.data = {}
            for key, value of resp.data
                key_str = if key == "__all__" then "error: " else "#{key} : "
                if key != "_reset_list"
                    if Array.isArray(value)
                        for sub_val in value
                            if sub_val.non_field_errors
                                error_list.push(key_str + sub_val.non_field_errors.join(", "))
                            else
                                error_list.push(key_str + String(sub_val))
                    else
                        if (typeof(value) == "object" or typeof(value) == "string") and (not key.match(/^_/) or key == "__all__")
                            error_list.push(key_str + if typeof(value) == "string" then value else value.join(", "))
            new_error_list = []
            for _err in error_list
                if _err not in new_error_list
                    new_error_list.push(_err)
                    toaster.pop("error", _err, "", 0)
            return true
        )
]).service("paginatorSettings", ["$filter", ($filter) ->
# in fact identical ?
# cur_mod.service("paginatorSettings", (paginator_class))
    return new paginator_root($filter)
]).service("restDataSource", ["$q", "Restangular", ($q, Restangular) ->
    _data = {}
    _build_key = (url, options) =>
        url_key = url
        for key, value of options
            url_key = "#{url_key},#{key}=#{value}"
        return url_key
    _do_query = (q_type, options) =>
        d = $q.defer()
        result = q_type.getList(options).then(
           (response) ->
               d.resolve(response)
        )
        return d.promise
    _reset = () ->
        _data = {}
    _load = (rest_tuple) ->
        if typeof(rest_tuple) == "string"
            rest_tuple = [rest_tuple, {}]
        url = rest_tuple[0]
        options = rest_tuple[1]
        if _build_key(url, options) of _data
            # queries with options are not shared
            return _get([url, options])
        else
            return _reload([url, options])
    _reload = (rest_tuple) =>
        if typeof(rest_tuple) == "string"
            rest_tuple = [rest_tuple, {}]
        url = rest_tuple[0]
        options = rest_tuple[1]
        if not _build_key(url, options) of _data
            # not there, call load
            return _load([url, options])
        else
            _data[_build_key(url, options)] = _do_query(Restangular.all(url.slice(1)), options)
            return _get(rest_tuple)
    _add_sources = (in_list) =>
        # in list is a list of (url, option) lists
        q_list = []
        r_list = []
        for rest_tuple in in_list
            rest_key = _build_key(rest_tuple[0], rest_tuple[1])
            if rest_key not of _data
                sliced = rest_tuple[0].slice(1)
                rest_tuple[1] ?= {}
                _data[rest_key] = _do_query(Restangular.all(sliced), rest_tuple[1])
                q_list.push(_data[rest_key])
            r_list.push(_data[rest_key])
        if q_list
            $q.all(q_list)
        return r_list
    _get = (rest_tuple) =>
        return _data[_build_key(rest_tuple[0], rest_tuple[1])]
    return {
        "reset":
            _reset
        "load": (rest_tuple) =>
            return _load(rest_tuple)
        "reload": (rest_tuple) =>
            return _reload(rest_tuple)
        "add_sources": (in_list) =>
            return _add_sources(in_list)
        "get": (rest_tuple) =>
            return _get(rest_tuple)
    }
]).directive("paginator", ["$templateCache", ($templateCache) ->
    link = (scope, element, attrs) ->
        #console.log attrs.pagSettings, scope.$eval(attrs.pagSettings), scope
        #pagSettings = scope.$eval(scope.pagSettings)
        pagSettings = scope.pagSettings
        pagSettings.conf.per_page = parseInt(attrs.perPage)
        #scope.pagSettings.conf.filter = attrs.paginatorFilter
        if attrs.paginatorEpp
            pagSettings.set_epp(attrs.paginatorEpp)
        if attrs.paginatorFilter
            pagSettings.conf.filter_mode = attrs.paginatorFilter
            if pagSettings.conf.filter_mode == "simple"
                pagSettings.conf.filter = ""
            else if pagSettings.conf.filter_mode == "func"
                pagSettings.conf.filter_func = scope.filterFunc
        scope.activate_page = (page_num) ->
            pagSettings.activate_page(page_num)
        scope.$watch(
            () -> return scope.entries
            (new_el) ->
                pagSettings.set_entries(new_el)
        )
        scope.$watch(
            () -> return pagSettings.conf.filter
            (new_el) ->
                pagSettings.set_entries(scope.entries)
        )
        scope.$watch(
            () -> return pagSettings.conf.per_page
            (new_el) ->
                pagSettings.set_entries(scope.entries)
        )
        scope.$watch(
            () -> return pagSettings.conf.filter_settings
            (new_el) ->
                pagSettings.set_entries(scope.entries)
            true
        )
    return {
        restrict : "EA"
        scope:
            entries     : "="
            pagSettings : "="
            paginatorFilter : "="
            filterFunc  : "&paginatorFilterFunc"
        template : $templateCache.get("icsw.tools.old.paginator")
        link     : link
    }
]).service("icswToolsSimpleModalService", ["$modal", "$q", "$templateCache", ($modal, $q, $templateCache) ->
    return (question) ->
        c_modal = $modal.open
            template : $templateCache.get("icsw.tools.simple.modal")
            controller : ["$scope", "$modalInstance", "question", ($scope, $modalInstance, question) ->
                $scope.question = question
                $scope.ok = () ->
                    $modalInstance.close(true)
                $scope.cancel = () ->
                    $modalInstance.dismiss("cancel")
            ]
            backdrop : "static"
            resolve :
                question : () ->
                    return question
        d = $q.defer()
        c_modal.result.then(
            () ->
                return d.resolve()
            () ->
                return d.reject()
        )
        return d.promise
]).service("icswToolsUUID", [() ->
    return () ->
        s4 = () -> Math.floor((1 + Math.random()) * 0x10000).toString(16).substring(1)
        uuid = "#{s4()}#{s4()}-#{s4()}-#{s4()}-#{s4()}-#{s4()}#{s4()}#{s4()}"
        return uuid
])

d3js_module = angular.module(
    "icsw.d3",
    []
).factory("d3_service", ["$document", "$q", "$rootScope", "ICSW_URLS",
    ($document, $q, $rootScope, ICSW_URLS) ->
        d = $q.defer()
        on_script_load = () ->
            $rootScope.$apply(() -> d.resolve(window.d3))
        script_tag = $document[0].createElement('script')
        script_tag.type = "text/javascript"
        script_tag.async = true
        script_tag.src = ICSW_URLS.D3_MIN_JS
        script_tag.onreadystatechange = () ->
            if this.readyState == 'complete'
                on_script_load()
        script_tag.onload = on_script_load
        s = $document[0].getElementsByTagName('body')[0]
        s.appendChild(script_tag)
        return {
            "d3" : () -> return d.promise
        }
])

dimple_module = angular.module(
    "icsw.dimple", []
).factory("dimple_service", ["$document", "$q", "$rootScope", "ICSW_URLS",
    ($document, $q, $rootScope, ICSW_URLS) ->
        d = $q.defer()
        on_script_load = () ->
            $rootScope.$apply(() -> d.resolve(window.dimple))
        script_tag = $document[0].createElement('script')
        script_tag.type = "text/javascript" 
        script_tag.async = true
        script_tag.src = ICSW_URLS.DIMPLE_MIN_JS
        script_tag.onreadystatechange = () ->
            if this.readyState == 'complete'
                on_script_load()
        script_tag.onload = on_script_load
        s = $document[0].getElementsByTagName('body')[0]
        s.appendChild(script_tag)
        return {
            "dimple" : () -> return d.promise
        }
])


angular.module(
    "init.csw.filters", []
).filter(
    "resolve_n2m", () ->
        return (in_array, f_array, n2m_key, null_msg) ->
            if typeof(in_array) == "string"
                # handle strings for chaining
                in_array = (parseInt(value) for value in in_array.split(/,\s*/))

            if null_msg
                ret = null_msg
            else
                ret = "N/A"

            if in_array
                res = (value for key, value of f_array when typeof(value) == "object" and value and value.idx in in_array)
                #ret_str = (f_array[key][n2m_key] for key in in_array).join(", ")
                if res.length
                    ret = (value[n2m_key] for value in res).join(", ")

            return ret

).filter(
    "follow_fk", () ->
        return (in_value, scope, fk_model, fk_key, null_msg) ->
            if in_value != null
                if scope[fk_model] and scope[fk_model][in_value]
                    return scope[fk_model][in_value][fk_key]
                else
                    return null_msg
            else
                return null_msg
).filter(
    "array_length", () ->
        return (array) ->
            return array.length
).filter(
    "array_lookup", () ->
        return (in_value, f_array, fk_key, null_msg) ->
            if in_value == null or in_value == undefined
                return if null_msg then null_msg else "N/A"
            else
                if fk_key
                    if angular.isString(in_value)
                        in_value = parseInt(in_value)
                    res_list = (entry[fk_key] for key, entry of f_array when typeof(entry) == "object" and entry and entry["idx"] == in_value)
                else
                    res_list = (entry for key, entry of f_array when typeof(entry) == "object" and entry and entry["idx"] == in_value)
                return if res_list.length then res_list[0] else "Key Error (#{in_value})"
).filter(
    "exclude_device_groups", () ->
        return (in_array) ->
            return (entry for entry in in_array when entry.is_meta_device == false)
).filter(
    "ip_fixed_width", () ->
        return (in_str) ->
            if in_str
                ip_field = in_str.split(".")
            else
                ip_field = ["?", "?", "?", "?"]
            return ("QQ#{part}".substr(-3, 3) for part in ip_field).join(".").replace(/Q/g, "&nbsp;")
).filter(
    "range", () ->
        return (in_value, upper_value) ->
            return (_val for _val in [1..parseInt(upper_value)])
).filter(
    "yesno1", () ->
        return (in_value) ->
            return if in_value then "yes" else "---"
).filter(
    "yesno2", () ->
        return (in_value) ->
            return if in_value then "yes" else "no"
).filter(
    "isset", () ->
        return (in_value) ->
            return if in_value then "set" else "not set"
).filter("limit_text", () ->
    return (text, max_len, show_info) ->
        if text.length > max_len
            if show_info
                return text[0..max_len] + "... (#{max_len}/#{text.length})"
            else
                return text[0..max_len] + "..."
        else
            return text
).filter("limit_text_no_dots", () ->
    return (text, max_len) ->
        if text.length > max_len
            return text[0..max_len]
        else
            return text
).filter("show_user", () ->
    return (user) ->
        if user
            if user.first_name and user.last_name
                return "#{user.login} (#{user.first_name} #{user.last_name})"
            else if user.first_name
                return "#{user.login} (#{user.first_name})"
            else if user.last_name
                return "#{user.login} (#{user.last_name})"
            else
                return "#{user.login}"
        else
            # in case user is undefined
            return "???"
).filter("show_dtn", () ->
    return (cur_dtn) ->
        r_str = if cur_dtn.node_postfix then "#{cur_dtn.node_postfix}" else ""
        if cur_dtn.depth
            r_str = "#{r_str}.#{cur_dtn.full_name}"
        else
            r_str = "#{r_str} [TLN]"
        return r_str
).filter("datetime1", () ->
    return (cur_dt) ->
        return moment(cur_dt).format("ddd, D. MMM YYYY, HH:mm:ss") + ", " + moment(cur_dt).fromNow()
).filter("datetime_concise", () ->
    return (cur_dt) ->
        return moment(cur_dt).format("DD.MM.YYYY HH:mm:ss")
).filter("get_size", () ->
    return (size, base_factor, factor, postfix="B", float_digits=0) ->
        size = size * base_factor
        f_idx = 0
        while size > factor
            size = parseFloat(parseInt(size)/factor)
            f_idx += 1
        factor_pf = ["", "k", "M", "G", "T", "P", "E"][f_idx]
        if not float_digits
            size = parseInt(size)
        else
            size = "#{size}".substring(0, "#{parseInt(size)}".length + 1 + float_digits)
        return "#{size} #{factor_pf}#{postfix}"
).filter("props_filter", () ->
    return (items, props) ->
        if angular.isArray(items)
            out = []
            for item in items
                for prop in Object.keys(props)
                    text = props[prop].toLowerCase()
                    if item[prop].toString().toLowerCase().indexOf(text) != -1
                        out.push(item)
                        break
        else
            # not an array, ignore filter
            out = items
        return out
)
