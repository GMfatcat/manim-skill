"""
共用樣式與工具函數
所有 dLM 動畫共用顏色、字型、過場、helper 等
"""

from manim import *

# ---------- 配色系統 (與 HTML 報告一致) ----------
BG_COLOR = "#FBF8F1"          # 淡米黃背景
BG_CARD = "#F4F0E6"           # 卡片背景
BG_CODE = "#ECE7D9"           # 程式碼背景 / mask 格
INK = "#1A1A1A"               # 主文字
INK_SOFT = "#4A4A48"          # 次要文字
INK_FAINT = "#7A7872"         # 標籤、註解
ACCENT = "#1E4F5C"            # 深青 - 主強調色 (AR, dLM 已敲定 token)
ACCENT_SOFT = "#3D7480"       # 淺青 - 次強調色
WARN = "#8B3A2E"              # 警告紅 - delete, 錯誤, 重點高亮
EXPAND = "#8B7A35"            # 棕黃 - expand token
EXPAND_BG = "#FAF1D7"         # 棕黃淺底
DELETE_BG = "#F4D2CC"         # 紅淺底 - delete
HIGHLIGHT = "#F4E9C9"         # 黃色高亮
RULE = "#C8C2B0"              # 分割線
RULE_SOFT = "#DDD7C5"         # 淺分割線

# ---------- 字型 ----------
# Latin 用 IBM Plex（已內建在 manim-skill docker image 裡）。CJK 字仍走
# Noto CJK fallback —— IBM Plex Sans TC 不在 IBM/plex GitHub repo，所以
# 沒裝。把 FONT_DISPLAY 從 "IBM Plex Sans TC" 改回 "IBM Plex Sans"，避
# 免 Pango 對 Latin 鄰接字元做 per-glyph fallback（會造成 "parallel"
# 變 "para llel" 那種不平均字距）。
FONT_DISPLAY = "IBM Plex Sans"
FONT_BODY = "IBM Plex Serif"
FONT_MONO = "IBM Plex Mono"

# 字型 fallback (如果系統沒裝 IBM Plex)
FONT_DISPLAY_FALLBACK = "Sans Serif"
FONT_MONO_FALLBACK = "Monospace"


def title_text(text, size=32, color=INK):
    """主標題文字"""
    return Text(text, font=FONT_DISPLAY, weight=BOLD, font_size=size, color=color)


def body_text(text, size=20, color=INK_SOFT, italic=False):
    """內文"""
    slant = ITALIC if italic else NORMAL
    return Text(text, font=FONT_BODY, slant=slant, font_size=size, color=color)


def mono_text(text, size=18, color=INK):
    """等寬程式碼字"""
    return Text(text, font=FONT_MONO, font_size=size, color=color)


def label_text(text, size=14, color=INK_FAINT):
    """小標籤"""
    return Text(text, font=FONT_MONO, font_size=size, color=color)


def make_token_box(text="", masked=False, expand=False, delete=False, defer=False,
                   width=0.9, height=0.7, font_size=20):
    """
    建立一個 token 方格 (代表序列中的一個位置)
    
    Args:
        text: 顯示文字 ("?" 代表 mask)
        masked: 是否為 mask 狀態 (虛線淺色邊框)
        expand: 是否為 expand 動作 (黃色)
        delete: 是否為 delete 動作 (紅色)
        defer: 是否為 defer 狀態 (灰色)
    """
    if expand:
        fill_color = EXPAND_BG
        stroke_color = EXPAND
        stroke_w = 2
        dash = False
    elif delete:
        fill_color = DELETE_BG
        stroke_color = WARN
        stroke_w = 2
        dash = False
    elif masked:
        fill_color = BG_CODE
        stroke_color = RULE
        stroke_w = 1.5
        dash = True
    elif defer:
        fill_color = BG_CODE
        stroke_color = INK_FAINT
        stroke_w = 1
        dash = True
    else:
        fill_color = BG_COLOR
        stroke_color = ACCENT
        stroke_w = 2
        dash = False
    
    if dash:
        box = DashedVMobject(
            Rectangle(width=width, height=height, 
                      stroke_color=stroke_color, stroke_width=stroke_w,
                      fill_color=fill_color, fill_opacity=1),
            num_dashes=20, dashed_ratio=0.5
        )
        # DashedVMobject doesn't fill well, use a filled rect underneath
        bg = Rectangle(width=width, height=height,
                       fill_color=fill_color, fill_opacity=1,
                       stroke_width=0)
        box = VGroup(bg, box)
    else:
        box = Rectangle(width=width, height=height,
                        stroke_color=stroke_color, stroke_width=stroke_w,
                        fill_color=fill_color, fill_opacity=1)
    
    if text:
        text_color = INK if not masked else INK_FAINT
        label = mono_text(text, size=font_size, color=text_color)
        label.move_to(box.get_center())
        return VGroup(box, label)
    return box


def make_chapter_card(num, title_zh, title_en):
    """章節過場卡片"""
    line_top = Line(LEFT * 3, RIGHT * 3, color=INK_FAINT, stroke_width=1)
    line_top.shift(UP * 1)
    
    chapter_num = Text(f"§ {num:02d}", font=FONT_MONO, font_size=18, 
                       color=ACCENT, weight=BOLD)
    chapter_num.shift(UP * 0.4)
    
    title = Text(title_zh, font=FONT_DISPLAY, font_size=36, 
                 weight=BOLD, color=INK)
    title.shift(DOWN * 0.3)
    
    subtitle = Text(title_en, font=FONT_MONO, font_size=16, 
                    color=INK_SOFT, slant=ITALIC)
    subtitle.shift(DOWN * 1)
    
    line_bot = Line(LEFT * 3, RIGHT * 3, color=INK_FAINT, stroke_width=1)
    line_bot.shift(DOWN * 1.6)
    
    return VGroup(line_top, chapter_num, title, subtitle, line_bot)


def transition_to_chapter(scene, num, title_zh, title_en, duration=3.0):
    """
    章節過場效果 (3 秒)
    - 0.5s fade to black
    - 1.0s 標題浮現
    - 1.0s 標題微縮
    - 0.5s fade to next scene
    """
    # 先清除當前畫面
    if scene.mobjects:
        scene.play(*[FadeOut(m) for m in scene.mobjects], run_time=0.5)
    
    card = make_chapter_card(num, title_zh, title_en)
    scene.play(FadeIn(card, shift=UP * 0.3), run_time=1.0)
    scene.play(card.animate.scale(1.05), run_time=0.5, rate_func=there_and_back)
    scene.wait(0.5)
    scene.play(FadeOut(card), run_time=0.5)


def setup_scene_background(scene):
    """設定 scene 背景顏色"""
    scene.camera.background_color = BG_COLOR


def make_footer_caption(text):
    """畫面底部來源引用小字"""
    return Text(text, font=FONT_MONO, font_size=12, 
                color=INK_FAINT, slant=ITALIC)
