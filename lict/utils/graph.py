import os
import warnings

import networkx as nx
from typing import Iterator
from collections import defaultdict
from matplotlib import pyplot as plt

"""
TODO: need write ut for this module @Zihao
"""

EdgeIndex = tuple[str, str, int]


class Vertex(dict):
    """
    A wrapper for node in networkx graph, the label is the only required parameter,
    other parameters are optional.
    """

    def __init__(self, label: str, **kwargs) -> None:
        """
        init a node object that can be added to the networkx graph.

        Args:
            label (str): the label of the node.
            **kwargs: the other parameters of the node.
        """
        super().__init__({"node_for_adding": label, **self._filter(kwargs)})

    @property
    def label(self) -> str:
        """get the label of the node."""
        return self["node_for_adding"]

    def _filter(self, kwargs):
        """filter the None value in the kwargs."""
        return {k: v for k, v in kwargs.items() if v != None}


class Edge(dict):
    """
    A wrapper for edge in networkx graph, the u and v are the only required parameter,
    other parameters are optional.
    """

    def __init__(self, u: str, v: str, **kwargs) -> None:
        """
        init a edge object that can be added to the networkx graph.

        Args:
            u (str): the source node of the edge.
            v (str): the target node of the edge.
            **kwargs: the other parameters of the edge.
        """

        super().__init__({"u_for_edge": str(u), "v_for_edge": str(v), **self._filter(kwargs)})

    @property
    def index(self) -> EdgeIndex:
        """get the index (EdgeIndex) of the edge in the graph."""
        return (self["u_for_edge"], self["v_for_edge"], self.get("key", -1))

    def _filter(self, kwargs):
        """filter the None value in the kwargs."""
        return {k: v for k, v in kwargs.items() if v != None}


class Triple:
    """
    A wrapper for the triple of (Vertex, Edge, Vertex) in networkx graph.
    """

    def __init__(self, source: Vertex, target: Vertex, edge: Edge = None, **kwargs) -> None:
        """
        init a triple object that can be added to the networkx graph.

        Args:
            source (Vertex): the source node of the edge.
            target (Vertex): the target node of the edge.
            edge (Edge): the edge object of the edge.
            **kwargs: the other parameters of the edge.
        """
        self.source = source
        self.target = target
        if edge:
            self.edge = edge
        else:
            self.edge = Edge(source["node_for_adding"], target["node_for_adding"], **kwargs)


class GraphManager:
    """
    A wrapper for networkx graph, the graph is a MultiDiGraph object.
    """

    _root_nodes: list = None
    _leaf_nodes: list = None
    _edge_keys_to_exclude: set = {"u_for_edge", "v_for_edge", "key"}

    def __init__(self, file_path: str = None) -> None:
        """
        Create Graph structure that can be used to store the graph data.
        It can be initialized from a file or a new graph, and save it to a file.

        Args:
            file_path (str, optional): the file path of the graph. Defaults to None.
        """
        self.graph = nx.MultiDiGraph()

        if file_path:
            if not os.path.exists(file_path):
                warnings.warn(f"{file_path} not exists, create a new graph")
            else:
                self.graph = nx.read_gml(file_path)

    @property
    def nodes(self, **kwargs):
        """wrapper for the nodes of the networkx."""
        return self.graph.nodes(**kwargs)

    @property
    def edges(self, **kwargs):
        """wrapper for the edges of the networkx."""
        return self.graph.edges(**kwargs)

    @property
    def in_edges(self):
        """wrapper for the in_edges of the networkx."""
        return self.graph.in_edges

    @property
    def out_edges(self):
        """wrapper for the out_edges of the networkx."""
        return self.graph.out_edges

    @property
    def root_nodes(self) -> list:
        if self._root_nodes == None:
            self._root_nodes = [node for node in self.graph.nodes if self.graph.in_degree(node) == 0]
        return self._root_nodes

    @property
    def leaf_nodes(self) -> list:
        if self._leaf_nodes == None:
            self._leaf_nodes = [node for node in self.graph.nodes if self.graph.out_degree(node) == 0]
        return self._leaf_nodes

    def deduplicate_and_reorder_edges(self) -> "GraphManager":
        """
        Create a new GraphManager with deduplicated and reordered edges.
        """
        seen = set()
        new_keys = defaultdict(int)
        new_graph = nx.MultiDiGraph()

        for u, v, key, data in self.graph.edges(data=True, keys=True):
            edge_tuple = (u, v, frozenset(data.items()))
            if edge_tuple not in seen:
                seen.add(edge_tuple)
                new_key = new_keys[(u, v)]
                new_keys[(u, v)] += 1
                new_graph.add_edge(u, v, key=new_key, **data)

        new_graph_manager = GraphManager()
        new_graph_manager.graph = new_graph
        return new_graph_manager

    def dfs(self):
        """depth first search the graph."""
        return nx.dfs_tree(self.graph)

    def successors(self, node: str):
        """get the successors of the node."""
        return self.graph.successors(node)

    def predecessors(self, node: str):
        """get the predecessors of the node."""
        return self.graph.predecessors(node)

    def is_leaf(self, node: str):
        """check if the node is a leaf."""
        return self.graph.out_degree(node) == 0

    def add_triplet(self, triple: Triple):
        """
        add a triple to the graph.

        Args:
            triple (Triple): the triple object that need to be added to the graph.
        """
        self.add_node(triple.source)
        self.add_node(triple.target)
        self.add_edge(triple.edge)

    def add_edge(self, edge: Edge):
        """
        add a edge to the graph.

        Args:
            edge (Edge): the edge object that need to be added to the graph.

        side effect: update the key of edge object with the key in the graph object
        """
        key = self.graph.add_edge(**edge)
        edge.update({"key": key})

    def remove_edge(self, edge_index: EdgeIndex):
        """
        remove a edge from the graph.

        Args:
            edge_index (EdgeIndex): the edge index that need to be removed from the graph.
        """
        self.graph.remove_edge(*edge_index)

    def add_node(self, vertex: Vertex):
        """
        add a node to the graph.

        Args:
            vertex (Vertex): the node object that need to be added to the graph.
        """
        self.graph.add_node(**vertex)

    def get_node(self, node: Vertex) -> any:
        """
        get the node object from the graph.

        Args:
            node (Vertex): the node object that need to be get from the graph.

        Returns:
            node: the node object (Networkx NodeView) that get from the graph.
        """
        return self.graph.nodes.get(node.label)

    def get_edge(self, edge: Edge) -> list[EdgeIndex]:
        """
        get the edge object from the graph.

        Args:
            edge (Edge): the edge object that need to be get from the graph.

        Returns:
            edges: the edge index list that get from the graph.
        """

        return self.query_edge_by_label(**edge)

    def get_edge_data(self, edge_index: EdgeIndex) -> dict:
        """
        get the edge data from the graph.

        Args:
            edge_index (EdgeIndex): the edge index that need to be get from the graph.

        Returns:
            edge_data: the edge data that get from the graph.
        """
        if edge_index[2] == -1:
            edge_index = (edge_index[0], edge_index[1])

        return self.graph.get_edge_data(*edge_index)

    def get_node_data(self, node_label: str) -> dict:
        """
        get the node data from the graph.

        Args:
            node_label (str): the label of the node.

        Returns:
            node_data: the node data that get from the graph.
        """
        return self.graph.nodes.get(node_label)

    def get_predecessors_of_type(self, node_label: str, edge_type: str):
        """
        get the predecessors of the node with the specific edge type.

        Args:
            node_label (str): the label of the node.
            edge_type (str): the type of the edge.

        Returns:
            predecessors: the predecessors of the node with the specific edge type.
        """
        return [u for u, v, data in self.graph.in_edges(node_label, data=True) if data.get("type") == edge_type]

    def edge_subgraph(self, edges: list[EdgeIndex]) -> "GraphManager":
        """ """
        new_graph = GraphManager()
        new_graph.graph = self.graph.edge_subgraph(edges)
        return new_graph

    def node_subgraph(self, nodes: list[str]):
        """ """
        new_graph = GraphManager()
        new_graph.graph = self.graph.subgraph(nodes)
        return new_graph

    def query_node_by_label(self, label: str) -> Vertex:
        """
        get the node object from the graph.

        Args:
            label (str): the label of the node.

        Returns:
            node: the node object (networkx NodeView) that get from the graph.
        """
        return self.graph.nodes.get(label)

    def query_edge_by_label(self, u_for_edge: str, v_for_edge: str, key=-1, **kwargs) -> EdgeIndex:
        """
        get the edge object from the graph.

        attention: only when the length of return list is zero, the edge is not in the graph.

        Args:
            u_for_edge (str): the source node (label) of the edge.
            v_for_edge (str): the target node (label) of the edge.
            key (int): the key of the edge.
            **kwargs: the other parameters of the edge.

        Returns:
            edge_index: the edge index that get from the graph.
        """
        edge_dict = self.graph.get_edge_data(u_for_edge, v_for_edge, None if key == -1 else key)

        if edge_dict is None:
            return []

        kwargs = {
            k: tuple(v) if isinstance(v, list) else v for k, v in kwargs.items() if k not in self._edge_keys_to_exclude
        }

        # ! get_edge_data return both multiple edges and single edge in dict.
        # * so we need to check the type of the key in the dict.

        if all(isinstance(key, str) for key in edge_dict.keys()):
            return [
                (u_for_edge, v_for_edge, key) for item in filter(lambda x: self._compare_edge(x, kwargs), [edge_dict])
            ]

        if all(isinstance(key, int) for key in edge_dict.keys()):
            return [
                (u_for_edge, v_for_edge, item[0])
                for item in filter(lambda x: self._compare_edge(x[1], kwargs), edge_dict.items())
            ]

        raise ValueError("The edge key is not consistent in the graph.")

    def _compare_edge(self, target: dict, edge_property_dict: dict) -> bool:
        """
        helper function to compare the edge object and the edge property dict.

        Args:
            target (dict): the edge object.
            edge_property_dict (dict): the edge property dict.

        Returns:
            bool: the result of the comparison.
        """
        if not target and not edge_property_dict:
            return True

        keys_to_exclude = {"u_for_edge", "v_for_edge", "key"}
        new_d = {k: tuple(v) if isinstance(v, list) else v for k, v in target.items() if k not in keys_to_exclude}

        edge_dict = {k: tuple(v) if isinstance(v, list) else v for k, v in edge_property_dict.items()}

        return set(set(edge_dict.items())).issubset(new_d.items())

    def _compare_node(self, target: dict, node_property_dict: dict) -> bool:
        """
        helper function to compare the node object and the node property dict.

        Args:
            target (dict): the node object.
            node_property_dict (dict): the node property dict.

        Returns:
            bool: the result of the comparison.
        """

        if not target and not node_property_dict:
            return True

        keys_to_exclude = {"node_for_adding"}
        new_d = {k: tuple(v) if isinstance(v, list) else v for k, v in target.items() if k not in keys_to_exclude}
        node_dict = {k: tuple(v) if isinstance(v, list) else v for k, v in node_property_dict.items()}
        return set(set(node_dict.items())).issubset(new_d.items())

    def filter_edges(self, **kwargs) -> Iterator[tuple[EdgeIndex, dict]]:
        """
        filter the edges in the graph by the edge property dict.

        Usage:
            ```python
            for edge_index, edge_data in graph.filter_edges(type="dependency"):
                graph.remove_edge(edge_index)
                ...
            ```

        Args:
            **kwargs: the edge property dict used to filter the edges.

        Returns:
            Iterator[EdgeIndex, Data]: the edge separated by the edge index and the edge data.
        """
        for edge in filter(lambda x: self._compare_edge(x[3], kwargs), self.graph.edges(data=True, keys=True)):
            yield (edge[0], edge[1], edge[2]), edge[3]

    def filter_nodes(self, **kwargs) -> Iterator[tuple[str, dict]]:
        """
        filter the nodes in the graph by the node property dict.

        Usage:
            ```python
            for node_index, node_data in graph.filter_nodes(type="package"):
                print(node_index, node_data)
            ```

        Args:
            **kwargs: the node property dict used to filter the nodes.

        Returns:
            Iterator[str, Data]: the node separated by the node label and the node data.
        """
        for node in filter(lambda x: self._compare_node(x[1], kwargs), self.graph.nodes(data=True)):
            yield node[0], node[1]

    def modify_node_attribute(self, node_label: str, new_attribute: str, new_value: str):
        """
        Modify the attribute of a node in the graph.

        Args:
            graph_manager (GraphManager): The graph manager object containing the graph.
            node_label (str): The label of the node to be modified.
            new_attribute (str): The name of the new attribute to be added or modified.
            new_value (str): The value of the new attribute.
        """
        target_node = self.query_node_by_label(node_label)
        if target_node:
            target_node[new_attribute] = new_value
            self.graph.nodes[node_label] = target_node
            return self
        else:
            raise Exception(f"Node with label '{node_label}' not found in the graph.")

    def save(self, file_path: str, stringizer=None):
        """save the graph to the file."""

        if not stringizer:
            stringizer = lambda x: str(x)

        nx.write_gml(self.graph, file_path, stringizer=stringizer)

    @classmethod
    def load_from_disk(cls, file_path: str):
        """load the graph from the file."""
        return cls(file_path)

    def viz(self, output_path: str = "graph.png"):
        """visualize the graph and save it to the file."""
        nx.draw(self.graph, with_labels=True, font_weight="bold")
        plt.savefig(output_path)
