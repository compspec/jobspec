create_subsystem_sql = """
CREATE TABLE subsystems (
  name TEXT PRIMARY KEY NOT NULL
);"""

create_nodes_sql = """CREATE TABLE nodes (
  subsystem TEXT NOT NULL,
  label TEXT NOT NULL,
  type TEXT NOT NULL,
  basename TEXT NOT NULL,
  name TEXT NOT NULL,
  id INTEGER NOT NULL,
  FOREIGN KEY(subsystem) REFERENCES subsystems(name),
  UNIQUE (subsystem, label)
);"""

create_attributes_sql = """CREATE TABLE attributes (
  name TEXT NOT NULL,
  value TEXT NOT NULL,
  node TEXT NOT NULL,
  FOREIGN KEY(node) REFERENCES nodes(label)
);"""
