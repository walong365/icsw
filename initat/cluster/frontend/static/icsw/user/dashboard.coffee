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
DT_FORM = "YYYY-MM-DD HH:mm"

# dashboard depends on user module
dashboard_module = angular.module(
    "icsw.user.dashboard",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular",
        "noVNC", "ui.select", "icsw.tools", "icsw.user.password", "icsw.user", "icsw.user.license",
    ]
).controller("icswUserJobInfoCtrl", ["$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$timeout", "$uibModal", "ICSW_URLS", "icswSimpleAjaxCall",
    ($scope, $compile, $filter, $templateCache, Restangular, $q, $timeout, $uibModal, ICSW_URLS, icswSimpleAjaxCall)->
        $scope.jobs_waiting = []
        $scope.jobs_running = []
        $scope.jobs_finished = []
        $scope.jobinfo_valid = false
        class jobinfo_timedelta
            constructor: (@name, @timedelta_description) ->
        $scope.all_timedeltas = [
            new jobinfo_timedelta("last 15 minutes", [15, "minutes"])
            new jobinfo_timedelta("last hour", [1, "hours"])
            new jobinfo_timedelta("last 4 hours", [4, "hours"])
            new jobinfo_timedelta("last day", [1, "days"])
            new jobinfo_timedelta("last week", [1, "weeks"])
        ]
        $scope.set_jobinfo_timedelta = (ts) ->
            $scope.last_jobinfo_timedelta = ts
            jobsfrom = moment().subtract(
                ts.timedelta_description[0],
                ts.timedelta_description[1]
            ).unix()
            icswSimpleAjaxCall(
                url      : ICSW_URLS.RMS_GET_RMS_JOBINFO
                data     :
                    "jobinfo_jobsfrom" : jobsfrom
                dataType : "json"
            ).then((json) ->
              $scope.jobinfo_valid = true
              $scope.jobs_running = json.jobs_running
              $scope.jobs_waiting = json.jobs_waiting
              $scope.jobs_finished = json.jobs_finished
            )
        $scope.set_jobinfo_timedelta( $scope.all_timedeltas[1] )
        listmax = 15
        jobidToString = (j) -> 
            if j[1] != ""
                return " "+j[0]+":"+j[1]
            else
                return " "+j[0]
                    
        $scope.longListToString = (l) ->
            if l.length < listmax
                return [jobidToString(i) for i in l].toString()
            else
                return (jobidToString(i) for i in l[0..listmax]).toString() + ", ..."
]).directive("icswUserJobInfo", ["$templateCache", ($templateCache) ->
        restrict : "EA"
        template : $templateCache.get("icsw.user.job.info")
        link: (scope, element, attrs) ->
]).directive("icswUserVduOverview", ["$compile", "$window", "$templateCache", "icswTools", "ICSW_URLS", "icswSimpleAjaxCall", ($compile, $window, $templateCache, icswTools, ICSW_URLS, icswSimpleAjaxCall) ->
        restrict : "EA"
        template : $templateCache.get("icsw.user.vdu.overview")
        link: (scope, element, attrs) ->
            scope.object = undefined
            
            scope.ips_for_devices = {}
            scope.ips_loaded = false

            scope.single_vdus_index = ""
            # TODO: get this from url via route or new django settings service. Needs to hide sidebar as well.
            scope.single_vdus = undefined
            scope.show_single_vdus = false

            scope.virtual_desktop_sessions = []
            scope.virtual_desktop_user_setting = []
            scope.$watch(attrs["object"], (new_val) ->
                scope.object = new_val
                    
                if scope.object?
                    scope.virtual_desktop_sessions = scope.virtual_desktop_user_setting.filter((vdus) ->  vdus.user == scope.object.idx && vdus.to_delete == false)
                    # get all ips
                    scope.retrieve_device_ip vdus.device for vdus in scope.virtual_desktop_sessions

                    if scope.single_vdus_index
                        scope.single_vdus = scope.virtual_desktop_user_setting.filter((vdus) -> vdus.idx == scope.single_vdus_index)[0]
                        scope.show_single_vdus = true
            )
            scope.get_vnc_display_attribute_value = (geometry) ->
                [w, h] = screen_size.parse_screen_size(geometry)
                return "{width:"+w+",height:"+h+",fitTo:'width',}"
            scope.get_device_by_index = (index) ->
                return _.find(scope.device, (vd) -> vd.idx == index)
            scope.get_virtual_desktop_protocol = (index) ->
                return _.find(scope.virtual_desktop_protocol, (vd) -> vd.idx == index)
            scope.get_window_manager = (index) ->
                return _.find(scope.window_manager, (vd) -> vd.idx == index)
            scope.open_vdus_in_new_tab = (vdus) ->
                url = ICSW_URLS.MAIN_VIRTUAL_DESKTOP_VIEWER
                $window.open(url + "?vdus_index=#{vdus.idx}")
                # prevent angular security error (due to coffeescript returning the last result)
                return false
            scope.show_viewer_command_line = (vdus) ->
                vdus.show_viewer_command_line = !vdus.show_viewer_command_line
            scope.retrieve_device_ip = (index) ->
                # set some dummy value so that the vnc directive doesn't complain
                dummy_ip = "0.0.0.0"
                scope.ips_for_devices[index] = dummy_ip
                icswSimpleAjaxCall(
                    url      : ICSW_URLS.USER_GET_DEVICE_IP
                    data     :
                        "device" : index
                    dataType : "json"
                ).then((json) ->
                    scope.ips_for_devices[index] = json.ip
                    if _.indexOf(scope.ips_for_devices, dummy_ip) == -1
                        # all are loaded
                        scope.ips_loaded = true

                        # calc command lines
                        for vdus in scope.virtual_desktop_sessions
                            vdus.viewer_cmd_line = virtual_desktop_utils.get_viewer_command_line(vdus, scope.ips_for_devices[vdus.device])
                )

            scope.download_vdus_start_script = (vdus) ->
                # create .vnc file (supported by at least tightvnc and realvnc on windows)
                content = ["[Connection]\n",
                          "Host=#{ scope.ips_for_devices[vdus.device] }:#{ vdus.effective_port }\n",
                          "Password=#{ vdus.vnc_obfuscated_password }\n"]
                blob = new Blob(content, {type: "text/plain;charset=utf-8"});
                # use FileSaver.js
                saveAs(blob, "#{ scope.get_device_by_index(vdus.device).name }.vnc");
]).controller("icswUserIndexCtrl", ["$scope", "$timeout", "$window", "ICSW_URLS", "icswAcessLevelService", "icswSimpleAjaxCall",
    ($scope, $timeout, $window, ICSW_URLS, icswAcessLevelService, icswSimpleAjaxCall) ->
        $scope.ICSW_URLS = ICSW_URLS
        $scope.show_index = true
        $scope.quick_open = true
        $scope.ext_open = false
        $scope.diskusage_open = true
        $scope.vdesktop_open = true
        $scope.jobinfo_open = true
        $scope.show_devices = false
        $scope.NUM_QUOTA_SERVERS = 0
        icswSimpleAjaxCall(
            {
                "url": ICSW_URLS.USER_GET_NUM_QUOTA_SERVERS
                "dataType": "json"
            }
        ).then(
            (json) ->
                $scope.NUM_QUOTA_SERVERS = json.num_quota_servers
        )
        $scope.has_menu_permission = icswAcessLevelService.has_menu_permission
]).directive("indexView", ["$templateCache", "icswAcessLevelService", "icswUserLicenseDataService", ($templateCache, icswAcessLevelService, icswUserLicenseDataService) ->
    return {
        restrict : "EA"
        template : $templateCache.get("icsw.user.index")
        link : (scope, element, attrs) ->
            scope.gridsterOpts = {
                columns: 6
                pushing: true
                floating: true
                swapping: false
                width: 'auto'
                colWidth: 'auto'
                rowHeight: '200'
                margins: [10, 10]
                outerMargin: true
                isMobile: true
                mobileBreakPoint: 600
                mobileModeEnabled: true
                minColumns: 1
                minRows: 2
                maxRows: 100,
                defaultSizeX: 2
                defaultSizeY: 1
                minSizeX: 1
                maxSizeX: null
                minSizeY: 1
                maxSizeY: null
                resizable: {
                   enabled: true,
                   handles: ['n', 'e', 's', 'w', 'ne', 'se', 'sw', 'nw']
                },
                draggable: {
                   enabled: true
                   handle: '.my-class'
                }
            }
            scope.elements = [
                { sizeX: 2, sizeY: 1, row: 0, col: 0, class: "warning", title: "Quick links", "template": "icsw.dashboard.quicklinks" },
                { sizeX: 2, sizeY: 2, row: 0, col: 2, class: "success", title: "External links", template: "icsw.dashboard.externallinks" },
                # Disk usage and Quota info from <ng-pluralize count="NUM_QUOTA_SERVERS" when="{'0' : 'no quota servers', 'one' : 'one quota server', 'other' : '{} quota servers'}"></ng-pluralize>
                { sizeX: 1, sizeY: 1, row: 0, col: 4, class: "success", title: "Disk usage and Quota info ???", template: "icsw.dashboard.diskquota" },
                { sizeX: 1, sizeY: 1, row: 0, col: 5, class: "primary", title: "Virtual desktops", template: "icsw.dashboard.virtualdesktops" },
                { sizeX: 2, sizeY: 1, row: 1, col: 0, class: "success", title: "Job info", template: "icsw.dashboard.jobinfo" },
            ]
            scope.get_panel_class = (item) ->
                return "panel-" + item.class
            scope.$on(
                "gridster-item-resized"
                (item) ->
                    # console.log "gite", item
            )
            scope.$watch(
                "elements"
                (els) ->
                    # console.log "c", els
                true
            )
            icswAcessLevelService.install(scope)
            scope.lds = icswUserLicenseDataService
    }
]).directive("icswDashboardElement", ["$templateCache", "$compile", ($templateCache, $compile) ->
    return {
        restrict: "E"
        link: (scope, element, attrs) ->
            if attrs["element"]?
                _el_name = attrs["element"]
                element.append($compile($templateCache.get(_el_name))(scope))
    }
])

virtual_desktop_utils = {
    get_viewer_command_line: (vdus, ip) ->
        return "echo \"#{vdus.password}\" | vncviewer -autopass #{ip}:#{vdus.effective_port }\n"
}
