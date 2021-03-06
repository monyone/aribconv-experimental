from mpeg2ts.pes import PES

from subtitle.JIS8 import JIS8, CSI, ESC, G_SET, G_DRCS
from subtitle.color import pallets
from subtitle.dictionary import Dictionary, HIRAGANA, KATAKANA, ALNUM, KANJI, MACRO

class NotImplementedYetError(Exception):
  pass

class VTTGenerator:

  def __init__(self, pes):
    self.pes = pes
    self.text = ''
    self.vtt = ''

    self.G_TEXT = {
      G_SET.KANJI: KANJI(),
      G_SET.ALNUM: ALNUM(),
      G_SET.HIRAGANA: HIRAGANA(),
      G_SET.KATAKANA: KATAKANA(),

      #エラーがでたら対応する
      G_SET.MOSAIC_A: None, # MOSAIC A
      G_SET.MOSAIC_B: None, # MOSAIC B
      G_SET.MOSAIC_C: None, # MOSAIC C
      G_SET.MOSAIC_D: None, # MOSAIC D
      # 実運用では出ないと規定されている
      G_SET.P_ALNUM: None, # P ALNUM (TODO: TR で使われないと規定されてるのでページ数を書く)
      G_SET.P_HIRAGANA: None, # P HIRAGANA (TODO: TR で使われないと規定されてるのでページ数を書く)
      G_SET.P_KATAKANA: None, # P KATAKANA (TODO: TR で使われないと規定されてるのでページ数を書く)
      # エラーが出たら対応する
      G_SET.JIS_X0201_KATAKANA: None, # JIS X0201 KATAKANA
      # ARIB TR-B14 第6.0版 第1分冊 p.89 で運用しないとされている
      G_SET.JIS_X0213_2004_KANJI_1: None, # JIS 1 KANJI
      G_SET.JIS_X0213_2004_KANJI_2: None, # JIS 2 KANJI
      G_SET.ADDITIONAL_SYMBOLS: None, # ADDITIONAL SYMBOLS
    }
    self.G_OTHER = {
      G_DRCS.DRCS_0: Dictionary(2, {}), # DRCS 2byte
      G_DRCS.DRCS_1: Dictionary(1, {}), # DRCS 1byte
      G_DRCS.DRCS_2: Dictionary(1, {}), # DRCS 1byte
      G_DRCS.DRCS_3: Dictionary(1, {}), # DRCS 1byte
      G_DRCS.DRCS_4: Dictionary(1, {}), # DRCS 1byte
      G_DRCS.DRCS_5: Dictionary(1, {}), # DRCS 1byte
      G_DRCS.DRCS_6: Dictionary(1, {}), # DRCS 1byte
      G_DRCS.DRCS_7: Dictionary(1, {}), # DRCS 1byte
      G_DRCS.DRCS_8: Dictionary(1, {}), # DRCS 1byte
      G_DRCS.DRCS_9: Dictionary(1, {}), # DRCS 1byte
      G_DRCS.DRCS_10: Dictionary(1, {}), # DRCS 1byte
      G_DRCS.DRCS_11: Dictionary(1, {}), # DRCS 1byte
      G_DRCS.DRCS_12: Dictionary(1, {}), # DRCS 1byte
      G_DRCS.DRCS_13: Dictionary(1, {}), # DRCS 1byte
      G_DRCS.DRCS_14: Dictionary(1, {}), # DRCS 1byte
      G_DRCS.DRCS_15: Dictionary(1, {}), # DRCS 1byte
      G_DRCS.MACRO: MACRO()
    }
    # (WARN: 本来は SWF は字幕管理データから取得する)
    self.swf, self.sdf, self.sdp = (960, 540), (960, 540), (0, 0)
    self.ssm, self.shs, self.svs = (36, 36), 4, 24
    self.text_size = (1, 1)
    self.pos = None # MEMO: SDF, SDF, SDP が変化している事があるため
    self.pallet = 0
    self.fg = pallets[self.pallet][7]
    self.bg = pallets[self.pallet][8]
    self.orn = None
    self.stl = False
    self.hlc = 0
    self.time_elapsed = 0
    self.end_time = None
    self.initialize()

  def initialize(self):
    self.G_BACK = [
      self.G_TEXT[0x42],  # KANJI
      self.G_TEXT[0x4A],  # ALNUM
      self.G_TEXT[0x30],  # HIRAGANA
      self.G_OTHER[0x70], # MACRO
    ]
    self.GL = 0
    self.GR = 2

  def PES_header_data_length(self):
    return self.pes[PES.HEADER_SIZE + 2]

  def PTS(self):
    pts = 0
    pts <<= 3; pts |= ((self.pes[PES.HEADER_SIZE + 3 + 0] & 0x0E) >> 1)
    pts <<= 8; pts |= ((self.pes[PES.HEADER_SIZE + 3 + 1] & 0xFF) >> 0)
    pts <<= 7; pts |= ((self.pes[PES.HEADER_SIZE + 3 + 2] & 0xFE) >> 1)
    pts <<= 8; pts |= ((self.pes[PES.HEADER_SIZE + 3 + 3] & 0xFF) >> 0)
    pts <<= 7; pts |= ((self.pes[PES.HEADER_SIZE + 3 + 4] & 0xFE) >> 1)
    return pts

  def generate(self):
    PES_data_packet_header_length = (self.pes[(PES.HEADER_SIZE + 3) + self.PES_header_data_length() + 2] & 0x0F)

    data_group = PES.HEADER_SIZE + (3 + self.PES_header_data_length()) + (3 + PES_data_packet_header_length)
    data_group_id = (self.pes[data_group + 0] & 0xFC) >> 2
    data_group_version = self.pes[data_group + 0] & 0x03
    data_group_number = self.pes[data_group + 1]
    last_data_group_number = self.pes[data_group + 2]
    data_group_size = (self.pes[data_group + 3] << 8) + self.pes[data_group + 4]
    CRC16 = (self.pes[data_group + (5 + data_group_size) + 0] << 8) | self.pes[data_group + (5 + data_group_size) + 1]

    if (data_group_id & 0x0F) != 1: # とりあえず第一言語字幕だけとる
      return

    # TMD は字幕では 00 固定なので見ない (ARIB TR-B14 2 4.2.6 字幕文データの運用)

    data_unit = data_group + 9
    while data_unit < data_group + (5 + data_group_size):
      unit_separator = self.pes[data_unit + 0]
      data_unit_parameter = self.pes[data_unit + 1]
      data_unit_size = (self.pes[data_unit + 2] << 16) | (self.pes[data_unit + 3] << 8) | self.pes[data_unit + 4]

      if data_unit_parameter == 0x20:
        self.parse_text(data_unit + 5, data_unit + 5 + data_unit_size)
      elif data_unit_parameter == 0x35:
        raise NotImplementedYetError() # ビットマップデータ
      elif data_unit_parameter == 0x30:
        self.parse_DRCS(1, data_unit + 5, data_unit + 5 + data_unit_size)
      elif data_unit_parameter == 0x31:
        self.parse_DRCS(2, data_unit + 5, data_unit + 5 + data_unit_size)
      else:
        raise NotImplementedYetError() # 2バイトDRCS

      data_unit += 5 + data_unit_size

  def kukaku(self):
    width = int((self.shs + self.ssm[0]) * self.text_size[0])
    height = int((self.svs + self.ssm[1]) * self.text_size[1])
    return (width, height)
  def move_absolute_dot(self, x, y):
    self.pos = (x, y)
  def move_absolute_pos(self, x, y):
    width, height = self.kukaku()
    self.pos = (self.sdp[0] + x * width, self.sdp[1] + (y + 1) * height)
  def move_relative_pos(self, x, y):
    if not self.pos: self.move_absolute_pos(0, 0)
    width, height = self.kukaku()
    while x < 0:
      x += 1
      self.pos = (self.pos[0] - width, self.pos[1])
      if self.pos[0] < self.sdp[0]:
        self.pos = (self.sdp[0] + self.sdf[0] - width, self.pos[1])
        y -= 1
    while x > 0:
      x -= 1
      self.pos = (self.pos[0] + width, self.pos[1])
      if self.pos[0] >= self.sdp[0] + self.sdf[0]:
        self.pos = (self.sdp[0], self.pos[1])
        y += 1
    while y < 0:
      y += 1
      self.pos = (self.pos[0], self.pos[1] - height)
    while y > 0:
      y -= 1
      self.pos = (self.pos[0], self.pos[1] + height)

  def move_newline(self):
    if not self.pos: self.move_absolute_pos(0, 0)
    width, height = self.kukaku()
    self.pos = (self.sdp[0], self.pos[1] + height)
    self.style_changed = True

  def parse_DRCS(self, size, begin, end):
    NumberOfCode = self.pes[begin + 0]
    begin += 1
    while begin < end:
      CharacterCode = (self.pes[begin + 0] << 8) | self.pes[begin + 1]
      NumberOfFont = self.pes[begin + 2]
      if size == 1:
        # 0x41 - 0x4F までが 1byte DRCS の対応なので、下の 4bit だけ取る
        index, ch = (CharacterCode & 0x0F00) >> 8, ((CharacterCode & 0x00FF) >> 0) & 0x7F
      elif size == 2:
        ch = CharacterCode & 0x7F7F

      begin += 3
      for font in range(NumberOfFont):
        fontId = (self.pes[begin + 0] & 0xF0) >> 4
        mode = self.pes[begin + 0] & 0x0F
        if mode == 0b0000 or mode == 0b0001 : #無圧縮の1bit(0000) or Nbit(0001) の DRCS
          depth = self.pes[begin + 1]
          width = self.pes[begin + 2]
          height = self.pes[begin + 3]
          depth_bits = len(bin(depth + 2)) - len(bin(depth + 2).rstrip('0'))
          length = (width * height * depth_bits) // 8 # FIXME: depth = 階調数 - 2 なので対応する
          if size == 1:
            self.G_OTHER[0x40 + index][ch] = self.pes[begin + 4: begin + 4 + length]
            begin += 4 + length
          elif size == 2:
            self.G_OTHER[0x40][ch] = self.pes[begin + 4: begin + 4 + length]
            begin += 4 + length
          else:
            raise NotImplementedYetError()
        else: # ジオメトリック図形は運用しない(TR-B14にて)
          raise NotImplementedYetError()

  def parse_text(self, begin, end):
    while begin < end:
      start = begin
      byte = self.pes[begin]
      if 0x20 < byte and byte < 0x7F:
        size = self.G_BACK[self.GL].size
        self.render_character(self.pes[begin:begin+size], self.G_BACK[self.GL])
        begin += size
      elif 0xA0 < byte and byte < 0xFF:
        size = self.G_BACK[self.GR].size
        self.render_character(self.pes[begin:begin+size], self.G_BACK[self.GR])
        begin += size
      else:
        if byte == JIS8.NUL:
          begin += 1 # (TODO: ignore したことをログに残す)
        elif byte == JIS8.BEL:
          begin += 1 # (TODO: ignore したことをログに残す)
        elif byte == JIS8.APB:
          self.move_relative_pos(-1, 0)
          self.style_changed = True
          begin += 1
        elif byte == JIS8.APF:
          self.move_relative_pos(1, 0)
          self.style_changed = True
          begin += 1
        elif byte == JIS8.APD:
          self.move_relative_pos(0, 1)
          self.style_changed = True
          begin += 1
        elif byte == JIS8.APU:
          self.move_relative_pos(0, -1)
          self.style_changed = True
          begin += 1
        elif byte == JIS8.CS:
          if self.time_elapsed != 0:
            self.end_time = self.time_elapsed
          begin += 1
        elif byte == JIS8.APR:
          self.move_newline()
          self.style_changed = True
          begin += 1
        elif byte == JIS8.LS1:
          self.GL = 1
          begin += 1
        elif byte == JIS8.LS0:
          self.GL = 0
          begin += 1
        elif byte == JIS8.PAPF:
          P1 = self.pes[begin + 1] & 0x3F # x
          self.move_relative_pos(P1, 0)
          self.style_changed = True
          begin += 2
        elif byte == JIS8.CAN:
          begin += 1 # (TODO: ignore したことをログに残す)
        elif byte == JIS8.SS2:
          size = self.G_BACK[2].size
          self.render_character(self.pes[begin + 1: begin + 1 + size], self.G_BACK[2])
          begin += 1 + size
        elif byte == JIS8.ESC:
          if self.pes[begin + 1] == ESC.LS2: ## LS2
            self.GL = 2 #GL = G2
            begin += 2
          elif self.pes[begin + 1] == ESC.LS3: ## LS3
            self.GL = 3 #GL = G3
            begin += 2
          elif self.pes[begin + 1] == ESC.LS1R: ## LS1R
            self.GR = 1 #GR = G1
            begin += 2
          elif self.pes[begin + 1] == ESC.LS2R: ## LS2R
            self.GR = 2 #GR = G2
            begin += 2
          elif self.pes[begin + 1] == ESC.LS3R: ## LS3R
            self.GR = 3 #GR = G3
            begin += 2
          elif 0x28 <= self.pes[begin + 1] and self.pes[begin + 1] <= 0x2B: # 1 byte
            GX = self.pes[begin + 1] - 0x28
            if self.pes[begin + 2] == 0x20:
              self.G_BACK[GX] = self.G_OTHER[self.pes[begin + 3]] # DRCS
              begin += 4
            else:
              self.G_BACK[GX] = self.G_TEXT[self.pes[begin + 2]] # TEXT
              begin += 3
          elif self.pes[begin + 1] == 0x24: # 2 byte
            if 0x28 <= self.pes[begin + 2] and self.pes[begin + 2] <= 0x2B: # 2 byte
              GX = self.pes[begin + 2] - 0x28
              if self.pes[begin + 3] == 0x20:
                self.G_BACK[GX] = self.G_OTHER[self.pes[begin + 4]] # DRCS
                begin += 5
              else:
                self.G_BACK[GX] = self.G_TEXT[self.pes[begin + 3]] # TEXT
                begin += 4
            else: # G0 (2byte G SET)
              self.G_BACK[0] = self.G_TEXT[self.pes[begin + 2]]
              begin += 3
          else:
            raise NotImplementedYetError(JIS8.ESC)
        elif byte == JIS8.APS:
          P1 = self.pes[begin + 1] & 0x3F # y
          P2 = self.pes[begin + 2] & 0x3F # x
          self.move_absolute_pos(P2, P1)
          self.style_changed = True
          begin += 3
        elif byte == JIS8.SS3:
          size = self.G_BACK[3].size
          self.render_character(self.pes[begin + 1: begin + 1 + size], self.G_BACK[3])
          begin += 1 + size
        elif byte == JIS8.RS:
          begin += 1 # (TODO: ignore したことをログに残す)
        elif byte == JIS8.US:
          begin += 1 # (TODO: ignore したことをログに残す)
        elif byte == JIS8.SP:
          self.render_character(b'\xa1\xa1', self.G_TEXT[G_SET.KANJI]) # 全角スペース
          begin += 1
        elif byte == JIS8.DEL:
          begin += 1 # (TODO: ignore したことをログに残す)
        elif byte == JIS8.BKF:
          self.fg = pallets[self.pallet][0]
          self.style_changed = True
          begin += 1
        elif byte == JIS8.RDF:
          self.fg = pallets[self.pallet][1]
          self.style_changed = True
          begin += 1
        elif byte == JIS8.GRF:
          self.fg = pallets[self.pallet][2]
          self.style_changed = True
          begin += 1
        elif byte == JIS8.YLF:
          self.fg = pallets[self.pallet][3]
          self.style_changed = True
          begin += 1
        elif byte == JIS8.BLF:
          self.fg = pallets[self.pallet][4]
          self.style_changed = True
          begin += 1
        elif byte == JIS8.MGF:
          self.fg = pallets[self.pallet][5]
          self.style_changed = True
          begin += 1
        elif byte == JIS8.CNF:
          self.fg = pallets[self.pallet][6]
          self.style_changed = True
          begin += 1
        elif byte == JIS8.WHF:
          self.fg = pallets[self.pallet][7]
          self.style_changed = True
          begin += 1
        elif byte == JIS8.SSZ:
          self.text_size = (0.5, 0.5)
          self.style_changed = True
          begin += 1
        elif byte == JIS8.MSZ:
          self.text_size = (0.5, 1)
          self.style_changed = True
          begin += 1
        elif byte == JIS8.NSZ:
          self.text_size = (1, 1)
          self.style_changed = True
          begin += 1
        elif byte == JIS8.SZX:
          raise NotImplementedYetError(JIS8.SZX)
        elif byte == JIS8.COL:
          P1 = self.pes[begin + 1]
          if P1 == 0x20:
            P2 = self.pes[begin + 2] & 0x0F
            self.pallet = P2
            begin += 3
          else:
            color = P1 & 0x0F
            if (P1 & 0x70) == 0x40:
              self.fg = pallets[self.pallet][color]
              self.style_changed = True
            elif (P1 & 0x70) == 0x50:
              self.bg = pallets[self.pallet][color]
              self.style_changed = True
            else:
              # (TODO: ignore したことをログに残す)
              pass
            begin += 2
        elif byte == JIS8.FLC: # 点滅(電話の着信を表す字幕で使われる)
          begin += 2 # (TODO: ignore したことをログに残す)
        elif byte == JIS8.CDC:
          raise NotImplementedYetError(JIS8.CDC)
        elif byte == JIS8.POL:
          raise NotImplementedYetError(JIS8.POL)
        elif byte == JIS8.WMM:
          raise NotImplementedYetError(JIS8.WMM)
        elif byte == JIS8.MACRO:
          raise NotImplementedYetError(JIS8.MACRO)
        elif byte == JIS8.HLC:
          self.prev_hlc = self.hlc
          self.hlc = self.pes[begin + 1] & 0x0F
          if self.prev_hlc == 0 and self.hlc != 0:
            self.style_changed = True
          elif self.prev_hlc != 0 and self.hlc == 0:
            self.style_changed = True

          begin += 2
        elif byte == JIS8.RPC:
          raise NotImplementedYetError(JIS8.RPC)
        elif byte == JIS8.SPL:
          self.stl = False
          self.style_changed = True
          begin += 1
        elif byte == JIS8.STL:
          self.stl = True
          self.style_changed = True
          begin += 1
        elif byte == JIS8.CSI:
          last = begin + 1
          while True:
            if self.pes[last] == CSI.GSM:
              raise NotImplementedYetError(CSI.GSM)
            elif self.pes[last] == CSI.SWF:
              index = begin + 1
              P1 = 0
              while self.pes[index] != 0x3B and self.pes[index] != 0x20:
                P1 *= 10
                P1 += self.pes[index] & 0x0F
                index += 1
              if self.pes[index] != 0x20:
                raise NotImplementedYetError(CSI.SWF)
              elif P1 == 5:
                self.swf = (1920, 1080)
                self.style_changed = True
              elif P1 == 7:
                self.swf = (960, 540)
                self.style_changed = True
              elif P1 == 9:
                self.swf = (720, 480)
                self.style_changed = True
              else:
                raise NotImplementedYetError(CSI.SWF)
              break
            elif self.pes[last] == CSI.CCC:
              raise NotImplementedYetError(CSI.CCC)
            elif self.pes[last] == CSI.SDF:
              index = begin + 1
              P1, P2 = 0, 0
              while self.pes[index] != 0x3B:
                P1 *= 10
                P1 += self.pes[index] & 0x0F
                index += 1
              index += 1
              while self.pes[index] != 0x20:
                P2 *= 10
                P2 += self.pes[index] & 0x0F
                index += 1
              self.sdf = (P1, P2)
              self.style_changed = True
              break
            elif self.pes[last] == CSI.SSM:
              index = begin + 1
              P1, P2 = 0, 0
              while self.pes[index] != 0x3B:
                P1 *= 10
                P1 += self.pes[index] & 0x0F
                index += 1
              index += 1
              while self.pes[index] != 0x20:
                P2 *= 10
                P2 += self.pes[index] & 0x0F
                index += 1
              self.ssm = (P1, P2)
              self.style_changed = True
              break
            elif self.pes[last] == CSI.SHS:
              index = begin + 1
              P1 = 0
              while self.pes[index] != 0x20:
                P1 *= 10
                P1 += self.pes[index] & 0x0F
                index += 1
              self.shs = P1
              self.style_changed = True
              break
            elif self.pes[last] == CSI.SVS:
              index = begin + 1
              P1 = 0
              while self.pes[index] != 0x20:
                P1 *= 10
                P1 += self.pes[index] & 0x0F
                index += 1
              self.svs = P1
              self.style_changed = True
              break
            elif self.pes[last] == CSI.PLD:
              raise NotImplementedYetError(CSI.PLD)
            elif self.pes[last] == CSI.PLU:
              raise NotImplementedYetError(CSI.PLU)
            elif self.pes[last] == CSI.GAA:
              raise NotImplementedYetError(CSI.GAA)
            elif self.pes[last] == CSI.SRC:
              raise NotImplementedYetError(CSI.SRC)
            elif self.pes[last] == CSI.SDP:
              index = begin + 1
              P1, P2 = 0, 0
              while self.pes[index] != 0x3B:
                P1 *= 10
                P1 += self.pes[index] & 0x0F
                index += 1
              index += 1
              while self.pes[index] != 0x20:
                P2 *= 10
                P2 += self.pes[index] & 0x0F
                index += 1
              self.sdp = (P1, P2)
              self.style_changed = True
              break
            elif self.pes[last] == CSI.ACPS:
              index = begin + 1
              P1, P2 = 0, 0
              while self.pes[index] != 0x3B:
                P1 *= 10
                P1 += self.pes[index] & 0x0F
                index += 1
              index += 1
              while self.pes[index] != 0x20:
                P2 *= 10
                P2 += self.pes[index] & 0x0F
                index += 1
              self.move_absolute_dot(P1, P2)
              self.style_changed = True
              break
            elif self.pes[last] == CSI.TCC:
              raise NotImplementedYetError(CSI.TCC)
            elif self.pes[last] == CSI.ORN:
              P1 = self.pes[begin + 1]
              if P1 == 0x30:
                self.orn = None
              elif P1 == 0x31:
                P2 = (self.pes[begin + 3] & 0x0F) * 10 + (self.pes[begin + 4] & 0x0F)
                P3 = (self.pes[begin + 5] & 0x0F) * 10 + (self.pes[begin + 6] & 0x0F)
                self.orn = pallets[P2][P3]
                self.style_changed = True
              else:
                raise NotImplementedYetError(CSI.ORN)
              break
            elif self.pes[last] == CSI.MDF:
              raise NotImplementedYetError(CSI.MDF)
            elif self.pes[last] == CSI.CFS:
              raise NotImplementedYetError(CSI.CFS)
            elif self.pes[last] == CSI.XCS:
              raise NotImplementedYetError(CSI.XCS)
            elif self.pes[last] == CSI.SCR:
              raise NotImplementedYetError(CSI.SCR)
            elif self.pes[last] == CSI.PRA:
              raise NotImplementedYetError(CSI.PRA)
            elif self.pes[last] == CSI.ACS:
              raise NotImplementedYetError(CSI.ACS)
            elif self.pes[last] == CSI.UED:
              raise NotImplementedYetError(CSI.UED)
            elif self.pes[last] == CSI.RCS: # (CS の代わりに塗りつぶしで場合がある)
              break #(TODO: 無視した事をログする)
            elif self.pes[last] == CSI.SCS:
              raise NotImplementedYetError(CSI.SCS)
            else:
              last += 1
          begin = last + 1
        elif byte == JIS8.TIME:
          # (TODO: ignore したことをログに残す)
          if self.pes[begin + 1] == 0x20:
            self.time_elapsed += (self.pes[begin + 2] & 0x3F) / 10
            begin += 3
          elif self.pes[begin + 1] == 0x28:
            raise NotImplementedYetError(JIS8.TIME)
          else:
            raise NotImplementedYetError(JIS8.TIME)
        else:
          raise NotImplementedYetError(hex(byte))

        self.vtt += "".join([f"<c.0x{b:02x}></c>" for b in self.pes[start:begin]])

  def render_character(self, ch_byte, dict):
    if not self.pos: self.move_absolute_pos(0, 0)

    character_key = int.from_bytes(ch_byte, byteorder='big') & int.from_bytes(b'\x7F' * dict.size, byteorder='big')
    character = dict[character_key]

    if type(character) == tuple: # MACRO
      self.vtt += "".join([f"<c.0x{b:02x}></c>" for b in ch_byte])
      self.G_BACK = [(self.G_TEXT[dictionary] if dictionary in G_SET else self.G_OTHER[dictionary]) for dictionary in character]
      self.GL = 0
      self.GR = 2
      return
    elif type(character) == bytearray: # DRCS
      width = int(self.ssm[0] * self.text_size[0])
      height = int(self.ssm[1] * self.text_size[1])
      depth = len(character) * 8 // (drcs[0] * drcs[1])
      self.vtt += f"<c.DRCS-{width}-{height}-{depth}-{character}></c>"
    else:
      self.vtt += character
      self.text += character

    self.move_relative_pos(1, 0)
