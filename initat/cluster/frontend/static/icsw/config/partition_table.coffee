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
partition_table_module = angular.module(
    "icsw.config.partition_table",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "ui.select", "restangular"
    ]
).controller("icswConfigPartitionTableCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "paginatorSettings", "restDataSource", "$q", "$timeout", "ICSW_URLS", "icswToolsSimpleModalService",
    ($scope, $compile, $filter, $templateCache, Restangular, paginatorSettings, restDataSource, $q, $timeout, ICSW_URLS, icswToolsSimpleModalService) ->
        $scope.entries = []
        $scope.edit_pts = []
        $scope.pagSettings = paginatorSettings.get_paginator("parts", $scope)
        $scope.pagSettings.conf.filter_settings = {
          
        }
        $scope.reload = (cb_func) ->
            wait_list = [
                restDataSource.reload([ICSW_URLS.REST_PARTITION_TABLE_LIST, {}]),
                restDataSource.reload([ICSW_URLS.REST_PARTITION_FS_LIST, {}]),
            ]
            $q.all(wait_list).then((data) ->
                $scope.entries = data[0]
                $scope.partition_fs = data[1]
                if cb_func?
                    cb_func()
            )
        $scope.create = () ->
            names = (entry.name for entry in $scope.entries)
            _idx = -1
            while true
                _idx += 1                  
                new_name = if _idx then "new_part_#{_idx}" else "new_part"
                if not (new_name in names)
                    break
            Restangular.all(ICSW_URLS.REST_PARTITION_TABLE_LIST.slice(1)).post(
                {
                    "name" : new_name
                    "sys_partition_set" : []
                    "lvm_vg_set" : []
                    "partition_disc_set" : []
                    "lvm_lv_set" : []
                }
            ).then((data) ->
                $scope.reload(() ->
                    $scope.edit_part(data)
                )
            )
        $scope.delete_ok = (obj) ->
            return if obj.new_partition_table.length + obj.act_partition_table.length == 0 then true else false
        $scope.not_open = (obj) ->
            return if (entry for entry in $scope.edit_pts when entry.idx == obj.idx).length then false else true
        $scope.close_part = (obj) ->
            $scope.edit_pts = (entry for entry in $scope.edit_pts when entry.idx != obj.idx)
        $scope.delete = (obj) ->
            icswToolsSimpleModalService("really delete partition table '#{obj.name}' ?").then(
                () ->
                    obj.remove().then(
                        $scope.close_part(obj)
                        $scope.entries = (entry for entry in $scope.entries when entry.idx != obj.idx)
                    )
            )
        $scope.edit_part = (obj) ->
            edit_part = (entry for entry in $scope.entries when entry.idx == obj.idx)[0]
            edit_part.tab_active = true
            $scope.edit_pts.push(edit_part)
        $scope.reload()
]).directive("icswConfigDiskLayout", ["$compile", "$templateCache", "Restangular", "ICSW_URLS", "icswSimpleAjaxCall", "$q", ($compile, $templateCache, Restangular, ICSW_URLS, icswSimpleAjaxCall, $q) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.disk.layout")
        scope  : true
        replace : false
        link : (scope, element, attrs) ->
            scope.part = scope.$eval(attrs["partTable"])
            scope.partition_fs = scope.$eval(attrs["partitionFs"])
            scope.edit_obj = scope.part
            scope.$on("icsw.part_changed", (args) ->
                if not scope.create_mode
                    scope.validate()
            )
            scope.valid_label_types = [
                {
                    "label" : "msdos",
                    "info_string" : "MSDOS",
                },
                {
                    "label" : "gpt",
                    "info_string" : "GPT",
                },
            ]
            scope.get_partition_fs = () ->
                for entry in scope.partition_fs
                    entry.full_info = "#{entry.name}" + if entry.need_mountpoint then " (need mountpoint)" else "" 
                return scope.partition_fs
            scope.partition_need_mountpoint = (part) ->
                if part.partition_fs
                    return (entry.need_mountpoint for entry in scope.partition_fs when entry.idx == part.partition_fs)[0]
                else
                    return true
            scope.validate = () ->
                if !scope.part.idx?
                    return
                icswSimpleAjaxCall(
                    url : ICSW_URLS.SETUP_VALIDATE_PARTITION
                    data : {
                        "pt_pk" : scope.part.idx
                    }
                    ignore_log_level: true
                ).then(
                    (xml) ->
                        error_list = []
                        $(xml).find("problem").each (idx, cur_p) =>
                            cur_p = $(cur_p)
                            error_list.push(
                                {
                                    "msg" : cur_p.text()
                                    "level" : parseInt(cur_p.attr("level"))
                                    "global" : if parseInt(cur_p.attr("g_problem")) then true else false
                                }
                            )
                        is_valid = if parseInt($(xml).find("problems").attr("valid")) then true else false
                        scope.edit_obj.valid = is_valid
                        scope.error_list = error_list
                )
            scope.error_list = []
            # watch edit_obj and validate if changed
            scope.$watch("edit_obj", () ->
                if not scope.create_mode
                    scope.validate()
            )
            scope.layout_edit = new angular_edit_mixin(scope, $templateCache, $compile, Restangular, $q)
            scope.layout_edit.change_signal = "icsw.part_changed"
            scope.layout_edit.create_template = "partition.disc.form"
            scope.layout_edit.create_rest_url = Restangular.all(ICSW_URLS.REST_PARTITION_DISC_LIST.slice(1))
            scope.layout_edit.create_list = scope.part.partition_disc_set
            scope.layout_edit.modify_data_after_post = (new_disc) ->
                new_disc.partition_set = []
                new_disc.sys_partition_set = []
            scope.layout_edit.new_object = (scope) ->
                return {
                    "partition_table"   : scope.edit_obj.idx
                    "disc"              : "/dev/sd"
                    "label_type"        : "gpt"
                }
            scope.sys_edit = new angular_edit_mixin(scope, $templateCache, $compile, Restangular, $q)
            scope.sys_edit.change_signal = "icsw.part_changed"
            scope.sys_edit.create_template = "partition.sys.form"
            scope.sys_edit.create_rest_url = Restangular.all(ICSW_URLS.REST_SYS_PARTITION_LIST.slice(1))
            scope.sys_edit.create_list = scope.part.sys_partition_set
            scope.sys_edit.new_object = (scope) ->
                return {
                    "partition_table" : scope.edit_obj.idx
                    "name"            : "new"
                    "mount_options"   : "defaults"
                    "mountpoint"      : "/"
                }
            scope.modify = () ->
                scope.part.put()
    }
]).directive("icswConfigPartitionTable", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        scope : false
        template : $templateCache.get("partition.table.form")
        link : (scope, element, attrs) ->
             scope.edit_obj = scope.data
    }
]).directive("icswConfigPartitionTableDisc", ["$compile", "$templateCache", "$q", "Restangular", "ICSW_URLS", ($compile, $templateCache, $q, Restangular, ICSW_URLS) ->
    return {
        restrict : "EA"
        #replace : true
        scope : true
        template : $templateCache.get("icsw.config.partition.table.disc")
        link : (scope, element, attrs) ->
            if scope.disc.partition_set.length
                # dirty hack but working
                element.after($("<tr>").append($templateCache.get("icsw.config.partition.table.header")))
            scope.partition_fs = scope.$eval(attrs["partitionFs"])
            scope.disc_edit = new angular_edit_mixin(scope, $templateCache, $compile, Restangular, $q)
            scope.disc_edit.change_signal = "icsw.part_changed"
            scope.disc_edit.create_template = "partition.form"
            scope.disc_edit.edit_template = "partition.disc.form"
            scope.disc_edit.modify_rest_url = ICSW_URLS.REST_PARTITION_DISC_DETAIL.slice(1).slice(0, -2)
            scope.disc_edit.create_rest_url = Restangular.all(ICSW_URLS.REST_PARTITION_LIST.slice(1))
            scope.disc_edit.create_list = scope.disc.partition_set
            scope.disc_edit.delete_list = scope.edit_obj.partition_disc_set
            scope.disc_edit.delete_confirm_str = (obj) -> "Really delete disc '#{obj.disc}' ?"
            scope.disc_edit.new_object = (scope) ->
                return {
                    "size" : 128
                    "partition_disc" : scope.disc.idx
                    "partition_fs" : (entry.idx for entry in scope.partition_fs when entry.name == "btrfs")[0]
                    "fs_freq" : 1
                    "fs_passno" : 2
                    "pnum" : 1
                    "warn_threshold" : 85
                    "crit_threshold" : 95
                    "mount_options" : "defaults"
                    "partition_hex" : "82"
                }
    }
]).directive("icswConfigPartitionTablePartition", ["$compile", "$templateCache", "$q", "Restangular", "ICSW_URLS", ($compile, $templateCache, $q, Restangular, ICSW_URLS) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.partition.table.partition")
        link : (scope, element, attrs) ->
            scope.part_edit = new angular_edit_mixin(scope, $templateCache, $compile, Restangular, $q)
            scope.part_edit.change_signal = "icsw.part_changed"
            scope.part_edit.edit_template = "partition.form"
            scope.part_edit.modify_rest_url = ICSW_URLS.REST_PARTITION_DETAIL.slice(1).slice(0, -2)
            scope.part_edit.delete_list = scope.disc.partition_set
            scope.part_edit.delete_confirm_str = (obj) -> "Really delete partition '#{obj.pnum}' ?"
    }
]).directive("icswConfigPartitionTableSystemPartition", ["$compile", "$templateCache", "$q", "Restangular", "ICSW_URLS", ($compile, $templateCache, $q, Restangular, ICSW_URLS) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.partition.table.system.partition")
        link : (scope, element, attrs) ->
            scope.sys_edit = new angular_edit_mixin(scope, $templateCache, $compile, Restangular, $q)
            scope.sys_edit.change_signal = "icsw.part_changed"
            scope.sys_edit.edit_template = "partition.sys.form"
            scope.sys_edit.modify_rest_url = ICSW_URLS.REST_SYS_PARTITION_DETAIL.slice(1).slice(0, -2)
            scope.sys_edit.delete_list = scope.edit_obj.sys_partition_set
            scope.sys_edit.delete_confirm_str = (obj) -> "Really delete sys partition '#{obj.name}' ?"
    }
]).directive("icswConfigPartitionTableRow", ["$compile", "$templateCache", ($compile, $templateCache) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.config.partition.table.row")
    }
])
