.. _device_networks:

Device Networks
=======================

You have to provide information about the network configuration of your devices to make them reachable. For a new device, you have to create a network device first, typically named **eth0**. Next, you have to assign an IP address and the network after expanding **ip**. Finally, expand **routing**, activate the routing capability for devices that are forwarding packets (hence, switches too) and add the device's peer(s).

Before you can configure a device's networks, make sure you have created the according networks in :ref:`networks`.

Below, you can see a visualization of your current network configuration after clicking **Redraw**.

To commit changes, you have to rebuild the monitoring config.
 
 