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
    "icsw.rrd.graphsetting",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).service("icswRrdGraphSettingService", ["$q", "icswCachingCall", "ICSW_URLS", "icswUserService", "Restangular", ($q, icswCachingCall, ICSW_URLS, icswUserService, Restangular) ->
    _url = ICSW_URLS.REST_GRAPH_SETTING_LIST
    _size_url = ICSW_URLS.REST_GRAPH_SETTING_SIZE_LIST
    _sets = []
    sizes = []
    size_waiters = []
    _set_version = 0
    _active = undefined
    _user = undefined
    $q.all(
        [
            icswCachingCall.fetch(client, _size_url, {}, [])
        ]
    ).then((data) ->
        sizes = data[0]
        for waiter in size_waiters
        if _size_waiters
    )
    load_data = (client) ->
        _defer= $q.defer()
        icswUserService.load().then((user) ->
            _user = user
            $q.all(
                [
                    icswCachingCall.fetch(client, _url, {"user__in": angular.toJson([user.idx])}, [])
                ]
            ).then((data) ->
                _sets = data[0]
                _sizes = data[1]
                if not _sets.length
                    # create default setting
                    create_default().promise.then((new_setting) ->
                        _sets = [new_setting]
                        _active = new_setting
                        _defer.resolve(_sets)
                    )
                else
                    _active = _sets[0]
                    _defer.resolve(data[0])
            )
        )
        return _defer
    create_default = () ->
        return create(get_default())
    create = (setting) ->
        setting.user = _user.idx
        _defer = $q.defer()
        Restangular.all(_url.slice(1)).post(setting).then((new_data) ->
            _sets.push(new_data)
            _defer.resolve(new_data)
        )
        return _defer
    delete_ = (setting) ->
        _defer = $q.defer()
        setting.remove().then((del) ->
            _.remove(_sets, (entry) -> return entry.idx == setting.idx)
            _defer.resolve(setting.idx)
        )
        return _defer
    refresh = (setting) ->
        _defer = $q.defer()
        # refresh setting (after create for instance)
        setting.get().then((prev) ->
            new_list = []
            for entry in _sets
                if entry.idx == prev.idx
                    new_list.push(prev)
                else
                    new_list.push(entry)
            _sets.length = 0
            for entry in new_list
                _sets.push(entry)
            _defer.resolve(prev)
        )
        return _defer
    legend_modes = [
        {"short": "f", "long": "full"}
        {"short": "t", "long": "only text"}
        {"short": "n", "long": "nothing"}
    ]
    scale_modes = [
        {"short": "l", "long": "level"}
        {"short": "n", "long": "none"}
        {"short": "t", "long": "to100"}
    ]
    get_default = () ->
        cur_setting = {
            "name": "default"
            "hide_empty": true
            "include_zero": false
            "merge_devices": false
            "merge_graphs": false
            "legend_mode": legend_modes[0]["short"]
            "scale_mode": scale_modes[0]["short"]
        }
        return cur_setting
    return {
        "set_version": () ->
            return _set_version
        "get_active": () ->
            return _active
        "set_active": (active) ->
            _active = active
        "load": (client) ->
            return load_data(client).promise
        "create_default": () ->
            return create_default().promise
        "create": (setting) ->
            return create(setting).promise
        "refresh": (setting) ->
            return refresh(setting).promise
        "delete": (setting) ->
            return delete_(setting).promise
        "get_list": () ->
            return _sets
        "scale_modes": () ->
            return scale_modes
        "legend_modes": () ->
            return legend_modes
    }
]).directive("icswRrdGraphSetting", ["$templateCache", "icswRrdGraphSettingService", "$compile", ($templateCache, icswRrdGraphSettingService, $compile) ->
    return {
        scope: true
        restrict: "EA"
        template: $templateCache.get("icsw.rrd.graphsetting.overview")
        link: (scope, el, attrs) ->
            scope.settings = []
            icswRrdGraphSettingService.load(scope.$id).then((data) ->
                scope.settings = data
                scope.current = icswRrdGraphSettingService.get_active()
                scope.show_settings = () ->
                    dia_scope = scope.$new()
                    dia_scope.settings = scope.settings
                    dia_div = $compile("<icsw-rrd-graph-setting-modify></icsw-rrd-graph-setting-modify>")(dia_scope)
                    BootstrapDialog.show
                        message: dia_div
                        draggable: true
                        closeable: true
                        title: "RRD graphing settings"
                        size: BootstrapDialog.SIZE_WIDE
                        cssClass: "modal-tall"
                        onhide: () ->
                            scope.current = icswRrdGraphSettingService.get_active()
            )
            scope.select_setting = (setting, x) ->
                icswRrdGraphSettingService.set_active(setting)
    }
]).directive("icswRrdGraphSettingModify", ["$templateCache", "icswRrdGraphSettingService", "$compile", "icswToolsSimpleModalService", ($templateCache, icswRrdGraphSettingService, $compile, icswToolsSimpleModalService) ->
    return {
        scope: true
        restrict: "EA"
        template: $templateCache.get("icsw.rrd.graphsetting.modify")
        link: (scope, el, attrs) ->
            scope.legend_modes = icswRrdGraphSettingService.legend_modes()
            scope.scale_modes = icswRrdGraphSettingService.scale_modes()
            scope.vars = {
                "current" : undefined
            }
            scope.set_current = (setting) ->
                setting.legend_mode2 = (entry for entry in icswRrdGraphSettingService.legend_modes() when entry.short == setting.legend_mode)[0]
                setting.scale_mode2 = (entry for entry in icswRrdGraphSettingService.scale_modes() when entry.short == setting.scale_mode)[0]
                scope.vars.current = setting
                icswRrdGraphSettingService.set_active(setting)
            scope.update_setting = () ->
                # transform legend_mode2 / scale_mode2
                scope.vars.current.legend_mode = scope.vars.current.legend_mode2["short"]
                scope.vars.current.scale_mode = scope.vars.current.scale_mode2["short"]
            scope.set_current(icswRrdGraphSettingService.get_active())
            scope.save_setting = () ->
                scope.update_setting()
                scope.vars.current.save()
            scope.create_setting = () ->
                scope.update_setting()
                icswRrdGraphSettingService.create(scope.vars.current).then((new_setting) ->
                    icswRrdGraphSettingService.refresh(scope.vars.current).then((_prev) -> )
                    scope.set_current(new_setting)
                )
            scope.delete_setting = () ->
                icswToolsSimpleModalService("Really delete setting ?").then((_act) ->
                    icswRrdGraphSettingService.delete(scope.vars.current).then((del_pk) ->
                        if scope.vars.current.idx == del_pk
                            if scope.settings.length
                                scope.settings = icswRrdGraphSettingService.get_list()
                                scope.set_current(scope.settings[0])
                            else
                                icswRrdGraphSettingService.create_default().then((new_setting) ->
                                    scope.set_current(new_setting)
                                    scope.settings = icswRrdGraphSettingService.get_list()
                                )
                        )
                )
            scope.select_setting = (new_setting, b) ->
                scope.set_current(new_setting)
    }
])
