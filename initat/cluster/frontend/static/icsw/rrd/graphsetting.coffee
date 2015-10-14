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
    _shift_url = ICSW_URLS.REST_GRAPH_SETTING_TIMESHIFT_LIST
    _forecast_url = ICSW_URLS.REST_GRAPH_SETTING_FORECAST_LIST
    _timeframe_url = ICSW_URLS.REST_GRAPH_TIME_FRAME_LIST
    _sets = []
    sizes = []
    shifts = []
    timeframes = []
    forecasts = []
    size_waiters = []
    shift_waiters = []
    forecast_waiters = []
    timeframe_waiters = []
    _set_version = 0
    _active = undefined
    _user = undefined
    $q.all(
        [
            icswCachingCall.fetch("graphsize", _size_url, {}, [])
            icswCachingCall.fetch("graphsize", _shift_url, {}, [])
            icswCachingCall.fetch("graphsize", _forecast_url, {}, [])
            icswCachingCall.fetch("graphsize", _timeframe_url, {}, [])
        ]
    ).then((data) ->
        sizes = data[0]
        shifts = data[1]
        forecasts = data[2]
        timeframes = data[3]
        for size in sizes
            size.info = "#{size.name} (#{size.width} x #{size.height})"
        for waiter in size_waiters
            waiter.resolve(sizes)
        size_waiters = []
        for waiter in shift_waiters
            waiter.resolve(shifts)
        shift_waiters = []
        for waiter in forecast_waiters
            waiter.resolve(forecasts)
        forecast_waiters = []
        for waiter in timeframe_waiters
            waiter.resolve(timeframes)
        timeframe_waiters = []
    )
    get_sizes = () ->
        _defer = $q.defer()
        if sizes.length
            _defer.resolve(sizes)
        else
            size_waiters.push(_defer)
        return _defer
    get_shifts = () ->
        _defer = $q.defer()
        if shifts.length
            _defer.resolve(shifts)
        else
            shift_waiters.push(_defer)
        return _defer
    get_forecasts = () ->
        _defer = $q.defer()
        if forecasts.length
            _defer.resolve(forecasts)
        else
            forecast_waiters.push(_defer)
        return _defer
    get_timeframes = () ->
        _defer = $q.defer()
        if timeframes.length
            _defer.resolve(timeframes)
        else
            timeframe_waiters.push(_defer)
        return _defer
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
        _defer = $q.defer()
        get_sizes().promise.then((sizes) ->
            _def_size = (size for size in sizes when size.default)[0]
            _def_dict = get_default()
            _def_dict.graph_setting_size = _def_size.idx
            create(_def_dict).promise.then((new_setting) ->
                _defer.resolve(new_setting)
            )
        )
        return _defer
    create = (setting) ->
        _defer = $q.defer()
        setting.user = _user.idx
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
        "get_sizes": () ->
            return get_sizes().promise
        "get_shifts": () ->
            return get_shifts().promise
        "get_forecasts": () ->
            return get_forecasts().promise
        "get_timeframes": () ->
            return get_timeframes().promise
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
            scope.sizes = []
            icswRrdGraphSettingService.get_sizes().then((sizes) ->
                scope.sizes = sizes
            )
            scope.shifts = []
            icswRrdGraphSettingService.get_shifts().then((shifts) ->
                scope.shifts = shifts
            )
            scope.forecasts = []
            icswRrdGraphSettingService.get_forecasts().then((forecasts) ->
                scope.forecasts = forecasts
            )
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
]).directive("icswRrdGraphTimeFrame", ["$templateCache", "icswRrdGraphSettingService", "$compile", "$timeout", "toaster", ($templateCache, icswRrdGraphSettingService, $compile, $timeout, toaster) ->
    return {
        scope: true
        restrict: "EA"
        scope:
            timeframe: "="
        template: $templateCache.get("icsw.rrd.graphsetting.timeframe")
        link: (scope, el, attrs) ->
            moment().utc()
            scope.timeframes = []
            scope.val =
                current: undefined
                from_data_mom: undefined
                to_date_mom: undefined
                valid: false
            scope.timeframe = scope.val
            icswRrdGraphSettingService.get_timeframes().then((data) ->
                scope.timeframes = data
                scope.val.current = data[0]
                scope.change_tf()
                scope.$watch(
                    () ->
                        return scope.val.from_date_mom
                    (new_val) ->
                        if scope.change_dt_to
                            $timeout.cancel(scope.change_dt_to)
                        scope.change_dt_to = $timeout(scope.update_dt, 2000)
                )
                scope.$watch(
                    () ->
                        return scope.val.to_date_mom
                    (new_val) ->
                        if scope.change_dt_to
                            $timeout.cancel(scope.change_dt_to)
                        scope.change_dt_to = $timeout(scope.update_dt, 2000)
                )
            )
            scope.move_to_now = () ->
                # shift timeframe
                _timeframe = moment.duration(scope.val.to_date_mom.unix() - scope.val.from_date_mom.unix(), "seconds")
                scope.val.from_date_mom = moment().subtract(_timeframe)
                scope.val.to_date_mom = moment()
            scope.set_to_now = () ->
                # set to_date to now
                scope.val.to_date_mom = moment()
            scope.update_dt = () ->
                # force moment
                from_date = moment(scope.val.from_date_mom)
                to_date = moment(scope.val.to_date_mom)
                scope.val.valid = from_date.isValid() and to_date.isValid()
                if scope.val.valid
                    diff = to_date - from_date
                    if diff < 0
                        toaster.pop("warning", "", "exchanged from with to date")
                        scope.val.to_date_mom = from_date
                        scope.val.from_date_mom = to_date
                    else if diff < 60000
                        scope.val.valid = false
            scope.change_tf = () ->
                get_time_string = (short) ->
                    return {
                        "h": "hour"
                        "d": "day"
                        "w": "week"
                        "m": "month"
                        "y": "year"
                        "D": "year"
                    }[short]
                _tf = scope.val.current
                _now = moment()
                if _tf.relative_to_now
                    # special relative to now
                    scope.val.to_date_mom = _now
                    scope.val.from_date_mom = moment(_now).subtract(_tf.seconds, "seconds")
                else
                    tfs = get_time_string(_tf.base_timeframe)
                    _start = _now.startOf(tfs)
                    if _tf.base_timeframe == "D"
                        # fix decade
                        _start.year(10 * parseInt(_start.year() / 10))
                    if _tf.timeframe_offset
                        if _tf.base_timeframe == "D"
                            _start = _start.subtract(-_tf.timeframe_offset * 10, tfs)
                        else
                            _start = _start.subtract(-_tf.timeframe_offset, tfs)
                    scope.val.from_date_mom = _start
                    scope.val.to_date_mom = moment(_start).add(_tf.seconds, "seconds")
    }
])
