import os
import numpy as np
import networkx as nx
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
from scipy.sparse.csgraph import shortest_path

# Import visualizer's sorter to ensure coordinates match the app perfectly
from visualizer import get_sorted_nodes

def get_physical_path(start, end, preds):
    path = []
    curr = end
    while curr != start and curr >= 0:
        path.append(curr)
        curr = preds[start, curr]
    path.reverse()
    return path

def run_ant_colony(distances, coords, n_ants=50, n_iterations=100, decay=0.1, alpha=1.0, beta=2.0):
    n_nodes = distances.shape[0]
    
    dist_matrix_for_pathing = np.where(distances == 0, np.inf, distances)
    np.fill_diagonal(dist_matrix_for_pathing, 0)
    all_pairs_distances, predecessors = shortest_path(csgraph=dist_matrix_for_pathing, directed=False, return_predecessors=True)
    
    pheromones = np.ones((n_nodes, n_nodes)) * 0.1
    best_macro_tour = None
    best_length = float('inf')
    
    start_node = np.lexsort((coords[:, 0], coords[:, 1]))[0]
    
    for iteration in range(n_iterations):
        all_tours = []
        all_lengths = []
        
        for ant in range(n_ants):
            unvisited = set(range(n_nodes))
            current_node = start_node 
            tour = [current_node]
            unvisited.remove(current_node)
            tour_length = 0.0
            
            while unvisited:
                candidates = list(unvisited)
                pher_values = pheromones[current_node, candidates]
                dist_values = all_pairs_distances[current_node, candidates]
                heuristic = 1.0 / (dist_values + 1e-10) 
                
                probabilities = (pher_values ** alpha) * (heuristic ** beta)
                if probabilities.sum() == 0:
                    probabilities = np.ones(len(candidates)) / len(candidates)
                else:
                    probabilities /= probabilities.sum() 
                
                next_node = np.random.choice(candidates, p=probabilities)
                
                tour.append(next_node)
                tour_length += all_pairs_distances[current_node, next_node]
                unvisited.remove(next_node)
                current_node = next_node
                
            tour_length += all_pairs_distances[tour[-1], tour[0]]
            tour.append(tour[0])
            
            all_tours.append(tour)
            all_lengths.append(tour_length)
            
            if tour_length < best_length:
                best_length = tour_length
                best_macro_tour = tour
                
        pheromones *= (1.0 - decay) 
        
        for tour, length in zip(all_tours, all_lengths):
            deposit_amount = 100.0 / length 
            for i in range(len(tour) - 1):
                u, v = tour[i], tour[i+1]
                pheromones[u, v] += deposit_amount
                pheromones[v, u] += deposit_amount 
            
    # Unpack the macro tour into physical steps
    physical_tour = [best_macro_tour[0]]
    for i in range(len(best_macro_tour) - 1):
        start_n = best_macro_tour[i]
        end_n = best_macro_tour[i+1]
        segment = get_physical_path(start_n, end_n, predecessors)
        physical_tour.extend(segment)
        
    return physical_tour, best_length

def draw_base_graph_edges(ax, distances, coords, color='red'):
    n_nodes = distances.shape[0]
    for u in range(n_nodes):
        for v in range(u + 1, n_nodes): 
            if distances[u, v] > 0 and distances[u, v] != np.inf:
                start_c = coords[u]
                end_c = coords[v]
                ax.annotate("", xy=end_c, xytext=start_c, 
                            arrowprops=dict(arrowstyle="-", color=color, linewidth=4.0, alpha=0.6, zorder=1))

def visualize_tour_app(coords, physical_tour, title, distances, width, height):
    fig, ax = plt.figure(figsize=(10, 10)), plt.gca()
    
    # Force grid to match app dimensions
    ax.set_xlim(-0.5, width - 0.5)
    ax.set_ylim(-0.5, height - 0.5)
    
    xs = coords[:, 0]
    ys = coords[:, 1]
    
    draw_base_graph_edges(ax, distances, coords)
    ax.scatter(xs, ys, c='blue', s=100, zorder=5)
    
    entrance_idx = physical_tour[0]
    ax.scatter(coords[entrance_idx, 0], coords[entrance_idx, 1], c='yellow', edgecolors='black', s=400, marker='*', zorder=10, label="Entrance")
    
    tour_coords = coords[physical_tour]
    
    for i in range(len(tour_coords) - 1):
        start_c = tour_coords[i]
        end_c = tour_coords[i+1]
        
        dx = end_c[0] - start_c[0]
        dy = end_c[1] - start_c[1]
        
        ax.plot([start_c[0], end_c[0]], [start_c[1], end_c[1]], 
                color="blue", linewidth=2.0, linestyle="--", zorder=6)
        
        mid_x = start_c[0] + dx * 0.50
        mid_y = start_c[1] + dy * 0.50
        target_x = start_c[0] + dx * 0.51
        target_y = start_c[1] + dy * 0.51
        
        ax.annotate("", xy=(target_x, target_y), xytext=(mid_x, mid_y),
                    arrowprops=dict(arrowstyle="-|>,head_width=0.4,head_length=0.8", 
                                    color="blue", linewidth=2.0, zorder=7))

    ax.set_title(title, pad=20, fontsize=14, fontweight='bold')
    ax.invert_yaxis() 
    ax.grid(True, linestyle=':', alpha=0.6)
    
    from matplotlib.lines import Line2D
    custom_lines = [Line2D([0], [0], color="blue", linewidth=2.0, linestyle="--"),
                    Line2D([0], [0], marker='*', color='w', markerfacecolor='yellow', markeredgecolor='black', markersize=15),
                    Line2D([0], [0], color="red", linewidth=4.0, alpha=0.6)]
    ax.legend(custom_lines, ['Worker Route', 'Entrance', 'Available Hallways'], loc="best")
    
    save_dir = "temp_visuals"
    os.makedirs(save_dir, exist_ok=True)
    save_filename = os.path.join(save_dir, "app_ant_route.png")
    
    plt.savefig(save_filename, bbox_inches='tight')
    plt.close()
    return save_filename

def solve_and_visualize(G, width, height):
    """Main function to be called from app.py"""
    sorted_nodes = get_sorted_nodes(G)
    n_nodes = len(sorted_nodes)
    
    # 1. Build Coordinates Matrix
    coords = np.array(sorted_nodes, dtype=np.float64)
    
    # 2. Build Distance Matrix (1 Move = 1 Travel Meter)
    distances = np.zeros((n_nodes, n_nodes), dtype=np.float64)
    for u, v in G.edges():
        idx_u = sorted_nodes.index(u)
        idx_v = sorted_nodes.index(v)
        distances[idx_u, idx_v] = 1.0
        distances[idx_v, idx_u] = 1.0
        
    # 3. Run the swarm
    physical_tour, best_length = run_ant_colony(distances, coords)
    
    # 4. Draw the image and return the path
    img_path = visualize_tour_app(coords, physical_tour, f"Ant Colony Optimized Route\nTotal Moves: {int(best_length)}", distances, width, height)
    return img_path, int(best_length)
