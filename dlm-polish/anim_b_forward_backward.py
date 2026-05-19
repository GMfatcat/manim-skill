"""
動畫 B: Forward / Backward Masking
總時長 ~55 秒

核心 message: 訓練時加噪、推理時去噪，兩者鏡像對稱
- Scene 1 (0-5s): 上下分屏
- Scene 2 (5-25s): Training forward 加噪 [zoom in t 採樣]
- Scene 3 (25-45s): Inference backward 去噪 [zoom in confidence commit]
- Scene 4 (45-55s): 對比強調

執行: manim -pqh anim_b_forward_backward.py SceneB
"""

from manim import *
from shared import *


class SceneB(MovingCameraScene):
    def construct(self):
        setup_scene_background(self)
        
        # ============ Scene 1: 上下分屏 (0-5s) ============
        title = title_text("Training / Inference Mirror Process", size=32)
        title.to_edge(UP, buff=0.4)
        self.play(Write(title), run_time=0.8)
        
        # 中間分隔線
        divider = DashedLine(LEFT * 6, RIGHT * 6, color=RULE, dash_length=0.15)
        divider.move_to(DOWN * 0.1)
        
        # 上方標籤: Training (forward 加噪)
        train_label = title_text("Training — Forward (加噪)", size=22, color=WARN)
        train_label.move_to(LEFT * 4 + UP * 2.5)
        
        # 下方標籤: Inference (backward 去噪)
        infer_label = title_text("Inference — Backward (去噪)", size=22, color=ACCENT)
        infer_label.move_to(LEFT * 4 + DOWN * 1.5)
        
        self.play(
            Create(divider),
            FadeIn(train_label, shift=DOWN * 0.2),
            FadeIn(infer_label, shift=UP * 0.2),
            run_time=0.8
        )
        self.wait(0.4)
        
        # ============ Scene 2: Training forward 加噪 (5-25s) ============
        # 顯示 5 個 token 在 t=0 (全部乾淨)
        tokens_text = ["The", "cat", "sat", "on", "mat"]
        train_boxes = VGroup()
        for i, tok in enumerate(tokens_text):
            box = make_token_box(text=tok, width=0.85, height=0.65, font_size=16)
            box.move_to(RIGHT * (i * 0.95) + UP * 1.5)
            train_boxes.add(box)
        train_boxes.move_to(RIGHT * 0.5 + UP * 1.5)
        
        # t 軸 (在訓練區下方)
        t_axis = NumberLine(
            x_range=[0, 1, 0.25],
            length=5,
            color=INK_FAINT,
            include_numbers=True,
            font_size=14,
            decimal_number_config={"num_decimal_places": 2},
            include_tip=False,
        )
        t_axis.move_to(RIGHT * 0.5 + UP * 0.55)
        
        t_axis_label = label_text("t (mask ratio)", size=13, color=INK_FAINT)
        t_axis_label.next_to(t_axis, DOWN, buff=0.1)
        
        self.play(FadeIn(train_boxes), run_time=0.6)
        self.play(Create(t_axis), FadeIn(t_axis_label), run_time=0.5)
        
        # 用一個 dot 在 t 軸上跳動表示「連續採樣」
        t_dot = Dot(color=WARN, radius=0.1)
        t_dot.move_to(t_axis.n2p(0))
        
        # t 值 label
        t_value = mono_text("t = 0.00", size=14, color=WARN)
        t_value.next_to(t_dot, UP, buff=0.15)
        
        self.play(FadeIn(t_dot), FadeIn(t_value), run_time=0.4)
        
        # 各個 t 值對應的 mask 比例
        t_demo_values = [
            (0.0, []),
            (0.3, [1]),
            (0.5, [0, 3]),
            (0.7, [0, 1, 4]),
            (0.9, [0, 1, 2, 4]),
            (1.0, [0, 1, 2, 3, 4]),
        ]
        
        for t_val, mask_indices in t_demo_values[1:]:
            new_t_dot_pos = t_axis.n2p(t_val)
            new_t_value = mono_text(f"t = {t_val:.2f}", size=14, color=WARN)
            new_t_value.next_to(Point(new_t_dot_pos), UP, buff=0.15)
            
            # 更新對應的 box 為 mask
            box_animations = []
            for i in range(5):
                if i in mask_indices:
                    new_box = make_token_box(masked=True, width=0.85, height=0.65, font_size=16)
                else:
                    new_box = make_token_box(text=tokens_text[i], width=0.85, height=0.65, font_size=16)
                new_box.move_to(train_boxes[i].get_center())
                box_animations.append(Transform(train_boxes[i], new_box))
            
            self.play(
                t_dot.animate.move_to(new_t_dot_pos),
                Transform(t_value, new_t_value),
                *box_animations,
                run_time=0.6
            )
            self.wait(0.15)
        
        # 🔍 Zoom-in #1: 拉近 t 軸區域，強調連續採樣
        self.play(
            self.camera.frame.animate.move_to(RIGHT * 0.5 + UP * 0.6).scale(0.6),
            run_time=1.2,
            rate_func=smooth
        )
        
        # 在放大狀態下，撒下更多紅點代表「t ~ Uniform[0, 1]」
        random_samples = VGroup()
        sample_positions = [0.12, 0.27, 0.41, 0.58, 0.73, 0.84, 0.92, 0.19, 0.35, 0.66]
        for pos in sample_positions:
            dot = Dot(color=WARN, radius=0.06)
            dot.move_to(t_axis.n2p(pos))
            random_samples.add(dot)
        
        self.play(
            LaggedStart(*[FadeIn(d, scale=2) for d in random_samples], lag_ratio=0.08),
            run_time=1.5
        )
        
        sampling_note = mono_text("t ~ Uniform[0, 1] · continuous", size=14, color=WARN)
        sampling_note.next_to(t_axis, DOWN, buff=0.5)
        self.play(FadeIn(sampling_note, shift=UP * 0.1), run_time=0.5)
        
        # Loss 公式浮現
        loss_formula = mono_text("L = E_t [ (1/t) · Σ -log P(x | x_t) ]", size=13, color=INK_SOFT)
        loss_formula.next_to(sampling_note, DOWN, buff=0.2)
        self.play(FadeIn(loss_formula), run_time=0.6)
        self.wait(1.0)
        
        # Zoom out
        self.play(
            self.camera.frame.animate.move_to(ORIGIN).scale(1/0.6),
            FadeOut(random_samples),
            FadeOut(sampling_note),
            FadeOut(loss_formula),
            run_time=1.0,
            rate_func=smooth
        )
        
        # 收尾 training side: 全部 mask
        final_train_boxes = VGroup()
        for i in range(5):
            box = make_token_box(masked=True, width=0.85, height=0.65, font_size=16)
            box.move_to(train_boxes[i].get_center())
            final_train_boxes.add(box)
        
        self.play(Transform(train_boxes, final_train_boxes), run_time=0.5)
        
        # ============ Scene 3: Inference backward 去噪 (25-45s) ============
        # 顯示 5 個全 mask 的 box 在下方
        infer_boxes = VGroup()
        for i in range(5):
            box = make_token_box(masked=True, width=0.85, height=0.65, font_size=16)
            box.move_to(RIGHT * (i * 0.95) + DOWN * 2.6)
            infer_boxes.add(box)
        infer_boxes.move_to(RIGHT * 0.5 + DOWN * 2.6)
        
        # s (denoising step) 標籤
        s_label = mono_text("s = T", size=16, color=ACCENT)
        s_label.move_to(LEFT * 4 + DOWN * 2.6)
        
        self.play(FadeIn(infer_boxes), FadeIn(s_label), run_time=0.6)
        self.wait(0.3)
        
        # 🔍 Zoom-in #2: 拉近 inference 區，展示 confidence commit
        self.play(
            self.camera.frame.animate.move_to(DOWN * 2.6).scale(0.6),
            run_time=1.2,
            rate_func=smooth
        )
        
        # 模擬 confidence-based commit
        # 第一輪: confidence 高的位置先敲定
        commit_steps = [
            # (要敲定的 idx, confidence scores, s 值, 此輪結束的 unmask 狀態)
            ([0, 4], [0.92, 0.31, 0.45, 0.52, 0.88], "s = T-1"),
            ([1, 3], [None, 0.85, 0.49, 0.81, None], "s = T-2"),
            ([2], [None, None, 0.79, None, None], "s = 0"),
        ]
        
        for commit_indices, confidences, new_s_str in commit_steps:
            # 先顯示 confidence scores
            conf_labels = VGroup()
            for i, conf in enumerate(confidences):
                if conf is not None:
                    color = WARN if conf > 0.75 else INK_FAINT
                    conf_label = mono_text(f"{conf:.2f}", size=10, color=color)
                    conf_label.next_to(infer_boxes[i], UP, buff=0.1)
                    conf_labels.add(conf_label)
            
            self.play(FadeIn(conf_labels), run_time=0.4)
            self.wait(0.3)
            
            # 敲定高 confidence 位置
            commit_animations = []
            new_s_label = mono_text(new_s_str, size=16, color=ACCENT)
            new_s_label.move_to(s_label.get_center())
            commit_animations.append(Transform(s_label, new_s_label))
            
            for idx in commit_indices:
                new_box = make_token_box(text=tokens_text[idx], width=0.85, height=0.65, font_size=16)
                new_box.move_to(infer_boxes[idx].get_center())
                commit_animations.append(Transform(infer_boxes[idx], new_box))
            
            self.play(*commit_animations, run_time=0.7)
            self.play(FadeOut(conf_labels), run_time=0.3)
            self.wait(0.2)
        
        # 強調 "confidence-driven, not left-to-right"
        infer_note = mono_text("✓ confidence-driven · not left-to-right", size=13, color=ACCENT)
        infer_note.next_to(infer_boxes, DOWN, buff=0.4)
        self.play(FadeIn(infer_note, shift=UP * 0.1), run_time=0.5)
        self.wait(0.6)
        
        # Zoom out
        self.play(
            self.camera.frame.animate.move_to(ORIGIN).scale(1/0.6),
            run_time=1.0,
            rate_func=smooth
        )
        
        # ============ Scene 4: 對比強調 (45-55s) ============
        # 移除 inference note 讓畫面更乾淨
        self.play(FadeOut(infer_note), run_time=0.3)
        
        # 中間箭頭和總結
        mirror_arrow = Arrow(
            UP * 1.5, DOWN * 1.8,
            buff=0.2, color=ACCENT_SOFT, stroke_width=3,
            max_tip_length_to_length_ratio=0.05
        )
        mirror_arrow.move_to(RIGHT * 4 + ORIGIN)
        
        self.play(Create(mirror_arrow), run_time=0.6)
        self.wait(2.5)
        
        # 收尾淡出
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=0.8)
