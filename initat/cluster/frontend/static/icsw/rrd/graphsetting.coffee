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
).service("icswRrdGraphSettingService", ["$q", "icswCachingCall", "ICSW_URLS", "icswUserService", ($q, icswCachingCall, ICSW_URLS, icswUserService) ->
  _url = ICSW_URLS.REST_GRAPH_SETTING_LIST
  _sets = []
  load_data = () ->
    _defer= $q.defer()
    icswUserService.load().then((user) ->
      $q.all(
        [
          icswCachingCall.fetch("graphset", _url, {"user__in": angular.toJson([user.idx])}, [])
        ]
      ).then((data) ->
        _defer.resolve(data[0])
      )
    )
    return _defer
  return {
    "load": () ->
      return load_data().promise
  }
  console.log _url
]).directive("icswRrdGraphSetting", ["$templateCache", "icswRrdGraphSettingService", "$compile", ($templateCache, icswRrdGraphSettingService, $compile) ->
  return {
    scope: true
    restrict: "EA"
    template: $templateCache.get("icsw.rrd.graphsetting.overview")
    link: (scope, el, attrs) ->
      icswRrdGraphSettingService.load().then((data) ->
        scope.show_settings = () ->
          dia_scope = scope.$new()
          dia_scope.settings = data
          dia_div = $compile("<icsw-rrd-graph-setting-modify></icsw-rrd-graph-setting-modify>")(dia_scope)
          BootstrapDialog.show
            message: dia_div
            draggable: true
            closeable: true
            title: "RRD graphing settings"
            size: BootstrapDialog.SIZE_WIDE
            cssClass: "modal-tall"
      )
  }
]).directive("icswRrdGraphSettingModify", ["$templateCache", "icswRrdGraphSettingService", "$compile", ($templateCache, icswRrdGraphSettingService, $compile) ->
  return {
    scope: true
    restrict: "EA"
    template: $templateCache.get("icsw.rrd.graphsetting.modify")
    link: (scope, el, attrs) ->
      scope.legend_modes = [
        {"short": "f", "long": "full"}
        {"short": "t", "long": "only text"}
        {"short": "n", "long": "nothing"}
      ]
      scope.scale_modes = [
        {"short": "l", "long": "level"}
        {"short": "n", "long": "none"}
        {"short": "t", "long": "to100"}
      ]
      scope.cur_setting = {
        "hide_empty": true
        "include_zero": false
        "merge_devices": false
        "merge_graphs": false
        "legend_mode": scope.legend_modes[0]
        "scale_mode": scope.scale_modes[0]
      }
  }
])
