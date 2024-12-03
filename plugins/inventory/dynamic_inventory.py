import psycopg
from ansible.plugins.inventory import BaseInventoryPlugin, Constructable, Cacheable
from ansible.errors import AnsibleError
import os

DOCUMENTATION = """
    name: dynamic_inventory
    plugin_type: inventory
    short_description: Returns Ansible inventory from a PostgreSQL database
    description:
        - Pulls hosts and their associated tags from a PostgreSQL database
    options:
        plugin:
            description: The name of the plugin
            required: true
            choices: ['dynamic_inventory']
        db_name:
            description: The name of the PostgreSQL database
            required: true
        db_user:
            description: The PostgreSQL user
            required: true
        db_password:
            description: The password for the PostgreSQL user
            required: true
        db_host:
            description: The host of the PostgreSQL database
            required: true
        db_port:
            description: The port of the PostgreSQL database
            required: true
"""

EXAMPLES = """
plugin: dynamic_inventory
db_name: dbname
db_user: dbuser
db_password: dbpassword
db_host: dbhost
db_port: 5432
"""


class InventoryModule(BaseInventoryPlugin, Constructable, Cacheable):
    NAME = "dynamic_inventory"

    def verify_file(self, path):
        """Verify if the file is a valid configuration file for this plugin"""
        valid = super(InventoryModule, self).verify_file(path)
        if valid:
            if path.endswith(("dynamic_inventory.yaml", "dynamic_inventory.yml")):
                return True
        return False

    def parse(self, inventory, loader, path, cache=True):
        """Parse the inventory file and populate the inventory"""
        super(InventoryModule, self).parse(inventory, loader, path)

        # Read the configuration file
        config = self._read_config_data(path)

        # Get database connection parameters from the configuration
        db_name = config.get("db_name", os.environ.get("db_name"))
        db_user = config.get("db_user", os.environ.get("db_user"))
        db_password = config.get("db_password", os.environ.get("db_password"))
        db_host = config.get("db_host", os.environ.get("db_host"))
        db_port = config.get("db_port", os.environ.get("db_port"))

        # Connect to the PostgreSQL database
        try:
            conn = psycopg.connect(
                dbname=db_name,
                user=db_user,
                password=db_password,
                host=db_host,
                port=db_port,
            )
            cursor = conn.cursor()
        except Exception as e:
            raise AnsibleError(f"Failed to connect to the database: {e}\n{db_host},{db_port}")

        # Fetch hosts and their tags from the database
        try:
            cursor.execute("SELECT host, tags FROM hosts")
            rows = cursor.fetchall()
        except Exception as e:
            raise AnsibleError(f"Failed to fetch hosts from the database: {e}")

        # Populate the inventory with hosts and their tags as host variables
        for row in rows:
            host = row[0]
            tags = row[1]
            self.inventory.add_host(host)
            for key, value in tags.items():
                self.inventory.set_variable(host, key, value)

        # Close the cursor and connection
        cursor.close()
        conn.close()
