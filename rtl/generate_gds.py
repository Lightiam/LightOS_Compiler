#!/usr/bin/env python3
"""
Procedural GDS Generator for NCE Core - Converts gate-level netlist to layout
Generates a simplified but realistic floor plan for sky130 technology
"""

import json
import sys
from pathlib import Path

try:
    import klayout.db as pya
except ImportError:
    print("ERROR: KLayout not found. Install with: pip install klayout")
    sys.exit(1)

# sky130 technology parameters (22nm LVT equivalent)
LAMBDA = 0.05  # 50nm lambda (0.1um = 100nm per unit)
GATE_LENGTH = 2 * LAMBDA  # 0.1um
MIN_TRACK_WIDTH = 2 * LAMBDA
MIN_PITCH = 4 * LAMBDA
CELL_HEIGHT = 100 * LAMBDA
ROW_HEIGHT = CELL_HEIGHT + 10 * LAMBDA

# Standard cell dimensions (approximate)
CELL_WIDTH = {
    # Basic gates
    '$and': 6 * LAMBDA,
    '$or': 6 * LAMBDA,
    '$xor': 8 * LAMBDA,
    '$not': 4 * LAMBDA,
    '$mux': 10 * LAMBDA,
    '$nand': 6 * LAMBDA,
    '$nor': 6 * LAMBDA,
    '$xnor': 8 * LAMBDA,
    # Arithmetic
    '$add': 20 * LAMBDA,
    '$sub': 20 * LAMBDA,
    '$mul': 60 * LAMBDA,
    '$div': 80 * LAMBDA,
    # Comparison
    '$eq': 15 * LAMBDA,
    '$ne': 15 * LAMBDA,
    '$gt': 15 * LAMBDA,
    '$ge': 15 * LAMBDA,
    '$lt': 15 * LAMBDA,
    '$le': 15 * LAMBDA,
    # Logic reduction
    '$reduce_and': 8 * LAMBDA,
    '$reduce_or': 8 * LAMBDA,
    '$reduce_xor': 8 * LAMBDA,
    '$reduce_bool': 4 * LAMBDA,
    # Multiplexer
    '$logic_and': 6 * LAMBDA,
    '$logic_or': 6 * LAMBDA,
    '$logic_not': 4 * LAMBDA,
    # Flip-flops
    '$dff': 10 * LAMBDA,
    '$dffe': 12 * LAMBDA,
    '$adff': 12 * LAMBDA,
    '$adffe': 14 * LAMBDA,
    '$dlatch': 8 * LAMBDA,
}

def get_cell_width(cell_type):
    """Get approximate cell width based on cell type"""
    return CELL_WIDTH.get(cell_type, 8 * LAMBDA)

def load_netlist(json_path):
    """Load Yosys JSON netlist"""
    with open(json_path, 'r') as f:
        return json.load(f)

def extract_design_info(netlist):
    """Extract design info from netlist"""
    modules = netlist.get('modules', {})
    design_info = {
        'modules': {},
        'total_cells': 0,
        'total_area': 0
    }

    for module_name, module_data in modules.items():
        cells = module_data.get('cells', {})
        design_info['modules'][module_name] = {
            'cell_count': len(cells),
            'cells': list(cells.items())
        }
        design_info['total_cells'] += len(cells)

    return design_info

def place_cells(cells_dict, cell_height=CELL_HEIGHT, row_height=ROW_HEIGHT):
    """Place cells in rows using simple left-to-right, top-to-bottom strategy"""
    placement = {}
    x_pos = 20 * LAMBDA
    y_pos = 20 * LAMBDA
    row_width = 500 * LAMBDA  # Max row width
    row_cells_width = 0

    for cell_name, cell_data in cells_dict.items():
        cell_type = cell_data.get('type', '$unknown')
        cell_width = get_cell_width(cell_type.lstrip('$'))

        # Check if cell fits in current row
        if row_cells_width + cell_width > row_width:
            # Start new row
            y_pos += row_height
            x_pos = 20 * LAMBDA
            row_cells_width = 0

        placement[cell_name] = {
            'x': x_pos,
            'y': y_pos,
            'width': cell_width,
            'height': cell_height,
            'type': cell_type
        }

        x_pos += cell_width + 5 * LAMBDA
        row_cells_width += cell_width + 5 * LAMBDA

    return placement

def calculate_die_size(placement):
    """Calculate die dimensions from placement"""
    if not placement:
        return 0, 0

    max_x = max(p['x'] + p['width'] for p in placement.values())
    max_y = max(p['y'] + p['height'] for p in placement.values())

    # Add margins
    die_width = max_x + 50 * LAMBDA
    die_height = max_y + 50 * LAMBDA

    return die_width, die_height

def create_gds_cell(lib, cell_name, placement, cell_types_map):
    """Create a GDS cell with placed components"""
    cell = lib.create_cell(cell_name)

    # Define layers (sky130 equivalent)
    layer_nwell = pya.LayerInfo(64, 20)
    layer_nmos = pya.LayerInfo(65, 20)
    layer_pmos = pya.LayerInfo(64, 20)
    layer_poly = pya.LayerInfo(66, 20)
    layer_contact = pya.LayerInfo(67, 20)
    layer_metal1 = pya.LayerInfo(68, 20)
    layer_metal2 = pya.LayerInfo(69, 20)
    layer_via = pya.LayerInfo(70, 20)

    # Get layers
    nwell_layer = cell.layout().find_layer(layer_nwell)
    if nwell_layer is None:
        nwell_layer = cell.layout().insert_layer(layer_nwell)

    metal1_layer = cell.layout().find_layer(layer_metal1)
    if metal1_layer is None:
        metal1_layer = cell.layout().insert_layer(layer_metal1)

    metal2_layer = cell.layout().find_layer(layer_metal2)
    if metal2_layer is None:
        metal2_layer = cell.layout().insert_layer(layer_metal2)

    # Draw placed cells
    for cell_name, cell_data in cell_types_map.items():
        if cell_name not in placement:
            continue

        pos = placement[cell_name]
        x, y = int(pos['x']), int(pos['y'])
        w, h = int(pos['width']), int(pos['height'])

        # Draw cell as a rectangle with label
        rect = pya.Box(x, y, x + w, y + h)
        cell.shapes(metal1_layer).insert(rect)

        # Add text label
        text = pya.Text(cell_name, x, y)
        cell.shapes(metal1_layer).insert(text)

    return cell

def draw_floorplan(lib, cell_name, die_width, die_height):
    """Create die boundary and core area"""
    cell = lib.create_cell(f"{cell_name}_fp")

    layer_boundary = pya.LayerInfo(235, 4)
    layer_core = pya.LayerInfo(235, 5)

    boundary_layer = cell.layout().find_layer(layer_boundary)
    if boundary_layer is None:
        boundary_layer = cell.layout().insert_layer(layer_boundary)

    core_layer = cell.layout().find_layer(layer_core)
    if core_layer is None:
        core_layer = cell.layout().insert_layer(layer_core)

    # Die boundary
    die_box = pya.Box(0, 0, int(die_width), int(die_height))
    cell.shapes(boundary_layer).insert(die_box)

    # Core area (with margin)
    margin = 50 * LAMBDA
    core_box = pya.Box(int(margin), int(margin),
                       int(die_width - margin), int(die_height - margin))
    cell.shapes(core_layer).insert(core_box)

    return cell

def generate_gds(netlist_path, output_gds_path):
    """Main GDS generation flow"""
    print(f"[*] Loading netlist from {netlist_path}")
    netlist = load_netlist(netlist_path)

    print("[*] Extracting design information")
    design_info = extract_design_info(netlist)
    print(f"    Total cells: {design_info['total_cells']}")

    # Get main module (nce_core_top)
    main_module = 'nce_core_top'
    if main_module not in design_info['modules']:
        main_module = list(design_info['modules'].keys())[0]
        print(f"    Using module: {main_module}")

    cells_list = design_info['modules'][main_module]['cells']

    print("[*] Performing cell placement")
    # Convert cells_list to dict for place_cells
    cells_dict = dict(cells_list)
    placement = place_cells(cells_dict)

    die_width, die_height = calculate_die_size(placement)
    print(f"    Die size: {die_width/LAMBDA:.1f} x {die_height/LAMBDA:.1f} lambda")
    print(f"    Die size: {die_width/5:.2f} x {die_height/5:.2f} um")

    print("[*] Creating GDS library")
    lib = pya.Layout()
    lib.dbu = 0.001  # 1nm database unit

    # Create design cell with placement
    design_cell = create_gds_cell(lib, 'nce_core_layout', placement, cells_dict)

    # Create floorplan cell
    floorplan_cell = draw_floorplan(lib, 'nce_core', die_width, die_height)

    # Create top cell
    top_cell = lib.create_cell('nce_core_top')
    inst = pya.CellInstArray(design_cell.cell_index(), pya.Trans())
    top_cell.insert(inst)

    print(f"[*] Writing GDS to {output_gds_path}")
    lib.write(output_gds_path)

    file_size = Path(output_gds_path).stat().st_size / 1024
    print(f"    GDS file size: {file_size:.1f} KB")

    return {
        'gds_file': output_gds_path,
        'die_width': die_width,
        'die_height': die_height,
        'cell_count': design_info['total_cells'],
        'dbu': lib.dbu
    }

if __name__ == '__main__':
    json_netlist = '/home/user/LightOS_Compiler/rtl/nce_core.json'
    gds_output = '/home/user/LightOS_Compiler/rtl/nce_core.gds'

    result = generate_gds(json_netlist, gds_output)

    print("\n[+] GDS generation complete!")
    print(f"    Output: {result['gds_file']}")
    print(f"    Die dimensions: {result['die_width']/5:.2f}um x {result['die_height']/5:.2f}um")
    print(f"    Cell count: {result['cell_count']}")
