# Copyright (C) 2012-2017 init.at
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
    "icsw.layout.theme",
    [
        "restangular"
    ]
).service('icswThemeService',
[
    "$http", "ICSW_URLS", "$window", "Restangular", "icswMenuSettings", "$timeout", "$injector",
(
    $http, ICSW_URLS, $window, Restangular, icswMenuSettings, $timeout, $injector,
) ->
    _theme_list = []
    _theme_lut = {}
    _theme_set = false
    _pending_sets = []
    # set in main.html
    active_theme = "default"
    theme_valid_emitted = false
    svg_style_set = false
    Restangular.all(ICSW_URLS.SESSION_GET_THEME_SETUP.slice(1)).getList().then(
        (data) ->
            $timeout(
                () ->
                    _t_setup = data.plain()
                    _theme_list.length = 0
                    _idx = 0
                    for entry in _t_setup
                        # salt with idx
                        entry.idx = _idx
                        _idx++
                        _theme_list.push(entry)
                    _theme_lut = _.keyBy(_theme_list, (entry) -> return entry.short)
                    _theme_set = true
                    _process_pending_sets()
                0
            )
    )

    _process_pending_sets = () ->
        if _pending_sets.length
            console.log("handling #{_pending_sets.length} pending theme selections")
            for entry in _pending_sets
                activate(entry)
            _pending_sets.length = 0

    activate = (theme) ->
        # normalize value
        theme = _.get(
            {
                "init": "cora"
            }
            theme
            theme
        )
        if not _theme_set
            _pending_sets.push(theme)
        else
            if not _theme_lut[theme]
                default_theme = $window.sessionStorage.getItem('default_theme')
                console.warn("theme '#{theme}' does not exist, setting default theme '#{default_theme}'")
                theme = default_theme
            if active_theme != theme or not svg_style_set
                # handle svg separately
                svg_style_set = true
                console.warn("setting svg_style to #{theme}")
                $http.get("#{ICSW_URLS.STATIC_URL}/svgstyle_#{theme}.css").then(
                    (response) ->
                        svgstyle_tag = angular.element.find("style[icsw-layout-svg-style]")[0]
                        data = if response.data? then response.data else response
                        svgstyle_tag.innerHTML = data
                    )
            if active_theme != theme
                console.warn "switch theme from #{active_theme} to #{theme}"
                active_theme = theme
                maintheme_tag = angular.element.find("link[icsw-layout-main-theme]")[0]
                # console.log "theme=", theme
                maintheme_tag.setAttribute("href", "static/theme_#{theme}.css")
                $timeout(
                    () ->
                        theme_valid_emitted = true
                        icswMenuSettings.set_themes_valid()
                    0
                )
            else
                if not theme_valid_emitted
                    theme_valid_emitted = true
                    icswMenuSettings.set_themes_valid()


    setdefault = (default_theme) =>
        $window.sessionStorage.setItem('default_theme', default_theme)
        current_theme = $window.sessionStorage.getItem('current_theme')
        theme = current_theme ? default_theme
        activate(theme)

    setcurrent = (current_theme) =>
        $window.sessionStorage.setItem('current_theme', current_theme)
        default_theme = $window.sessionStorage.getItem('default_theme')
        theme = current_theme ? default_theme
        activate(theme)

    toggle = () =>
        if _theme_list.length == 1
            return
        current_theme = $window.sessionStorage.getItem('current_theme')
        # console.log current_theme, _theme_lut
        _idx = _theme_lut[current_theme].idx + 1
        if _idx == _theme_list.length
            _idx = 0
        new_theme = _theme_list[_idx].short
        $window.sessionStorage.setItem('current_theme', new_theme)
        icswUserService = $injector.get("icswUserService")
        _cur_user = icswUserService.get()
        if _cur_user? and _cur_user
            _cur_user.set_var("$$ICSW_THEME_SELECTION$$", new_theme, "s")
        activate(new_theme)

    return {
        get_theme_list: () ->
            return _theme_list

        setdefault: setdefault

        setcurrent: setcurrent

        toggle: toggle

        activate: activate
    }

]).directive('icswLayoutMainTheme',
[
    "$window", "icswThemeService",
(
    $window, icswThemeService,
) ->
    link: (scope, element, attributes) ->
        default_theme = $window.sessionStorage.getItem('default_theme')
        current_theme = $window.sessionStorage.getItem('current_theme')
        theme = current_theme ? default_theme
        if theme
            icswThemeService.activate(theme)
])
