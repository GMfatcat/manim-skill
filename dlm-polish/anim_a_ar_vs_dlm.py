"""
動畫 A: AR vs dLM 生成對比
總時長 ~45 秒

核心 message: 兩種範式的本質差異 — 序列 vs 並行
- Scene 1 (0-5s): 標題與設定
- Scene 2 (5-20s): AR 序列生成 [zoom in AR]
- Scene 3 (20-35s): dLM 並行生成 [zoom in dLM]
- Scene 4 (35-45s): 並列回放

執行: manim -pqh anim_a_ar_vs_dlm.py SceneA
"""

from manim import *
from shared import *


class SceneA(MovingCameraScene):
    def construct(self):
        setup_scene_background(self)
        
        # ============ Scene 1: 標題與設定 (0-5s) ============
        title = title_text("AR vs dLM 生成過程", size=36)
        title.to_edge(UP, buff=0.6)
        
        self.play(Write(title), run_time=0.8)
        self.wait(0.5)
        
        # 左右分區標題
        ar_header = title_text("Autoregressive", size=24, color=ACCENT)
        ar_header.move_to(LEFT * 3.5 + UP * 1.8)
        ar_sub = label_text("Sequential · 1 token per step", size=13)
        ar_sub.next_to(ar_header, DOWN, buff=0.15)
        
        dlm_header = title_text("Diffusion (dLM)", size=24, color=WARN)
        dlm_header.move_to(RIGHT * 3.5 + UP * 1.8)
        dlm_sub = label_text("Parallel · all positions per step", size=13)
        dlm_sub.next_to(dlm_header, DOWN, buff=0.15)
        
        divider = DashedLine(UP * 2.5, DOWN * 3, color=RULE, dash_length=0.1)
        
        self.play(
            FadeIn(ar_header, shift=LEFT * 0.3),
            FadeIn(dlm_header, shift=RIGHT * 0.3),
            run_time=0.8
        )
        self.play(FadeIn(ar_sub), FadeIn(dlm_sub), Create(divider), run_time=0.5)
        self.wait(0.5)
        
        # ============ Scene 2: AR 序列生成 (5-20s) ============
        tokens_correct = ["The", "cat", "sat", "on", "mat"]
        ar_boxes = VGroup()
        ar_box_size = 0.85
        for i in range(5):
            box = make_token_box(masked=True, width=ar_box_size, height=0.7)
            box.move_to(LEFT * 5.5 + RIGHT * (i * 0.95) + DOWN * 0.5)
            ar_boxes.add(box)
        
        # AR 步驟標籤
        ar_step_label = label_text("t = 1", size=14, color=ACCENT)
        ar_step_label.move_to(LEFT * 6.3 + DOWN * 0.5)
        
        self.play(FadeIn(ar_boxes), run_time=0.5)
        self.play(FadeIn(ar_step_label), run_time=0.3)
        self.wait(0.3)
        
        # 🔍 Zoom-in #1: 拉近 AR 區
        self.play(
            self.camera.frame.animate.move_to(LEFT * 3.5 + DOWN * 0.3).scale(0.65),
            run_time=1.2,
            rate_func=smooth
        )
        
        # 依序填入 AR token
        for i in range(5):
            new_box = make_token_box(text=tokens_correct[i], width=ar_box_size, height=0.7)
            new_box.move_to(ar_boxes[i].get_center())
            
            new_step_label = label_text(f"t = {i+1}", size=14, color=ACCENT)
            new_step_label.move_to(ar_step_label.get_center())
            
            self.play(
                Transform(ar_boxes[i], new_box),
                Transform(ar_step_label, new_step_label),
                run_time=0.6
            )
            
            # 強調: AR 是嚴格依賴前面的 token
            if i < 4:
                # 從已填入的格子畫一個小箭頭指向下一格
                arrow = Arrow(
                    ar_boxes[i].get_top() + UP * 0.05,
                    ar_boxes[i+1].get_top() + UP * 0.05,
                    buff=0.05, color=ACCENT_SOFT, stroke_width=2,
                    max_tip_length_to_length_ratio=0.15
                )
                arrow.shift(UP * 0.3)
                self.play(Create(arrow), run_time=0.3)
                self.play(FadeOut(arrow), run_time=0.2)
            else:
                self.wait(0.2)
        
        # AR 完成註記
        ar_done = mono_text("✓ 5 steps", size=14, color=ACCENT)
        ar_done.next_to(ar_boxes, DOWN, buff=0.5)
        self.play(FadeIn(ar_done, shift=UP * 0.1), run_time=0.5)
        
        # Zoom out
        self.play(
            self.camera.frame.animate.move_to(ORIGIN).scale(1/0.65),
            run_time=1.0,
            rate_func=smooth
        )
        
        # ============ Scene 3: dLM 並行生成 (20-35s) ============
        dlm_boxes = VGroup()
        for i in range(5):
            box = make_token_box(masked=True, width=ar_box_size, height=0.7)
            box.move_to(RIGHT * 1.5 + RIGHT * (i * 0.95) + DOWN * 0.5)
            dlm_boxes.add(box)
        
        dlm_step_label = label_text("s = T", size=14, color=WARN)
        dlm_step_label.move_to(RIGHT * 0.7 + DOWN * 0.5)
        
        self.play(FadeIn(dlm_boxes), FadeIn(dlm_step_label), run_time=0.6)
        self.wait(0.3)
        
        # 🔍 Zoom-in #2: 拉近 dLM 區
        self.play(
            self.camera.frame.animate.move_to(RIGHT * 3.7 + DOWN * 0.3).scale(0.65),
            run_time=1.2,
            rate_func=smooth
        )
        
        # dLM 並行生成: 每步同時更新多個位置
        # s=T → s=T-1: 敲定 "The" (idx 0) 和 "mat" (idx 4) — 不相鄰，按 confidence
        # s=T-1 → s=T-2: 敲定 "cat" (idx 1) 和 "on" (idx 3)
        # s=T-2 → s=0: 敲定 "sat" (idx 2)
        
        commit_schedule = [
            ([0, 4], "s = T-1"),  # 第一輪同時敲定兩個非相鄰位置
            ([1, 3], "s = T-2"),  # 第二輪
            ([2], "s = 0"),       # 最後一輪
        ]
        
        # 添加 confidence 標籤（簡化版）
        for indices, step_label_str in commit_schedule:
            new_step_label = label_text(step_label_str, size=14, color=WARN)
            new_step_label.move_to(dlm_step_label.get_center())
            
            # 為這一輪要敲定的位置同時做 transform
            animations = [Transform(dlm_step_label, new_step_label)]
            
            # 顯示 "parallel update" 提示
            for idx in indices:
                new_box = make_token_box(text=tokens_correct[idx], width=ar_box_size, height=0.7)
                new_box.move_to(dlm_boxes[idx].get_center())
                animations.append(Transform(dlm_boxes[idx], new_box))
            
            self.play(*animations, run_time=0.9)
            
            # 標示「同時敲定」的視覺
            if len(indices) > 1:
                hint_lines = VGroup()
                for idx in indices:
                    pulse = Circle(radius=0.5, color=WARN, stroke_width=2)
                    pulse.move_to(dlm_boxes[idx].get_center())
                    hint_lines.add(pulse)
                self.play(
                    *[Create(p) for p in hint_lines],
                    rate_func=there_and_back,
                    run_time=0.6
                )
                self.play(FadeOut(hint_lines), run_time=0.2)
            else:
                self.wait(0.3)
        
        # dLM 完成註記
        dlm_done = mono_text("✓ 3 steps", size=14, color=WARN)
        dlm_done.next_to(dlm_boxes, DOWN, buff=0.5)
        self.play(FadeIn(dlm_done, shift=UP * 0.1), run_time=0.5)
        
        # Zoom out
        self.play(
            self.camera.frame.animate.move_to(ORIGIN).scale(1/0.65),
            run_time=1.0,
            rate_func=smooth
        )
        
        # ============ Scene 4: 並列回放 + 結論 (35-45s) ============
        self.wait(0.3)
        
        # 結論文字浮現
        conclusion_bg = Rectangle(
            width=10, height=1.2,
            fill_color=BG_CARD, fill_opacity=1,
            stroke_color=RULE_SOFT, stroke_width=1
        )
        conclusion_bg.move_to(DOWN * 2.5)
        
        conclusion_left = mono_text("AR · 5 steps", size=18, color=ACCENT)
        conclusion_left.move_to(LEFT * 2.8 + DOWN * 2.5)

        vs_text = mono_text("vs", size=16, color=INK_FAINT)
        vs_text.move_to(DOWN * 2.5)

        conclusion_right = mono_text("dLM · 3 steps", size=18, color=WARN)
        conclusion_right.move_to(RIGHT * 2.8 + DOWN * 2.5)
        
        self.play(FadeIn(conclusion_bg), run_time=0.4)
        self.play(
            Write(conclusion_left),
            FadeIn(vs_text),
            Write(conclusion_right),
            run_time=1.0
        )
        self.wait(2.0)
        
        # 收尾淡出
        self.play(
            *[FadeOut(m) for m in self.mobjects],
            run_time=0.8
        )
