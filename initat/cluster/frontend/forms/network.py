# -*- coding: utf-8 -*-

""" formulars for the NOCTUA / CORVUS webfrontend """

from crispy_forms.bootstrap import FormActions
from crispy_forms.helper import FormHelper
from crispy_forms.layout import Submit, Layout, Field, Button, Fieldset, Div, HTML
from django.db.models import Q
from django.forms import Form, ModelForm, CharField, ModelChoiceField, \
    ModelMultipleChoiceField, ChoiceField, BooleanField
from initat.cluster.backbone.models import network, network_type, network_device_type, \
    netdevice, net_ip, peer_information


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
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "edit_mixin.modify()"
    master_network = ModelChoiceField(queryset=empty_query_set(), empty_label="No master network", required=False)
    network_type = ModelChoiceField(queryset=empty_query_set(), empty_label=None)
    network_device_type = ModelMultipleChoiceField(queryset=empty_query_set(), required=False)
    helper.layout = Layout(
        HTML("<h2>Network</h2>"),
        Fieldset(
            "Base data",
            Field("identifier", wrapper_class="ng-class:edit_mixin.form_error('identifier')", placeholder="Identifier"),
            Field("network", wrapper_class="ng-class:edit_mixin.form_error('network')", ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Network"),
            Field("netmask", wrapper_class="ng-class:edit_mixin.form_error('netmask')", ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Netmask"),
            Field("broadcast", wrapper_class="ng-class:edit_mixin.form_error('broadcast')", ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Broadcast"),
            Field("gateway", wrapper_class="ng-class:edit_mixin.form_error('gateway')", ng_pattern="/^\d+\.\d+\.\d+\.\d+$/", placeholder="Gateway"),
        ),
        Fieldset(
            "Additional settings",
            Field(
                "network_type",
                ng_options="value.idx as value.description for value in rest_data.network_types",
                ng_disabled="has_master_network(_edit_obj)",
                chosen=True
            ),
            Field(
                "master_network",
                ng_options="value.idx as value.identifier for value in get_production_networks(this)",
                wrapper_ng_show="is_slave_network(this, _edit_obj.network_type)",
                chosen=True
            ),
            Field(
                "network_device_type",
                ng_options="value.idx as value.identifier for value in rest_data.network_device_types",
                chosen=True
            ),
        ),
        Fieldset(
            "Flags and priority",  # {% verbatim %}{{ _edit_obj }}{% endverbatim %}",
            Field("enforce_unique_ips"),
            Field("gw_pri"),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
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
    identifier = ModelChoiceField(queryset=empty_query_set(), empty_label=None)
    helper.layout = Layout(
        HTML("<h2>Network type</h2>"),
        Fieldset(
            "Base data",
            Field("description", wrapper_class="ng-class:form_error('description')", placeholder="Description"),
            Field("identifier", ng_options="key as value for (key, value) in settings.network_types", chosen=True),
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
    routing = BooleanField(required=False, label="routing target")
    inter_device_routing = BooleanField(required=False)
    enabled = BooleanField(required=False)
    helper.layout = Layout(
        HTML("<h2>Netdevice '{% verbatim %}{{ _edit_obj.devname }}{% endverbatim %}'</h2>"),
        Fieldset(
            "Basic settings",
            Field("devname", wrapper_class="ng-class:form_error('devname')", placeholder="devicename"),
            Field("description"),
            Field("netdevice_speed", ng_options="value.idx as value.info_string for value in netdevice_speeds", chosen=True),
            Field("enabled"),
            Field(
                "is_bridge",
                wrapper_ng_show="!_edit_obj.vlan_id && !_edit_obj.bridge_device",
                ng_disabled="has_bridge_slaves(_edit_obj)",
            ),
            Field(
                "bridge_device",
                ng_options="value.idx as value.devname for value in get_bridge_masters(_edit_obj)",
                chosen=True,
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
            "",
            Button(
                "show ethtool", "show ethtool", ng_click="_edit_obj.show_ethtool = !_edit_obj.show_ethtool",
                ng_class="_edit_obj.show_ethtool && 'btn btn-sm btn-success' || 'btn btn-sm'",
            ),
            Button(
                "show hardware", "show hardware", ng_click="_edit_obj.show_hardware = !_edit_obj.show_hardware",
                ng_class="_edit_obj.show_hardware && 'btn btn-sm btn-success' || 'btn btn-sm'",
            ),
            Button(
                "show vlan", "show vlan", ng_click="_edit_obj.show_vlan = !_edit_obj.show_vlan",
                ng_class="_edit_obj.show_vlan && 'btn btn-sm btn-success' || 'btn btn-sm'",
            ),
            Button(
                "show mac", "show mac", ng_click="_edit_obj.show_mac = !_edit_obj.show_mac",
                ng_class="_edit_obj.show_mac && 'btn btn-sm btn-success' || 'btn btn-sm'",
            ),
        ),
        Fieldset(
            "hardware settings",
            Field("driver"),
            Field("driver_options"),
            ng_show="_edit_obj.show_hardware",
        ),
        Fieldset(
            "ethtool settings (for cluster boot)",
            Field("ethtool_autoneg", ng_change="update_ethtool(_edit_obj)"),
            Field("ethtool_duplex", ng_change="update_ethtool(_edit_obj)"),
            Field("ethtool_speed", ng_change="update_ethtool(_edit_obj)"),
            ng_show="_edit_obj.show_ethtool",
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
            ng_show="_edit_obj.show_mac",
        ),
        Fieldset(
            "VLAN settings",
            Field("master_device", ng_options="value.idx as value.devname for value in get_vlan_masters(_edit_obj)", chosen=True),
            Field("vlan_id", min=0, max=255),
            ng_show="_edit_obj.show_vlan && !_edit_obj.is_bridge",
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        )
    )

    def __init__(self, *args, **kwargs):
        super(netdevice_form, self).__init__(*args, **kwargs)
        for clear_f in ["netdevice_speed"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None
        for clear_f in ["master_device"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = "---"

    class Meta:
        model = netdevice
        fields = (
            "devname", "netdevice_speed", "description", "driver", "driver_options", "is_bridge",
            "macaddr", "fake_macaddr", "dhcp_device", "vlan_id", "master_device", "routing", "penalty",
            "bridge_device", "inter_device_routing", "enabled")


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
            Field("netdevice", wrapper_ng_show="create_mode", ng_options="value.idx as value.devname for value in _current_dev.netdevice_set", chosen=True),
            Field("ip", wrapper_class="ng-class:form_error('devname')", placeholder="IP address"),
            Field("network", ng_options="value.idx as value.info_string for value in networks", chosen=True),
            Field("domain_tree_node", ng_options="value.idx as value.tree_info for value in domain_tree_node", chosen=True),
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

    def __init__(self, *args, **kwargs):
        super(net_ip_form, self).__init__(*args, **kwargs)
        for clear_f in ["network", "domain_tree_node", "netdevice"]:
            self.fields[clear_f].queryset = empty_query_set()
            self.fields[clear_f].empty_label = None

    class Meta:
        model = net_ip
        fields = ("ip", "network", "domain_tree_node", "alias", "alias_excl", "netdevice",)


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
Peer information from {{ get_peer_src_info(_edit_obj) }}
 (<span ng-show='source_is_local'>source</span><span ng-show='!source_is_local'>destination</span>)
</h2>
{% endverbatim %}
        """),
        Fieldset(
            "Settings",
            Field("penalty", min=1, max=128),
            HTML("""
<div ng-if="source_is_local">
    <div class='form-group' ng-show="create_mode">
        <label class='control-label col-sm-2'>
            Source
        </label>
        <div class='col-sm-9'>
            <select chosen="True" class="select form-control" ng-model="_edit_obj.s_netdevice"
                ng-options="value.idx as value.devname for value in _current_dev.netdevice_set"
                required="True" ng-if="source_is_local">
            </select>
        </div>
    </div>
    <div class='form-group'>
        <label class='control-label col-sm-2'>
            Destination
        </label>
        <div class='col-sm-9'>
            <select chosen="True" class="select form-control" ng-model="_edit_obj.d_netdevice"
                ng-options="value.idx as value.info_string group by value.device_group_name for value in get_route_peers()"
                required="True" ng-if="source_is_local">
            </select>
        </div>
    </div>
</div>
<div ng-if="!source_is_local">
    <div class='form-group'>
        <label class='control-label col-sm-2'>
            Source
        </label>
        <div class='col-sm-9'>
            <select chosen="True" class="select form-control" ng-model="_edit_obj.s_netdevice"
                ng-options="value.idx as value.info_string group by value.device_group_name for value in get_route_peers()"
                required="True" ng-if="!source_is_local">
            </select>
        </div>
    </div>
</div>
<div ng-if="!source_is_local">
    <div class='form-group' ng-show="create_mode">
        <label class='control-label col-sm-2'>
            Destination
        </label>
        <div class='col-sm-9'>
            <select chosen="True" class="select form-control" ng-model="_edit_obj.d_netdevice"
                ng-options="value.idx as value.devname for value in _current_dev.netdevice_set"
                required="True" ng-if="!source_is_local">
            </select>
        </div>
    </div>
</div>
            """),
            Field("s_spec"),
            Field("d_spec"),
        ),
        FormActions(
            Submit("submit", "", css_class="primaryAction", ng_value="action_string"),
        )
    )

    class Meta:
        model = peer_information
        fields = ("penalty", "s_spec", "d_spec",)


class device_network_scan_form(Form):
    helper = FormHelper()
    helper.form_id = "form"
    helper.form_name = "form"
    helper.form_class = 'form-horizontal'
    helper.label_class = 'col-sm-3'
    helper.field_class = 'col-sm-7'
    helper.ng_model = "_edit_obj"
    helper.ng_submit = "cur_edit.modify(this)"
    scan_address = CharField(max_length=128)
    strict_mode = BooleanField(required=False)
    helper.layout = Layout(
        HTML("<h2>Scan device</h2>"),
        Fieldset(
            "Base data",
            Field("scan_address"),
        ),
        Fieldset(
            "Flags",
            Field("strict_mode"),
        ),
        FormActions(
            Button("scan", "scan", css_class="btn btn-sm btn-primary", ng_click="fetch_device_network()"),
            Submit("cancel", "cancel", css_class="btn btn-sm btn-warning"),
        ),
    )
