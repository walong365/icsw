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
    "icsw.rrd.graphsetting",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular"
    ]
).service("icswRRDGraphBasicSetting",
[
    "$q",
(
    $q,
) ->
    class icswRRDGraphBasicSetting
        constructor: () ->
            # settings switch visible
            @display_settings_switch = true
            # show settings
            @show_settings = true
            # tree switch visible
            @display_tree_switch = true
            # show tree
            @show_tree = true
            # draw on init
            @draw_on_init = false
            # search string, not used for seleciton on initial load 
            @search_string = ""
            # initial select keys, can be used for initial selection
            @auto_select_keys = []
            
        clear_search_string: () =>
            @search_string = ""
            
        get_search_re: () =>
            if @search_string
                try
                    cur_re = new RegExp(@search_string, "gi")
                catch
                    cur_re = new RegExp("^$", "gi")
            else
                cur_re = new RegExp("^$", "gi")
            return cur_re
            
        set_auto_select_re: () =>
            if @auto_select_keys.length
                try
                    @auto_select_re = new RegExp(@auto_select_keys.join("|"))
                catch
                    @auto_select_re = null
            else
                @auto_select_re = null

]).service("icswRRDGraphBaseSetting",
[
    "$q", "ICSW_URLS", "Restangular",
(
    $q, ICSW_URLS, Restangular
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
            for [attr_name, in_list] in [
                ["size_list", size_list]
                ["timeshift_list", timeshift_list]
                ["forecast_list", forecast_list]
                ["timeframe_list", timeframe_list]
                ["sensor_action_list", sensor_action_list]
            ]
                @[attr_name].length = 0
                for entry in in_list
                    @[attr_name].push(entry)
            @build_luts()

        enrich_default: (ddict) =>
            # set default values for default
            ddict.graph_setting_size = (size for size in @size_list when size.default)[0].idx
            ddict.graph_setting_timeshift = null
            ddict.graph_setting_forecast = null
            ddict.cf = @cf_list[0].short
            ddict.legend_mode = @legend_mode_list[0].short
            ddict.scale_mode = @scale_mode_list[0].short

        build_luts: () =>
            @size_lut = _.keyBy(@size_list, "idx")
            @timeshift_lut = _.keyBy(@timeshift_list, "idx")
            @forecast_lut = _.keyBy(@forecast_list, "idx")
            @timeframe_lut = _.keyBy(@timeframe_list, "idx")
            @sensor_action_lut = _.keyBy(@sensor_action_list, "idx")
            @link()

        resolve: (setting) =>
            # replaces all idx with settings
            for [name, dict] in [
                ["graph_setting_size", "size_lut"]
                ["graph_setting_timeshift", "timeshift_lut"]
                ["graph_setting_forecast", "forecast_lut"]
            ]
                if setting[name]? and angular.isNumber(setting[name])
                    setting[name] = Restangular.stripRestangular(@[dict][setting[name]])
                if not setting[name]?
                    delete setting[name]

        link: () =>
            # create info fields
            for size_e in @size_list
                size_e.info = "#{size_e.name} (#{size_e.width} x #{size_e.height})"

]).service("icswRRDGraphBaseSettingService",
[
    "$q", "ICSW_URLS", "Restangular",
    "icswRRDGraphBaseSetting", "icswTreeBase";
(
    $q, ICSW_URLS, Restangular,
    icswRRDGraphBaseSetting, icswTreeBase,
) ->
    rest_map = [
        ICSW_URLS.REST_GRAPH_SETTING_SIZE_LIST
        ICSW_URLS.REST_GRAPH_SETTING_TIMESHIFT_LIST
        ICSW_URLS.REST_GRAPH_SETTING_FORECAST_LIST
        ICSW_URLS.REST_GRAPH_TIME_FRAME_LIST
        ICSW_URLS.REST_SENSOR_ACTION_LIST
    ]
    return new icswTreeBase(
        "RRDGraphBaseSetting"
        icswRRDGraphBaseSetting
        rest_map
        ""
    )

]).service("icswRRDGraphUserSetting",
[
    "$q", "ICSW_URLS", "Restangular",
(
    $q, ICSW_URLS, Restangular
) ->
    class icswRRDGraphUserSetting
        constructor: (s_list, th_list, @base, user) ->
            @user = user.user
            @list = []
            @threshold_list = []
            @_active = undefined
            @update((entry for entry in s_list when entry.user == @user.idx), th_list)

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

        set_custom_size: (setting, w, h) =>
            setting.graph_setting_size = {
                width: w
                height: h
            }
            
        build_luts: () =>
            for entry in @list
                if not entry.$$synced?
                    entry.$$synced = true
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

        resolve: (setting) =>
            # returns active elemt with all subelements expanded
            _act = Restangular.stripRestangular(setting)
            @base.resolve(_act)
            return _act

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
                    # is always synced
                    created.$$synced = true
                    @list.push(created)
                    @build_luts()
                    defer.resolve(created)
            )
            return defer.promise

        get_new_threshold: (sensor) =>
            _mv = sensor.mean_value
            none_action = (entry for entry in @base.sensor_action_list when entry.action == "none")[0].idx
            threshold = {
                name: "Threshold for #{sensor.mv_key}"
                lower_value: _mv - _mv / 10
                upper_value: _mv + _mv / 10
                lower_mail: true
                upper_mail: true
                lower_enabled: false
                upper_enabled: false
                notify_users: []
                create_user: @user.idx
                lower_sensor_action: none_action
                upper_sensor_action: none_action
                device_selection: undefined
                mv_value_entry: sensor.mvv_id
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
    "ICSW_URLS", "icswUserService",
    "icswRRDGraphBaseSettingService", "icswRRDGraphUserSetting", "icswTreeBase",
(
    ICSW_URLS, icswUserService, 
    icswRRDGraphBaseSettingService, icswRRDGraphUserSetting, icswTreeBase,
) ->
    rest_map = [
        ICSW_URLS.REST_GRAPH_SETTING_LIST
        ICSW_URLS.REST_SENSOR_THRESHOLD_LIST
    ]
    class LocalTree extends icswTreeBase
        extra_calls: (client) =>
            return [
                icswRRDGraphBaseSettingService.load(client)
                icswUserService.load(client)
            ]

    return new LocalTree(
        "RRDGraphUserSettings"
        icswRRDGraphUserSetting
        rest_map
        ""
    )

]).directive("icswRrdGraphSetting",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        scope: true
        restrict: "EA"
        template: $templateCache.get("icsw.rrd.graphsetting.overview")
        controller: "icswRrdGraphSettingCtrl"
    }
]).controller("icswRrdGraphSettingCtrl",
[
    "$scope", "icswRRDGraphUserSettingService", "$compile", "icswComplexModalService",
    "blockUI", "toaster", "icswToolsSimpleModalService", "icswRRDGraphSettingBackup", "$q",
    "$templateCache",
(
    $scope, icswRRDGraphUserSettingService, $compile, icswComplexModalService,
    blockUI, toaster, icswToolsSimpleModalService, icswRRDGraphSettingBackup, $q,
    $templateCache,
) ->
    $scope.struct = {
        # settings tree
        settings: []
        # current setting
        current: undefined
    }

    load = () ->
        icswRRDGraphUserSettingService.load($scope.$id).then(
            (data) ->
                $scope.struct.settings = data
                $scope.struct.current = $scope.struct.settings.get_active()
        )

    load()
    
    $scope.select_setting = (setting) ->
        $scope.struct.settings.set_active(setting)

    $scope.save_current = () ->
        current = $scope.struct.current
        if not current.$$synced
            blockUI.start()
            $scope.struct.current.save().then(
                (ok) ->
                    blockUI.stop()
                    # only save sets synced to true
                    $scope.struct.current.$$synced = true
                (notok) ->
                    blockUI.stop()
            )

    $scope.edit_settings = () ->
        sub_scope = $scope.$new()
        sub_scope.base_setting = $scope.struct.settings.base
        sub_scope.user_setting = $scope.struct.settings
        sub_scope.vars = {
            current: sub_scope.user_setting.get_active()
            # previous (for changing)
            prev: sub_scope.user_setting.get_active()
        }
        # to check for changes
        bu_obj = new icswRRDGraphSettingBackup()
        bu_obj.create_backup(sub_scope.vars.current)

        # flags for current changed and name is new (== new setting can be created)
        sub_scope.name_is_new = false

        _check_changed = () ->
            # update changed flag and name_is_new
            if bu_obj.changed(sub_scope.vars.current)
                sub_scope.vars.current.$$synced = false
            all_names = (entry.name for entry in $scope.struct.settings.list when entry.idx != sub_scope.vars.current.idx)
            if not bu_obj.attribute_changed(sub_scope.vars.current, "name")
                sub_scope.name_is_new = false
            else
                sub_scope.name_is_new = sub_scope.vars.current.name not in all_names

        sub_scope.create_setting = () ->
            $scope.struct.settings.create_setting(sub_scope.vars.current).then(
                (new_setting) ->
                    $scope.select_setting(new_setting)
                    sub_scope.vars.current = new_setting
                    sub_scope.vars.prev = new_setting
                    # new backup
                    bu_obj.create_backup(sub_scope.vars.current)
                    _check_changed()
            )

        sub_scope.save_setting = () ->
            $scope.struct.settings.get_active().save().then(
                (ok) ->
                    bu_obj.create_backup(sub_scope.vars.current)
                    # only save sets synced to true
                    sub_scope.vars.current.$$synced = true
                    _check_changed()
            )

        sub_scope.delete_setting = () ->
            cur = sub_scope.vars.current
            icswToolsSimpleModalService("Really delete setting '#{cur.name}' ?").then(
                (is_ok) ->
                    $scope.struct.settings.delete_setting(sub_scope.vars.current).then(
                        (done) ->
                            $scope.struct.settings.ensure_active().then(
                                (new_act) ->
                                    $scope.select_setting(new_act)
                                    sub_scope.vars.current = new_act
                                    sub_scope.vars.prev = new_act
                                    bu_obj.create_backup(sub_scope.vars.current)
                            )
                    )
            )

        sub_scope.select_setting = (a, b, c) ->
            bu_obj.create_backup(sub_scope.vars.current)
            sub_scope.vars.prev = sub_scope.vars.current
            $scope.select_setting(sub_scope.vars.current)
            _check_changed()

        sub_scope.$watch(
            # track changes
            "vars.current"
            (new_val) ->
                _check_changed()
            true
        )

        icswComplexModalService(
            {
                message: $compile($templateCache.get("icsw.rrd.graphsetting.modify"))(sub_scope)
                title: "RRD Graph Settings"
                closable: true
                ok_label: "Close"
                ok_callback: (modal) ->
                    d = $q.defer()
                    # reset current
                    d.resolve("Close")
                    return d.promise
            }
        ).then(
            (fin) ->
                sub_scope.$destroy()
                $scope.struct.current = $scope.struct.settings.get_active()
        )
]).service("icswTimeFrameService",
[
    "$q",
(
    $q,
) ->
    class icswTimeFrame
        constructor: (minimum_diff=60000) ->
            @current = undefined
            @from_date_mom = undefined
            @to_date_mom = undefined
            @valid = false
            @external_set = false
            @changed = 0
            # to be valid
            @minimum_diff = minimum_diff

        date_to_mom: () =>
            console.log @from_date, @to_date
            @from_date_mom = moment(@from_date)
            @to_date_mom = moment(@to_date)

        mom_to_date: () =>
            @from_date = @from_date_mom.toDate()
            @to_date = @to_date_mom.toDate()

        check_validity: () =>
            @valid = @from_date_mom.isValid() and @to_date_mom.isValid()
            return @valid

        check_for_exchange: () =>
            # check if from < to
            diff = @to_date - @from_date
            _exc = false
            if diff < 0
                [@from_date_mom, @to_date_mom] = [@to_date_mom, @from_date_mom]
                @mom_to_date()
                _exc = true
            return _exc

        check_for_minimum_diff: () =>
            diff = @to_date - @from_date
            if diff < @minimum_diff
                @valid = false
            return @valid

        set_from_to_mom: (from_mom, to_mom) =>
            @external_set = true
            @from_date_mom = from_mom
            @to_date_mom = to_mom
            @mom_to_date()

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

            scope.timeframes = []
            scope.val = scope.timeframe

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

            icswRRDGraphBaseSettingService.load(scope.$id).then(
                (base) ->
                    scope.timeframes = base.timeframe_list
                    scope.val.current = scope.timeframes[0]
                    if not scope.val.external_set
                        scope.change_tf()
                    scope.$watch(
                        () ->
                            return scope.val.from_date
                        (new_val) ->
                            scope.val.from_date_mom = moment(scope.val.from_date)
                            if scope.change_dt_to
                                $timeout.cancel(scope.change_dt_to)
                            scope.change_dt_to = $timeout(scope.update_dt, 2000)
                    )
                    scope.$watch(
                        () ->
                            return scope.val.to_date
                        (new_val) ->
                            scope.val.to_date_mom = moment(scope.val.to_date)
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
                scope.val.mom_to_date()

            scope.set_to_now = () ->
                # set to_date to now
                scope.val.to_date_mom = moment()
                scope.val.mom_to_date()

            scope.update_dt = () ->
                # force moment
                scope.val.date_to_mom()
                if scope.val.check_validity()
                    if scope.val.check_for_exchange()
                        toaster.pop("warning", "", "exchanged from with to date")
                    if not scope.val.check_for_minimum_diff()
                        toaster.pop("error", "", "timespan is too small")

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
                scope.val.mom_to_date()
    }
])
