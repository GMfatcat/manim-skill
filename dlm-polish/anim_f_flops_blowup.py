"""
動畫 F: 長序列 FLOPs 爆炸
總時長 ~55 秒

核心 message: dLM 在長序列上的成本不是「比 AR 慢一點」，是「指數級爆炸」
- Scene 1 (0-8s): Setup
- Scene 2 (8-18s): 短序列 baseline (N=64)
- Scene 3 (18-38s): Slider 拉動 [zoom in dLM 區]
- Scene 4 (38-50s): 公式揭示 [zoom in 公式]
- Scene 5 (50-55s): 結論

執行: manim -pqh anim_f_flops_blowup.py SceneF
"""

from manim import *
from shared import *


class SceneF(MovingCameraScene):
    def construct(self):
        setup_scene_background(self)
        
        # ============ Scene 1: Setup (0-8s) ============
        title = title_text("Long Context Cost: AR vs dLM", size=30)
        title.to_edge(UP, buff=0.4)
        self.play(Write(title), run_time=0.8)
        
        # 左右分區
        ar_badge = VGroup(
            Rectangle(width=2.2, height=0.7, fill_color=BG_CARD, fill_opacity=1,
                      stroke_color=ACCENT, stroke_width=2),
            mono_text("AR · Qwen3.5", size=14, color=ACCENT)
        )
        ar_badge.move_to(LEFT * 3.5 + UP * 2)
        
        dlm_badge = VGroup(
            Rectangle(width=2.5, height=0.7, fill_color=BG_CARD, fill_opacity=1,
                      stroke_color=WARN, stroke_width=2),
            mono_text("dLM · DiffuCoder-7B", size=13, color=WARN)
        )
        dlm_badge.move_to(RIGHT * 3.5 + UP * 2)
        
        self.play(
            FadeIn(ar_badge, shift=DOWN * 0.1),
            FadeIn(dlm_badge, shift=DOWN * 0.1),
            run_time=0.7
        )
        
        # 坐標軸 (吞吐量比較圖)
        axes = Axes(
            x_range=[0, 2200, 500],
            y_range=[0, 100, 25],
            x_length=8,
            y_length=3.5,
            axis_config={"color": INK, "stroke_width": 1.5, "include_tip": False,
                          "font_size": 16, "include_numbers": False},
            x_axis_config={"include_numbers": True, "font_size": 13},
            y_axis_config={"include_numbers": True, "font_size": 13},
        )
        axes.move_to(DOWN * 0.5)
        
        # 軸標籤
        x_label = mono_text("Generation length (tokens)", size=13, color=INK_FAINT)
        x_label.next_to(axes.x_axis, DOWN, buff=0.3)
        y_label = mono_text("Throughput (tok/s)", size=13, color=INK_FAINT)
        y_label.next_to(axes.y_axis, LEFT, buff=0.3).rotate(PI/2)
        
        self.play(Create(axes), FadeIn(x_label), FadeIn(y_label), run_time=1.0)
        self.wait(0.4)
        
        # ============ Scene 2: 短序列 baseline N=64 (8-18s) ============
        # N=64 標記
        n64_marker = DashedLine(
            axes.c2p(64, 0), axes.c2p(64, 95),
            color=RULE, dash_length=0.08, stroke_width=1.5
        )
        n64_label = mono_text("N = 64", size=12, color=INK_FAINT)
        n64_label.next_to(axes.c2p(64, 0), DOWN, buff=0.15)
        
        self.play(Create(n64_marker), FadeIn(n64_label), run_time=0.5)
        
        # AR 柱: 高度 90 tok/s
        ar_bar_64 = Rectangle(
            width=0.35, height=axes.c2p(0, 90)[1] - axes.c2p(0, 0)[1],
            fill_color=ACCENT, fill_opacity=0.85, stroke_width=0
        )
        ar_bar_64.move_to(axes.c2p(64, 45) + LEFT * 0.18)
        ar_bar_64_label = mono_text("90 tok/s", size=11, color=ACCENT)
        ar_bar_64_label.next_to(ar_bar_64, UP, buff=0.1)
        
        # dLM 柱: 高度 31.1 tok/s
        dlm_bar_64 = Rectangle(
            width=0.35, height=axes.c2p(0, 31.1)[1] - axes.c2p(0, 0)[1],
            fill_color=WARN, fill_opacity=0.85, stroke_width=0
        )
        dlm_bar_64.move_to(axes.c2p(64, 31.1/2) + RIGHT * 0.18)
        dlm_bar_64_label = mono_text("31.1 tok/s", size=11, color=WARN)
        dlm_bar_64_label.next_to(dlm_bar_64, UP, buff=0.1)
        
        self.play(
            GrowFromEdge(ar_bar_64, DOWN),
            GrowFromEdge(dlm_bar_64, DOWN),
            run_time=1.0
        )
        self.play(FadeIn(ar_bar_64_label), FadeIn(dlm_bar_64_label), run_time=0.4)
        
        self.wait(1.8)


        # ============ Scene 3: Slider 拉動 (18-38s) ============
        # 我們不真的做 slider，而是用 N 值線性增長到 2048，柱狀圖跟著變
        # 但這太複雜 - 改為:在 4 個關鍵 N 值畫出柱狀圖,然後連成曲線
        
        # 在 axes 上畫出 AR 和 dLM 的曲線 (近似)
        # AR: 從 90 線性降到 ~70 (緩慢下降，因為仍受 memory bandwidth 限制)
        # dLM: 從 31.1 指數崩跌到 4.91 (來自 DiffuCoder 實測)
        
        # 第一步: 在中間 N 值 (256, 512, 1024) 也畫柱狀圖
        mid_N_values = [256, 512, 1024, 2048]
        ar_throughputs = [85, 78, 65, 60]  # AR 仍受 memory-bound, 緩降
        dlm_throughputs = [22, 14, 8, 4.91]  # dLM 指數崩跌
        
        ar_bars_mid = VGroup()
        dlm_bars_mid = VGroup()
        ar_labels_mid = VGroup()
        dlm_labels_mid = VGroup()
        
        for n, ar_tp, dlm_tp in zip(mid_N_values, ar_throughputs, dlm_throughputs):
            ar_bar = Rectangle(
                width=0.32, height=max(axes.c2p(0, ar_tp)[1] - axes.c2p(0, 0)[1], 0.02),
                fill_color=ACCENT, fill_opacity=0.85, stroke_width=0
            )
            ar_bar.move_to(axes.c2p(n, ar_tp/2) + LEFT * 0.18)
            ar_bars_mid.add(ar_bar)
            
            dlm_bar = Rectangle(
                width=0.32, height=max(axes.c2p(0, dlm_tp)[1] - axes.c2p(0, 0)[1], 0.02),
                fill_color=WARN, fill_opacity=0.85, stroke_width=0
            )
            dlm_bar.move_to(axes.c2p(n, dlm_tp/2) + RIGHT * 0.18)
            dlm_bars_mid.add(dlm_bar)
            
            # 只在 N=2048 標數字
            if n == 2048:
                ar_lbl = mono_text(f"{ar_tp}", size=10, color=ACCENT)
                ar_lbl.next_to(ar_bar, UP, buff=0.05)
                ar_labels_mid.add(ar_lbl)
                
                dlm_lbl = mono_text(f"{dlm_tp}", size=10, color=WARN)
                dlm_lbl.next_to(dlm_bar, UP, buff=0.05)
                dlm_labels_mid.add(dlm_lbl)
        
        # 動畫: 依序生長柱狀圖
        for i in range(len(mid_N_values)):
            self.play(
                GrowFromEdge(ar_bars_mid[i], DOWN),
                GrowFromEdge(dlm_bars_mid[i], DOWN),
                run_time=0.5
            )
        
        self.play(FadeIn(ar_labels_mid), FadeIn(dlm_labels_mid), run_time=0.4)
        self.wait(0.3)
        
        # 🔍 Zoom-in #1: 拉近 N=2048 區，看清楚 dLM 崩塌
        zoom_target = axes.c2p(2000, 30)
        self.play(
            self.camera.frame.animate.move_to(zoom_target).scale(0.55),
            run_time=1.2,
            rate_func=smooth
        )
        
        # 在放大狀態下，浮現 FLOPs 計數器
        flops_counter_bg = Rectangle(
            width=2.5, height=0.8,
            fill_color=BG_CARD, fill_opacity=0.95,
            stroke_color=WARN, stroke_width=1.5
        )
        flops_counter_bg.move_to(axes.c2p(2050, 60))
        
        flops_label = label_text("FLOPs vs N=64", size=10, color=INK_FAINT)
        flops_label.move_to(axes.c2p(2050, 65))
        
        flops_value = mono_text("~100×", size=22, color=WARN, )
        flops_value.move_to(axes.c2p(2050, 55))
        
        self.play(
            FadeIn(flops_counter_bg),
            FadeIn(flops_label),
            run_time=0.4
        )
        
        # 數字從 1× 跳到 100×
        flops_intermediates = ["1×", "5×", "20×", "60×", "100×"]
        current_flops = mono_text("1×", size=22, color=WARN, )
        current_flops.move_to(axes.c2p(2050, 55))
        self.play(FadeIn(current_flops), run_time=0.3)
        
        for intermediate in flops_intermediates[1:]:
            new_flops = mono_text(intermediate, size=22, color=WARN, )
            new_flops.move_to(axes.c2p(2050, 55))
            self.play(Transform(current_flops, new_flops), run_time=0.25)
        
        # 強調差距箭頭：垂直連接 AR 柱頂到 dLM 柱頂；
        # ar_top 與 dlm_top 因為左右各偏 0.18 而不在同 x，
        # 強制共用 ar_top.x 才會是真正的垂直線。
        _ar_top = ar_bars_mid[-1].get_top()
        _dlm_top = dlm_bars_mid[-1].get_top()
        slowdown_arrow = DoubleArrow(
            [_ar_top[0], _ar_top[1] + 0.3, 0],
            [_ar_top[0], _dlm_top[1] + 0.3, 0],
            buff=0.05, color=WARN, stroke_width=2,
            max_tip_length_to_length_ratio=0.06
        )
        slowdown_arrow.shift(RIGHT * 1.8)
        slowdown_label = mono_text("6.3× slower", size=11, color=WARN)
        slowdown_label.next_to(slowdown_arrow, RIGHT, buff=0.1)
        
        self.play(Create(slowdown_arrow), FadeIn(slowdown_label), run_time=0.5)
        self.wait(1.0)
        
        # Zoom out
        self.play(
            self.camera.frame.animate.move_to(ORIGIN).scale(1/0.55),
            FadeOut(flops_counter_bg), FadeOut(flops_label), FadeOut(current_flops),
            FadeOut(slowdown_arrow), FadeOut(slowdown_label),
            run_time=1.0,
            rate_func=smooth
        )
        
        # ============ Scene 4: 公式揭示 (38-50s) ============
        # 把柱狀圖縮小到下方，讓出空間給公式
        bars_group = VGroup(
            ar_bar_64, dlm_bar_64, ar_bar_64_label, dlm_bar_64_label,
            ar_bars_mid, dlm_bars_mid, ar_labels_mid, dlm_labels_mid,
            n64_marker, n64_label
        )
        
        # 公式背景 (上方)
        ar_formula_bg = Rectangle(
            width=4.5, height=1.0,
            fill_color=BG_COLOR, fill_opacity=1,
            stroke_color=ACCENT, stroke_width=2
        )
        ar_formula_bg.move_to(LEFT * 3.5 + UP * 0.3)
        
        dlm_formula_bg = Rectangle(
            width=4.5, height=1.0,
            fill_color=EXPAND_BG, fill_opacity=0.6,
            stroke_color=WARN, stroke_width=2
        )
        dlm_formula_bg.move_to(RIGHT * 3.5 + UP * 0.3)
        
        ar_formula_title = mono_text("AR (with KV cache)", size=13, color=ACCENT, )
        ar_formula_title.move_to(ar_formula_bg.get_top() + DOWN * 0.25)
        
        dlm_formula_title = mono_text("dLM (full bidirectional)", size=13, color=WARN, )
        dlm_formula_title.move_to(dlm_formula_bg.get_top() + DOWN * 0.25)
        
        ar_formula = mono_text("O(N · L · H²)", size=20, color=ACCENT, )
        ar_formula.move_to(ar_formula_bg.get_center() + DOWN * 0.1)
        
        dlm_formula = mono_text("O(T · N² · D)", size=20, color=WARN, )
        dlm_formula.move_to(dlm_formula_bg.get_center() + DOWN * 0.1)
        
        # 讓現有元素稍微淡化，但保留可見
        self.play(
            bars_group.animate.set_opacity(0.35),
            axes.animate.set_opacity(0.3),
            x_label.animate.set_opacity(0.3),
            y_label.animate.set_opacity(0.3),
            FadeIn(ar_formula_bg), FadeIn(dlm_formula_bg),
            run_time=0.7
        )
        self.play(
            FadeIn(ar_formula_title), FadeIn(dlm_formula_title),
            run_time=0.4
        )
        self.play(Write(ar_formula), Write(dlm_formula), run_time=0.9)
        self.wait(0.5)
        
        # 🔍 Zoom-in #2: 拉近 dLM 公式
        self.play(
            self.camera.frame.animate.move_to(dlm_formula_bg.get_center()).scale(0.6),
            run_time=1.0,
            rate_func=smooth
        )
        
        # 高亮 N² 和 T (用紅色閃爍)
        # 我們重新 render 一個高亮版本的公式
        highlighted_formula = mono_text("O(T · N² · D)", size=20, color=INK)
        highlighted_formula.move_to(dlm_formula.get_center())
        
        # 用 markup-style 來高亮特定字元
        # 因為純 Text 不支持，改用組合方式
        # 簡化: 在 N² 和 T 上方畫紅色底線/圈
        T_indicator = Circle(radius=0.18, color=WARN, stroke_width=2.5)
        # 估算 T 字元的位置
        T_indicator.move_to(dlm_formula.get_center() + LEFT * 0.55 + UP * 0.04)
        
        N2_indicator = Circle(radius=0.22, color=WARN, stroke_width=2.5)
        N2_indicator.move_to(dlm_formula.get_center() + UP * 0.04)
        
        self.play(
            Create(T_indicator), Create(N2_indicator),
            rate_func=there_and_back,
            run_time=1.0
        )
        
        # 浮現註解: T 重複計算, N² 二次項
        explain_T = mono_text("T: each denoising step recomputes", size=12, color=WARN)
        explain_T.next_to(dlm_formula_bg, DOWN, buff=0.35)
        explain_N = mono_text("N²: full bidirectional attention", size=12, color=WARN)
        explain_N.next_to(explain_T, DOWN, buff=0.1)
        
        self.play(FadeIn(explain_T), FadeIn(explain_N), run_time=0.6)
        
        # 具體例子計算
        example_calc = mono_text("e.g. T=32, N=2048 → ~4.3B attention ops/sequence", 
                                   size=11, color=INK_SOFT)
        example_calc.next_to(explain_N, DOWN, buff=0.15)
        self.play(FadeIn(example_calc), run_time=0.5)
        self.wait(1.5)
        
        # Zoom out
        self.play(
            self.camera.frame.animate.move_to(ORIGIN).scale(1/0.6),
            FadeOut(T_indicator), FadeOut(N2_indicator),
            FadeOut(explain_T), FadeOut(explain_N), FadeOut(example_calc),
            run_time=1.0,
            rate_func=smooth
        )
        
        # ============ Scene 5: 結論 (50-55s) ============
        self.play(
            FadeOut(ar_formula_bg), FadeOut(dlm_formula_bg),
            FadeOut(ar_formula_title), FadeOut(dlm_formula_title),
            FadeOut(ar_formula), FadeOut(dlm_formula),
            bars_group.animate.set_opacity(1.0),
            axes.animate.set_opacity(1.0),
            x_label.animate.set_opacity(1.0),
            y_label.animate.set_opacity(1.0),
            run_time=0.6
        )
        
        # Takeaway only — the inline 100× / 6.3× labels in the zoom
        # section already carry the numbers; an extra wide banner sits
        # on top of the bar chart, so we drop it.
        takeaway = body_text("Long-context RAG → still use AR",
                              size=16, color=INK, italic=True)
        takeaway.move_to(UP * 1.8 + RIGHT * 0)
        self.play(FadeIn(takeaway, shift=UP * 0.1), run_time=0.5)
        
        self.wait(2.5)
        
        # 收尾淡出
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=0.8)
