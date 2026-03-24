import os
import sys
import numpy as np
import networkx as nx

from network_generator import NetworkGenerator
from visualizer import get_sorted_nodes

def create_renovation_dataset():
    print("Generating 10 graphs. Accepting any valid room count...")
    
    all_distance_matrices = []
    all_coord_matrices = []
    
    success_count = 0
    
    while success_count < 10:
        sys.stdout.write('.')
        sys.stdout.flush()
            
        try:
            # We let your generator do what it does best.
            # We keep target_edges reasonable (75) so it doesn't get stuck drawing crossing lines.
            gen = NetworkGenerator(
                width=8, 
                height=8, 
                variant="Custom", 
                topology="highly_connected", 
                node_drop_fraction=0.2,
                target_edges=75  
            )
            G = gen.generate()
            
            sorted_nodes = get_sorted_nodes(G)
            num_nodes = len(sorted_nodes)
            
            # Convert to ML Matrices
            coords = np.array(sorted_nodes, dtype=np.float32)
            dist_matrix = np.zeros((num_nodes, num_nodes), dtype=np.float32)
            
            for u, v in G.edges():
                idx_u = sorted_nodes.index(u)
                idx_v = sorted_nodes.index(v)
                dist = np.sqrt((u[0] - v[0])**2 + (u[1] - v[1])**2)
                dist_matrix[idx_u][idx_v] = dist
                dist_matrix[idx_v][idx_u] = dist
                
            all_coord_matrices.append(coords)
            all_distance_matrices.append(dist_matrix)
            
            success_count += 1
            print(f"\n✅ Graph {success_count} generated with {num_nodes} rooms!")
                
        except Exception as e:
            # If the generator fails to find a valid layout, quietly try again
            continue

    # Because our matrices might be slightly different sizes (e.g., 51 vs 52), 
    # we save them as 'object' arrays so NumPy doesn't complain.
    os.makedirs("dataset", exist_ok=True)
    np.savez_compressed(
        "dataset/renovation_data.npz", 
        distances=np.array(all_distance_matrices, dtype=object), 
        coords=np.array(all_coord_matrices, dtype=object)
    )
    
    print("\n🎉 Done! Data saved to dataset/renovation_data.npz")

if __name__ == "__main__":
    create_renovation_dataset()