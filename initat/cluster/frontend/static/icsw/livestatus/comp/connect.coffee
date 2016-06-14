# Copyright (C) 2016 init.at
#
# Send feedback to: <lang-nevyjel@init.at>
#
# This file is part of icsw-server
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

# livestatus connector components

angular.module(
    "icsw.livestatus.comp.connect",
    [
        "ngResource", "ngCookies", "ngSanitize", "ui.bootstrap", "init.csw.filters", "restangular", "ui.router",
    ]
).service("icswMonLivestatusConnector",
[
    "$q", "$rootScope", "$injector",
(
    $q, $rootScope, $injector,
) ->
    # creates a DisplayPipeline
    class icswMonLivestatusConnector
        constructor: (name, spec) ->
            @name = name
            # connection specification as text
            @spec_src = spec
            console.log "Connector #{@name} (spec: #{@spec_src})"
            @root_element = undefined
            @resolve()

        resolve: () =>
            # dict element name -> service
            elements = {}

            # simple iteratee for resolving

            _resolve_iter = (in_obj, depth=0) =>
                if _.keys(in_obj).length != 1
                    console.error in_obj
                    throw new Error("Only one element allowed at any level")
                for key, value of in_obj
                    if key not of elements
                        # console.log key, depth
                        elements[key] = $injector.get(key)
                    for _el in value
                        _resolve_iter(_el, depth+1)

            # build dependencies
            _build_iter = (in_obj, depth=0) =>
                for key, value of in_obj
                    node = new elements[key](@)
                    if depth == 0
                        @root_element = node
                        @root_element.check_for_emitter()
                    for _el in value
                        node.add_child_node(_build_iter(_el, depth+1))
                return node
                    
            # interpret and resolve spec_src
            @spec_json = angular.fromJson(@spec_src)
            # resolve elements
            _resolve_iter(@spec_json)
            # build tree
            _build_iter(@spec_json)
            
        new_devsel: (devs) =>
            # start loop
            console.log @root_element, "*"
            @root_element.new_devsel(devs)
])
