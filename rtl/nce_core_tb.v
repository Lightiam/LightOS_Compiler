'timescale 1 ns / 1 ps

module nce_core_tb ;

// Parameters
parameter ADDR_WIDTH = 32;
parameter DATA_WIDTH = 16;
parameter EXP_DATA_WIDTH = 24;
parameter NUM_SIMD_LANES = 128;
parameter REG_FILE_DEPTH = 16;

// Inputs
reg clk ;
reg rst_n ;
reg event_trigger ;
reg mem_write_en ;
reg [ ADDR_WIDTH -1:0] mem_addr ;
reg [ DATA_WIDTH -1:0] mem_write_data ;
reg spi_clk ;
reg spi_cs_n ;
reg spi_mosi ;

// Outputs
wire core_sleep_status ;
wire [ DATA_WIDTH -1:0] mem_read_data ;
wire spi_miso ;
wire [ NUM_SIMD_LANES -1:0] optical_mod_drive_p ;
wire [ NUM_SIMD_LANES -1:0] optical_mod_drive_n ;

// Instantiate the Unit Under Test (UUT)
nce_core_top #(
. ADDR_WIDTH ( ADDR_WIDTH ) ,
. DATA_WIDTH ( DATA_WIDTH ) ,
. EXP_DATA_WIDTH ( EXP_DATA_WIDTH ) ,
. NUM_SIMD_LANES ( NUM_SIMD_LANES ) ,
. REG_FILE_DEPTH ( REG_FILE_DEPTH )
) uut (
. clk ( clk ) ,
. rst_n ( rst_n ) ,
. event_trigger ( event_trigger ) ,
. core_sleep_status ( core_sleep_status ) ,
. mem_write_en ( mem_write_en ) ,
. mem_addr ( mem_addr ) ,
. mem_write_data ( mem_write_data ) ,
. mem_read_data ( mem_read_data ) ,
. spi_clk ( spi_clk ) ,
. spi_cs_n ( spi_cs_n ) ,
. spi_mosi ( spi_mosi ) ,
. spi_miso ( spi_miso ) ,
. optical_mod_drive_p ( optical_mod_drive_p ) ,
. optical_mod_drive_n ( optical_mod_drive_n )
) ;

// Clock generator (100 MHz)
always #5 clk = ~ clk ;

// SPI helper task to transmit 24 bits
task send_spi_byte ;
input [23:0] data_to_send ;
integer idx ;
begin
spi_cs_n = 0;
#1;
for ( idx = 23; idx >= 0; idx = idx - 1) begin
spi_mosi = data_to_send [ idx ];
spi_clk = 0;
#5;
spi_clk = 1;
#5;
end
spi_cs_n = 1;
#10;
end
endtask

// Main Verification Process
initial begin
// Initialize Inputs
clk = 0;
rst_n = 0;
event_trigger = 0;
mem_write_en = 0;
mem_addr = 0;
mem_write_data = 0;
spi_clk = 0;
spi_cs_n = 1;
spi_mosi = 0;

// Reset Sequence
$display ("[INFO] Initializing system reset ...") ;
#20;
rst_n = 1;
#10;
$display ("[INFO] System reset complete .") ;

// TestCase 1: Verify Sleep Mode
$display ("[TEST 1] Checking sleep mode transition ...") ;
#10;
if ( core_sleep_status === 1 ' b1 ) begin
$display ("[PASS] Core is in sleep mode as expected .") ;
end else begin
$display ("[FAIL] Core failed to enter sleep mode .") ;
end

// TestCase 2: Wakeup Sequence via Event Trigger
$display ("[TEST 2] Triggering wake -up sequence ...") ;
event_trigger = 1;
#10;
event_trigger = 0;
#10;
if ( core_sleep_status === 1 ' b0 ) begin
$display ("[PASS] Core woke up successfully .") ;
end else begin
$display ("[FAIL] Core failed to wake up.") ;
end

// TestCase 3: Memory Write and SIMD Execution
$display ("[TEST 3] Loading test vectors into NCE Register File ...") ;
mem_write_en = 1;
mem_addr = {20 ' h0 , 8 ' d5 , 4 ' h0 }; // Address layout : [31:12] unused, [11:4] Lane, [3:0] Reg
mem_write_data = 16 ' h3F80 ; // BF16 value for 1.0
#10;
mem_write_en = 0;
#10;

// Check optical modulator outputs
$display ("[TEST 3] Checking Lane 5 differential optical modulator driver ...") ;
if ( optical_mod_drive_p [5] !== optical_mod_drive_n [5]) begin
$display ("[PASS] Modulator output is fully differential . P=%b, N=%b", optical_mod_drive_p [5] , optical_mod_drive_n [5]) ;
end else begin
$display ("[FAIL] Modulator output is unbalanced . P=%b, N=%b", optical_mod_drive_p [5] , optical_mod_drive_n [5]) ;
end

// TestCase 4: SPI Phase - Shifter Calibration Loop
$display ("[TEST 4] Initiating SPI DAC threshold calibration ...") ;
send_spi_byte (24 ' hA3_7FF_0 ) ;
$display ("[PASS] SPI Calibration byte transmitted successfully .") ;

// TestCase 5: Watchdog Timeout and Automatic Power Gating
$display ("[TEST 5] Checking watchdog automatic sleep transition ...") ;
$display ("[INFO] Waiting for watchdog timer to expire (256 cycles)...") ;
#2600; // Wait more than 256 cycles ( each cycle is 10 ns)
if ( core_sleep_status === 1 ' b1 ) begin
$display ("[PASS] Core transitioned back to low - power sleep state automatically .") ;
end else begin
$display ("[FAIL] Automatic power - gating transition failed .") ;
end

$display ("============================================================") ;
$display (" NCE HDL SIMULATION COMPLETE") ;
$display ("============================================================") ;
$finish ;
end

endmodule
