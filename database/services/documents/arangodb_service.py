import os

from arango import ArangoClient

ARANGO_HOST = os.getenv("ARANGO_HOST")
ARANGO_DB = os.getenv("ARANGO_DB")
ARANGO_USER = os.getenv("ARANGO_USER")
ARANGO_PASSWORD = os.getenv("ARANGO_PASSWORD")
print("ARANGO_HOST =", ARANGO_HOST)
print("ARANGO_DB =", ARANGO_DB)
print("ARANGO_USER =", ARANGO_USER)
print("ARANGO_PASSWORD =", ARANGO_PASSWORD)

client = ArangoClient(
    hosts=ARANGO_HOST
)

sys_db = client.db(
    "_system",
    username=ARANGO_USER,
    password=ARANGO_PASSWORD
)

if not sys_db.has_database(ARANGO_DB):
    sys_db.create_database(ARANGO_DB)

db = client.db(
    ARANGO_DB,
    username=ARANGO_USER,
    password=ARANGO_PASSWORD
)

if not db.has_collection("nodes"):
    db.create_collection("nodes")

if not db.has_collection("edges"):
    db.create_collection(
        "edges",
        edge=True
    )

nodes_collection = db.collection("nodes")
edges_collection = db.collection("edges")


class ArangoDBService:

    @staticmethod
    def store_graph(graph_data: dict):

        nodes = graph_data.get("nodes", [])
        edges = graph_data.get("edges", [])

        for node in nodes:

            key = node["id"].replace(" ", "_")

            doc = {
                "_key": key,
                "name": node["id"],
                "type": node.get("type")
            }

            if not nodes_collection.has(key):
                nodes_collection.insert(doc)

        for edge in edges:

            from_key = edge["from"].replace(" ", "_")
            to_key = edge["to"].replace(" ", "_")

            edge_doc = {
                "_from": f"nodes/{from_key}",
                "_to": f"nodes/{to_key}",
                "relation": edge.get("relation")
            }

            edges_collection.insert(edge_doc)