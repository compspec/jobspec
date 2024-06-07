import os
import sqlite3

import jobspec.core as core
import jobspec.subsystem.queries as queries
import jobspec.utils as utils
from jobspec.logger import LogColors, logger


class SubsystemRegistry:
    """
    A subsystem registry has (and loads) one or more subsystems.

    Right now we use an in memory sqlite database since it's
    efficient.
    """

    def __init__(self, path):
        self.systems = {}
        self.conn = sqlite3.connect(":memory:")
        self.create_tables()
        self.load(path)

    def __exit__(self):
        self.close()

    def close(self):
        self.conn.close()

    def create_tables(self):
        """
        Create tables for subsytems, nodes, edges.

        Note that I'm flattening the graph, so edges become attributes for
        nodes so it's easy to query. This is a reasonable first shot over
        implementing an actual graph database.
        """
        cursor = self.conn.cursor()

        # Only save metadata we absolutely need
        # Note I'm not saving edges because we don't use
        # them for anything - we are going to parse them
        # into node attributes instead.
        create_sql = [
            queries.create_subsystem_sql,
            queries.create_nodes_sql,
            queries.create_attributes_sql,
        ]
        for sql in create_sql:
            cursor.execute(sql)
        self.conn.commit()

    def load(self, path):
        """
        Load a group of subsystem files, typically json JGF.
        """
        if not os.path.exists(path):
            raise ValueError(f"User subsystem directory {path} does not exist.")
        files = utils.recursive_find(path, "[.]json")
        if not files:
            raise ValueError(f"There are no subsystem files in {path}")
        for filename in files:
            new_subsystem = Subsystem(filename)
            self.load_subsystem(new_subsystem)

    def load_subsystem(self, subsystem):
        """
        Load a new subsystem to the memory database
        """
        cursor = self.conn.cursor()

        # Create the subsystem - it should error if already exists
        values = f"('{subsystem.name}')"
        fields = '("name")'
        statement = f"INSERT INTO subsystems {fields} VALUES {values}"
        logger.debug(statement)
        cursor.execute(statement)
        self.conn.commit()

        # These are fields to insert a node and attributes
        node_fields = '("subsystem", "label", "type", "basename", "name", "id")'

        # First create all nodes
        for nid, node in subsystem.graph["nodes"].items():
            typ = node["metadata"]["type"]
            basename = node["metadata"]["basename"]
            name = node["metadata"]["name"]
            id = node["metadata"]["id"]
            node_values = f"('{subsystem.name}', '{nid}', '{typ}', '{basename}', '{name}', '{id}')"
            statement = f"INSERT INTO nodes {node_fields} VALUES {node_values}"
            logger.debug(statement)
            cursor.execute(statement)

        # Commit transaction
        self.conn.commit()
        attr_fields = '("node", "name", "value")'

        # Now all attributes
        for nid, node in subsystem.graph["nodes"].items():
            for key, value in node["metadata"].get("attributes", {}).items():
                attr_values = f"('{nid}', '{key}', '{value}')"
                statement = f"INSERT INTO attributes {attr_fields} VALUES {attr_values}"
                logger.debug(statement)
                cursor.execute(statement)

        # Note that we aren't doing anything with edges.
        # We are going to query for nodes we need directly. This assumes
        # that a software environment would be a global, resource-wide thing.
        self.conn.commit()

    def get_subsystem_node_type(self, subsys, match):
        """
        Get nodes of a specific type under a subsystem
        """
        statement = f"SELECT label from nodes WHERE subsystem = '{subsys}' AND type = '{match}';"
        labels = self.query(statement)
        return [f"'{x[0]}'" for x in labels]

    def find_node_attributes(self, attribute, value, labels=None):
        """
        Given a list of node labels, find children (attributes)
        that have a specific key/value.
        """
        # These will typically be node ids, but we need to filter attribute
        listing = "(%s)" % ",".join(labels)
        if labels is not None:
            statement = f"SELECT * from attributes WHERE name = '{attribute}' AND value = '{value}' and node IN {listing};"
        else:
            statement = (
                f"SELECT * from attributes WHERE name = '{attribute}' AND value = '{value}';"
            )
        return self.query(statement)

    def query(self, statement):
        """
        Issue a query to the database, returning fetchall.
        """
        cursor = self.conn.cursor()
        printed = statement

        # Don't overwhelm the output!
        if len(printed) > 150:
            printed = printed[:150] + "..."
        logger.info(printed)

        cursor.execute(statement)
        self.conn.commit()
        return cursor.fetchall()

    def satisfied(self, jobspec, ignore_missing=True):
        """
        Determine if a jobspec is satisfied by user-space subsystems.

        If ignore_missing is true, we assume missing the data does not
        disqualify the job.
        """
        js = core.Jobspec(jobspec)

        # We don't care about the association with tasks - the requires must be met
        # We could optimize this to be fewer queries, but it's likely trivial for now
        for _, requires in js.get("requires", {}).items():
            for item in requires:
                # If this returns None, ignore_missing is True and we ignore/continue
                subsys = self.get_item_subsystem(item, ignore_missing)
                if not subsys:
                    continue

                # Right now just require either:
                # 1. type, match, without attribute (no query to attribute table)
                # 2. type, match, attribute, value (query to nodes and attribute table)
                # 3. attribute and value (query only to attribute table)
                attribute = item.get("attribute")
                value = item.get("value")
                field = item["field"]
                match = item["match"]

                # We are being strict now and enforcing that field == type
                # We could support more, but would need to add them to the database
                # custom attributes should go under attributes
                if field != "type":
                    logger.warning(
                        f'Item {item} is searching for field other than "type," not supported yet.'
                    )
                    continue

                # We need at least a set of either
                if not all([attribute, value]) or not all([field, match]):
                    logger.warning(
                        f"Item {item} is missing 'field' and/or 'match' and cannot be assessed."
                    )
                    continue

                # 2. type, match, attribute, value (query to nodes and attribute table)
                if all([attribute, value, match]):
                    # "Get nodes in subsystem X of this type"
                    labels = self.get_subsystem_node_type(subsys, match)
                    if not labels:
                        print(
                            f"{LogColors.OKBLUE}{js.name}{LogColors.ENDC} {LogColors.RED}NOT OK{LogColors.ENDC}"
                        )
                        return False

                    # "Get attribute key values associated with any of these nodes"
                    # Here we get back matches that mean we are good (satisfied)
                    matches = self.find_node_attributes(attribute, value, labels)
                    if not matches:
                        print(
                            f"{LogColors.OKBLUE}{js.name}{LogColors.ENDC} {LogColors.RED}NOT OK{LogColors.ENDC}"
                        )
                        return False

                # 3. attribute and value (query only to attribute table)
                elif all([attribute, value]):
                    matches = self.find_node_attributes(attribute, value)
                    if not matches:
                        print(
                            f"{LogColors.OKBLUE}{js.name}{LogColors.ENDC} {LogColors.RED}NOT OK{LogColors.ENDC}"
                        )
                        return False

                # 1. type, match, without attribute (no query to attribute table)
                elif match is not None:
                    labels = self.get_subsystem_node_type(subsys, match)
                    if not labels:
                        print(
                            f"{LogColors.OKBLUE}{js.name}{LogColors.ENDC} {LogColors.RED}NOT OK{LogColors.ENDC}"
                        )
                        return False

        print(f"{LogColors.OKBLUE}{js.name}{LogColors.ENDC} {LogColors.OKGREEN}OK{LogColors.ENDC}")
        return True

    def get_item_subsystem(self, item, ignore_missing=True):
        """
        Get the subsystem for an item
        """
        # Check 1: the item provides the name of a subsystem
        group = item.get("name")
        if not group:
            msg = f"User subsystem requirement {item} is missing a subsystem name."
            if ignore_missing:
                logger.warning(msg)
            else:
                raise ValueError(msg)

        # Check 2: the subsystem exists in our database
        statement = f"SELECT name from subsystems WHERE name = '{group}';"
        match = self.query(statement)
        if not match and not ignore_missing:
            raise ValueError(f"User subsystem {group} is not known, and is required.")

        return group


class Subsystem:
    def __init__(self, filename):
        """
        Load a single subsystem
        """
        self._name = None
        self.load(filename)

    def load(self, filename):
        """
        Load a subsystem file, ensuring it exists.
        """
        # Derive the subsystem name from the filepath
        basename = os.path.basename(filename)
        self.data = utils.read_json(filename)

        if "graph" not in self.data:
            raise ValueError(f"Subsystem from {basename} is missing a graph")

        # Nodes are required (edges are not)
        if "nodes" not in self.graph or not self.graph["nodes"]:
            raise ValueError(f"Subsystem from {basename} is missing nodes")

    @property
    def graph(self):
        """
        Return the graph, which is required to exist and be populated to load.
        """
        return self.data["graph"]

    @property
    def name(self):
        """
        The subsystem name is typically the top level type of resource from the first
        node in the graph. We also could have a metadata feature.
        """
        if self._name is not None:
            return self._name
        # The subsystem won't load without nodes, so we have them
        for nid, node in self.graph["nodes"].items():
            # This is a fallback to invalid metadata (which should not happen)
            if "metadata" not in node or "type" not in node["metadata"]:
                self._name = nid.replace("0", "")
                return self._name

            self._name = node["metadata"]["type"]
            return self._name
