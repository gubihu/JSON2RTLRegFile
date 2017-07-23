libraries = '''library IEEE;
use ieee.std_logic_1164.all;
'''
entity_header = '''
entity axilite_reg_if is
  generic (
    C_S_AXI_DATA_WIDTH : integer := {};
    C_S_AXI_ADDR_WIDTH : integer := {}
    );
  port (
'''
st_in = '    {name:{pad}} : in  std_logic;\n'
st_out = '    {name:{pad}} : out std_logic;\n'
sv_in = '    {name:{pad}} : in  std_logic_vector({width} downto 0);\n'
sv_out = '    {name:{pad}} : out std_logic_vector({width} downto 0);\n'
clock_comment = '    -- Clocks\n'
pl_port_comment = '    -- PL Ports\n'
axi_ports_end = '''    -- AXILite Signal
    s_axi_aclk    {spaces}: in  std_logic;
    s_axi_areset  {spaces}: in  std_logic;
    s_axi_awaddr  {spaces}: in  std_logic_vector(C_S_AXI_ADDR_WIDTH-1 downto 0);
    s_axi_awprot  {spaces}: in  std_logic_vector(2 downto 0);
    s_axi_awvalid {spaces}: in  std_logic;
    s_axi_awready {spaces}: out std_logic;
    s_axi_wdata   {spaces}: in  std_logic_vector(C_S_AXI_DATA_WIDTH-1 downto 0);
    s_axi_wstrb   {spaces}: in  std_logic_vector((C_S_AXI_DATA_WIDTH/8)-1 downto 0);
    s_axi_wvalid  {spaces}: in  std_logic;
    s_axi_wready  {spaces}: out std_logic;
    s_axi_bresp   {spaces}: out std_logic_vector(1 downto 0);
    s_axi_bvalid  {spaces}: out std_logic;
    s_axi_bready  {spaces}: in  std_logic;
    s_axi_araddr  {spaces}: in  std_logic_vector(C_S_AXI_ADDR_WIDTH-1 downto 0);
    s_axi_arprot  {spaces}: in  std_logic_vector(2 downto 0);
    s_axi_arvalid {spaces}: in  std_logic;
    s_axi_arready {spaces}: out std_logic;
    s_axi_rdata   {spaces}: out std_logic_vector(C_S_AXI_DATA_WIDTH-1 downto 0);
    s_axi_rresp   {spaces}: out std_logic_vector(1 downto 0);
    s_axi_rvalid  {spaces}: out std_logic;
    s_axi_rready  {spaces}: in  std_logic
    );
end entity axilite_reg_if;

architecture arch_imp of axilite_reg_if is
'''.format

components = '''
  component cdc_sync
    generic (
      WIDTH      : natural := 1;
      WITH_VLD   : boolean := false;
      SRC_PER_NS : real    := 5.0;
      DST_PER_NS : real    := 8.0;
      DAT_IS_REG : boolean := true;
      IS_PULSE   : boolean := false
      );
    port (
      src_clk : in  std_logic;
      src_dat : in  std_logic_vector (WIDTH-1 downto 0);
      src_vld : in  std_logic;
      dst_clk : in  std_logic;
      dst_dat : out std_logic_vector (WIDTH-1 downto 0);
      dst_vld : out std_logic
      );
  end component cdc_sync;
'''

constants = '''
  constant ADDR_LSB          : integer := (C_S_AXI_DATA_WIDTH/32)+ 1;
  constant OPT_MEM_ADDR_BITS : integer := {};
'''

internal_signals = '''
  -- AXI4LITE signals
  signal axi_awaddr  : std_logic_vector(C_S_AXI_ADDR_WIDTH-1 downto 0) := (others => '0');
  signal axi_awready : std_logic := '0';
  signal axi_wready  : std_logic := '0';
  signal axi_bresp   : std_logic_vector(1 downto 0) := (others => '0');
  signal axi_bvalid  : std_logic := '0';
  signal axi_araddr  : std_logic_vector(C_S_AXI_ADDR_WIDTH-1 downto 0) := (others => '0');
  signal axi_arready : std_logic := '0';
  signal axi_rdata   : std_logic_vector(C_S_AXI_DATA_WIDTH-1 downto 0) := (others => '0');
  signal axi_rresp   : std_logic_vector(1 downto 0) := (others => '0');
  signal axi_rvalid  : std_logic := '0';

  signal slv_reg_rden : std_logic := '0';
  signal slv_reg_wren : std_logic := '0';
  signal reg_data_out : std_logic_vector(C_S_AXI_DATA_WIDTH-1 downto 0) := (others => '0');

'''

signal_sv = '  signal {name:{pad}} : std_logic_vector({width} downto 0) := (others => \'0\');\n'
signal_st = '  signal {name:{pad}} : std_logic := \'0\';\n'
reg_signal = '  signal slv_reg{num}{pad} : std_logic_vector(C_S_AXI_DATA_WIDTH-1 downto 0) := (others => \'0\');\n'

begin_io_assgns_axi_logic = '''
begin

  -- I/O Connections assignments
  s_axi_awready <= axi_awready;
  s_axi_wready  <= axi_wready;
  s_axi_bresp   <= axi_bresp;
  s_axi_bvalid  <= axi_bvalid;
  s_axi_arready <= axi_arready;
  s_axi_rdata   <= axi_rdata;
  s_axi_rresp   <= axi_rresp;
  s_axi_rvalid  <= axi_rvalid;

  -- Implement axi_awready generation
  -- axi_awready is asserted for one s_axi_aclk clock cycle when both
  -- s_axi_awvalid and s_axi_wvalid are asserted. axi_awready is
  -- de-asserted when reset is low.

  process (s_axi_aclk)
  begin
    if rising_edge(s_axi_aclk) then
      if s_axi_areset = '1' then
        axi_awready <= '0';
      else
        if axi_awready = '0' and s_axi_awvalid = '1' and s_axi_wvalid = '1' then
          -- slave is ready to accept write address when
          -- there is a valid write address and write data
          -- on the write address and data bus. This design
          -- expects no outstanding transactions.
          axi_awready <= '1';
        else
          axi_awready <= '0';
        end if;
      end if;
    end if;
  end process;

  -- Implement axi_awaddr latching
  -- This process is used to latch the address when both
  -- s_axi_awvalid and s_axi_wvalid are valid.

  process (s_axi_aclk)
  begin
    if rising_edge(s_axi_aclk) then
      if s_axi_areset = '1' then
        axi_awaddr <= (others => '0');
      else
        if axi_awready = '0' and s_axi_awvalid = '1' and s_axi_wvalid = '1' then
          -- Write Address latching
          axi_awaddr <= s_axi_awaddr;
        end if;
      end if;
    end if;
  end process;

  -- Implement axi_wready generation
  -- axi_wready is asserted for one s_axi_aclk clock cycle when both
  -- s_axi_awvalid and s_axi_wvalid are asserted. axi_wready is
  -- de-asserted when reset is low.

  process (s_axi_aclk)
  begin
    if rising_edge(s_axi_aclk) then
      if s_axi_areset = '1' then
        axi_wready <= '0';
      else
        if axi_wready = '0' and s_axi_wvalid = '1' and s_axi_awvalid = '1' then
          -- slave is ready to accept write data when
          -- there is a valid write address and write data
          -- on the write address and data bus. This design
          -- expects no outstanding transactions.
          axi_wready <= '1';
        else
          axi_wready <= '0';
        end if;
      end if;
    end if;
  end process;

  -- Implement memory mapped register select and write logic generation
  -- The write data is accepted and written to memory mapped registers when
  -- axi_awready, s_axi_wvalid, axi_wready and s_axi_wvalid are asserted. Write strobes are used to
  -- select byte enables of slave registers while writing.
  -- These registers are cleared when reset (active low) is applied.
  -- Slave register write enable is asserted when valid address and data are available
  -- and the slave is ready to accept the write address and write data.
  slv_reg_wren <= axi_wready and s_axi_wvalid and axi_awready and s_axi_awvalid;
'''

axi_write_header = '''
  process (s_axi_aclk)
    variable loc_addr : std_logic_vector(OPT_MEM_ADDR_BITS downto 0);
  begin
    if rising_edge(s_axi_aclk) then
      if s_axi_areset = '1' then'''
axi_write_reset_reg = '\n'+'  '*4+'slv_reg{} <= (others => \'0\');'
axi_write_else_header = '''
      else
        loc_addr := axi_awaddr(ADDR_LSB + OPT_MEM_ADDR_BITS downto ADDR_LSB);
        if slv_reg_wren = '1' then'''
axi_write_assign = '''
          if loc_addr = b"{val}" then
            for i in 0 to (C_S_AXI_DATA_WIDTH/8-1) loop
              if s_axi_wstrb(i) = '1' then
                slv_reg{num}(i*8+7 downto i*8) <= s_axi_wdata(i*8+7 downto i*8);
              end if;
            end loop;'''
axi_write_assign_else = '\n          else'
axi_write_assign_end = '\n          end if;'
axi_write_else = '\n        else'
axi_sclr_part1 = ''
axi_sclr_part2 = ' & '
axi_sclr_part3 = '({} downto {})'
axi_sclr_part4 = '"{val}"'
axi_sclr_part5 = ';'
axi_write_footer = '''
        end if;
      end if;
    end if;
  end process;
'''
axi_logic2 = '''
  -- Implement write response logic generation
  -- The write response and response valid signals are asserted by the slave
  -- when axi_wready, s_axi_wvalid, axi_wready and s_axi_wvalid are asserted.
  -- This marks the acceptance of address and indicates the status of
  -- write transaction.

  process (s_axi_aclk)
  begin
    if rising_edge(s_axi_aclk) then
      if s_axi_areset = '1' then
        axi_bvalid <= '0';
        axi_bresp  <= "00";             --need to work more on the responses
      else
        if axi_awready = '1' and s_axi_awvalid = '1' and axi_wready = '1'
          and s_axi_wvalid = '1' and axi_bvalid = '0' then
          axi_bvalid <= '1';
          axi_bresp  <= "00";
        elsif s_axi_bready = '1' and axi_bvalid = '1' then
          --check if bready is asserted while bvalid is high)
          -- (there is a possibility that bready is always asserted high)
          axi_bvalid <= '0';
        end if;
      end if;
    end if;
  end process;

  -- Implement axi_arready generation
  -- axi_arready is asserted for one s_axi_aclk clock cycle when
  -- s_axi_arvalid is asserted. axi_awready is
  -- de-asserted when reset (active low) is asserted.
  -- The read address is also latched when s_axi_arvalid is
  -- asserted. axi_araddr is reset to zero on reset assertion.

  process (s_axi_aclk)
  begin
    if rising_edge(s_axi_aclk) then
      if s_axi_areset = '1' then
        axi_arready <= '0';
        axi_araddr  <= (others => '1');
      else
        if axi_arready = '0' and s_axi_arvalid = '1' then
          -- indicates that the slave has acceped the valid read address
          axi_arready <= '1';
          -- Read Address latching
          axi_araddr  <= s_axi_araddr;
        else
          axi_arready <= '0';
        end if;
      end if;
    end if;
  end process;

  -- Implement axi_arvalid generation
  -- axi_rvalid is asserted for one s_axi_aclk clock cycle when both
  -- s_axi_arvalid and axi_arready are asserted. The slave registers
  -- data are available on the axi_rdata bus at this instance. The
  -- assertion of axi_rvalid marks the validity of read data on the
  -- bus and axi_rresp indicates the status of read transaction.axi_rvalid
  -- is deasserted on reset (active low). axi_rresp and axi_rdata are
  -- cleared to zero on reset (active low).
  process (s_axi_aclk)
  begin
    if rising_edge(s_axi_aclk) then
      if s_axi_areset = '1' then
        axi_rvalid <= '0';
        axi_rresp  <= "00";
      else
        if axi_arready = '1' and s_axi_arvalid = '1' and axi_rvalid = '0' then
          -- Valid read data is available at the read data bus
          axi_rvalid <= '1';
          axi_rresp  <= "00";           -- 'OKAY' response
        elsif axi_rvalid = '1' and s_axi_rready = '1' then
          -- Read data is accepted by the master
          axi_rvalid <= '0';
        end if;
      end if;
    end if;
  end process;

  -- Implement memory mapped register select and read logic generation
  -- Slave register read enable is asserted when valid address is available
  -- and the slave is ready to accept the read address.
  slv_reg_rden <= axi_arready and s_axi_arvalid and (not axi_rvalid);
'''
reg_data_out_header = '''
  process ({sens}axi_araddr, s_axi_areset, slv_reg_rden)
    variable loc_addr : std_logic_vector(OPT_MEM_ADDR_BITS downto 0);
  begin
    if s_axi_areset = '1' then
      reg_data_out <= (others => '0');
    else
      -- Address decoding for reading registers
      loc_addr := axi_araddr(ADDR_LSB + OPT_MEM_ADDR_BITS downto ADDR_LSB);
      case loc_addr is'''
reg_data_out_when = '''
        when b"{num_bin}" =>
          reg_data_out <= slv_reg{num};'''
reg_data_out_footer_axi_logic = '''
        when others =>
          reg_data_out <= (others => '0');
      end case;
    end if;
  end process;

  -- Output register or memory read data
  process(s_axi_aclk) is
  begin
    if rising_edge (s_axi_aclk) then
      if s_axi_areset = '1' then
        axi_rdata <= (others => '0');
      else
        if slv_reg_rden = '1' then
          -- When there is a valid read address (s_axi_arvalid) with
          -- acceptance of read address by the slave (axi_arready),
          -- output the read dada
          -- Read address mux
          axi_rdata <= reg_data_out;    -- register read data
        end if;
      end if;
    end if;
  end process;
'''
ctrl_sig_assgns_header = '\n  -- Assign registers to control signals\n'
ctrl_sig_assgns = '  {:{}} <= slv_reg{}({} downto {});\n'
ctrl_sig_assgns_1bit = '  {:{}} <= slv_reg{}({});\n'
sts_sig_assgns_header = '''
  -- Assign status signals to registers
  process(s_axi_aclk)
    variable loc_addr : std_logic_vector(OPT_MEM_ADDR_BITS downto 0);
  begin
    if rising_edge(s_axi_aclk) then
      if s_axi_areset = '1' then'''
sts_sig_assgns_reset = '\n        slv_reg{} <= (others => \'0\');'
sts_sig_assgns_reset_else = '''
      else
        loc_addr := axi_awaddr(ADDR_LSB + OPT_MEM_ADDR_BITS downto ADDR_LSB);'''
sts_sig_assgns_no_clr = '\n        slv_reg{reg_no}({msb} downto {lsb}) <= {signal};'
sts_sig_assgns_no_clr_1bit = '\n        slv_reg{reg_no}({msb}) <= {signal};'
sts_sig_assgns_with_clr = '''
        if {signal_valid} = '1' then
          slv_reg{reg_no}({msb} downto {lsb}) <= {signal};
        elsif slv_reg_wren = '1' and loc_addr = b"{addr_bin}"
          and S_AXI_WSTRB({strb_lsb} downto {strb_msb}) = "{strb_1s}" then
          slv_reg{reg_no}({msb} downto {lsb}) <= (others => \'0\');
        else
          slv_reg{reg_no}({msb} downto {lsb}) <= slv_reg{reg_no}({msb} downto {lsb});
        end if;'''
sts_sig_assgns_with_clr_1bit = '''
        if {signal_valid} = '1' then
          slv_reg{reg_no}({msb}) <= {signal};
        elsif slv_reg_wren = '1' and loc_addr = b"{addr_bin}"
          and S_AXI_WSTRB({strb_lsb} downto {strb_msb}) = "{strb_1s}" then
          slv_reg{reg_no}({msb}) <= \'0\';
        else
          slv_reg{reg_no}({msb}) <= slv_reg{reg_no}({msb});
        end if;'''
sts_sig_assgns_footer = '''
      end if;
    end if;
  end process;
'''
cdc_inst_pl_read = '''
  {signal}_cdc : cdc_sync
    generic map (
      WIDTH      => {width},
      WITH_VLD   => false,
      DAT_IS_REG => true
      )
    port map (
      src_clk{spaces} => s_axi_aclk,
      src_dat{onebit} => {signal}_sync,
      src_vld{spaces} => '1',
      dst_clk{spaces} => {clock},
      dst_dat{onebit} => {signal},
      dst_vld{spaces} => open
      );
'''
cdc_inst_pl_read_pulse = '''
  {signal}_cdc : cdc_sync
    generic map (
      WIDTH      => {width},
      WITH_VLD   => false,
      SRC_PER_NS => {src_per},
      DST_PER_NS => {dst_per},
      IS_PULSE   => true
      )
    port map (
      src_clk{spaces} => s_axi_aclk,
      src_dat{onebit} => {signal}_sync,
      src_vld{spaces} => '1',
      dst_clk{spaces} => {clock},
      dst_dat{onebit} => {signal},
      dst_vld{spaces} => open
      );
'''
cdc_inst_pl_write = '''
  {signal}_cdc : cdc_sync
    generic map (
      WIDTH      => {width},
      WITH_VLD   => false,
      DAT_IS_REG => false
      )
    port map (
      src_clk{spaces} => {clock},
      src_dat{onebit} => {signal},
      src_vld{spaces} => '1',
      dst_clk{spaces} => s_axi_aclk,
      dst_dat{onebit} => {signal}_sync,
      dst_vld{spaces} => open
      );
'''
cdc_inst_pl_write_vld = '''
  {signal}_cdc : cdc_sync
    generic map (
      WIDTH      => {width},
      WITH_VLD   => true,
      SRC_PER_NS => {src_per},
      DST_PER_NS => {dst_per},
      DAT_IS_REG => false
      )
    port map (
      src_clk{spaces} => {clock},
      src_dat{onebit} => {signal},
      src_vld{spaces} => {signal}_vld,
      dst_clk{spaces} => s_axi_aclk,
      dst_dat{onebit} => {signal}_sync,
      dst_vld{spaces} => {signal}_vld_sync
      );
'''
arc_footer = '\nend arch_imp;'
