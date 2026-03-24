import networkx as nx
import matplotlib.pyplot as plt
from datetime import datetime
import os
import shutil

IMG_WIDTH_PX = 800
IMG_HEIGHT_PX = 800
TEMP_DIR = "temp_visuals"

# --- NEW CLEANUP LOGIC ---
# Wipe the folder clean when the app starts, then recreate it
if os.path.exists(TEMP_DIR):
    shutil.rmtree(TEMP_DIR)
os.makedirs(TEMP_DIR, exist_ok=True)
# -------------------------

def get_sorted_nodes(G):
    """Returns nodes sorted by X, then Y to ensure consistent IDs."""
    return sorted(list(G.nodes()), key=lambda l: (l[0], l[1]))

def plot_graph_to_image(graph, width, height, title="Network", highlight_node=None, save_dir=TEMP_DIR):
    """Generates a matplotlib plot and saves it as an image file."""
    dpi = 100
    fig = plt.figure(figsize=(IMG_WIDTH_PX/dpi, IMG_HEIGHT_PX/dpi), dpi=dpi)
    ax = fig.add_axes([0, 0, 1, 1]) 
    
    pos = {node: (node[0], node[1]) for node in graph.nodes()}
    
    # Dynamic sizing to prevent jamming
    max_dim = max(width, height)
    if max_dim <= 6:
        n_sz, f_sz, h_sz = 900, 12, 1100
    elif max_dim <= 10:
        n_sz, f_sz, h_sz = 500, 9, 650
    elif max_dim <= 16:
        n_sz, f_sz, h_sz = 200, 7, 280
    elif max_dim <= 24:
        n_sz, f_sz, h_sz = 100, 5, 140
    else:
        n_sz, f_sz, h_sz = 50, 4, 80

    nx.draw_networkx_edges(graph, pos, ax=ax, width=2, alpha=0.6, edge_color="#333")
    
    normal_nodes = [n for n in graph.nodes() if n != highlight_node]
    nx.draw_networkx_nodes(graph, pos, ax=ax, nodelist=normal_nodes, node_size=n_sz, node_color="#4F46E5", edgecolors="white", linewidths=1.5)
    
    if highlight_node and graph.has_node(highlight_node):
        nx.draw_networkx_nodes(graph, pos, ax=ax, nodelist=[highlight_node], node_size=h_sz, node_color="#EF4444", edgecolors="white", linewidths=2.0)
    
    sorted_nodes = get_sorted_nodes(graph)
    labels = {node: str(i+1) for i, node in enumerate(sorted_nodes)}
    nx.draw_networkx_labels(graph, pos, labels, ax=ax, font_size=f_sz, font_color="white", font_weight="bold")
    
    ax.set_xlim(-0.5, width + 0.5)
    ax.set_ylim(height + 0.5, -0.5)
    ax.grid(True, linestyle=':', alpha=0.3)
    ax.set_axis_on()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    prefix = "temp_plot" if save_dir == TEMP_DIR else "saved_plot"
    fname = os.path.join(save_dir, f"{prefix}_{timestamp}.png")
    
    plt.savefig(fname)
    plt.close(fig)
    return fname