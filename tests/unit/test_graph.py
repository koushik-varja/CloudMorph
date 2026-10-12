from app.graph_engine import analyze_graph, build_graph
from app.schemas import Application, Dependency, Portfolio


def cyclic_portfolio() -> Portfolio:
    return Portfolio(
        applications=[
            Application(
                application_id="a", name="A", dependencies=[Dependency(target="b")]
            ),
            Application(
                application_id="b", name="B", dependencies=[Dependency(target="c")]
            ),
            Application(
                application_id="c", name="C", dependencies=[Dependency(target="a")]
            ),
            Application(
                application_id="d", name="D", dependencies=[Dependency(target="a")]
            ),
            Application(application_id="e", name="E"),
        ]
    )


def test_graph_construction_and_scc():
    p = cyclic_portfolio()
    g = build_graph(p)
    assert g.number_of_nodes() == 5
    assert g.number_of_edges() == 4
    result = analyze_graph(p)
    assert ["a", "b", "c"] in result["strongly_connected_components"]
    assert any(m["application_id"] == "e" and m["orphan"] for m in result["metrics"])


def test_blast_radius_is_upstream_dependents():
    p = Portfolio(
        applications=[
            Application(application_id="db", name="DB"),
            Application(
                application_id="api", name="API", dependencies=[Dependency(target="db")]
            ),
            Application(
                application_id="web",
                name="Web",
                dependencies=[Dependency(target="api")],
            ),
        ]
    )
    metrics = {m["application_id"]: m for m in analyze_graph(p)["metrics"]}
    assert metrics["db"]["blast_radius"] == 2
    assert metrics["web"]["blast_radius"] == 0
