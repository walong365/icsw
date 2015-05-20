# config file to use with create_cluster_nodes.py

CSV_FILE = "/home/mallinger/ac2t-nodes.csv"

# used to get number of node
CSV_DEVICE_NAME_RE = "^[a-zA-Z]*(\d+)$"

DEVICE_NAME_PATTERN = "node{}"
IPMI_DEVICE_NAME_PATTERN = "node{}-ipmi"

DEVICE_DOMAIN_TREE_NODE = "foo.prod"
IPMI_DEVICE_DOMAIN_TREE_NODE = "foo.apc"

IB_IP_PATTERN = "10.0.0.{}"

DEVICE_PROD_IP_PATTERN = "1.16.0.{}"
DEVICE_BOOT_IP_PATTERN = "1.17.0.{}"

BOOTSERVER_NAME = "bootserver"

DEVICE_GROUP_NAME = "nodes_new"
IPMI_GROUP_NAME = "impi_new"

IB_SWITCH_NAMES = ["ib_switch", "ib_switch"]
IPMI_SWITCH_NAMES = ["ipmi_switch"]

DEVICE_SWITCH_NAMES = ["switch"]