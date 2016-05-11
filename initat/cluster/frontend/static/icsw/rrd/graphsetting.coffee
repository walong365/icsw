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
    "icsw.rrd.graphsetting",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).service("icswRRDGraphBaseSetting",
[
    "$q", "icswCachingCall", "ICSW_URLS", "icswUserService", "Restangular",
(
    $q, icswCachingCall, ICSW_URLS, icswUserService, Restangular
) ->
    class icswRRDGraphBaseSetting
        constructor: (size_list, timeshift_list, forecast_list, timeframe_list, sensor_action_list) ->
            @size_list = []
            @timeshift_list = []
            @forecast_list = []
            @timeframe_list = []
            @sensor_action_list = []
            @update(size_list, timeshift_list, forecast_list, timeframe_list, sensor_action_list)
            @legend_mode_list = [
                {short: "f", long: "full"}
                {short: "t", long: "only text"}
                {short: "n", long: "nothing"}
            ]
            @scale_mode_list = [
                {short: "l", long: "level"}
                {short: "n", long: "none"}
                {short: "t", long: "to100"}
            ]
            @cf_list = [
                {short: "MIN", long: "minimum"}
                {short: "AVERAGE", long: "average"}
                {short: "MAX", long: "maximum"}
            ]
        update: (size_list, timeshift_list, forecast_list, timeframe_list, sensor_action_list) =>
            for [attr_name, in_list] in [["size_list", size_list], ["timeshift_list", timeshift_list],
            ["forecast_list", forecast_list], ["timeframe_list", timeframe_list],
            ["sensor_action_list", sensor_action_list]]
                @[attr_name].length = 0
                for entry in in_list
                    @[attr_name].push(entry)
            @build_luts()

        enrich_default: (ddict) =>
            # set default values for default
            ddict.graph_setting_size = (size for size in @size_list when size.default)[0].idx
            ddict.graph_setting_timeshift = null
            ddict.graph_setting_forecast = null
            ddict.cf = "MIN"
            ddict.legend_mode = "f"
            ddict.scale_mode = "l"

        build_luts: () =>
            @size_lut = _.keyBy(@size_list, "idx")
            @timeshift_lut = _.keyBy(@timeshift_list, "idx")
            @forecast_lut = _.keyBy(@forecast_list, "idx")
            @timeframe_lut = _.keyBy(@timeframe_list, "idx")
            @sensor_action_lut = _.keyBy(@sensor_action_list, "idx")
            @link()

        link: () =>
            # create info fields
            for size_e in @size_list
                size_e.info = "#{size_e.name} (#{size_e.width} x #{size_e.height})"

]).service("icswRRDGraphBaseSettingService",
[
    "$q", "icswCachingCall", "ICSW_URLS", "icswUserService", "Restangular",
    "icswRRDGraphBaseSetting",
(
    $q, icswCachingCall, ICSW_URLS, icswUserService, Restangular,
    icswRRDGraphBaseSetting,
) ->
    rest_map = [
        [ICSW_URLS.REST_GRAPH_SETTING_SIZE_LIST, {}]
        [ICSW_URLS.REST_GRAPH_SETTING_TIMESHIFT_LIST, {}]
        [ICSW_URLS.REST_GRAPH_SETTING_FORECAST_LIST, {}]
        [ICSW_URLS.REST_GRAPH_TIME_FRAME_LIST, {}]
        [ICSW_URLS.REST_SENSOR_ACTION_LIST, {}]
    ]
    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false

    load_data = (client) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** graphbasesetting loaded ***"
                _result = new icswRRDGraphBaseSetting(data[0], data[1], data[2], data[3], data[4], data[5])
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

    return {
        "load": (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
    }

]).service("icswRRDGraphUserSetting",
[
    "$q", "icswCachingCall", "ICSW_URLS", "icswUserService", "Restangular",
(
    $q, icswCachingCall, ICSW_URLS, icswUserService, Restangular
) ->
    class icswRRDGraphUserSetting
        constructor: (s_list, th_list, @base, @user) ->
            @list = []
            @threshold_list = []
            @_active = undefined
            @update(s_list, th_list)

        update: (s_list, th_list) =>
            @list.length = 0
            for entry in s_list
                @list.push(entry)
            @threshold_list.length = 0
            for entry in th_list
                @threshold_list.push(entry)
            @build_luts()
            @ensure_active()

        ensure_active: () =>
            defer = $q.defer()
            # check actives
            if not @_active
                if not @list.length
                    _def = @get_default()
                    @create_setting(_def).then(
                        (new_set) =>
                            @_active = @list[0]
                            defer.resolve(@_active)
                    )
                else
                    @_active = @list[0]
                    defer.resolve(@_active)
            else
                if not @_active.idx of @lut
                    @_active = @list[0]
                defer.resolve(@_active)
            return defer.promise

        get_default: () =>
            _def = {
                name: "default"
                hide_empty: true
                include_zero: false
                merge_devices: false
                merge_graphs: false
                user: @user.idx
            }
            @base.enrich_default(_def)
            return _def

        build_luts: () =>
            @lut = _.keyBy(@list, "idx")
            @threshold_lut = _.keyBy(@threshold_list, "idx")
            _mv_lut = {}
            for entry in @threshold_list
                if entry.mv_value_entry not of _mv_lut
                    _mv_lut[entry.mv_value_entry] = []
                _mv_lut[entry.mv_value_entry].push(entry)
            @threshold_lut_by_mvv_id = _mv_lut
            console.log "mv_lut=", _mv_lut

        get_active: () =>
            return @_active

        set_active: (act) =>
            @_active = act

        delete_setting: (cur_set) =>
            defer = $q.defer()
            cur_set.remove().then(
                (deleted) =>
                    _.remove(@list, (entry) -> return entry.idx == cur_set.idx)
                    @build_luts()
                    if @_active? and @_active.idx == cur_set.idx
                        # active was deleted
                        @_active = undefined
                        @ensure_active().then(
                            (new_act) =>
                                defer.resolve("deleted and created active")
                        )
                    else
                        defer.resolve("deleted")
            )
            return defer.promise

        create_setting: (new_set) =>
            defer = $q.defer()
            Restangular.all(ICSW_URLS.REST_GRAPH_SETTING_LIST.slice(1)).post(new_set).then(
                (created) =>
                    @list.push(created)
                    @build_luts()
                    defer.resolve(created)
            )
            return defer.promise

        get_new_threshold: (sensor) =>
            _mv = sensor.mean_value
            none_action = (entry for entry in @base.sensor_action_list when entry.action == "none")[0].idx
            threshold = {
                "name": "Threshold for #{sensor.mv_key}"
                "lower_value": _mv - _mv / 10
                "upper_value": _mv + _mv / 10
                "lower_mail": true
                "upper_mail": true
                "lower_enabled": false
                "upper_enabled": false
                "notify_users": []
                "create_user": @user.idx
                "lower_sensor_action": none_action
                "upper_sensor_action": none_action
                "device_selection": undefined
                "mv_value_entry": sensor.mvv_id
            }
            return threshold

        create_threshold_entry: (sensor, threshold) =>
            d = $q.defer()
            Restangular.all(ICSW_URLS.REST_SENSOR_THRESHOLD_LIST.slice(1)).post(threshold).then(
                (new_obj) =>
                    @threshold_list.push(new_obj)
                    @build_luts()
                    sensor.thresholds.push(new_obj)
                    d.resolve(new_obj)
                (not_ok) =>
                    d.reject("create error")
            )
            return d.promise

        remove_threshold_entry: (sensor, threshold) =>
            d = $q.defer()
            threshold.remove().then(
                (removed) =>
                    _.remove(@threshold_list, (entry) -> return entry.idx == threshold.idx)
                    _.remove(sensor.thresholds, (entry) -> return entry.idx == threshold.idx)
                    @build_luts()
                    d.resolve("deleted")
                (not_rem) =>
                    d.resolve("not deleted")
            )
            return d.promise

]).service("icswRRDGraphUserSettingService",
[
    "$q", "icswCachingCall", "ICSW_URLS", "icswUserService", "Restangular",
    "icswRRDGraphBaseSettingService", "icswRRDGraphUserSetting",
(
    $q, icswCachingCall, ICSW_URLS, icswUserService, Restangular,
    icswRRDGraphBaseSettingService, icswRRDGraphUserSetting,
) ->
    rest_map = [
        [ICSW_URLS.REST_GRAPH_SETTING_LIST, {}]
        [ICSW_URLS.REST_SENSOR_THRESHOLD_LIST, {}]
    ]
    _fetch_dict = {}
    _result = undefined
    # load called
    load_called = false

    load_data = (client) ->
        load_called = true
        _wait_list = (icswCachingCall.fetch(client, _entry[0], _entry[1], []) for _entry in rest_map)
        _wait_list.push(icswRRDGraphBaseSettingService.load(client))
        _wait_list.push(icswUserService.load(client))
        _defer = $q.defer()
        $q.all(_wait_list).then(
            (data) ->
                console.log "*** graphusersetting loaded ***"
                _result = new icswRRDGraphUserSetting((entry for entry in data[0] when entry.user == data[3].idx), data[1], data[2], data[3])
                _result.ensure_active().then(
                    (_act) =>
                        _defer.resolve(_result)
                        for client of _fetch_dict
                            # resolve clients
                            _fetch_dict[client].resolve(_result)
                        # reset fetch_dict
                        _fetch_dict = {}
                )
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

    return {
        "load": (client) ->
            if load_called
                # fetch when data is present (after sidebar)
                return fetch_data(client).promise
            else
                return load_data(client).promise
    }

]).directive("icswRrdGraphSetting",
[
    "$templateCache", "icswRRDGraphUserSettingService", "$compile", "icswComplexModalService",
    "blockUI", "toaster", "icswToolsSimpleModalService", "icswRRDGraphSettingBackup", "$q",
(
    $templateCache, icswRRDGraphUserSettingService, $compile, icswComplexModalService,
    blockUI, toaster, icswToolsSimpleModalService, icswRRDGraphSettingBackup, $q,
) ->
    return {
        scope: true
        restrict: "EA"
        template: $templateCache.get("icsw.rrd.graphsetting.overview")
        link: (scope, el, attrs) ->
            scope.settings = []
            icswRRDGraphUserSettingService.load(scope.$id).then(
                (data) ->
                    scope.settings = data
                    scope.current = scope.settings.get_active()
                    scope.edit_settings = () ->
                        sub_scope = scope.$new()
                        sub_scope.base_setting = scope.settings.base
                        sub_scope.user_setting = scope.settings
                        sub_scope.vars = {
                            current: sub_scope.user_setting.get_active()
                            # previous (for changing)
                            prev: sub_scope.user_setting.get_active()
                        }
                        bu_obj = new icswRRDGraphSettingBackup()
                        bu_obj.create_backup(sub_scope.vars.current)

                        sub_scope.create_setting = () ->
                            scope.settings.create_setting(sub_scope.vars.current).then(
                                (new_setting) ->
                                    scope.select_setting(new_setting)
                                    # reset current
                                    bu_obj.restore_backup(sub_scope.vars.current)
                                    sub_scope.vars.current = new_setting
                                    sub_scope.vars.prev = new_setting
                                    # new backup
                                    bu_obj.create_backup(sub_scope.vars.current)
                            )

                        sub_scope.save_setting = () ->
                            scope.settings.get_active().save().then(
                                (ok) ->
                                    bu_obj.create_backup(sub_scope.vars.current)
                            )

                        sub_scope.delete_setting = () ->
                            cur = sub_scope.vars.current
                            icswToolsSimpleModalService("Really delete setting '#{cur.name}' ?").then(
                                (is_ok) ->
                                    scope.settings.delete_setting(sub_scope.vars.current).then(
                                        (done) ->
                                            scope.settings.ensure_active().then(
                                                (new_act) ->
                                                    scope.select_setting(new_act)
                                                    sub_scope.vars.current = new_act
                                                    sub_scope.vars.prev = new_act
                                                    bu_obj.create_backup(sub_scope.vars.current)
                                            )
                                    )
                            )

                        sub_scope.select_setting = (a, b, c) ->
                            bu_obj.restore_backup(sub_scope.vars.prev)
                            bu_obj.create_backup(sub_scope.vars.current)
                            sub_scope.vars.prev = sub_scope.vars.current
                            scope.select_setting(sub_scope.vars.current)

                        icswComplexModalService(
                            {
                                message: $compile($templateCache.get("icsw.rrd.graphsetting.modify"))(sub_scope)
                                title: "RRD graph settings"
                                ok_label: "Close"
                                ok_callback: (modal) ->
                                    # reset current
                                    bu_obj.restore_backup(sub_scope.vars.current)
                                    d = $q.defer()
                                    d.resolve("Close")
                                    return d.promise
                            }
                        ).then(
                            (fin) ->
                                sub_scope.$destroy()
                                scope.current = scope.settings.get_active()
                        )
            )
            scope.select_setting = (setting) ->
                scope.settings.set_active(setting)
    }
]).directive("icswRrdGraphTimeFrame",
[
    "$templateCache", "icswRRDGraphBaseSettingService", "$compile", "$timeout", "toaster",
(
    $templateCache, icswRRDGraphBaseSettingService, $compile, $timeout, toaster
) ->
    return {
        scope: true
        restrict: "EA"
        scope:
            timeframe: "="
            detail: "@"
        template: $templateCache.get("icsw.rrd.graphsetting.timeframe")
        link: (scope, el, attrs) ->
            if parseInt(if scope.detail? then scope.detail else "0")
                scope.show_detail = true
            else
                scope.show_detail = false
            moment().utc()

            _mom_to_date = () ->
                scope.val.from_date = scope.val.from_date_mom.toDate()
                scope.val.to_date = scope.val.to_date_mom.toDate()

            scope.timeframes = []
            scope.val =
                current: undefined
                from_date_mom: undefined
                to_date_mom: undefined
                valid: false

            scope.button_bar = {
                show: true
                now: {
                    show: true
                    text: 'Now'
                },
                today: {
                    show: true
                    text: 'Today'
                },
                clear: {
                    show: false
                    text: 'Clear'
                },
                date: {
                    show: true
                    text: 'Date'
                },
                time: {
                    show: true
                    text: 'Time'
                },
                close: {
                    show: true
                    text: 'Close'
                }
            }
            # from / to picker options
            scope.from_picker = {
                date_options: {
                    format: "dd.MM.yyyy"
                    formatYear: "yyyy"
                    maxDate: new Date()
                    minDate: new Date(2000, 1, 1)
                    startingDay: 1
                    minMode: "day"
                    datepickerMode: "day"
                }
                time_options: {
                    showMeridian: false
                }
                open: false
            }

            scope.to_picker = {
                date_options: {
                    format: "dd.MM.yyyy"
                    formatYear: "yyyy"
                    minDate: new Date(2000, 1, 1)
                    startingDay: 1
                    minMode: "day"
                    datepickerMode: "day"
                }
                time_options: {
                    showMeridian: false
                }
                open: false
            }

            scope.open_calendar = ($event, picker) ->
                scope[picker].open = true

            # set timeframe from parent scope
            scope.timeframe = scope.val
            icswRRDGraphBaseSettingService.load(scope.$id).then(
                (base) ->
                    scope.timeframes = base.timeframe_list
                    scope.val.current = scope.timeframes[0]
                    scope.change_tf()
                    scope.$watch(
                        () ->
                            return scope.val.from_date
                        (new_val) ->
                            if scope.change_dt_to
                                $timeout.cancel(scope.change_dt_to)
                            scope.change_dt_to = $timeout(scope.update_dt, 2000)
                    )
                    scope.$watch(
                        () ->
                            return scope.val.to_date
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
                _mom_to_date()

            scope.set_to_now = () ->
                # set to_date to now
                scope.val.to_date_mom = moment()
                _mom_to_date()

            scope.update_dt = () ->
                # force moment
                from_date = moment(scope.val.from_date)
                to_date = moment(scope.val.to_date)
                scope.val.valid = from_date.isValid() and to_date.isValid()
                [scope.val.from_date_mom, scope.val.to_date_mom] = [from_date, to_date]
                if scope.val.valid
                    diff = to_date - from_date
                    if diff < 0
                        toaster.pop("warning", "", "exchanged from with to date")
                        [scope.val.from_date, scope.val.to_date] = [scope.val.to_date, scope.val.from_date]
                        [scope.val.from_date_mom, scope.val.to_date_mom] = [scope.val.to_date_mom, scope.val.from_date_mom]
                    else if diff < 60000
                        scope.val.valid = false

            scope.change_tf = () ->
                get_time_string = (short) ->
                    return {
                        h: "hour"
                        d: "day"
                        w: "week"
                        m: "month"
                        y: "year"
                        D: "year"
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
                _mom_to_date()
    }
])
