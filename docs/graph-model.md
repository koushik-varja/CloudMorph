# Graph model

Applications are nodes in a directed graph. An edge `A -> B` means **A depends on B**. This direction makes `ancestors(B)` a useful blast-radius approximation: those are applications that can be affected by loss/change of B.

Decision-support metrics are deliberately limited to in/out degree, dependency depth on the condensation DAG, betweenness, SCCs, ancestor blast radius, articulation-like bridges on the undirected projection, orphans, and shared-database coupling. Betweenness is exact for estates up to 300 nodes and sampled with a fixed seed above that size.

Strongly connected components are migration coupling groups because a cycle cannot be strictly topologically ordered. The optimizer forces members of an SCC to the same migration wave unless the dependency architecture is changed before planning.
