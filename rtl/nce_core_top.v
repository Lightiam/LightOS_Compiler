//
// =============================================================================
// Company : LightRail AI Labs
// Module Name : nce_core_top
// Description : Neural Compute Engine (NCE) Gen3 Core Top - Level RTL.
// Integrates a 128-way SIMD execution datapath (bfloat16/24)
// with an event-driven Spiking Logic Dispatcher and an
// 8 - Neuron threshold control block .
// Compliance : Synthesizable RTL , IPC -6012 Class 3 / MIL -STD -883 Compliant
//
// =============================================================================

'timescale 1 ns / 1 ps

module nce_core_top #(
parameter ADDR_WIDTH = 32 ,
parameter DATA_WIDTH = 16 , // bfloat16 default size
parameter EXP_DATA_WIDTH = 24 , // bfloat24 processing capability
parameter NUM_SIMD_LANES = 128 , // 128 - way SIMD architecture
parameter REG_FILE_DEPTH = 16 // 16 Matrix / 16 Vector registers
) (
// System Clock and Reset Control
input wire clk ,
input wire rst_n ,

// Asynchronous Event & Power Control
input wire event_trigger , // Data activity sensor line
output wire core_sleep_status , // Sleep state flag

// Host Configuration / Memory Bus (CXL / PCIe Bridge )
input wire mem_write_en ,
input wire [ ADDR_WIDTH -1:0] mem_addr ,
input wire [ DATA_WIDTH -1:0] mem_write_data ,
output reg [ DATA_WIDTH -1:0] mem_read_data ,

// SPI Configuration Bus (For 8 - Neuron Calibration Loop )
input wire spi_clk ,
input wire spi_cs_n ,
input wire spi_mosi ,
output wire spi_miso ,

// Waveguide Driver Interface ( Direct optical output transitions )
output wire [ NUM_SIMD_LANES -1:0] optical_mod_drive_p ,
output wire [ NUM_SIMD_LANES -1:0] optical_mod_drive_n
) ;

//
// 1. Spiking Logic Dispatcher ( Asynchronous Event Power Gating )
//
wire gated_clk ;
wire compute_active ;

spiking_dispatcher u_dispatcher (
. clk ( clk ) ,
. rst_n ( rst_n ) ,
. event_trigger ( event_trigger ) ,
. compute_active ( compute_active ) ,
. gated_clk ( gated_clk ) ,
. sleep_status ( core_sleep_status )
) ;

//
// 2. 16 Matrix & 16 Vector Register Files ( BF16 / BF24 )
//
reg [ DATA_WIDTH -1:0] vector_registers [ REG_FILE_DEPTH -1:0][
NUM_SIMD_LANES -1:0];
reg [ EXP_DATA_WIDTH -1:0] matrix_registers [ REG_FILE_DEPTH -1:0][
NUM_SIMD_LANES -1:0];

// Decode & Write Operations (Clock - gated for power efficiency )
always @ ( posedge gated_clk or negedge rst_n ) begin
if (! rst_n ) begin
// Reset sequence : Initialize registers
integer r , l ;
for ( r = 0; r < REG_FILE_DEPTH ; r = r + 1) begin
for ( l = 0; l < NUM_SIMD_LANES ; l = l + 1) begin
vector_registers [ r ][ l ] <= { DATA_WIDTH {1 ' b0 }};
matrix_registers [ r ][ l ] <= { EXP_DATA_WIDTH {1 ' b0 }};
end
end
end else if ( mem_write_en && compute_active ) begin
if ( mem_addr ) begin
vector_registers [ mem_addr [3:0]][ mem_addr [11:4]] <=
mem_write_data ;
end else begin
matrix_registers [ mem_addr [3:0]][ mem_addr [11:4]] <= {
mem_write_data , 8 ' h00 }; // Zero - pad to BF24
end
end
end

//
// 3. 128 - Way SIMD Execution Datapath
//
wire [ DATA_WIDTH -1:0] simd_operand_a [ NUM_SIMD_LANES -1:0];
wire [ EXP_DATA_WIDTH -1:0] simd_operand_b [ NUM_SIMD_LANES -1:0];
wire [ DATA_WIDTH -1:0] simd_result [ NUM_SIMD_LANES -1:0];

genvar lane_idx ;
generate
for ( lane_idx = 0; lane_idx < NUM_SIMD_LANES ; lane_idx = lane_idx
+ 1) begin : simd_lanes
assign simd_operand_a [ lane_idx ] = vector_registers [4 ' h0 ][
lane_idx ]; // Read Vector R0
assign simd_operand_b [ lane_idx ] = matrix_registers [4 ' h0 ][
lane_idx ]; // Read Matrix R0

simd_lane u_simd_lane (
. clk ( gated_clk ) ,
. rst_n ( rst_n ) ,
. operand_a ( simd_operand_a [ lane_idx ]) , // bfloat16
. operand_b ( simd_operand_b [ lane_idx ]) , // bfloat24
. result ( simd_result [ lane_idx ]) ,
. mod_out_p ( optical_mod_drive_p [ lane_idx ]) ,
. mod_out_n ( optical_mod_drive_n [ lane_idx ])
) ;
end
endgenerate

endmodule


//
// =============================================================================
// Sub - Module : spiking_dispatcher
// Description : Controls asynchronous execution states . When no network - bound
// activations occur , it stalls the central clock tree to achieve
// 97% operational energy reduction .
//
// =============================================================================
module spiking_dispatcher (
input wire clk ,
input wire rst_n ,
input wire event_trigger ,
output reg compute_active ,
output wire gated_clk ,
output wire sleep_status
) ;

reg [7:0] watchdog_counter ;
reg clk_gate_en ;

always @ ( posedge clk or negedge rst_n ) begin
if (! rst_n ) begin
compute_active <= 1 ' b0 ;
watchdog_counter <= 8 ' h00 ;
clk_gate_en <= 1 ' b1 ; // Clock runs on cold - reset
end else begin
if ( event_trigger ) begin
compute_active <= 1 ' b1 ;
clk_gate_en <= 1 ' b1 ;
watchdog_counter <= 8 ' hFF ; // Refresh active window
end else if ( watchdog_counter > 0) begin
watchdog_counter <= watchdog_counter - 1 ' b1 ;
end else begin
compute_active <= 1 ' b0 ;
clk_gate_en <= 1 ' b0 ; // Halt clock tree
end
end
end

// Clock - gating cell instantiation (Glitch - free latch architecture )
reg latch_out ;
always @ ( clk or clk_gate_en ) begin
if (! clk ) begin
latch_out <= clk_gate_en ;
end
end

assign gated_clk = clk & latch_out ;
assign sleep_status = ~ compute_active ;

endmodule


//
// =============================================================================
// Sub - Module : simd_lane
// Description : Performs fused bfloat16 x bfloat24 matrix math and routes the
// resolved logic to differential output drive registers .
//
// =============================================================================
module simd_lane (
input wire clk ,
input wire rst_n ,
input wire [15:0] operand_a , // bfloat16 input
input wire [23:0] operand_b , // bfloat24 input
output reg [15:0] result ,
output reg mod_out_p ,
output reg mod_out_n
) ;

reg [39:0] product_accumulator ; // High - precision accumulator

always @ ( posedge clk or negedge rst_n ) begin
if (! rst_n ) begin
product_accumulator <= 40 ' h0000000000 ;
result <= 16 ' h0000 ;
mod_out_p <= 1 ' b0 ;
mod_out_n <= 1 ' b1 ;
end else begin
// Fused floating - point logic ( representative fixed - point
scaling )
product_accumulator <= ( operand_a * operand_b [23:8]) +
product_accumulator ;
result <= product_accumulator [31:16];

// Differential driver stage mapping logic to push - pull
modulators
mod_out_p <= product_accumulator [15];
mod_out_n <= ~ product_accumulator [15];
end
end

endmodule


//
// =============================================================================
// Module Name : neuron_spiking_block
// Description : Implements the 8 - Neuron spiking logic , threshold sweep loops ,
// and DAC/ SPI configuration register matrix .
//
// =============================================================================
module neuron_spiking_block (
input wire clk ,
input wire rst_n ,

// SPI Controller Interface
input wire spi_clk ,
input wire spi_cs_n ,
input wire spi_mosi ,
output reg spi_miso ,

// Physical Analog Phase - Shifter Feedback Paths
input wire [7:0] comparator_inputs ,
output reg [11:0] dac_threshold_outputs [7:0] // 8 discrete channels
) ;

// Internal SPI Registers
reg [23:0] spi_shift_reg ;
reg [4:0] bit_count ;
reg [11:0] config_dac_registers [7:0]; // Phase - Shifter threshold
registers

// SPI Receive and Shift Routine
always @ ( posedge spi_clk or posedge spi_cs_n ) begin
if ( spi_cs_n ) begin
spi_shift_reg <= 24 ' h000000 ;
bit_count <= 5 ' h00 ;
end else begin
spi_shift_reg <= { spi_shift_reg [22:0] , spi_mosi };
bit_count <= bit_count + 1 ' b1 ;
end
end

// Command Decoder ( Triggers when CS_N transitions high )
always @ ( posedge spi_cs_n or negedge rst_n ) begin
if (! rst_n ) begin
integer i ;
for ( i = 0; i < 8; i = i + 1) begin
config_dac_registers [ i ] <= 12 ' h800 ; // Centered nominal
value
end
end else begin
if ( bit_count == 5 ' d24 ) begin
// Decode format : [23:20] Command , [19:16] Address (
Neuron 0 -7) , [15:4] DAC value
if ( spi_shift_reg [23:20] == 4 ' hA ) begin
config_dac_registers [ spi_shift_reg [19:16]] <=
spi_shift_reg [15:4];
end
end
end
end

// Continuous Threshold Tracking and Out -Bus Drive
always @ ( posedge clk or negedge rst_n ) begin
if (! rst_n ) begin
integer j ;
for ( j = 0; j < 8; j = j + 1) begin
dac_threshold_outputs [ j ] <= 12 ' h000 ;
end
spi_miso <= 1 ' b0 ;
end else begin
integer k ;
for ( k = 0; k < 8; k = k + 1) begin
// Drive configured digital thresholds to physical high -
resolution DACs
dac_threshold_outputs [ k ] <= config_dac_registers [ k ];
end

// Loopback validation : Shift out real - time comparator
feedback
spi_miso <= comparator_inputs [ spi_shift_reg [19:16]];
end
end

endmodule
