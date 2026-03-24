import gradio as gr
import os
import shutil
import random
import json
import zipfile
import networkx as nx
from datetime import datetime

# Import from our custom modules
from network_generator import NetworkGenerator, validate_topology
from visualizer import plot_graph_to_image, IMG_WIDTH_PX, IMG_HEIGHT_PX, TEMP_DIR
from json_handler import generate_full_json_dict, load_graph_from_json, load_graph_from_data

# --- NEW: ANTS ---
from ants import solve_and_visualize

# ==========================================
# DIRECTORY MANAGEMENT
# ==========================================
PERM_VIS_DIR = "saved_visuals"
ZIP_DIR = "saved_zips"

os.makedirs(PERM_VIS_DIR, exist_ok=True)
os.makedirs(ZIP_DIR, exist_ok=True)

def get_local_zips():
    if not os.path.exists(ZIP_DIR): return []
    return [f for f in os.listdir(ZIP_DIR) if f.endswith('.zip')]

def extract_jsons_from_zip(zip_path):
    loaded = []
    with zipfile.ZipFile(zip_path, 'r') as z:
        for filename in z.namelist():
            if filename.endswith('.json'):
                with z.open(filename) as f:
                    data = json.load(f)
                    loaded.append(load_graph_from_data(data, filename))
    return loaded

# ==========================================
# UI EVENT HANDLERS
# ==========================================

# --- NEW: ANTS HANDLER ---
def handle_release_ants(state_data):
    if not state_data or "graph" not in state_data: 
        return gr.update(), "⚠️ Please generate a network first before releasing the ants.", state_data
    
    G = state_data["graph"]
    w = state_data["width"]
    h = state_data["height"]
    
    try:
        # Run the ACO algorithm
        img_path, best_length = solve_and_visualize(G, w, h)
        metrics = f"**🐜 Swarm Complete!**\nFound highly optimized path covering all {len(G.nodes())} rooms in **{best_length} moves**."
        return img_path, metrics, state_data
    except Exception as e:
        return gr.update(), f"⚠️ Ant Colony Error: {str(e)}", state_data


def handle_plot_click(evt: gr.SelectData, click_mode, state_data):
    if not state_data or "graph" not in state_data: 
        return None, "Generate first.", state_data
    
    click_x, click_y = evt.index 
    width = state_data["width"]
    height = state_data["height"]
    
    norm_x = click_x / IMG_WIDTH_PX
    norm_y = click_y / IMG_HEIGHT_PX
    grid_x = int(round(norm_x * (width + 1.0) - 0.5))
    grid_y = int(round(norm_y * (height + 1.0) - 0.5))
    
    # Correction for edge cases
    if grid_x < 0: grid_x = 0
    if grid_y < 0: grid_y = 0
    if grid_x >= width: grid_x = width - 1
    if grid_y >= height: grid_y = height - 1
    
    gen = NetworkGenerator(width, height)
    gen.graph = state_data["graph"]
    
    action_msg = "Ignored"
    success = False
    highlight = None

    target_coord = (grid_x, grid_y)
    
    if click_mode == "Add/Remove Node":
        state_data["edge_start"] = None 
        if gen.graph.has_node(target_coord):
            success, action_msg = gen.manual_delete_node(*target_coord)
        else:
            success, action_msg = gen.manual_add_node(*target_coord)
            if success: highlight = target_coord
            
    elif click_mode == "Add/Remove Edge":
        if not gen.graph.has_node(target_coord):
            state_data["edge_start"] = None
            success = True
            action_msg = "Selection cleared."
        else:
            start_node = state_data.get("edge_start")
            
            if start_node is None:
                state_data["edge_start"] = target_coord
                highlight = target_coord
                success = True
                node_id = gen.get_node_id_str(target_coord)
                action_msg = f"Node {node_id} selected. Click another node to link."
            elif start_node == target_coord:
                state_data["edge_start"] = None
                success = True
                action_msg = "Selection cleared."
            else:
                success, action_msg = gen.manual_toggle_edge(start_node, target_coord)
                state_data["edge_start"] = None 

    if success:
        state_data["graph"] = gen.graph
        img_path = plot_graph_to_image(gen.graph, width, height, highlight_node=highlight)
        metrics = f"**Nodes:** {len(gen.graph.nodes())} | **Edges:** {len(gen.graph.edges())} | **Action:** {action_msg}"
        return img_path, metrics, state_data
    else:
        return gr.update(), f"⚠️ Error: {action_msg}", state_data


def get_preset_dims(preset_mode, topology):
    if preset_mode == "Custom": return gr.update(interactive=True), gr.update(interactive=True)
    dims = (6, 11) if topology=="linear" and preset_mode=="Medium" else (8,8)
    if preset_mode == "Small": dims = (4, 4)
    if preset_mode == "Large": dims = (16, 16) if topology!="linear" else (10, 26)
    return gr.update(value=dims[0], interactive=False), gr.update(value=dims[1], interactive=False)

def update_ui_for_variant(variant, width, height, topology, void_frac):
    is_custom = (variant == "Custom")
    
    # Calculate Capable Edges
    temp_gen = NetworkGenerator(width, height, "F", topology, void_frac)
    max_edges = temp_gen.calculate_max_capacity()
    
    if is_custom:
        n, e = temp_gen.calculate_defaults()
        return (gr.update(interactive=True), 
                gr.update(value=e, maximum=max_edges, interactive=True),
                f"Active Grid Capacity: ~{max_edges} edges")
    else:
        area = width*height
        val = 0.60 if area <= 20 else 0.35
        return (gr.update(value=val, interactive=False), 
                gr.update(value=0, interactive=False),
                f"Active Grid Capacity: ~{max_edges} edges")

def generate_and_store(topology, preset, width, height, variant, void_frac, t_edges):
    try:
        var_code = "F" if variant == "Fixed" else "R"
        actual_edges = 0 if variant == "Fixed" else int(t_edges)
        
        gen = NetworkGenerator(width, height, var_code, topology, void_frac, target_edges=actual_edges)
        graph = gen.generate()
        
        is_valid, val_msg = validate_topology(graph, topology)
        val_icon = "✅" if is_valid else "⚠️"
        
        status_header = "✅ **Status:** Generation Successful."
        status_detail = ""
        
        if variant == "Custom" and actual_edges > 0:
            current_edges = len(graph.edges())
            diff = current_edges - actual_edges
            
            if diff < 0:
                missing = abs(diff)
                status_header = f"⚠️ **Status:** Saturation Limit Reached (Missing {missing} Edges)"
                status_detail = (f"The generator saturated at **{current_edges} edges**. It could not place the remaining {missing} edges without crossing existing lines.\n\n"
                                 f"**Suggestion:** To fit {actual_edges} edges, please **increase the Grid Width/Height** or **decrease Void Fraction** to create more physical space.")
            elif diff > 0:
                extra = diff
                status_header = f"⚠️ **Status:** Connectivity Forced (Added {extra} Edges)"
                status_detail = (f"The target was {actual_edges}, but **{current_edges} edges** were required to keep the graph connected.\n"
                                 f"The system automatically added links to prevent isolated nodes.")
            else:
                status_header = f"✅ **Status:** Exact Target Met ({actual_edges} Edges)"
        
        img_path = plot_graph_to_image(graph, width, height)
        
        # Combined Metrics Block
        metrics = (f"**Nodes:** {len(graph.nodes())} | **Edges:** {len(graph.edges())}\n\n"
                   f"{val_icon} **Topology:** {val_msg}\n\n"
                   f"--- \n"
                   f"{status_header}\n{status_detail}")
                   
        state_data = { "graph": graph, "width": width, "height": height, "topology": topology, "edge_start": None }
        
        # --- NEW: Enable Ants Button after generation ---
        return img_path, metrics, state_data, gr.update(interactive=True), gr.update(interactive=True)
    except Exception as e:
        return None, f"Error: {e}", None, gr.update(interactive=False), gr.update(interactive=False)

def run_batch_generation(count, topology, width, height, variant, min_v, max_v, min_e, max_e):
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dir_name = f"batch_{timestamp}"
    temp_build_dir = os.path.join(ZIP_DIR, dir_name)
    os.makedirs(temp_build_dir, exist_ok=True)
    var_code = "F" if variant == "Fixed" else "R"
    
    try:
        for i in range(int(count)):
            if variant == "Custom":
                t_e = random.randint(int(min_e), int(max_e))
                current_void = random.uniform(float(min_v), float(max_v))
            else:
                t_e = 0
                current_void = min_v 
                
            gen = NetworkGenerator(width, height, var_code, topology, current_void, target_edges=t_e)
            G = gen.generate()
            
            json_content = generate_full_json_dict(G, loop=i+1)
            with open(os.path.join(temp_build_dir, f"inst_{i+1}.json"), 'w') as f:
                json.dump(json_content, f, indent=4)
        
        zip_base_name = os.path.join(ZIP_DIR, dir_name)
        zip_path = shutil.make_archive(zip_base_name, 'zip', temp_build_dir)
        shutil.rmtree(temp_build_dir) 
        
        return zip_path, gr.update(choices=get_local_zips())
    except Exception as e:
        return None, gr.update()

def save_permanent_visual(state_data):
    if not state_data or "graph" not in state_data: return "No graph to save."
    img_path = plot_graph_to_image(state_data["graph"], state_data["width"], state_data["height"], save_dir=PERM_VIS_DIR)
    return f"Saved successfully to {img_path}"

def save_single_json_action(state_data):
    if not state_data or "graph" not in state_data: return None
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_content = generate_full_json_dict(state_data["graph"], loop=1)
    fname = f"single_network_{timestamp}.json"
    with open(fname, 'w') as f:
        json.dump(json_content, f, indent=4)
    return fname

def process_uploaded_files(files):
    if not files:
        return None, "No files uploaded.", gr.update(interactive=False), gr.update(interactive=False), [], 0
    
    loaded_data = []
    for f in files:
        try:
            if f.name.endswith('.zip'):
                loaded_data.extend(extract_jsons_from_zip(f.name))
            else:
                loaded_data.append(load_graph_from_json(f.name))
        except Exception as e:
            print(f"Failed to load {f.name}: {e}")
            
    if not loaded_data:
        return None, "Failed to parse files.", gr.update(interactive=False), gr.update(interactive=False), [], 0
        
    img_path, info_text = render_loaded_graph(0, loaded_data)
    return img_path, info_text, gr.update(interactive=True), gr.update(interactive=True), loaded_data, 0

def process_local_zip_selection(zip_filename):
    if not zip_filename:
        return None, "No ZIP selected.", gr.update(interactive=False), gr.update(interactive=False), [], 0
        
    zip_path = os.path.join(ZIP_DIR, zip_filename)
    try:
        loaded_data = extract_jsons_from_zip(zip_path)
    except Exception as e:
        return None, f"Failed to read ZIP: {e}", gr.update(interactive=False), gr.update(interactive=False), [], 0
        
    if not loaded_data:
        return None, "ZIP was empty or invalid.", gr.update(interactive=False), gr.update(interactive=False), [], 0

    img_path, info_text = render_loaded_graph(0, loaded_data)
    return img_path, info_text, gr.update(interactive=True), gr.update(interactive=True), loaded_data, 0

def change_loaded_graph(direction, current_idx, loaded_data):
    if not loaded_data: 
        return None, "No data.", gr.update(), gr.update(), current_idx
    
    new_idx = current_idx + direction
    if new_idx < 0: new_idx = len(loaded_data) - 1
    if new_idx >= len(loaded_data): new_idx = 0
    
    img_path, info_text = render_loaded_graph(new_idx, loaded_data)
    return img_path, info_text, gr.update(interactive=True), gr.update(interactive=True), new_idx

def render_loaded_graph(idx, loaded_data):
    data = loaded_data[idx]
    G = data["graph"]
    w = data["width"]
    h = data["height"]
    name = data["name"]
    img_path = plot_graph_to_image(G, w, h, title=f"Loaded: {name}", save_dir=TEMP_DIR)
    info_text = f"**Viewing {idx + 1} of {len(loaded_data)}**\n\nFile: `{name}`\nNodes: {len(G.nodes())} | Edges: {len(G.edges())}"
    return img_path, info_text

# ==========================================
# GRADIO UI LAYOUT
# ==========================================
with gr.Blocks(title="Interactive Network Generator") as demo:
    state = gr.State({"edge_start": None})
    load_state = gr.State([])
    load_idx = gr.State(0)
    
    gr.Markdown("# Interactive Network Generator")
    
    with gr.Tabs():
        with gr.Tab("Generate & Edit"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### 1. Configuration")
                    topology = gr.Dropdown(["highly_connected", "bottlenecks", "linear"], value="highly_connected", label="Topology")
                    preset = gr.Radio(["Small", "Medium", "Large", "Custom"], value="Medium", label="Preset")
                    
                    with gr.Row():
                        width = gr.Number(8, label="Grid Width", interactive=False, precision=0)
                        height = gr.Number(8, label="Grid Height", interactive=False, precision=0)
                    
                    with gr.Group():
                        variant = gr.Dropdown(["Fixed", "Custom"], value="Fixed", label="Variant", info="Custom unlocks Overrides.")
                        void_frac = gr.Slider(0.0, 0.9, 0.35, step=0.05, label="Void Fraction (Controls Nodes)", interactive=False)
                        t_edges = gr.Slider(0, 800, 0, step=1, label="Target Edges (0 = Auto)", interactive=False)
                        capacity_info = gr.Markdown("Active Grid Capacity: N/A")
                    
                    gen_btn = gr.Button("Generate Network", variant="primary")
                    
                    # --- NEW: ANTS BUTTON IN UI ---
                    ants_btn = gr.Button("🐜 Release Ants (Find Route)", variant="secondary", interactive=False)
                    
                    with gr.Row():
                        save_json_btn = gr.Button("Download JSON", interactive=False)
                        save_vis_btn = gr.Button("💾 Save Visual Locally", interactive=False)
                    save_msg = gr.Markdown()
                    json_file = gr.File(label="Saved JSON", visible=False)

                with gr.Column(scale=2):
                    metrics = gr.Markdown("Ready to generate.")
                    click_mode = gr.Radio(["Add/Remove Node", "Add/Remove Edge"], value="Add/Remove Node", label="Mouse Interaction Mode",
                                          info="For Edges: Click Node 1, then Node 2. Click empty space to cancel selection.")
                    plot_img = gr.Image(label="Interactive Graph", interactive=False, height=800, width=800)

        with gr.Tab("Batch Export"):
            gr.Markdown(f"Generates multiple JSON files into a single ZIP. Automatically saves to your `{ZIP_DIR}/` directory.")
            with gr.Row():
                with gr.Column():
                    batch_count = gr.Slider(1, 50, 5, step=1, label="Generation Count")
                    with gr.Group():
                        gr.Markdown("### Range Controls (Custom Variant Only)")
                        with gr.Row():
                            b_min_void = gr.Slider(0.0, 0.9, 0.1, step=0.05, label="Min Void Fraction")
                            b_max_void = gr.Slider(0.0, 0.9, 0.6, step=0.05, label="Max Void Fraction")
                        with Row():
                            b_min_edges = gr.Number(10, label="Min Target Edges", precision=0)
                            b_max_edges = gr.Number(100, label="Max Target Edges", precision=0)
                    batch_btn = gr.Button("Generate Batch ZIP", variant="primary")
                    file_out = gr.File(label="Download ZIP")

        with gr.Tab("Load & View JSON"):
            gr.Markdown("Upload JSON/ZIP files or choose a previously generated local ZIP from the dropdown.")
            with gr.Row():
                with gr.Column(scale=1):
                    upload_files = gr.File(label="Upload JSON(s) or ZIP(s)", file_count="multiple", file_types=[".json", ".zip"])
                    gr.Markdown("---")
                    with gr.Row():
                        local_zips = gr.Dropdown(choices=get_local_zips(), label="Select a local ZIP", interactive=True)
                        refresh_zip_btn = gr.Button("🔄 Refresh List")
                    gr.Markdown("---")
                    with gr.Row():
                        btn_prev = gr.Button("⬅️ Prev", interactive=False)
                        btn_next = gr.Button("Next ➡️", interactive=False)
                    load_info = gr.Markdown("No files loaded.")
                with gr.Column(scale=2):
                    load_plot = gr.Image(label="Loaded Graph", interactive=False, height=800, width=800)

    # EVENTS
    inputs_dims = [preset, topology]
    preset.change(get_preset_dims, inputs_dims, [width, height])
    topology.change(get_preset_dims, inputs_dims, [width, height])
    
    inputs_var = [variant, width, height, topology, void_frac]
    variant.change(update_ui_for_variant, inputs_var, [void_frac, t_edges, capacity_info])
    width.change(update_ui_for_variant, inputs_var, [void_frac, t_edges, capacity_info])
    height.change(update_ui_for_variant, inputs_var, [void_frac, t_edges, capacity_info])
    topology.change(update_ui_for_variant, inputs_var, [void_frac, t_edges, capacity_info])
    void_frac.change(update_ui_for_variant, inputs_var, [void_frac, t_edges, capacity_info])

    gen_args = [topology, preset, width, height, variant, void_frac, t_edges]
    # Updated output mapping to enable the ants button
    gen_btn.click(generate_and_store, gen_args, [plot_img, metrics, state, save_json_btn, ants_btn])
    plot_img.select(handle_plot_click, [click_mode, state], [plot_img, metrics, state])

    # --- NEW: ANTS CLICK EVENT ---
    ants_btn.click(handle_release_ants, [state], [plot_img, metrics, state])

    save_json_btn.click(save_single_json_action, [state], [json_file]).then(lambda: gr.update(visible=True), None, [json_file])
    save_vis_btn.click(save_permanent_visual, [state], [save_msg])

    batch_args = [batch_count, topology, width, height, variant, b_min_void, b_max_void, b_min_edges, b_max_edges]
    batch_btn.click(run_batch_generation, batch_args, [file_out, local_zips])
    
    upload_files.upload(process_uploaded_files, [upload_files], [load_plot, load_info, btn_prev, btn_next, load_state, load_idx])
    refresh_zip_btn.click(lambda: gr.update(choices=get_local_zips()), None, [local_zips])
    local_zips.change(process_local_zip_selection, [local_zips], [load_plot, load_info, btn_prev, btn_next, load_state, load_idx])
    btn_prev.click(lambda idx, data: change_loaded_graph(-1, idx, data), [load_idx, load_state], [load_plot, load_info, btn_prev, btn_next, load_idx])
    btn_next.click(lambda idx, data: change_loaded_graph(1, idx, data), [load_idx, load_state], [load_plot, load_info, btn_prev, btn_next, load_idx])

if __name__ == "__main__":
    demo.launch()
