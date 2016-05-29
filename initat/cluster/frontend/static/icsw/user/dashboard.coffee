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
DT_FORM = "YYYY-MM-DD HH:mm"

# dashboard depends on user module
dashboard_module = angular.module(
    "icsw.user.dashboard",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular",
        "noVNC", "ui.select", "icsw.tools", "icsw.user.password", "icsw.user", "icsw.user.license",
    ]
).config(["$stateProvider", "icswRouteExtensionProvider", ($stateProvider, icswRouteExtensionProvider) ->
    $stateProvider.state(
        "main.dashboard",
          {
              url: "/dashboard"
              templateUrl: "icsw/main/dashboard.html"
              icswData: icswRouteExtensionProvider.create
                  pageTitle: "Dashboard"
          }
    )
]).config(["$stateProvider", "icswRouteExtensionProvider", ($stateProvider, icswRouteExtensionProvider) ->
    $stateProvider.state(
        "main.userjobinfo", {
            url: "/userjobinfo"
            templateUrl: 'icsw.dashboard.jobinfo'
            icswData: icswRouteExtensionProvider.create
                pageTitle: "RMS Information"
                licenses: ["rms"]
                service_types: ["rms-server"]
                rights: ["user.rms_show"]
                dashboardEntry:
                    size_x: 3
                    size_y: 2
        }
    ).state(
        "main.userquotainfo", {
            url: "/userquotainfo"
            templateUrl: 'icsw.dashboard.diskquota'
            icswData: icswRouteExtensionProvider.create
                pageTitle: "User Disk and Quota info"
                dashboardEntry:
                    size_x: 3
                    size_y: 2
        }
    ).state(
        "main.virtualdesktopinfo", {
            url: "/vduinfo"
            templateUrl: "icsw.dashboard.virtualdesktops"
            icswData: icswRouteExtensionProvider.create
                pageTitle: "Virtual Desktops"
                dashboardEntry:
                    size_x: 3
                    size_y: 2
        }
    )
]).directive("icswUserJobInfo",
[
    "$templateCache",
(
    $templateCache
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.user.job.info")
        controller: "icswUserJobInfoCtrl"
    }
]).controller("icswUserJobInfoCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q",
    "$timeout", "$uibModal", "ICSW_URLS", "icswSimpleAjaxCall",
(
    $scope, $compile, $filter, $templateCache, Restangular, $q,
    $timeout, $uibModal, ICSW_URLS, icswSimpleAjaxCall
)->
    class jobinfo_timedelta
        constructor: (@name, @timedelta_description) ->

    $scope.jobs_waiting = []
    $scope.jobs_running = []
    $scope.jobs_finished = []
    $scope.jobinfo_valid = false

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
            url: ICSW_URLS.RMS_GET_RMS_JOBINFO
            data:
                "jobinfo_jobsfrom": jobsfrom
            dataType: "json"
        ).then(
            (json) ->
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

]).directive("icswUserVduOverview",
[
    "$compile", "$window", "$templateCache", "icswTools", "ICSW_URLS", "icswSimpleAjaxCall",
(
    $compile, $window, $templateCache, icswTools, ICSW_URLS, icswSimpleAjaxCall
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.user.vdu.overview")
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
                    scope.virtual_desktop_sessions = scope.virtual_desktop_user_setting.filter((vdus) -> vdus.user == scope.object.idx && vdus.to_delete == false)
                    # get all ips
                    scope.retrieve_device_ip vdus.device for vdus in scope.virtual_desktop_sessions

                    if scope.single_vdus_index
                        scope.single_vdus = scope.virtual_desktop_user_setting.filter((vdus) -> vdus.idx == scope.single_vdus_index)[0]
                        scope.show_single_vdus = true
            )
            scope.get_vnc_display_attribute_value = (geometry) ->
                [w, h] = screen_size.parse_screen_size(geometry)
                return "{width:" + w + ",height:" + h + ",fitTo:'width',}"
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
                    url: ICSW_URLS.USER_GET_DEVICE_IP
                    data:
                        "device": index
                    dataType: "json"
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
                content = [
                    "[Connection]\n",
                    "Host=#{ scope.ips_for_devices[vdus.device] }:#{ vdus.effective_port }\n",
                    "Password=#{ vdus.vnc_obfuscated_password }\n"
                ]
                blob = new Blob(content, {type: "text/plain;charset=utf-8"});
                # use FileSaver.js
                saveAs(blob, "#{ scope.get_device_by_index(vdus.device).name }.vnc");
    }
]).directive("icswDashboardView",
[
    "$templateCache",
(
    $templateCache,
) ->
    return {
        restrict: "EA"
        template: $templateCache.get("icsw.dashboard.overview")
        controller: "icswDashboardViewCtrl"
    }
]).controller("icswDashboardViewCtrl",
[
    "$scope", "$compile", "$filter", "$templateCache", "Restangular", "$q", "$timeout",
    "icswAcessLevelService", "ICSW_URLS", "icswSimpleAjaxCall",  "icswUserLicenseDataService",
    "icswDashboardElement", "icswDashboardContainerService", "icswUserService",
    "toaster",
(
    $scope, $compile, $filter, $templateCache, Restangular, $q, $timeout,
    icswAcessLevelService, ICSW_URLS, icswSimpleAjaxCall, icswUserLicenseDataService,
    icswDashboardElement, icswDashboardContainerService, icswUserService,
    toaster,
) ->
    icswAcessLevelService.install($scope)
    $scope.ICSW_URLS = ICSW_URLS
    $scope.NUM_QUOTA_SERVERS = 0
    icswSimpleAjaxCall(
        {
            url: ICSW_URLS.USER_GET_NUM_QUOTA_SERVERS
            dataType: "json"
        }
    ).then(
        (json) ->
            $scope.NUM_QUOTA_SERVERS = json.num_quota_servers
    )
    $scope.gridsterOpts = {
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
           handles: ["n", 'w', 'ne', 'se', 'sw', 'nw']
           stop: (event, element, options) ->
               options.ps_changed()
               # console.log "size stop", event, element, options
        }
        draggable: {
           enabled: true
           handle: '.my-class'
           stop: (event, element, options) ->
               options.ps_changed()
               # console.log "drag stop", event, element, options
        }
    }
    $scope.struct = {
        # data loaded
        data_loaded: false
        # user
        user: undefined
        # elements
        container: []
    }

    load = () ->
        $q.all(
            [
                icswUserService.load($scope.$id)
            ]
        ).then(
            (data) ->
                $scope.struct.user = data[0]
                $scope.struct.container = icswDashboardContainerService.get_container()
                $scope.struct.container.populate($scope.struct.user).then(
                    (done) ->
                        $scope.struct.data_loaded = true
                )
                # console.log $scope.struct.elements
        )

    load()

    $scope.$on(
        "gridster-item-resized"
        (item) ->
            # console.log "git-r", item
    )
    $scope.$on(
        "gridster-resized"
        (item) ->
            # console.log "git-R", item
    )
    $scope.$on(
        "gridster-resizable-changed"
        (item) ->
            # console.log "git-c", item
    )
    $scope.$on(
        "gridster-draggable-changed"
        (item) ->
            # console.log "git-d", item
    )
    $scope.$on(
        "gridster-item-transition-end"
        (sizes, gridster) ->
            # console.log "tchanged", sizes, gridster
    )
    $scope.$watch(
        "elements"
        (els) ->
            # console.log "c", els
        true
    )
    $scope.lds = icswUserLicenseDataService
    $scope.has_menu_permission = icswAcessLevelService.has_menu_permission
]).service("icswDashboardElement", [
    "$templateCache", "$q", "$compile", "$state",
(
    $templateCache, $q, $compile, $state,
) ->
    class icswDashboardElement
        constructor: (@state) ->
            # console.log @state
            # dashboardEntry
            _e = @state.icswData.dashboardEntry
            @dbe = _e
            @sizeX = _e.size_x
            @sizeY = _e.size_y
            @cls = _e.header_class
            @title = @state.icswData.pageTitle
            # camelcase is important here
            @$$panel_class = "panel-#{@cls}"
            @state = $state.get(@state.name)
            @template_name = @state.templateUrl

        close: ($event) ->
            @container.close_element(@)

        destroy: () ->
            console.log "destroy", @sizeX, @sizeY

        ps_changed: () =>
            console.log "psc", @sizeX, @sizeY, @col, @row

]).config(["$stateProvider", "icswRouteExtensionProvider", ($stateProvider, icswRouteExtensionProvider) ->
    $stateProvider.state(
        "main.quicklinks", {
            url: "/quicklinks"
            templateUrl: 'icsw.dashboard.quicklinks'
            icswData: icswRouteExtensionProvider.create
                pageTitle: "Quicklinks"
                dashboardEntry:
                    size_x: 2
                    size_y: 1
        }
    )
]).config(["$stateProvider", "icswRouteExtensionProvider", ($stateProvider, icswRouteExtensionProvider) ->
    $stateProvider.state(
        "main.externallinks", {
            url: "/externallinks"
            templateUrl: 'icsw.dashboard.externallinks'
            icswData: icswRouteExtensionProvider.create
                pageTitle: "External links"
                dashboardEntry:
                    size_x: 2
                    size_y: 1
        }
    )
]).service("icswDashboardContainer", [
    "$q", "$rootScope", "ICSW_SIGNALS", "icswRouteHelper", "icswDashboardElement",
(
    $q, $rootScope, ICSW_SIGNALS, icswRouteHelper, icswDashboardElement,
) ->
    class icswDashboardContainer
        constructor: () ->
            @elements = []
            @populated = false
            @_rights_are_valid = icswRouteHelper.get_struct().valid
            @_wait_for_rights = false
            $rootScope.$on(ICSW_SIGNALS("ICSW_ROUTE_RIGHTS_VALID"), () =>
                @_rights_are_valid = true
                if @_wait_for_rights
                    @_populate()
            )
            $rootScope.$on(ICSW_SIGNALS("ICSW_ROUTE_RIGHTS_INVALID"), () =>
                @_rights_are_valid = false
            )
            @reset()
        
        populate: (user) =>
            @reset()
            @_user = user
            @_populate_defer = $q.defer()
            if @_rights_are_valid
                @_populate()
                @_wait_for_rights = false
            else
                @_wait_for_rights = true
            return @_populate_defer.promise

        _populate: () =>
            for state in icswRouteHelper.get_struct().dashboard_states
                el = new icswDashboardElement(state)
                @add_element(el, @_user)
            @elements_lut = _.keyBy(@elements, "element_id")
            @open_elements = (el for el in @elements when el.$$open)
            @populated = true
            @_populate_defer.resolve("done")

        reset: () =>
            @element_id = 0
            @num_total = 0
            @num_open = 0
            @num_close = 0
            @elements.length = 0

        add_element: (element, user) =>
            @element_id++
            element.container = @
            element.element_id = @element_id
            element.user = user
            # default settings
            element.$$open = true
            @elements.push(element)
            @num_total++
            if element.$$open
                @num_open++
            else
                @num_close++
            return element
            
        close_element: (element) =>
            if element.$$open
                @num_close++
                @num_open--
                element.$$open = false
                _.remove(@open_elements, (el) -> return el.element_id == element.element_id)

        open_element: (element) =>
            if not element.$$open
                @num_close--
                @num_open++
                element.$$open = true
                @open_elements.push(element)

        reopen_closed_elements: () =>
            (@open_element(el) for el in @elements when not el.$$open)

]).service("icswDashboardContainerService", [
    "$q", "icswDashboardContainer",
(
    $q, icswDashboardContainer,
) ->
    _elements = new icswDashboardContainer()

    return {
        get_container: () ->
            return _elements

    }
]).directive("icswDashboardElementDisplay",
[
    "$templateCache", "$compile",
(
    $templateCache, $compile
) ->
    return {
        restrict: "E"
        scope:
            db_element: "=icswDashboardElement"
        controller: "icswDashboardElementCtrl"
        link: (scope, element, attrs) ->
            _outer = $templateCache.get("icsw.dashboard.element")
            _content = $templateCache.get(scope.db_element.template_name)
            _template_content = _outer + _content + "</div></div>"
            element.append($compile(_template_content)(scope))

    }
]).controller("icswDashboardElementCtrl", [
    "$scope", "icswRouteHelper", "$templateCache", "$compile", "$q",
    "$state",
(
    $scope, icswRouteHelper, $templateCache, $compile, $q,
    $state,
) ->
    $scope.close = () ->
        $scope.db_element.close()

    $scope.show = () ->
        # open quick dialog

        sub_scope = $scope.$new(true)
        d = $q.defer()
        # to be improved, use icswComplexModalService
        BootstrapDialog.show
            message: $compile($templateCache.get($scope.db_element.template_name))(sub_scope)
            title: $scope.db_element.title
            size: BootstrapDialog.SIZE_WIDE
            cssClass: "modal-tall modal-wide"
            draggable: true
            animate: false
            closable: true
            onshown: (ref) ->
                # hack to position to the left
                _tw = ref.getModal().width()
                _diag = ref.getModalDialog()
                if prev_left?
                    $(_diag[0]).css("left", prev_left)
                    $(_diag[0]).css("top", prev_top)
                else
                    $(_diag[0]).css("left", - (_tw - 600)/2)
                sub_scope.modal = ref
            onhidden: (ref) ->
                _diag = ref.getModalDialog()
                prev_left = $(_diag[0]).css("left")
                prev_top = $(_diag[0]).css("top")
                d.resolve("closed")
            buttons: [
                {
                    icon: "glyphicon glyphicon-ok"
                    cssClass: "btn-warning"
                    label: "close"
                    action: (ref) ->
                        ref.close()
                }
            ]
        d.promise.then(
            (ok) ->
                sub_scope.$destroy()
        )

    $scope.state = () ->
        $state.go($scope.db_element.state)

    $scope.$on("$destroy", () =>
        console.log "DESTROY", $scope
        $scope.db_element.destroy()
    )

]).controller("icswDashboardQuicklinksCtrl", [
    "$scope", "icswRouteHelper",
(
    $scope, icswRouteHelper,
) ->
    $scope.quicklink_states = icswRouteHelper.get_struct().quicklink_states
    # console.log route_struct
])

virtual_desktop_utils = {
    get_viewer_command_line: (vdus, ip) ->
        return "echo \"#{vdus.password}\" | vncviewer -autopass #{ip}:#{vdus.effective_port }\n"
}
