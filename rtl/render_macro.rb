
require 'klayout/db'

layout = RBA::Layout.new
layout.read('/home/user/LightOS_Compiler/rtl/nce_core_enhanced.gds')

# Create a view for rendering
view = RBA::LayoutView.new
view.load_layout(layout, false)

# Apply layer properties if available
if File.exist?('/home/user/LightOS_Compiler/rtl/sky130_render.lyp')
  view.load_layer_properties('/home/user/LightOS_Compiler/rtl/sky130_render.lyp')
end

# Fit view
view.zoom_fit

# Export to PNG
view.save_as('/home/user/LightOS_Compiler/rtl/nce_core_tinytapeout.png')
