# -*- coding: utf-8 -*-

""" formulars for the NOCTUA / CORVUS webfrontend """

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Button, Fieldset, Div, HTML
from django.forms import Form, ModelForm, CharField, ModelChoiceField, \
    ModelMultipleChoiceField, ChoiceField, BooleanField
from initat.cluster.backbone.models import network, network_type, network_device_type, \
    netdevice, net_ip, peer_information
from initat.cluster.frontend.widgets import ui_select_widget, ui_select_multiple_widget


__all__ = [
    "network_form",
    "network_type_form",
    "network_device_type_form",
    "netdevice_form",
    "net_ip_form",
    "peer_information_form",
    "device_network_scan_form",
]


# empty query set
class empty_query_set(object):
    def all(self):
        raise StopIteration


class network_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    master_network = ModelChoiceField(queryset=empty_query_set(), empty_label="No master network", required=False, widget=ui_select_widget)
    network_type = ModelChoiceField(queryset=empty_query_set(), empty_label=None, widget=ui_select_widget)
    network_device_type = ModelMultipleChoiceField(queryset=empty_query_set(), required=False, widget=ui_select_multiple_widget)
    helper.layout = Layout(
        HTML("<h2>Network</h2>"),
        Fieldset(
            "Base data",
            Field("identifier", wrapper_class="ng-class:form_error('identifier')", placeholder="Identifier"),
            Field("network", wrapper_class="ng-class:form_error('network')", ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Network"),
            Field("netmask", wrapper_class="ng-class:form_error('netmask')", ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Netmask"),
            Field("broadcast", wrapper_class="ng-class:form_error('broadcast')", ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Broadcast"),
            Field("gateway", wrapper_class="ng-class:form_error('gateway')", ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Gateway"),
        ),
        Fieldset(
            "Additional settings",
            Field(
                "network_type",
                repeat="value.idx as value in config_service.network_types",
                display="description",
                placeholder="network type",
                filter="{description:$select.search}",
                readonly="has_master_network(_edit_obj)",
            ),
            Field(
                "master_network",
                repeat="value.idx as value in get_production_networks()",
                display="identifier",
                placeholder="master network",
                filter="{identifier:$select.search}",
                null=True,
                wrapper_ng_show="is_slave_network(_edit_obj.network_type)",
            ),
            Field(
                "network_device_type",
                repeat="value.idx as value in config_service.network_device_types",
                display="identifier",
                placeholder="network device types",
                filter="{identifier:$select.search}",
            ),
        ),
        Fieldset(
            "Flags and priority",  # {% verbatim %}{{ _edit_obj }}{% endverbatim %}",
            Field("enforce_unique_ips"),
            Field("gw_pri"),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
        ),
    )

    class Meta:
        model = network
        fields = (
            "identifier", "network", "netmask", "broadcast", "gateway", "master_network",
            "network_type", "network_device_type", "enforce_unique_ips", "gw_pri",
        )


class network_type_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    identifier = ModelChoiceField(queryset=empty_query_set(), empty_label=None, widget=ui_select_widget)
    helper.layout = Layout(
        HTML("<h2>Network type</h2>"),
        Fieldset(
            "Base data",
            Field("description", wrapper_class="ng-class:form_error('description')", placeholder="Description"),
            Field(
                "identifier",
                repeat="value.value as value in config_service.network_types",
                display="name",
                placeholder="network type type",
            ),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
        ),
    )

    class Meta:
        model = network_type
        fields = ["identifier", "description"]


class network_device_type_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "edit_obj"
    helper.layout = Layout(
        HTML("<h2>Network device type</h2>"),
        Fieldset(
            "Base data",
            Field("identifier", wrapper_class="ng-class:form_error('identifier')", placeholder="Identifier"),
            Field("description", wrapper_class="ng-class:form_error('description')", placeholder="Description"),
            Field("name_re", wrapper_class="ng-class:form_error('name_re')", placeholder="Regular expression"),
            Field("mac_bytes", placeholder="MAC bytes", min=6, max=24),
        ),
        Fieldset(
            "Flags",
            Field("allow_virtual_interfaces"),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="get_action_string()"),
        ),
    )

    class Meta:
        model = network_device_type
        fields = ("identifier", "description", "mac_bytes", "name_re", "allow_virtual_interfaces",)


class netdevice_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-8'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    ethtool_speed = ChoiceField(choices=[(0, "default"), (1, "10 MBit"), (2, "100 MBit"), (3, "1 GBit"), (4, "10 GBit")])
    ethtool_autoneg = ChoiceField(choices=[(0, "default"), (1, "on"), (2, "off")])
    ethtool_duplex = ChoiceField(choices=[(0, "default"), (1, "on"), (2, "off")])
    dhcp_device = BooleanField(required=False, label="force write DHCP address")
    show_ethtool = BooleanField(required=False)
    show_hardware = BooleanField(required=False)
    show_mac = BooleanField(required=False)
    show_vlan = BooleanField(required=False)
    routing = BooleanField(required=False, label="network topology central node")
    inter_device_routing = BooleanField(required=False)
    enabled = BooleanField(required=False)
    helper.layout = Layout(
        HTML("<h2>Netdevice '{% verbatim %}{{ _edit_obj.devname }}{% endverbatim %}'</h2>"),
        HTML("<tabset><tab heading='basic settings'>"),
        Fieldset(
            "Basic settings",
            Field("devname", wrapper_class="ng-class:form_error('devname')", placeholder="devicename"),
            Field("description"),
            Field("mtu"),
            Field(
                "netdevice_speed",
                repeat="value.idx as value in netdevice_speeds",
                placeholder="select a target netdevice speed",
                display="info_string",
            ),
            Field("enabled"),
            Field(
                "is_bridge",
                wrapper_ng_show="!_edit_obj.vlan_id && !_edit_obj.bridge_device",
                ng_disabled="has_bridge_slaves(_edit_obj)",
            ),
            Field(
                "bridge_device",
                repeat="value.idx as value in get_bridge_masters(_edit_obj)",
                # ng_options="value.idx as value.devname for value in get_bridge_masters(_edit_obj)",
                placeholder="bridge master device",
                display="devname",
                wrapper_ng_show="!_edit_obj.is_bridge && get_bridge_masters(_edit_obj).length",
            ),
        ),
        Fieldset(
            "Routing settings",
            Field("penalty", min=1, max=128),
            Field("routing"),
            Field("inter_device_routing"),
        ),
        Fieldset(
            "VLAN settings",
            Field(
                "master_device",
                repeat="value.idx as value in get_vlan_masters(_edit_obj)",
                # ng_options="value.idx as value.devname for value in get_bridge_masters(_edit_obj)",
                placeholder="VLAN master device",
                display="devname",
                null=True,
            ),
            Field("vlan_id", min=0, max=255),
            ng_show="!_edit_obj.is_bridge && get_vlan_masters(_edit_obj).length",
        ),
        HTML("</tab><tab heading='hardware'>"),
        Fieldset(
            "hardware settings",
            Field("driver"),
            Field("driver_options"),
        ),
        Fieldset(
            "ethtool settings (for cluster boot)",
            Field("ethtool_autoneg", ng_change="update_ethtool(_edit_obj)"),
            Field("ethtool_duplex", ng_change="update_ethtool(_edit_obj)"),
            Field("ethtool_speed", ng_change="update_ethtool(_edit_obj)"),
        ),
        Fieldset(
            "MAC Address settings",
            Div(
                Div(
                    # disable enabled-flag for clusterdevicegroup
                    Field("macaddr"),
                    css_class="col-md-6",
                ),
                Div(
                    Field("fake_macaddr"),
                    css_class="col-md-6",
                ),
                css_class="row",
            ),
            Field("dhcp_device"),
        ),
        HTML("</tab></tabset>"),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        )
    )

    class Meta:
        model = netdevice
        fields = (
            "devname", "netdevice_speed", "description", "driver", "driver_options", "is_bridge",
            "macaddr", "fake_macaddr", "dhcp_device", "vlan_id", "master_device", "routing", "penalty",
            "bridge_device", "inter_device_routing", "enabled", "mtu")
        widgets = {
            "netdevice_speed": ui_select_widget(),
            "bridge_device": ui_select_widget(),
            "master_device": ui_select_widget(),
        }


class net_ip_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-9'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    alias_excl = BooleanField(required=False)
    helper.layout = Layout(
        HTML("<h2>IP Address '{% verbatim %}{{ _edit_obj.ip }}{% endverbatim %}'</h2>"),
        Fieldset(
            "Basic settings",
            Field(
                "netdevice",
                repeat="value.idx as value in _current_dev.netdevice_set",
                placeholder="netdevice",
                display="devname",
                wrapper_ng_show="create_mode",
            ),
            Field("ip", wrapper_class="ng-class:form_error('devname')", placeholder="IP address"),
            Field(
                "network",
                repeat="value.idx as value in networks",
                placeholder="network",
                display="info_string",
                filter="{info_string:$select.search}",
                # wrapper_ng_show="create_mode",
            ),
            Field(
                "domain_tree_node",
                repeat="value.idx as value in domain_tree_node",
                placeholder="Domain tree node",
                display="tree_info",
                filter="{tree_info:$select.search}",
                # wrapper_ng_show="create_mode",
            ),
        ),
        Fieldset(
            "Alias settings (will be written without node postfixes)",
            Field("alias"),
            Field("alias_excl"),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        )
    )

    class Meta:
        model = net_ip
        fields = ("ip", "network", "domain_tree_node", "alias", "alias_excl", "netdevice",)
        widgets = {
            "netdevice": ui_select_widget(),
            "network": ui_select_widget(),
            "domain_tree_node": ui_select_widget(),
        }


class peer_information_form(ModelForm):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-2'
    helper.field_class = 'col-sm-9'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    helper.layout = Layout(
        HTML("""
{%verbatim%}
<h2>
Network topology connection information from {{ get_peer_src_info(_edit_obj) }}
 (<span ng-show='source_is_local'>source</span><span ng-show='!source_is_local'>destination</span>)
</h2>
{% endverbatim %}
        """),
        Fieldset(
            "Settings",
            Field("penalty", min=1, max=128),
            HTML("""
{% verbatim %}
<div ng-if="source_is_local">
    <div class='form-group' ng-if="create_mode">
        <label class='control-label col-sm-2'>
            Source
        </label>
        <div class='col-sm-9'>
            <ui-select ng-model="_edit_obj.s_netdevice" ng-required="true">
                <ui-select-match placeholder="select a netdevice">{{$select.selected.devname}}</ui-select-match>
                <ui-select-choices repeat="value.idx as value in _current_dev.netdevice_set | props_filter:{devname:$select.search}">
                    <div ng-bind-html="value.devname | highlight: $select.search"></div>
                </ui-select-choices>
            </ui-select>
        </div>
    </div>
    <div class='form-group'>
        <label class='control-label col-sm-2'>
            Network topology central node
        </label>
        <div class='col-sm-9'>
            <ui-select ng-model="_edit_obj.d_netdevice" ng-required="true">
                <ui-select-match placeholder="select a target device">{{$select.selected.info_string}}</ui-select-match>
                <ui-select-choices repeat="value.idx as value in get_route_peers() | props_filter:{info_string:$select.search}" group-by="'device_group_name'">
                    <div ng-bind-html="value.info_string | highlight: $select.search"></div>
                </ui-select-choices>
            </ui-select>
        </div>
    </div>
</div>
<div ng-if="!source_is_local">
    <div class='form-group'>
        <label class='control-label col-sm-2'>
            Source
        </label>
        <div class='col-sm-9'>
            <ui-select ng-model="_edit_obj.s_netdevice" ng-required="true">
                <ui-select-match placeholder="select a target device">{{$select.selected.info_string}}</ui-select-match>
                <ui-select-choices repeat="value.idx as value in get_route_peers() | props_filter:{info_string:$select.search}" group-by="'device_group_name'">
                    <div ng-bind-html="value.info_string | highlight: $select.search"></div>
                </ui-select-choices>
            </ui-select>
            <!--<select chosen="True" class="select form-control" ng-model="_edit_obj.s_netdevice"
                ng-options="value.idx as value.info_string group by value.device_group_name for value in get_route_peers()"
                required="True" ng-if="!source_is_local">
            </select>-->
        </div>
    </div>
</div>
<div ng-if="!source_is_local">
    <div class='form-group' ng-if="create_mode">
        <label class='control-label col-sm-2'>
            Destination
        </label>
        <div class='col-sm-9'>
            <ui-select ng-model="_edit_obj.d_netdevice" ng-required="true">
                <ui-select-match placeholder="select a netdevice">{{$select.selected.devname}}</ui-select-match>
                <ui-select-choices repeat="value.idx as value in _current_dev.netdevice_set | props_filter:{devname:$select.search}">
                    <div ng-bind-html="value.devname | highlight: $select.search"></div>
                </ui-select-choices>
            </ui-select>
            <!--<select chosen="True" class="select form-control" ng-model="_edit_obj.d_netdevice"
                ng-options="value.idx as value.devname for value in _current_dev.netdevice_set"
                required="True" ng-if="!source_is_local">
            </select>-->
        </div>
    </div>
</div>
{% endverbatim %}
            """),
            Field("s_spec"),
            Field("d_spec"),
            Field("info"),
            HTML("""
{% verbatim %}
<div class='form-group' ng-if="!create_mode">
    <label class='control-label col-sm-2'>
        Creation info
    </label>
    <div class='col-sm-9'>
        <span ng-show="_edit_obj.autocreated" class="label label-warning">autocreated</span>
        <span ng-show="!_edit_obj.autocreated" class="label label-success">manually created</span>
    </div>
</div>
{% endverbatim %}
"""),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        )
    )

    class Meta:
        model = peer_information
        fields = ("penalty", "s_spec", "d_spec", "info",)


class device_network_scan_form(Form):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    snmp_community = CharField(max_length=128)
    snmp_version = ChoiceField(choices=[(1, "1"), (2, "2")])
    strict_mode = BooleanField(required=False, label="all netdevices must be recognizable")
    remove_not_found = BooleanField(required=False)
    helper.layout = Layout(
        HTML("<h2>Scan network of settings device {% verbatim %}{{ _current_dev.full_name }}{% endverbatim %}</h2>"),
        Fieldset(
            "Scan address, {% verbatim %}{{ _current_dev.ip_list.length }}{% endverbatim %} non-local IPs defined",
            HTML("""
<div>{% verbatim %}
<ul class="list-group">
    <li class="list-group-item" ng-repeat="ip in _edit_obj.ip_list">
        <input type="button" class="btn btn-sm btn-primary" value="{{ ip }}" ng-click="_edit_obj.manual_address=ip"></input>
    </li>
    <li class="list-group-item">
        IP: <input ng-model="_edit_obj.manual_address"></input>
    </li>
</ul>
{% endverbatim %}</div>"""),
        ),
        # HTML("<tabset><tab heading='Hostmonitor' disabled='no_objects_defined(_current_dev)'"
        # " select='set_scan_mode(\"hm\")' active='_current_dev.scan_hm_active'>"),
        HTML("<tabset><tab heading='Hostmonitor' select='set_scan_mode(\"hm\")' active='_current_dev.scan_hm_active'>"),
        Fieldset(
            "Flags",
            Field("strict_mode"),
        ),
        HTML("</tab><tab heading='SNMP' select='set_scan_mode(\"snmp\")' active='_current_dev.scan_snmp_active'>"),
        Fieldset(
            "Base data",
            Field("snmp_community"),
            Field("snmp_version"),
        ),
        Fieldset(
            "Flags",
            Field("remove_not_found"),
        ),
        HTML("</tab></tabset>"),
        FormActions(
            Button("scan", "scan", css_class="btn btn-sm btn-primary", ng_click="fetch_device_network()"),
            Submit("cancel", "cancel", css_class="btn btn-sm btn-warning"),
        ),
    )
