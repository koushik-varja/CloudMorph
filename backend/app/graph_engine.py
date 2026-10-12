from __future__ import annotations

from collections import defaultdict
import networkx as nx
from .schemas import Portfolio


def build_graph(portfolio: Portfolio) -> nx.DiGraph:
    graph = nx.DiGraph()
    for app in portfolio.applications:
        graph.add_node(
            app.application_id, name=app.name, type="Application", domain=app.business_domain
        )
    for app in portfolio.applications:
        for dep in app.dependencies:
            # source depends on target; direction shows dependency relation source -> target
            graph.add_edge(
                app.application_id,
                dep.target,
                integration_type=dep.integration_type.value,
                synchronous=dep.synchronous,
            )
    return graph


def analyze_graph(portfolio: Portfolio) -> dict:
    graph = build_graph(portfolio)
    n = max(1, graph.number_of_nodes() - 1)
    sccs = [sorted(c) for c in nx.strongly_connected_components(graph) if len(c) > 1]
    condensation = nx.condensation(graph)
    component_of = condensation.graph["mapping"]
    depth_by_component: dict[int, int] = {}
    migration_dag = condensation.reverse(copy=False)
    for comp in nx.topological_sort(migration_dag):
        preds = list(migration_dag.predecessors(comp))
        depth_by_component[comp] = 0 if not preds else 1 + max(depth_by_component[p] for p in preds)
    undirected = graph.to_undirected()
    articulation = set(nx.articulation_points(undirected)) if graph.number_of_nodes() > 1 else set()
    if graph.number_of_nodes() <= 300:
        between = nx.betweenness_centrality(graph, normalized=True)
        betweenness_mode = "exact"
    else:
        k = min(100, graph.number_of_nodes())
        between = nx.betweenness_centrality(graph, k=k, normalized=True, seed=42)
        betweenness_mode = f"sampled-k={k}"
    db_users: dict[str, list[str]] = defaultdict(list)
    for app in portfolio.applications:
        if app.database:
            db_users[app.database].append(app.application_id)
    shared_db = {db: sorted(users) for db, users in db_users.items() if len(users) > 1}
    metrics = []
    for node in graph.nodes:
        descendants = nx.descendants(graph, node)
        ancestors = nx.ancestors(graph, node)
        metrics.append(
            {
                "application_id": node,
                "in_degree": graph.in_degree(node),
                "out_degree": graph.out_degree(node),
                "betweenness": round(float(between.get(node, 0)), 6),
                "dependency_depth": depth_by_component[component_of[node]],
                "blast_radius": len(ancestors),
                "dependency_reach": len(descendants),
                "articulation_like": node in articulation,
                "orphan": graph.degree(node) == 0,
                "hub_score": round(
                    (graph.in_degree(node) + graph.out_degree(node)) / max(1, 2 * n), 6
                ),
            }
        )
    metrics.sort(key=lambda x: (x["blast_radius"], x["betweenness"], x["in_degree"]), reverse=True)
    return {
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "strongly_connected_components": sccs,
        "coupling_groups": [{"applications": c, "reason": "cyclic dependencies"} for c in sccs],
        "shared_database_coupling": shared_db,
        "betweenness_mode": betweenness_mode,
        "metrics": metrics,
    }


def graph_payload(portfolio: Portfolio) -> dict:
    graph = build_graph(portfolio)
    return {
        "nodes": [{"id": n, **graph.nodes[n]} for n in graph.nodes],
        "edges": [{"source": u, "target": v, **d} for u, v, d in graph.edges(data=True)],
    }
