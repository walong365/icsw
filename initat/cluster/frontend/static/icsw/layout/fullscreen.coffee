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

# BEWARE - MASSIVE JQUERY AND DOM MANIPULATION!
angular.module(
    "icsw.layout.fullscreen",
    [
    ]
).service('icswFullscreenService',
[
    "$window", "$rootScope", "ICSW_SIGNALS",
(
    $window, $rootScope, ICSW_SIGNALS
) ->
    default_settings =
        body_paddingtop: undefined
        menu_top: undefined
        submenu_top: undefined
    body_elem = undefined
    main_menu_elem = undefined
    sub_menu_elem = undefined
    anim_time = 400
    initialized = false
    panel_dict = {}
    init = () ->
        body_elem = angular.element.find("body")[0]
        main_menu_elem = angular.element.find("icsw-layout-menubar nav.navbar")[0]
        sub_menu_elem = angular.element.find("icsw-layout-sub-menubar nav.navbar")[0]

        body_elem_data = $window.getComputedStyle(body_elem)
        default_settings.body_paddingtop = parseInt(body_elem_data.paddingTop)
        main_menu_elem_data = $window.getComputedStyle(main_menu_elem)
        default_settings.menu_top = parseInt(main_menu_elem_data.top)
        if sub_menu_elem?
            sub_menu_elem_data = $window.getComputedStyle(sub_menu_elem)
            default_settings.submenu_top = parseInt(sub_menu_elem_data.top)
        initialized = true

    active = () ->
        return body_elem.getAttribute("fullscreen") == "1"

    toggle = () ->
        if not initialized
            init()
        if @active()
            @unsetfullscreen()
        else
            @setfullscreen()


    setfullscreen = () ->
        if not initialized
            init()
        #menu will be moved by amount of body padding top
        $(main_menu_elem).animate(
            top: default_settings.menu_top - default_settings.body_paddingtop,
            anim_time
        )
        if sub_menu_elem?
            $(sub_menu_elem).animate(
                top: default_settings.submenu_top - default_settings.body_paddingtop,
                anim_time
            )
        $(body_elem).animate(
            paddingTop: 0,
            anim_time
        )
        $("div.panel-heading:visible").addClass("fscr-hide")
        $rootScope.$emit(ICSW_SIGNALS("ICSW_SVG_FULLSIZELAYOUT_SETUP"))
        $rootScope.$emit(ICSW_SIGNALS("ICSW_TRIGGER_PANEL_LAYOUTCHECK"))
        body_elem.setAttribute("fullscreen", "1")

    unsetfullscreen = () ->
        #menu will be moved by amount of body padding top
        $(main_menu_elem).animate(
            top: default_settings.menu_top,
            anim_time
        )
        if sub_menu_elem?
            $(sub_menu_elem).animate(
                top: default_settings.submenu_top,
                anim_time
            )
        $(body_elem).animate(
            paddingTop: default_settings.body_paddingtop,
            anim_time,
        )

        $("div.panel-heading").removeClass("fscr-hide")
        $rootScope.$emit(ICSW_SIGNALS("ICSW_SVG_FULLSIZELAYOUT_SETUP"))
        $rootScope.$emit(ICSW_SIGNALS("ICSW_TRIGGER_PANEL_LAYOUTCHECK"))
        body_elem.setAttribute("fullscreen", "0")

    return {
        active: active

        toggle: toggle

        setfullscreen: setfullscreen

        unsetfullscreen: unsetfullscreen
    }

])