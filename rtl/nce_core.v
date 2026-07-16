// LightRail AI Neural Compute Engine (NCE) Core - Synthesizable RTL
// Revision 6.3 (Tape-out Ready)

`timescale 1ns/1ps

module nce_core_top #(
  parameter ADDR_WIDTH = 32,
  parameter DATA_WIDTH = 16,
  parameter EXP_DATA_WIDTH = 24,
  parameter NUM_SIMD_LANES = 128,
  parameter REG_FILE_DEPTH = 16
) (
  input wire clk,
  input wire rst_n,
  input wire event_trigger,
  output wire core_sleep_status,
  input wire mem_write_en,
  input wire [ADDR_WIDTH-1:0] mem_addr,
  input wire [DATA_WIDTH-1:0] mem_write_data,
  output reg [DATA_WIDTH-1:0] mem_read_data,
  input wire spi_clk,
  input wire spi_cs_n,
  input wire spi_mosi,
  output wire spi_miso,
  output wire [NUM_SIMD_LANES-1:0] optical_mod_drive_p,
  output wire [NUM_SIMD_LANES-1:0] optical_mod_drive_n
);

wire gated_clk;
wire compute_active;

spiking_dispatcher u_dispatcher (
  .clk(clk),
  .rst_n(rst_n),
  .event_trigger(event_trigger),
  .compute_active(compute_active),
  .gated_clk(gated_clk),
  .sleep_status(core_sleep_status)
);

reg [DATA_WIDTH-1:0] vector_registers [REG_FILE_DEPTH-1:0][NUM_SIMD_LANES-1:0];
reg [EXP_DATA_WIDTH-1:0] matrix_registers [REG_FILE_DEPTH-1:0][NUM_SIMD_LANES-1:0];

integer r, l;

always @(posedge gated_clk or negedge rst_n) begin
  if (!rst_n) begin
    for (r = 0; r < REG_FILE_DEPTH; r = r + 1) begin
      for (l = 0; l < NUM_SIMD_LANES; l = l + 1) begin
        vector_registers[r][l] <= {DATA_WIDTH{1'b0}};
        matrix_registers[r][l] <= {EXP_DATA_WIDTH{1'b0}};
      end
    end
  end else if (mem_write_en && compute_active) begin
    if (mem_addr[4]) begin
      vector_registers[mem_addr[3:0]][mem_addr[11:4]] <= mem_write_data;
    end else begin
      matrix_registers[mem_addr[3:0]][mem_addr[11:4]] <= {mem_write_data, 8'h00};
    end
  end
end

wire [DATA_WIDTH-1:0] simd_operand_a [NUM_SIMD_LANES-1:0];
wire [EXP_DATA_WIDTH-1:0] simd_operand_b [NUM_SIMD_LANES-1:0];
wire [DATA_WIDTH-1:0] simd_result [NUM_SIMD_LANES-1:0];

genvar lane_idx;
generate
  for (lane_idx = 0; lane_idx < NUM_SIMD_LANES; lane_idx = lane_idx + 1) begin : simd_lanes
    assign simd_operand_a[lane_idx] = vector_registers[4'h0][lane_idx];
    assign simd_operand_b[lane_idx] = matrix_registers[4'h0][lane_idx];

    simd_lane u_simd_lane (
      .clk(gated_clk),
      .rst_n(rst_n),
      .operand_a(simd_operand_a[lane_idx]),
      .operand_b(simd_operand_b[lane_idx]),
      .result(simd_result[lane_idx]),
      .mod_out_p(optical_mod_drive_p[lane_idx]),
      .mod_out_n(optical_mod_drive_n[lane_idx])
    );
  end
endgenerate

endmodule

module spiking_dispatcher (
  input wire clk,
  input wire rst_n,
  input wire event_trigger,
  output reg compute_active,
  output wire gated_clk,
  output wire sleep_status
);

reg [7:0] watchdog_counter;
reg clk_gate_en;

always @(posedge clk or negedge rst_n) begin
  if (!rst_n) begin
    compute_active <= 1'b0;
    watchdog_counter <= 8'h00;
    clk_gate_en <= 1'b1;
  end else begin
    if (event_trigger) begin
      compute_active <= 1'b1;
      clk_gate_en <= 1'b1;
      watchdog_counter <= 8'hFF;
    end else if (watchdog_counter > 0) begin
      watchdog_counter <= watchdog_counter - 1'b1;
    end else begin
      compute_active <= 1'b0;
      clk_gate_en <= 1'b0;
    end
  end
end

reg latch_out;
always @(clk or clk_gate_en) begin
  if (!clk) begin
    latch_out <= clk_gate_en;
  end
end

assign gated_clk = clk & latch_out;
assign sleep_status = ~compute_active;

endmodule

module simd_lane (
  input wire clk,
  input wire rst_n,
  input wire [15:0] operand_a,
  input wire [23:0] operand_b,
  output reg [15:0] result,
  output reg mod_out_p,
  output reg mod_out_n
);

reg [39:0] product_accumulator;

always @(posedge clk or negedge rst_n) begin
  if (!rst_n) begin
    product_accumulator <= 40'h0000000000;
    result <= 16'h0000;
    mod_out_p <= 1'b0;
    mod_out_n <= 1'b1;
  end else begin
    product_accumulator <= (operand_a * operand_b[23:8]) + product_accumulator;
    result <= product_accumulator[31:16];
    mod_out_p <= product_accumulator[15];
    mod_out_n <= ~product_accumulator[15];
  end
end

endmodule
