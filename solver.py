import os
import numpy as np
import matplotlib
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
from scipy.sparse.csgraph import shortest_path

# --- NEW HELPER: Reconstructs the exact physical hallways walked ---
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
    
    # 1. The "Smart GPS" (NOW WITH return_predecessors=True)
    dist_matrix_for_pathing = np.where(distances == 0, np.inf, distances)
    np.fill_diagonal(dist_matrix_for_pathing, 0)
    all_pairs_distances, predecessors = shortest_path(csgraph=dist_matrix_for_pathing, directed=False, return_predecessors=True)
    
    # 2. Initialize Pheromones
    pheromones = np.ones((n_nodes, n_nodes)) * 0.1
    
    best_macro_tour = None
    best_length = float('inf')
    
    # Entrance Logic
    start_node = np.lexsort((coords[:, 0], coords[:, 1]))[0]
    print(f"Entrance Identified: Room {start_node} at coordinates {coords[start_node]}")
    print(f"Unleashing {n_ants} ants for {n_iterations} iterations...")
    
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
                
        if iteration % 10 == 0:
            print(f"Iteration {iteration:03d} | Best Route: {int(best_length)} total moves")
            
    # --- NEW: UNPACK THE MACRO TOUR INTO PHYSICAL STEPS ---
    physical_tour = [best_macro_tour[0]]
    for i in range(len(best_macro_tour) - 1):
        start_n = best_macro_tour[i]
        end_n = best_macro_tour[i+1]
        # Inject the actual hallway nodes into the array
        segment = get_physical_path(start_n, end_n, predecessors)
        physical_tour.extend(segment)
        
    return physical_tour, best_length, all_pairs_distances

def draw_base_graph_edges(ax, distances, coords, color='red'):
    n_nodes = distances.shape[0]
    for u in range(n_nodes):
        for v in range(u + 1, n_nodes): 
            if distances[u, v] > 0 and distances[u, v] != np.inf:
                start_c = coords[u]
                end_c = coords[v]
                ax.annotate("", xy=end_c, xytext=start_c, 
                            arrowprops=dict(arrowstyle="-", color=color, linewidth=4.0, alpha=0.6, zorder=1))

def visualize_tour(coords, physical_tour, title, distances):
    fig, ax = plt.figure(figsize=(10, 10)), plt.gca()
    
    xs = coords[:, 0]
    ys = coords[:, 1]
    
    draw_base_graph_edges(ax, distances, coords)
    ax.scatter(xs, ys, c='blue', s=100, zorder=5)
    
    entrance_idx = physical_tour[0]
    ax.scatter(coords[entrance_idx, 0], coords[entrance_idx, 1], c='yellow', edgecolors='black', s=400, marker='*', zorder=10, label="Entrance")
    
    # The physical_tour now ONLY contains strictly adjacent nodes!
    tour_coords = coords[physical_tour]
    
    for i in range(len(tour_coords) - 1):
        start_c = tour_coords[i]
        end_c = tour_coords[i+1]
        
        dx = end_c[0] - start_c[0]
        dy = end_c[1] - start_c[1]
        
        # Draw the continuous dashed line between adjacent rooms
        ax.plot([start_c[0], end_c[0]], [start_c[1], end_c[1]], 
                color="blue", linewidth=2.0, linestyle="--", zorder=6)
        
        # Drop the arrowhead exactly at the 50% midpoint
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
    save_filename = os.path.join(save_dir, "optimized_directional_renovation_route.png")
    
    plt.savefig(save_filename, bbox_inches='tight')
    print(f"\n🗺️  Map saved successfully! Check your folder for '{save_filename}'")
    plt.close()

if __name__ == "__main__":
    dataset_path = os.path.join("dataset", "renovation_data.npz")
    print(f"Loading data from {dataset_path}...")
    
    data = np.load(dataset_path, allow_pickle=True)
    distances_array = data['distances']
    coords_array = data['coords']
    
    print(f"Loaded {len(distances_array)} graphs. We will solve Graph #1.")
    
    original_distances = np.array(distances_array[0], dtype=np.float64)
    test_coords = np.array(coords_array[0], dtype=np.float64)
    
    # 1 Move = 1 Travel Meter
    test_distances = np.where(original_distances > 0, 1.0, 0.0)
    
    print(f"Graph #1 has {test_distances.shape[0]} rooms.")
    
    physical_tour, best_length, all_pairs_distances = run_ant_colony(test_distances, test_coords)
    
    print("\n✅ Simulation Complete!")
    print(f"Shortest path found covers all rooms in {int(best_length)} total moves.")
    
    visualize_tour(test_coords, physical_tour, f"Ant Colony Optimized Renovation Route\nTotal Moves: {int(best_length)}", original_distances)