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

# livestatus sources and filter functions (components)

angular.module(
    "icsw.livestatus.comp.category",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).config(["icswLivestatusPipeRegisterProvider", (icswLivestatusPipeRegisterProvider) ->
    icswLivestatusPipeRegisterProvider.add("icswLivestatusMonCategoryFilter", true)
    icswLivestatusPipeRegisterProvider.add("icswLivestatusDeviceCategoryFilter", true)
]).service('icswLivestatusMonCategoryFilter',
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusMonCategoryFilter extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusMonCategoryFilter", true, true)
            @set_template(
                '<h4>Monitoring Category Filter</h4>
                <icsw-config-category-tree-select icsw-mode="filter" icsw-sub-tree="\'mon\'" icsw-mode="filter" icsw-connect-element="con_element"></icsw-config-category-tree-select>'
                "Monitoring Category Filter"
                5
                2
            )
            @_emit_data = new icswMonitoringResult()
            @_cat_filter = undefined
            @_latest_data = undefined
            @new_data_notifier = $q.defer()
            #  @new_data_notifier = $q.defer()

        set_category_filter: (sel_cat) ->
            @_cat_filter = sel_cat
            @pipeline_settings_changed(@_cat_filter)
            if @_latest_data?
                @emit_data_downstream(@new_data_received(@_latest_data))

        get_category_filter: () ->
            return @_cat_filter

        restore_settings: (f_list) ->
            @_cat_filter = f_list

        new_data_received: (data) ->
            @_latest_data = data
            if @_cat_filter?
                @_emit_data.apply_category_filter(@_cat_filter, @_latest_data, "mon")
            @new_data_notifier.notify(data)
            return @_emit_data

        pipeline_reject_called: (reject) ->
            # ignore, stop processing
]).service('icswLivestatusDeviceCategoryFilter',
[
    "$q", "icswMonLivestatusPipeBase", "icswMonitoringResult",
(
    $q, icswMonLivestatusPipeBase, icswMonitoringResult,
) ->
    class icswLivestatusDeviceCategoryFilter extends icswMonLivestatusPipeBase
        constructor: () ->
            super("icswLivestatusDeviceCategoryFilter", true, true)
            @set_template(
                '<h4>Device Category Filter</h4>
                <icsw-config-category-tree-select icsw-mode="filter" icsw-sub-tree="\'device\'" icsw-mode="filter" icsw-connect-element="con_element"></icsw-config-category-tree-select>'
                "Device Category Filter"
                4
                2
            )
            @_emit_data = new icswMonitoringResult()
            @_cat_filter = undefined
            @_latest_data = undefined
            @new_data_notifier = $q.defer()
            #  @new_data_notifier = $q.defer()

        set_category_filter: (sel_cat) ->
            @_cat_filter = sel_cat
            @pipeline_settings_changed(@_cat_filter)
            if @_latest_data?
                @emit_data_downstream(@new_data_received(@_latest_data))

        get_category_filter: () ->
            return @_cat_filter

        restore_settings: (f_list) ->
            @_cat_filter = f_list

        new_data_received: (data) ->
            @_latest_data = data
            if @_cat_filter?
                @_emit_data.apply_category_filter(@_cat_filter, @_latest_data, "device")
            @new_data_notifier.notify(data)
            return @_emit_data

        pipeline_reject_called: (reject) ->
            # ignore, stop processing
])
