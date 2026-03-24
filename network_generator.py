import networkx as nx
import random
from visualizer import get_sorted_nodes

def validate_topology(G, topology):
    n = len(G.nodes())
    e = len(G.edges())
    if n < 3: return True, "Graph too small for strict validation."
    
    avg_deg = (2.0 * e) / n
    
    if topology == "highly_connected":
        if avg_deg < 2.5:
            return False, f"Graph is sparse (Avg Degree: {avg_deg:.1f}) for 'Highly Connected'. Add more target edges."
            
    elif topology == "bottlenecks":
        bridges = list(nx.bridges(G))
        if len(bridges) == 0 and avg_deg > 3.0:
            return False, "Graph lacks distinct bottleneck links (bridges) and is too dense. Reduce target edges."
            
    elif topology == "linear":
        max_deg = max([d for n, d in G.degree()]) if len(G.nodes()) > 0 else 0
        if max_deg > 4 or avg_deg > 2.5:
            return False, f"Graph contains hub nodes (Max Degree: {max_deg}) or is too dense for 'Linear'. Reduce edges."
            
    return True, "Topology matches definition."

class NetworkGenerator:
    def __init__(self, width=10, height=10, variant="F", topology="highly_connected", 
                 node_drop_fraction=0.1, target_edges=0,
                 bottleneck_cluster_count=None, bottleneck_edges_per_link=1):
        
        self.variant = variant.upper() 
        self.topology = topology.lower()
        self.width = int(width)
        self.height = int(height)
        
        self.node_drop_fraction = float(node_drop_fraction)
        self.target_edges = int(target_edges)
        self.node_factor = 0.4 
        
        if bottleneck_cluster_count is None:
            area = self.width * self.height
            self.bottleneck_cluster_count = max(2, int(area / 18))
        else:
            self.bottleneck_cluster_count = int(bottleneck_cluster_count)
            
        self.bottleneck_edges_per_link = int(bottleneck_edges_per_link)
        self.graph = None
        self.active_positions = None 

    # def calculate_defaults(self):
    #     total_possible = (self.width + 1) * (self.height + 1)
    #     scale = {"highly_connected": 1.2, "bottlenecks": 0.85, "linear": 0.75}.get(self.topology, 1.0)
        
    #     if self.topology == "highly_connected": vf = max(0.0, self.node_drop_fraction * 0.8)
    #     elif self.topology == "linear": vf = min(0.95, self.node_drop_fraction * 1.2)
    #     else: vf = self.node_drop_fraction
        
    #     est_nodes = int(self.node_factor * scale * total_possible * (1.0 - vf))
        
    #     if self.topology == "highly_connected": est_edges = int(3.5 * est_nodes)
    #     elif self.topology == "bottlenecks": est_edges = int(1.8 * est_nodes)
    #     else: est_edges = int(1.5 * est_nodes)
        
    #     return est_nodes, est_edges

    def calculate_defaults(self):
        total_possible = self.width * self.height
        scale = {"highly_connected": 1.2, "bottlenecks": 0.85, "linear": 0.75}.get(self.topology, 1.0)
        
        # NEW: Use the unified fraction method we just updated above
        vf = self._effective_node_drop_fraction()
        
        est_nodes = int(self.node_factor * scale * total_possible * (1.0 - vf))
        if self.topology == "highly_connected": est_edges = int(3.5 * est_nodes)
        elif self.topology == "bottlenecks": est_edges = int(1.8 * est_nodes)
        else: est_edges = int(1.5 * est_nodes)
        return est_nodes, est_edges
        
    def calculate_max_capacity(self):
        """Estimates max possible edges for planar-like spatial graph."""
        total_possible_nodes = int(self.width * self.height * (1.0 - self.node_drop_fraction))
        if self.topology == "highly_connected":
            return int(total_possible_nodes * 4.5)
        return int(total_possible_nodes * 3.0)

    def generate(self):
        max_attempts = 15 
        for attempt in range(max_attempts):
            self._build_node_mask()
            self._initialize_graph()
            self._add_nodes()

            nodes = list(self.graph.nodes())
            if len(nodes) < 2: continue

            if self.topology == "bottlenecks":
                self._build_bottleneck_clusters(nodes)
            else:
                self._connect_all_nodes_by_nearby_growth(nodes)
                self._add_edges()

            self._remove_intersections()
            
            if self.target_edges > 0:
                self._adjust_edges_to_target()
            else:
                self._enforce_edge_budget()

            if not nx.is_connected(self.graph):
                self._force_connect_components()
            
            self._remove_intersections() 
            
            if nx.is_connected(self.graph):
                return self.graph

        raise RuntimeError("Failed to generate valid network. Loosen overrides.")

    # def _effective_node_drop_fraction(self):
    #     base = self.node_drop_fraction
    #     if self.topology == "highly_connected": return max(0.0, base * 0.8)
    #     if self.topology == "linear": return min(0.95, base * 1.2)
    #     return base

    def _effective_node_drop_fraction(self):
        base = self.node_drop_fraction
        
        # Fix: app.py passes "R" when the "Custom" variant is selected
        if self.variant == "R":
            return base
            
        # Safety net for 'Fixed' ("F") presets
        if self.topology == "highly_connected": return max(0.0, base * 0.8)
        if self.topology == "linear": return min(0.95, base * 1.2)
        return base

    def _build_node_mask(self):
        all_positions = [(x, y) for x in range(self.width) for y in range(self.height)]
        drop_frac = self._effective_node_drop_fraction()
        drop = int(drop_frac * len(all_positions))
        deactivated = set(random.sample(all_positions, drop)) if drop > 0 else set()
        self.active_positions = set(all_positions) - deactivated

    def _initialize_graph(self):
        self.graph = nx.Graph()
        margin_x = max(1, self.width // 4)
        margin_y = max(1, self.height // 4)
        low_x, high_x = margin_x, self.width - 1 - margin_x
        low_y, high_y = margin_y, self.height - 1 - margin_y
        
        if low_x > high_x: low_x, high_x = 0, self.width - 1
        if low_y > high_y: low_y, high_y = 0, self.height - 1

        middle_active = [p for p in self.active_positions if low_x <= p[0] <= high_x and low_y <= p[1] <= high_y]
        
        if middle_active: seed = random.choice(middle_active)
        elif self.active_positions: seed = random.choice(list(self.active_positions))
        else: return 
        self.graph.add_node(tuple(seed))

    def _add_nodes(self):
        for n in self.active_positions:
            if not self.graph.has_node(n):
                self.graph.add_node(n)

    def _connect_all_nodes_by_nearby_growth(self, nodes):
        connected = set()
        remaining = set(nodes)
        if not remaining: return
        current = random.choice(nodes)
        connected.add(current)
        remaining.remove(current)

        while remaining:
            candidates = []
            for n in remaining:
                closest_dist = min([abs(n[0]-c[0]) + abs(n[1]-c[1]) for c in connected])
                if closest_dist <= 4:
                    candidates.append(n)
            
            if not candidates:
                 best_n = min(remaining, key=lambda r: min(abs(r[0]-c[0]) + abs(r[1]-c[1]) for c in connected))
                 candidates.append(best_n)

            candidate = random.choice(candidates)
            neighbors = sorted(list(connected), key=lambda c: abs(c[0]-candidate[0]) + abs(c[1]-candidate[1]))
            for n in neighbors[:3]:
                if not self._would_create_intersection(n, candidate):
                    self.graph.add_edge(n, candidate)
                    break
            else:
                self.graph.add_edge(neighbors[0], candidate)

            connected.add(candidate)
            remaining.remove(candidate)

    def _compute_edge_count(self):
        if self.target_edges > 0: return self.target_edges
        n = len(self.graph.nodes())
        if self.topology == "highly_connected": return int(3.5 * n)
        if self.topology == "bottlenecks": return int(1.8 * n)
        return int(random.uniform(1.2, 2.0) * n)

    def _add_edges(self):
        nodes = list(self.graph.nodes())
        if self.topology == "highly_connected": self._add_cluster_dense(nodes, self._compute_edge_count())
        elif self.topology == "linear": self._make_linear(nodes)

    def _make_linear(self, nodes):
        nodes_sorted = sorted(nodes, key=lambda x: (x[0], x[1]))
        if not nodes_sorted: return
        prev = nodes_sorted[0]
        for nxt in nodes_sorted[1:]:
            if not self._would_create_intersection(prev, nxt): self.graph.add_edge(prev, nxt)
            prev = nxt

    def _add_cluster_dense(self, nodes, max_edges):
        edges_added = 0
        nodes = list(nodes)
        random.shuffle(nodes)
        dist_limit = 10 if self.target_edges > 0 else 4
        
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                if self.target_edges == 0 and edges_added >= max_edges: return
                n1, n2 = nodes[i], nodes[j]
                dist = max(abs(n1[0]-n2[0]), abs(n1[1]-n2[1]))
                if dist <= dist_limit: 
                    if not self._would_create_intersection(n1, n2):
                        self.graph.add_edge(n1, n2)
                        edges_added += 1

    def _build_bottleneck_clusters(self, nodes):
        self.graph.remove_edges_from(list(self.graph.edges()))
        clusters, centers = self._spatial_cluster_nodes(nodes, k=self.bottleneck_cluster_count)
        for cluster in clusters:
            if len(cluster) < 2: continue
            # FIX: Call main connectivity directly
            self._connect_all_nodes_by_nearby_growth(cluster)
            self._add_cluster_dense(list(cluster), max_edges=max(1, int(3.5 * len(cluster))))
        
        order = sorted(range(len(clusters)), key=lambda i: (centers[i][0], centers[i][1]))
        for a_idx, b_idx in zip(order[:-1], order[1:]):
            self._add_bottleneck_links(clusters[a_idx], clusters[b_idx], self.bottleneck_edges_per_link)
        
        if not nx.is_connected(self.graph): self._force_connect_components()

    def _force_connect_components(self):
        components = list(nx.connected_components(self.graph))
        while len(components) > 1:
            c1, c2 = list(components[0]), list(components[1])
            best_pair, min_dist = None, float('inf')
            s1 = c1 if len(c1)<30 else random.sample(c1, 30)
            s2 = c2 if len(c2)<30 else random.sample(c2, 30)
            for u in s1:
                for v in s2:
                    d = (u[0]-v[0])**2 + (u[1]-v[1])**2
                    if d < min_dist and not self._would_create_intersection(u, v):
                        min_dist, best_pair = d, (u, v)
            if best_pair: self.graph.add_edge(best_pair[0], best_pair[1])
            else: break 
            prev_len = len(components)
            components = list(nx.connected_components(self.graph))
            if len(components) == prev_len: break

    def _spatial_cluster_nodes(self, nodes, k):
        nodes = list(nodes)
        if k >= len(nodes): return [[n] for n in nodes], nodes[:]
        centers = random.sample(nodes, k)
        clusters = [[] for _ in range(k)]
        for n in nodes:
            best_i = min(range(k), key=lambda i: max(abs(n[0]-centers[i][0]), abs(n[1]-centers[i][1])))
            clusters[best_i].append(n)
        return clusters, centers

    def _add_bottleneck_links(self, cluster_a, cluster_b, m):
        pairs = []
        for u in cluster_a:
            for v in cluster_b:
                dist = max(abs(u[0]-v[0]), abs(u[1]-v[1]))
                pairs.append((dist, u, v))
        pairs.sort(key=lambda t: t[0])
        added = 0
        for _, u, v in pairs:
            if added >= m: break
            if not self.graph.has_edge(u, v) and not self._would_create_intersection(u, v): 
                self.graph.add_edge(u, v)
                added += 1

    def _remove_intersections(self):
        pass_no = 0
        while pass_no < 5:
            pass_no += 1
            edges = list(self.graph.edges())
            intersections = []
            check_edges = random.sample(edges, 400) if len(edges) > 600 else edges
            for i in range(len(check_edges)):
                for j in range(i+1, len(check_edges)):
                    e1, e2 = check_edges[i], check_edges[j]
                    if self._segments_intersect(e1[0], e1[1], e2[0], e2[1]): intersections.append((e1, e2))
            if not intersections: break
            for e1, e2 in intersections:
                if not self.graph.has_edge(*e1) or not self.graph.has_edge(*e2): continue
                l1 = (e1[0][0]-e1[1][0])**2 + (e1[0][1]-e1[1][1])**2
                l2 = (e2[0][0]-e2[1][0])**2 + (e2[0][1]-e2[1][1])**2
                rem = e1 if l1 > l2 else e2
                self.graph.remove_edge(*rem)

    def _adjust_edges_to_target(self):
        current_edges = list(self.graph.edges())
        curr_count = len(current_edges)
        if curr_count > self.target_edges:
            to_remove = curr_count - self.target_edges
            sorted_edges = sorted(current_edges, key=lambda e: (e[0][0]-e[1][0])**2 + (e[0][1]-e[1][1])**2, reverse=True)
            for e in sorted_edges:
                if len(self.graph.edges()) <= self.target_edges: break
                self.graph.remove_edge(*e)
                if not nx.is_connected(self.graph): self.graph.add_edge(*e) 
        elif curr_count < self.target_edges:
            needed = self.target_edges - curr_count
            nodes = list(self.graph.nodes())
            attempts = 0
            while len(self.graph.edges()) < self.target_edges and attempts < (needed * 30):
                attempts += 1
                u = random.choice(nodes)
                candidates = sorted(nodes, key=lambda n: (n[0]-u[0])**2 + (n[1]-u[1])**2)
                if len(candidates) < 2: continue
                v = random.choice(candidates[1:min(len(candidates), 10)])
                if not self.graph.has_edge(u, v) and not self._would_create_intersection(u, v):
                    self.graph.add_edge(u, v)

    def _enforce_edge_budget(self):
        budget = self._compute_edge_count()
        while len(self.graph.edges()) > budget:
            edges = list(self.graph.edges())
            rem = random.choice(edges)
            self.graph.remove_edge(*rem)
            if not nx.is_connected(self.graph):
                self.graph.add_edge(*rem)
                break 

    def _segments_intersect(self, a, b, c, d):
        if a == c or a == d or b == c or b == d: return False
        def ccw(A,B,C): return (C[1]-A[1]) * (B[0]-A[0]) > (B[1]-A[1]) * (C[0]-A[0])
        return ccw(a,c,d) != ccw(b,c,d) and ccw(a,b,c) != ccw(a,b,d)

    def _would_create_intersection(self, u, v):
        for a, b in self.graph.edges():
            if u == a or u == b or v == a or v == b: continue
            if self._segments_intersect(u, v, a, b): return True
        return False

    def _get_intersecting_edge(self, u, v):
        for a, b in self.graph.edges():
            if u == a or u == b or v == a or v == b: continue
            if self._segments_intersect(u, v, a, b): return (a, b)
        return None

    def get_node_id_str(self, node):
        sorted_nodes = get_sorted_nodes(self.graph)
        if node in sorted_nodes:
            return str(sorted_nodes.index(node) + 1)
        return "?"

    def manual_add_node(self, x, y):
        x, y = int(x), int(y)
        # FIX: Bounds check against Width-1
        if not (0 <= x < self.width and 0 <= y < self.height): return False, "Out of bounds."
        if self.graph.has_node((x, y)): return False, "Already exists."
        self.graph.add_node((x, y))
        nodes = list(self.graph.nodes())
        if len(nodes) > 1:
            closest = min([n for n in nodes if n != (x,y)], key=lambda n: (n[0]-x)**2 + (n[1]-y)**2)
            if not self._would_create_intersection((x,y), closest): self.graph.add_edge((x,y), closest)
        return True, "Node added."

    def manual_delete_node(self, x, y):
        x, y = int(x), int(y)
        if not self.graph.has_node((x, y)): return False, "Node not found."
        self.graph.remove_node((x, y))
        if len(self.graph.nodes()) > 1 and not nx.is_connected(self.graph):
            self._force_connect_components()
        return True, "Node removed."
        
    def manual_toggle_edge(self, u, v):
        if self.graph.has_edge(u, v):
            self.graph.remove_edge(u, v)
            if not nx.is_connected(self.graph): 
                self.graph.add_edge(u, v)
                return False, "Cannot remove edge (breaks connectivity)."
            return True, "Edge removed."
        else:
            intersecting_edge = self._get_intersecting_edge(u, v)
            if not intersecting_edge:
                self.graph.add_edge(u, v)
                return True, "Edge added."
            else:
                a, b = intersecting_edge
                id_a = self.get_node_id_str(a)
                id_b = self.get_node_id_str(b)
                return False, f"Intersect with {id_a}-{id_b}."