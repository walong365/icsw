// Copyright (C) 2012-2016 init.at
//
// Send feedback to: <lang-nevyjel@init.at>
//
// This file is part of webfrontend
//
// This program is free software; you can redistribute it and/or modify
// it under the terms of the GNU General Public License Version 2 as
// published by the Free Software Foundation.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program; if not, write to the Free Software
// Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
//

// Naming conventions
//
// - where possible use CamelCase
// - controllers end with "Ctrl"
// - module names start with "icsw.", separation with dots (no CamelCase)
// - second part is the name of the directory
// - then the (optional) functionality (for example icsw.device.network)
// - directives use '-' as separator, CamelCase in code
// - service, provider and factory names end with service, provider, factory and also use CamelCase
//
// Directory setup
//
// - below templates
// - top level equals the second part of the module name
// - second level (optional) for functionality (icsw.device.network -> templates/device/network/ )
// - shared functions in utils.{function} (app icsw.utils) [init.csw.filters -> icsw.utils.filters]
//
// File separation inside directories
//
// - one or more file(s) for HTML and cs / js code
// - no templates in coffeescript files
// - templates in .html via script type=ng-template/script
// - name of templates start with the name of the module with underscores, ending is ".html"
// - no root. bindings

icsw_app = angular.module(
    "icsw.app",
    [
        "ngResource",
        "ngCookies",
        "ngSanitize",
        "ngPromiseExtras",
        "ui.bootstrap",
        "ui.router",
        "restangular",
        "blockUI",
        "toaster",
        "gridster",
        "cfp.hotkeys",
        "init.csw.filters",
        "icsw.tools.tree",
        "icsw.layout.menu",
        "icsw.tools",
        "icsw.login",
        "icsw.layout.routing",
        "icsw.user",
        "icsw.user.password",
        "icsw.user.dashboard",
        "icsw.user.license",
        "icsw.backend.domain_name_tree",
        "icsw.backend.category_tree",
        "icsw.backend.devicetree",
        "icsw.backend.backup",
        "icsw.backend.network",
        "icsw.backend.config",
        "icsw.rrd.graph",
        "icsw.info.background",
        "icsw.server.info",
        "icsw.config.config",
        "icsw.config.generate",
        "icsw.device.variables",
        "icsw.device.info",
        "icsw.device.tree",
        "icsw.device.asset",
        "icsw.config.category_tree",
        "icsw.config.category_location",
        "icsw.config.domain_name_tree",
        "icsw.device.network",
        "icsw.device.network.graph",
        "icsw.device.config",
        "icsw.device.connection",
        "icsw.device.category",
        "icsw.device.livestatus",
        "icsw.device.monconfig",
        "icsw.device.location",
        "icsw.device.status_history",
        "icsw.device.partition",
        "icsw.license.overview",
        "icsw.monitoring.overview",
        "icsw.monitoring.monitoring_basic",
        "icsw.monitoring.device",
        "icsw.monitoring.cluster",
        "icsw.monitoring.escalation",
        "icsw.monitoring.build_info",
        "icsw.package.install",
        "icsw.device.boot",
        "icsw.device.create",
        "icsw.config.kernel",
        "icsw.config.kpi",
        "icsw.config.image",
        "icsw.config.partition_table",
        "icsw.rms",
        "icsw.history",
        "icsw.discovery",
        // <!-- ICSWAPPS:MODULES:START -->
        // <!-- ICSWAPPS:MODULES:END -->
        "icsw.discovery.event_log"
    ]
).config(
    [
        "blockUIConfig",
        function(blockUIConfig) {
            blockUIConfig.delay = 0;
            blockUIConfig.message = "Loading, please wait ...";
            blockUIConfig.autoBlock = false;
            blockUIConfig.autoInjectBodyBlock = false;
        }
    ]
).config(
    function(hotkeysProvider) {
        hotkeysProvider.templateHeader = "<h1>ICSW Key help</h1>"
        hotkeysProvider.includeCheatSheet = true;
    }
).constant(
    "ICSW_URLS", {
        <!-- inject:urls:html -->
        <!-- endinject -->
        "D3_MIN_JS": "/icsw/static/d3.min.js",
        "DIMPLE_MIN_JS": "/icsw/static/dimple.v2.1.6.min.js",
        "STATIC_URL": "/icsw/static"
    }
).config(function(uiGmapGoogleMapApiProvider) {
    uiGmapGoogleMapApiProvider.configure(
        {
            //    key: 'your api key',
            v: '3.23', //defaults to latest 3.X anyhow
            libraries: 'weather,geometry,visualization'
        }
    );
});
