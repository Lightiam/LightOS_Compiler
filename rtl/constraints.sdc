# LightRail AI NCE Core Synthesis Constraints
# Target: 22nm LVT Process (1.4 GHz operation)
# Version: Revision 6.3 (Tape-out Ready)

# Define master logic clock at 1.4 GHz on a 22 nm LVT process library
create_clock -name sys_clk -period 0.714 [get_ports clk]

# Constrain gated clock latency limits separately to prevent phase skew
set_clock_latency -source -max 0.150 [get_clocks gated_clk]
set_clock_uncertainty -setup 0.015 [get_clocks gated_clk]

# Add input/output delay constraints for external interfaces
set_input_delay -clock sys_clk -max 0.100 [get_ports event_trigger]
set_input_delay -clock sys_clk -max 0.100 [get_ports mem_write_en]
set_input_delay -clock sys_clk -max 0.100 [get_ports mem_addr]
set_input_delay -clock sys_clk -max 0.100 [get_ports mem_write_data]

set_output_delay -clock sys_clk -max 0.150 [get_ports optical_mod_drive_p]
set_output_delay -clock sys_clk -max 0.150 [get_ports optical_mod_drive_n]
set_output_delay -clock sys_clk -max 0.100 [get_ports core_sleep_status]

# SPI clock domain (separate from core clock)
create_clock -name spi_clk -period 20.0 [get_ports spi_clk]
set_clock_latency -source -max 0.050 [get_clocks spi_clk]

# Clock domain crossing: SPI to core domain
set_false_path -from [get_clocks spi_clk] -to [get_clocks sys_clk]
set_false_path -from [get_clocks sys_clk] -to [get_clocks spi_clk]

# Area and power optimization directives
set_max_dynamic_power 10.0W
set_max_static_power 2.5W

# Clock tree skew constraint (critical for 128-way SIMD)
set_max_skew -clock sys_clk 0.015
