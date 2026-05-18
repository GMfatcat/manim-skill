"""
合成影片: 開場 + 6 個動畫 + 章節過場 + 收尾
總時長 ~5:45

執行: manim -pqh anim_full.py FullVideo

順序 (符合報告章節邏輯):
  Opening (5s)
  → A: AR vs dLM 對比 (45s)
  → [Transition 3s]
  → B: Forward/Backward (55s)
  → [Transition 3s]
  → C: 訓練 t vs 推理 T (40s)
  → [Transition 3s]
  → E: AR-to-dLM 轉換 (55s)
  → [Transition 3s]
  → D: DreamOn expand/delete (65s)
  → [Transition 3s]
  → F: 長序列 FLOPs 爆炸 (55s)
  → Closing (5s)
"""

from manim import *
from shared import *

# Import each scene's construct logic
from anim_a_ar_vs_dlm import SceneA
from anim_b_forward_backward import SceneB
from anim_c_t_vs_T import SceneC
from anim_d_dreamon import SceneD
from anim_e_ar_to_dlm import SceneE
from anim_f_flops_blowup import SceneF


class Opening(MovingCameraScene):
    """開場 (5s)"""
    def construct(self):
        # 黑色背景
        self.camera.background_color = BG_COLOR
        
        # 主標題
        main_title = Text(
            "Diffusion Language Models",
            font=FONT_DISPLAY, weight=BOLD, font_size=48, color=INK
        )
        main_title.shift(UP * 0.5)
        
        # 副標題
        subtitle = Text(
            "視覺化詳解",
            font=FONT_DISPLAY, font_size=28, color=ACCENT
        )
        subtitle.next_to(main_title, DOWN, buff=0.4)
        
        # AI Team 標記
        team_label = Text(
            "AI Team research memo  ·  2026/05",
            font=FONT_MONO, font_size=16, color=INK_SOFT, slant=ITALIC
        )
        team_label.shift(DOWN * 2)
        
        # 裝飾線
        top_line = Line(LEFT * 3, RIGHT * 3, color=INK_FAINT, stroke_width=1)
        top_line.shift(UP * 1.8)
        bot_line = Line(LEFT * 3, RIGHT * 3, color=INK_FAINT, stroke_width=1)
        bot_line.shift(DOWN * 1.4)
        
        self.play(
            FadeIn(top_line, shift=DOWN * 0.1),
            FadeIn(bot_line, shift=UP * 0.1),
            run_time=0.6
        )
        self.play(
            Write(main_title),
            run_time=1.2
        )
        self.play(
            FadeIn(subtitle, shift=UP * 0.2),
            FadeIn(team_label, shift=UP * 0.1),
            run_time=0.8
        )
        self.wait(1.8)
        
        # 淡出全部
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=0.6)


class Closing(MovingCameraScene):
    """收尾 (5s)"""
    def construct(self):
        self.camera.background_color = BG_COLOR
        
        end_text = Text(
            "END / 完",
            font=FONT_DISPLAY, weight=BOLD, font_size=42, color=INK
        )
        end_text.shift(UP * 0.3)
        
        credit = Text(
            "Compiled by AI Team  ·  2026-05",
            font=FONT_MONO, font_size=14, color=INK_FAINT, slant=ITALIC
        )
        credit.next_to(end_text, DOWN, buff=0.6)
        
        self.play(FadeIn(end_text), run_time=1.0)
        self.play(FadeIn(credit), run_time=0.6)
        self.wait(2.4)
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=1.0)


class Transition(MovingCameraScene):
    """章節過場 (3s)
    用法: Transition.set_chapter(num, zh, en) 然後 manim 執行
    或在 FullVideo 內部直接 inline 處理 transitions
    """
    chapter_num = 1
    chapter_zh = ""
    chapter_en = ""

    @classmethod
    def set_chapter(cls, num, zh, en):
        cls.chapter_num = num
        cls.chapter_zh = zh
        cls.chapter_en = en

    def construct(self):
        self.camera.background_color = BG_COLOR
        do_transition(self, self.chapter_num, self.chapter_zh, self.chapter_en)


# 6 個固定 chapter 子類，方便用 manim CLI 直接渲染並 ffmpeg concat
class TransitionCh1(Transition):
    chapter_num = 1
    chapter_zh = "AR vs Diffusion"
    chapter_en = "Two Generation Paradigms"


class TransitionCh2(Transition):
    chapter_num = 2
    chapter_zh = "訓練與推理"
    chapter_en = "Forward / Backward Masking"


class TransitionCh3(Transition):
    chapter_num = 3
    chapter_zh = "連續 t 與離散 T"
    chapter_en = "Training-Inference Decoupling"


class TransitionCh4(Transition):
    chapter_num = 4
    chapter_zh = "AR 轉 dLM"
    chapter_en = "Attention Pattern Evolution"


class TransitionCh5(Transition):
    chapter_num = 5
    chapter_zh = "DreamOn 變長機制"
    chapter_en = "Dynamic Length via Sentinel Tokens"


class TransitionCh6(Transition):
    chapter_num = 6
    chapter_zh = "長序列吞吐瓶頸"
    chapter_en = "Long Context FLOPs Blowup"


def do_transition(scene, num, title_zh, title_en):
    """在當前 scene 內執行過場 (3 秒)"""
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
    
    card = VGroup(line_top, chapter_num, title, subtitle, line_bot)
    
    # 1.0s fade in
    scene.play(FadeIn(card, shift=UP * 0.3), run_time=1.0)
    # 1.0s 微縮
    scene.play(card.animate.scale(1.05), run_time=0.5, rate_func=there_and_back)
    scene.wait(0.5)
    # 1.0s fade out
    scene.play(FadeOut(card), run_time=1.0)


# ============================================================
# 主合成影片
# ============================================================
class FullVideo(MovingCameraScene):
    """
    完整合成影片
    
    注意:
    - Manim 不支援直接「串接」多個 Scene class
    - 解決方法: 把每個 Scene 的 construct 內容當作 self 的方法呼叫
    - 為了避免巨大檔案，我們重用各 Scene 的 construct 邏輯
    """
    def construct(self):
        setup_scene_background(self)
        
        # ============ Opening ============
        self._run_opening()
        
        # ============ Chapter 1: A (AR vs dLM) ============
        do_transition(self, 1, "AR vs Diffusion", "Two Generation Paradigms")
        scene_a = SceneA()
        scene_a.camera = self.camera
        scene_a.renderer = self.renderer
        scene_a.construct()
        
        # ============ Chapter 2: B (Forward/Backward) ============
        do_transition(self, 2, "訓練與推理", "Forward / Backward Masking")
        scene_b = SceneB()
        scene_b.camera = self.camera
        scene_b.renderer = self.renderer
        scene_b.construct()
        
        # ============ Chapter 3: C (t vs T) ============
        do_transition(self, 3, "連續 t 與離散 T", "Training-Inference Decoupling")
        scene_c = SceneC()
        scene_c.camera = self.camera
        scene_c.renderer = self.renderer
        scene_c.construct()
        
        # ============ Chapter 4: E (AR-to-dLM) ============
        do_transition(self, 4, "AR 轉 dLM", "Attention Pattern Evolution")
        scene_e = SceneE()
        scene_e.camera = self.camera
        scene_e.renderer = self.renderer
        scene_e.construct()
        
        # ============ Chapter 5: D (DreamOn) ============
        do_transition(self, 5, "DreamOn 變長機制", "Dynamic Length via Sentinel Tokens")
        scene_d = SceneD()
        scene_d.camera = self.camera
        scene_d.renderer = self.renderer
        scene_d.construct()
        
        # ============ Chapter 6: F (FLOPs blowup) ============
        do_transition(self, 6, "長序列吞吐瓶頸", "Long Context FLOPs Blowup")
        scene_f = SceneF()
        scene_f.camera = self.camera
        scene_f.renderer = self.renderer
        scene_f.construct()
        
        # ============ Closing ============
        self._run_closing()
    
    def _run_opening(self):
        """Opening 5s"""
        main_title = Text(
            "Diffusion Language Models",
            font=FONT_DISPLAY, weight=BOLD, font_size=48, color=INK
        )
        main_title.shift(UP * 0.5)
        
        subtitle = Text("視覺化詳解", font=FONT_DISPLAY, font_size=28, color=ACCENT)
        subtitle.next_to(main_title, DOWN, buff=0.4)
        
        team_label = Text(
            "AI Team research memo  ·  2026/05",
            font=FONT_MONO, font_size=16, color=INK_SOFT, slant=ITALIC
        )
        team_label.shift(DOWN * 2)
        
        top_line = Line(LEFT * 3, RIGHT * 3, color=INK_FAINT, stroke_width=1)
        top_line.shift(UP * 1.8)
        bot_line = Line(LEFT * 3, RIGHT * 3, color=INK_FAINT, stroke_width=1)
        bot_line.shift(DOWN * 1.4)
        
        self.play(
            FadeIn(top_line, shift=DOWN * 0.1),
            FadeIn(bot_line, shift=UP * 0.1),
            run_time=0.6
        )
        self.play(Write(main_title), run_time=1.2)
        self.play(
            FadeIn(subtitle, shift=UP * 0.2),
            FadeIn(team_label, shift=UP * 0.1),
            run_time=0.8
        )
        self.wait(1.8)
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=0.6)
    
    def _run_closing(self):
        """Closing 5s"""
        end_text = Text(
            "END / 完",
            font=FONT_DISPLAY, weight=BOLD, font_size=42, color=INK
        )
        end_text.shift(UP * 0.3)
        
        credit = Text(
            "Compiled by AI Team  ·  2026-05",
            font=FONT_MONO, font_size=14, color=INK_FAINT, slant=ITALIC
        )
        credit.next_to(end_text, DOWN, buff=0.6)
        
        self.play(FadeIn(end_text), run_time=1.0)
        self.play(FadeIn(credit), run_time=0.6)
        self.wait(2.4)
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=1.0)
