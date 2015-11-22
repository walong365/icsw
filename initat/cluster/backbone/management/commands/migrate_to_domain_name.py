#!/usr/bin/python-init -Otu
#
# -*- coding: utf-8 -*-
#
# Copyright (C) 2013-2015 Andreas Lang-Nevyjel
#
# Send feedback to: <lang-nevyjel@init.at>
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
""" migrates from network-based names to domain-base names """

from django.core.management.base import BaseCommand
from django.db.models import Q

from initat.cluster.backbone.models import domain_tree_node, network, net_ip, domain_name_tree, device
from initat.tools import logging_tools


class DTNode(object):
    def __init__(self, name="", depth=0):
        self.name = name
        self.depth = depth
        self.cur_net = None
        self.sub_nodes = {}
        if not self.name:
            self.top_node = True
        else:
            self.top_node = False

    def feed_name(self, name, cur_net):
        if not name.strip():
            self.cur_net = cur_net
            # nothing more to add or top node
            return self
        else:
            name_parts = list(name.strip().split("."))
            last_part = name_parts[-1]
            if last_part not in self.sub_nodes:
                # create new sub_node
                self.sub_nodes[last_part] = DTNode(last_part, depth=self.depth + 1)
            return self.sub_nodes[last_part].feed_name(".".join(name_parts[:-1]), cur_net)

    def create_db_entries(self, top_node=None):
        full_name = self.name
        if top_node and top_node.name:
            full_name = "{}.{}".format(full_name, top_node.name)
        if self.cur_net:
            cur_db = domain_tree_node(
                name=self.name,
                parent=top_node.db_obj if top_node else None,
                full_name=full_name,
                node_postfix=self.cur_net.postfix,
                create_short_names=self.cur_net.short_names,
                write_nameserver_config=self.cur_net.write_bind_config,
                always_create_ip=self.cur_net.write_other_network_config,
                depth=self.depth,
            )
        else:
            cur_db = domain_tree_node(
                name=self.name,
                parent=top_node.db_obj if top_node else None,
                full_name=full_name,
                depth=self.depth,
            )
        cur_db.save()
        self.db_obj = cur_db
        [value.create_db_entries(top_node=self) for value in self.sub_nodes.itervalues()]


class Command(BaseCommand):
    option_list = BaseCommand.option_list
    help = ("Migration old device naming scheme to new domain-tree bases naming scheme.")
    args = ''

    def handle(self, **options):
        main()


def main():
    cur_dns = domain_tree_node.objects.all()
    if len(cur_dns):
        print "domain tree already in use, skipping init..."
    else:
        print "Migrating to domain_tree_node system"
        net_tree = DTNode()
        for cur_net in network.objects.all():  # @UndefinedVariable
            _dns_node = net_tree.feed_name(cur_net.name, cur_net)
        net_tree.create_db_entries()
    cur_dnt = domain_name_tree()
    # check for intermediate nodes
    for key in cur_dnt.keys():
        cur_node = cur_dnt[key]
        if cur_node == cur_dnt._root_node:
            im_state = False
        else:
            im_state = True if (
                net_ip.objects.filter(Q(domain_tree_node=cur_node)).count() + device.objects.filter(Q(domain_tree_node=cur_node)).count() == 0
            ) else False
        if cur_node.intermediate != im_state:
            cur_node.intermediate = im_state
            cur_node.save()
    # read network dict
    net_dict = {}
    for nw_obj in network.objects.all():  # @UndefinedVariable
        net_dict[nw_obj.pk] = nw_obj
        try:
            nw_obj.dns_node = domain_tree_node.objects.get(Q(full_name=nw_obj.name))
        except:
            # not found, use top-level node
            nw_obj.dns_node = domain_tree_node.objects.get(Q(depth=0))
    # modify net_ip
    print "migrating {}".format(logging_tools.get_plural("netip", net_ip.objects.filter(Q(domain_tree_node=None)).count()))
    for cur_ip in net_ip.objects.filter(Q(domain_tree_node=None)):
        cur_ip.domain_tree_node = net_dict[cur_ip.network_id].dns_node
        cur_ip.save()
    for cur_dev in device.objects.all().prefetch_related("netdevice_set__net_ip_set").order_by("name"):
        if not cur_dev.domain_tree_node_id:
            all_ips = sum(
                [
                    list(cur_nd.net_ip_set.all()) for cur_nd in cur_dev.netdevice_set.all()
                ],
                []
            )
            valid_ips = [cur_ip for cur_ip in all_ips if cur_ip.ip != "127.0.0.1"]
            dom_id = None
            if len(valid_ips) == 1:
                # direct match
                dom_id = valid_ips[0].domain_tree_node_id
            elif len(valid_ips) == 0:
                # no ips, no domain name, take root node
                dom_id = cur_dnt._root_node.pk
            else:
                dom_ids = list(set([cur_ip.domain_tree_node_id for cur_ip in valid_ips]))
                if len(dom_ids) == 1:
                    # more than one netdevice but all in the same domain
                    dom_id = dom_ids[0]
                else:
                    # take the first one
                    dom_id = valid_ips[0].domain_tree_node_id
            if cur_dev.name.count("."):
                new_domain = "{}.{}".format(cur_dev.name.split(".", 1)[1], cur_dnt[dom_id].full_name)
                cur_dev.name = cur_dev.name.split(".")[0]
                new_dom = cur_dnt.add_domain(new_domain)
                # is not intermediate
                new_dom.intermediate = False
                new_dom.save()
                dom_id = new_dom.pk
            cur_dev.domain_tree_node = cur_dnt[dom_id]
            cur_dev.save()
    print "done."
