import json
from simple_salesforce import Salesforce
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
module: salesforce
plugin_type: inventory
short_description: Salesforce inventory source
version_added: "2.17.0"
description:
    - Reads inventory from a Salesforce Org instance.
options:
      org_username:
        description: Salesforce Organization Username
        required: true
      org_password:
        description: Salesforce Organization Password
        required: true
      org_token:
        description: Salesforce Organization Token
        required: true
      org_object:
        description: Salesforce Object
        required: true
      object_schema:
        description: Salesforce Object Schema
        required: true
author:
    - Alex Raddas
"""


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    """An example inventory plugin."""

    NAME = "network.inventory.salesforce"

    def parse(self, inventory, loader, path, cache=True):
        """Parse and populate the inventory with data about hosts.

        Parameters:
            inventory The inventory to populate
        """
        super(InventoryModule, self).parse(inventory, loader, path, cache)
        self._read_config_data(path)  # This also loads the cache
        try:
            params = {
                "username": self.get_option("org_username"),
                "password": self.get_option("org_password"),
                "token": self.get_option("org_token"),
                "org_object": self.get_option("org_object"),
                "object_schema": self.get_option("object_schema"),
            }

            records = SalesforceInventory(**params).get()

            inventory_data = Processors(
                object_schema=self.get_option("object_schema")
            ).records_to_schema(records)
            if not inventory_data:
                raise AnsibleParserError("No records found in Salesforce")
            for host_data in inventory_data:
                self.inventory.add_host(host_data["host"])
                for k, v in host_data.get("variables").items():
                    self.inventory.set_variable(host_data["host"], k, v)
                for grp in host_data.get("groups"):
                    self.inventory.add_group(grp)
                    self.inventory.add_child(grp, host_data["host"])
        except Exception as e:
            raise AnsibleParserError("unable to parse : %s" % (str(e)))


class SalesforceInventory:
    def __init__(self, username, password, token, org_object, object_schema):
        self.username = username
        self.password = password
        self.token = token
        self.org_object = org_object
        self.object_schema = object_schema
        self.sf_instance = Salesforce(
            username=self.username,
            password=self.password,
            security_token=self.token,
        )

    def get(self):
        fields = ", ".join(list(self.object_schema.keys()))
        query = f"SELECT {fields} FROM {self. org_object}"
        records = self.sf_instance.query(query)
        return json.loads(json.dumps(records["records"]))


class Processors:
    def __init__(self, object_schema):
        self.object_schema = object_schema

    def records_to_schema(self, records):
        inventory = []
        for r in records:
            host = [
                r[sk]
                for sk, schema in self.object_schema.items()
                if "host" in schema.keys()
            ][0]
            inventory.append({"host": host, "variables": {}, "groups": []})
            for sk, schema in self.object_schema.items():
                try:
                    dtype = schema["types"]
                    if "variable" in dtype:
                        inventory[-1]["variables"][schema["value"]] = r[sk]
                    if "group" in dtype:
                        inventory[-1]["groups"].append(r[sk])
                except KeyError:
                    pass
        return inventory
