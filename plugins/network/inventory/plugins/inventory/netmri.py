import re
import infoblox_netmri as nmri
from ansible.plugins.inventory import (
    BaseInventoryPlugin,
    Cacheable,
    Constructable,
    AnsibleParserError,
)

ANSIBLE_METADATA = {
    "metadata_version": "1.0.0",
    "status": ["preview"],
    "supported_by": "community",
}

DOCUMENTATION = r"""
---
module: netmri
plugin_type: inventory
short_description: NetMRI inventory source
version_added: "2.17.0"
description:
    - Reads inventory from a NetMRI Instance.
options:
      username:
        description: NetMRI Username
        required: True
      password:
        description: NetMRI Password
        required: True
      netmri_host:
        description: NetMRI Host
        required: True
      dropprefix:
        description: Drop prefix from variables
        required: False
        default: False
      lowercase:
        description: Change variable names to lowercase
        required: False
        default: False
      device_limit:
        description: Limit the number of devices to fetch
        required: False
        default: 3000
      groups:
        description: List of groups to add to the inventory
        required: False
        default: []
author:
    - Alex Raddas
"""


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    """An example inventory plugin."""

    NAME = "network.inventory.netmri"

    def parse(self, inventory, loader, path, cache=True):
        """Parse and populate the inventory with data about hosts.

        Parameters:
            inventory The inventory to populate
        """
        super(InventoryModule, self).parse(inventory, loader, path, cache)
        self._read_config_data(path)  # This also loads the cache
        try:
            self.dropprefix = self.get_option("dropprefix") or False
            self.lowercase = self.get_option("lowercase") or False
            self.device_limit = self.get_option("device_limit") or 3000
            self.groups = self.get_option("groups") or []
            params = {
                "username": self.get_option("username"),
                "password": self.get_option("password"),
                "netmri_host": self.get_option("netmri_host"),
            }

            device_data = NetMRI(**params).get_device_data(
                groups=self.groups, device_limit=self.device_limit
            )
            inventory_data = Processors().transform_variables(
                data=device_data, lowercase=self.lowercase, dropprefix=self.dropprefix
            )

            if not inventory_data:
                raise AnsibleParserError("No records found in NetMRI")
            for host, host_data in inventory_data.items():
                self.inventory.add_host(host)
                for k, v in host_data.get("variables").items():
                    self.inventory.set_variable(host, k, v)
                for grp in host_data.get("groups"):
                    self.inventory.add_group(grp)
                    self.inventory.add_child(grp, host)
        except Exception as e:
            raise AnsibleParserError("unable to parse : %s" % (str(e)))


class NetMRI:
    def __init__(self, netmri_host, username, password):
        self.netmri_host = netmri_host
        self.username = username
        self.password = password
        self.client = nmri.InfobloxNetMRI(netmri_host, username, password)

    def get_device_data(self, groups: list = [], device_limit: int = 3000):
        data = self.client.api_request("devices/index", {"limit": device_limit})
        device_data = {}
        for device in data.get("devices", []):
            try:
                dname = device.get("DeviceName")
                device_data[dname] = {"variables": {}, "groups": []}
                for k, v in device.items():
                    if k in groups and v is not None and v != "":
                        device_data[dname]["groups"].append(v)
                    device_data[dname]["variables"][k] = v

            except Exception as e:
                print(e)
        return device_data


class Processors:
    def transform_variables(self, data: dict, lowercase=False, dropprefix=False):
        newdata = {}

        for device, attr in data.items():
            newvars = {}
            for k, v in attr.get("variables").items():
                newkey = k.lower() if lowercase else k
                newkey = re.sub(r"^[D-d]evice", "", newkey) if dropprefix else newkey
                newvars[newkey] = v
            newdata[device] = {"variables": newvars, "groups": attr.get("groups")}

        return newdata
