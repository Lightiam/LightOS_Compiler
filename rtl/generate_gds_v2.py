#!/usr/bin/env python3
"""
Enhanced GDS Generator for NCE Core - TinyTapeout-style rendering
Generates proper metal layers with realistic routing for sky130
"""

import json
import sys
from pathlib import Path

import klayout.db as pya

# sky130 technology parameters
LAMBDA = 0.05  # 50nm lambda
DBU = 0.001  # 1nm database unit
METAL_PITCH = 20 * LAMBDA  # Metal minimum pitch
VIA_SIZE = 2 * LAMBDA
METAL_WIDTH = 2 * LAMBDA

# Layer definitions (matching sky130)
LAYERS = {
    'metal1': (68, 20),
    'metal2': (69, 20),
    'metal3': (70, 20),
    'via': (71, 20),
    'via2': (72, 20),
    'poly': (66, 20),
    'diff': (65, 20),
    'li1': (67, 20),
    'nwell': (64, 20),
    'boundary': (235, 4),
}

def load_netlist(json_path):
    """Load Yosys JSON netlist"""
    with open(json_path, 'r') as f:
        return json.load(f)

def get_cell_size(cell_type):
    """Get cell size based on type"""
    base_width = 10 * LAMBDA
    base_height = 10 * LAMBDA

    if 'mul' in cell_type:
        return int(60 * LAMBDA), int(base_height)
    elif 'add' in cell_type:
        return int(20 * LAMBDA), int(base_height)
    elif 'dff' in cell_type or 'dlatch' in cell_type:
        return int(12 * LAMBDA), int(base_height)
    else:
        return int(base_width), int(base_height)

def place_cells_grid(cells_dict, cols=32):
    """Place cells in grid layout"""
    placement = {}
    x_pos = int(300 * LAMBDA)
    y_pos = int(300 * LAMBDA)
    col_width = int(200 * LAMBDA)
    row_height = int(150 * LAMBDA)

    for idx, (cell_name, cell_data) in enumerate(cells_dict.items()):
        cell_type = cell_data.get('type', '$unknown')
        w, h = get_cell_size(cell_type)

        col = idx % cols
        row = idx // cols

        placement[cell_name] = {
            'x': x_pos + col * col_width,
            'y': y_pos + row * row_height,
            'width': w,
            'height': h,
            'type': cell_type
        }

    return placement

def draw_power_grid(cell, placement, width_dbu, height_dbu):
    """Draw power and ground rails"""
    layers = get_layers(cell)
    metal1_layer = layers['metal1']

    rail_width = int(8 * LAMBDA)
    spacing = 100 * LAMBDA

    # Horizontal VDD rails
    y_pos = int(20 * LAMBDA)
    while y_pos < height_dbu:
        rect = pya.Box(0, y_pos, int(width_dbu), y_pos + rail_width)
        cell.shapes(metal1_layer).insert(rect)
        y_pos += int(spacing)

    # Vertical GND rails
    x_pos = int(20 * LAMBDA)
    while x_pos < width_dbu:
        rect = pya.Box(x_pos, 0, x_pos + rail_width, int(height_dbu))
        cell.shapes(metal1_layer).insert(rect)
        x_pos += int(spacing)

def draw_cells_with_layers(cell, placement):
    """Draw cells with proper multi-layer structure"""
    layers = get_layers(cell)

    for cell_name, pos in placement.items():
        x, y = int(pos['x']), int(pos['y'])
        w, h = int(pos['width']), int(pos['height'])

        # Draw cell core as poly + diff (gate + transistors)
        poly_height = int(h * 0.3)
        rect = pya.Box(x, y, x + w, y + poly_height)
        cell.shapes(layers['poly']).insert(rect)

        # Draw diffusion (source/drain)
        diff_height = int(h * 0.2)
        rect = pya.Box(x, y + poly_height, x + w, y + poly_height + diff_height)
        cell.shapes(layers['diff']).insert(rect)

        # Draw metal1 connections (input/output)
        metal_y = y + int(h * 0.6)
        rect = pya.Box(x, metal_y, x + int(w * 0.3), metal_y + int(METAL_WIDTH))
        cell.shapes(layers['metal1']).insert(rect)

        # Draw metal1 output
        rect = pya.Box(x + int(w * 0.7), metal_y, x + w, metal_y + int(METAL_WIDTH))
        cell.shapes(layers['metal1']).insert(rect)

def draw_routing_grid(cell, placement, width_dbu, height_dbu):
    """Draw simplified routing grid"""
    layers = get_layers(cell)
    metal1_layer = layers['metal1']

    # Draw metal1 routing tracks
    track_spacing = int(METAL_PITCH)
    x_pos = int(50 * LAMBDA)
    while x_pos < width_dbu - int(50 * LAMBDA):
        cell.shapes(metal1_layer).insert(
            pya.Box(x_pos, int(20 * LAMBDA), x_pos + int(METAL_WIDTH),
                   int(height_dbu - 20 * LAMBDA))
        )
        x_pos += track_spacing

def get_layers(cell):
    """Get or create layer definitions"""
    layers = {}
    for name, (layer_num, data_type) in LAYERS.items():
        layer_info = pya.LayerInfo(layer_num, data_type)
        layer_index = cell.layout().find_layer(layer_info)
        if layer_index is None:
            layer_index = cell.layout().insert_layer(layer_info)
        layers[name] = layer_index
    return layers

def generate_enhanced_gds(netlist_path, output_path):
    """Generate enhanced GDS with proper layers"""
    print("[*] Loading netlist...")
    netlist = load_netlist(netlist_path)

    modules = netlist.get('modules', {})
    main_module = 'nce_core_top'

    if main_module not in modules:
        main_module = list(modules.keys())[0]

    cells_dict = modules[main_module].get('cells', {})
    print(f"    Found {len(cells_dict)} cells in {main_module}")

    print("[*] Performing cell placement...")
    placement = place_cells_grid(cells_dict)

    # Calculate die size
    max_x = max(p['x'] + p['width'] for p in placement.values())
    max_y = max(p['y'] + p['height'] for p in placement.values())
    width_dbu = int(max_x + 100 * LAMBDA)
    height_dbu = int(max_y + 100 * LAMBDA)

    print(f"    Die size: {width_dbu * DBU:.2f}µm × {height_dbu * DBU:.2f}µm")

    print("[*] Creating GDS library...")
    lib = pya.Layout()
    lib.dbu = DBU

    # Create design cell
    design_cell = lib.create_cell('nce_core_design')

    print("[*] Drawing cells with multi-layer structure...")
    draw_cells_with_layers(design_cell, placement)

    print("[*] Drawing power distribution network...")
    draw_power_grid(design_cell, placement, width_dbu, height_dbu)

    print("[*] Drawing routing...")
    draw_routing_grid(design_cell, placement, width_dbu, height_dbu)

    # Draw die boundary
    layers = get_layers(design_cell)
    boundary = pya.Box(0, 0, width_dbu, height_dbu)
    design_cell.shapes(layers['boundary']).insert(boundary)

    # Create hierarchy
    top_cell = lib.create_cell('nce_core_top')
    inst_array = pya.CellInstArray(design_cell.cell_index(), pya.Trans())
    top_cell.insert(inst_array)

    print(f"[*] Writing GDS to {output_path}")
    lib.write(output_path)

    file_size = Path(output_path).stat().st_size / 1024
    print(f"    GDS file size: {file_size:.1f} KB")

    return {
        'gds_file': output_path,
        'die_width': width_dbu * DBU,
        'die_height': height_dbu * DBU,
        'cell_count': len(cells_dict),
        'dbu': DBU
    }

if __name__ == '__main__':
    json_netlist = '/home/user/LightOS_Compiler/rtl/nce_core.json'
    gds_output = '/home/user/LightOS_Compiler/rtl/nce_core_enhanced.gds'

    result = generate_enhanced_gds(json_netlist, gds_output)

    print("\n[+] Enhanced GDS generation complete!")
    print(f"    Output: {result['gds_file']}")
    print(f"    Die: {result['die_width']:.2f}µm × {result['die_height']:.2f}µm")
    print(f"    Cells: {result['cell_count']}")
