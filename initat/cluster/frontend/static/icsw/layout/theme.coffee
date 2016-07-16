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
    "icsw.layout.theme",
    ["restangular"]
).value("themes",
    "default" : "Default",
    "cora" : "Cora",
    "sirocco" : "Sirocco"
).service('icswSaveTheme',
[
    "Restangular", "ICSW_URLS", "$window",
(
    Restangular, ICSW_URLS, $window
) ->
    setTheme = (theme) ->
        Restangular.all(ICSW_URLS.USER_SET_THEME.slice(1)).customGET("", {theme: theme}).then(
            (theme_data) ->
                $window.sessionStorage.setItem('current_theme', theme)
        )
        return theme
]).service('setupTheme',
[
    "$http", "ICSW_URLS", "themes", "$window",
(
    $http, ICSW_URLS, themes, $window
) ->
    setup = (theme) ->
        default_theme = $window.sessionStorage.getItem('default_theme')
        if theme == "init" then theme = "cora"
        if not themes[theme]?
            theme = default_theme
            console.log("theme does not exist setting default theme:", theme)

        maintheme_tag = angular.element.find("link[icsw-layout-main-theme]")[0]
        maintheme_tag.setAttribute("href", "static/theme_#{theme}.css")
        $http.get("#{ICSW_URLS.STATIC_URL}/svgstyle_#{theme}.css").then((response) ->
            svgstyle_tag = angular.element.find("style[icsw-layout-svg-style]")[0]
            if svgstyle_tag?
                svgstyle_tag.innerHTML = response
        )
]).service('setDefaultTheme',
[
    "$window", "setupTheme",
(
    $window, setupTheme
) ->
    setdefault = (default_theme) ->
        $window.sessionStorage.setItem('default_theme', default_theme)
        current_theme = $window.sessionStorage.getItem('current_theme')
        theme = current_theme ? default_theme
        setupTheme(theme)
]).service('setCurrentTheme',
[
    "$window", "setupTheme",
(
    $window, setupTheme
) ->
    setcurrent = (current_theme) ->
        $window.sessionStorage.setItem('current_theme', current_theme)
        default_theme = $window.sessionStorage.getItem('default_theme')
        theme = current_theme ? default_theme
        setupTheme(theme)
]).directive('icswLayoutMainTheme',
[
    "$window", "setupTheme",
(
    $window, setupTheme
) ->
    link: (scope, element, attributes) ->
        default_theme = $window.sessionStorage.getItem('default_theme')
        current_theme = $window.sessionStorage.getItem('current_theme')
        theme = current_theme ? default_theme
        if theme then setupTheme(theme)
])
