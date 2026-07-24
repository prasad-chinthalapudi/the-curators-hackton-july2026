"""NetworkX people/projects graph — Person A owns the BUILD + PERSIST side.

Person B owns the LOOKUP side (`lookup_poc(project, topic)`). To avoid merge
conflicts on this file, B is recommended to put lookups in `graph_lookup.py`
and import `load_graph` from here. Everything below is A's.

Node id convention (so B can find nodes deterministically):
    person node id  = f"Person:{name}"
    project node id = f"Project:{name}"
Each node carries kind='person'|'project' plus its attributes.

Schema (§0):
    Person{name, email?, geography?}
    Project{name, client?, date?}
    edge Person->Project with role in
        {led, signed_deal, data_scientist, data_engineer, pm, knows_about}
    knows_about edges may carry a `topic`.
"""
from __future__ import annotations

import json
import logging
import os

import networkx as nx

from . import config

log = logging.getLogger("pih.graph")

VALID_ROLES = {"led", "signed_deal", "data_scientist", "data_engineer", "pm", "knows_about"}


def person_id(name: str) -> str:
    return f"Person:{name.strip()}"


def project_id(name: str) -> str:
    return f"Project:{name.strip()}"


def new_graph() -> nx.MultiDiGraph:
    # MultiDiGraph: a person can hold more than one role on the same project
    # (e.g. both `led` and a `knows_about` topic edge). A plain DiGraph would
    # collapse those into a single edge and silently drop roles.
    return nx.MultiDiGraph()


def add_project(g: nx.MultiDiGraph, name: str, client: str | None = None, date: str | None = None) -> str:
    """Add/update a Project node. Returns its node id."""
    nid = project_id(name)
    attrs = {"kind": "project", "name": name.strip()}
    if client:
        attrs["client"] = client
    if date:
        attrs["date"] = date
    if g.has_node(nid):
        g.nodes[nid].update({k: v for k, v in attrs.items() if v})
    else:
        g.add_node(nid, **attrs)
    return nid


def add_person_edge(
    g: nx.MultiDiGraph,
    person: str,
    project: str,
    role: str,
    *,
    email: str | None = None,
    geography: str | None = None,
    topic: str | None = None,
) -> None:
    """Ensure Person + Project nodes exist and add a Person->Project role edge."""
    if role not in VALID_ROLES:
        log.warning("add_person_edge: unknown role '%s' (person=%s, project=%s); keeping it anyway.",
                    role, person, project)
    pid = person_id(person)
    prid = project_id(project)

    p_attrs = {"kind": "person", "name": person.strip()}
    if email:
        p_attrs["email"] = email
    if geography:
        p_attrs["geography"] = geography
    if g.has_node(pid):
        g.nodes[pid].update({k: v for k, v in p_attrs.items() if v})
    else:
        g.add_node(pid, **p_attrs)

    if not g.has_node(prid):
        g.add_node(prid, kind="project", name=project.strip())

    edge_attrs = {"role": role}
    if role == "knows_about" and topic:
        edge_attrs["topic"] = topic

    # Dedup: skip if an identical (role, topic) edge from pid->prid already
    # exists, so re-runs don't accumulate duplicate edges.
    if g.has_edge(pid, prid):
        for d in g.get_edge_data(pid, prid).values():
            if d.get("role") == role and d.get("topic") == edge_attrs.get("topic"):
                return
    g.add_edge(pid, prid, **edge_attrs)


def save_graph(g: nx.DiGraph, path: str = config.GRAPH_PATH) -> None:
    """Persist to JSON via node-link format."""
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        data = nx.node_link_data(g, edges="links")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        log.info("saved graph: %d nodes, %d edges -> %s", g.number_of_nodes(), g.number_of_edges(), path)
    except Exception as e:
        log.error("save_graph failed (%s): %s", path, e)
        raise


def load_graph(path: str = config.GRAPH_PATH) -> nx.MultiDiGraph:
    """Load the graph (empty MultiDiGraph if the file doesn't exist yet)."""
    if not os.path.exists(path):
        log.warning("load_graph: %s not found; returning empty graph.", path)
        return nx.MultiDiGraph()
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        return nx.node_link_graph(data, directed=True, multigraph=True, edges="links")
    except Exception as e:
        log.error("load_graph failed (%s): %s", path, e)
        raise
