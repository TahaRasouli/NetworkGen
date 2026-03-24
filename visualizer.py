import networkx as nx
import matplotlib.pyplot as plt
from datetime import datetime
import os
import shutil
import os
import matplotlib
matplotlib.use('Agg')
import networkx as nx

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

def plot_graph_to_image(G, width, height, highlight_node=None, title=None, save_dir="temp_visuals"):
    """
    Renders the NetworkX graph to a PNG image with a locked, centered camera.
    """
    os.makedirs(save_dir, exist_ok=True)
    filepath = os.path.join(save_dir, "current_graph.png")

    fig, ax = plt.subplots(figsize=(10, 10))

    # 1. Map Coordinates for nodes
    pos = {n: (n[0], n[1]) for n in G.nodes()}

    # 2. Sort nodes to match the numbering from top-left to bottom-right
    sorted_nodes = sorted(list(G.nodes()), key=lambda x: (x[1], x[0]))
    labels = {n: str(i + 1) for i, n in enumerate(sorted_nodes)}

    # 3. Determine node colors (highlighting selected nodes if applicable)
    node_colors = []
    for n in G.nodes():
        if highlight_node and n == highlight_node:
            node_colors.append('lime')
        else:
            node_colors.append('#6366f1') # The purple/indigo from your screenshot

    # 4. Draw the base graph (Edges first so they sit under the nodes)
    nx.draw_networkx_edges(G, pos, ax=ax, edge_color='gray', width=2.0, alpha=0.8)
    nx.draw_networkx_nodes(G, pos, ax=ax, node_color=node_colors, node_size=700, edgecolors='white', linewidths=2)
    nx.draw_networkx_labels(G, pos, labels=labels, ax=ax, font_color='white', font_weight='bold', font_size=10)

    # 5. Draw the background grid
    ax.set_xticks(range(int(width)))
    ax.set_yticks(range(int(height)))
    ax.grid(True, linestyle=':', alpha=0.5)

    if title:
        ax.set_title(title, pad=20, fontsize=14, fontweight='bold')

    # --- THE CAMERA FIX ---
    # This forces the camera to look at the entire grid evenly, 
    # regardless of whether edge nodes are missing.
    ax.set_xlim(-1, width)
    ax.set_ylim(height, -1) # Going from height -> -1 automatically inverts the Y-axis!
    # ----------------------

    # Lighten the outer border box
    for spine in ax.spines.values():
        spine.set_color('#dddddd')

    # Save and cleanup
    plt.tight_layout()
    plt.savefig(filepath, bbox_inches='tight', dpi=100)
    plt.close(fig)

    return filepath