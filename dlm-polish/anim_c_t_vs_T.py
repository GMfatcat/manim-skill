"""
動畫 C: 訓練連續 t vs 推理離散 T
總時長 ~40 秒

核心 message: 訓練端沒有 step 數，推理端 T 是 config，兩者解耦
- Scene 1 (0-18s): Training side [zoom in t 軸密度]
- Scene 2 (18-34s): Inference side [zoom in T schedule]
- Scene 3 (34-40s): 連接訓練與推理

執行: manim -pqh anim_c_t_vs_T.py SceneC
"""

from manim import *
from shared import *
import random


class SceneC(MovingCameraScene):
    def construct(self):
        setup_scene_background(self)
        random.seed(42)  # 固定亂數種子
        
        # ============ 標題 ============
        title = title_text("Training Continuous t  vs  Inference Discrete T", size=28)
        title.to_edge(UP, buff=0.5)
        self.play(Write(title), run_time=0.8)
        self.wait(0.3)
        
        # ============ Scene 1: Training side (0-18s) ============
        train_label = title_text("Training", size=22, color=WARN)
        train_label.move_to(LEFT * 5.5 + UP * 2.0)
        train_sub = label_text("t ~ Uniform[0, 1]  continuous", size=13)
        train_sub.next_to(train_label, DOWN, buff=0.15, aligned_edge=LEFT)
        
        self.play(FadeIn(train_label, shift=RIGHT * 0.2), FadeIn(train_sub), run_time=0.6)
        
        # 訓練用的 t 軸 (number line)
        train_axis = NumberLine(
            x_range=[0, 1, 0.25],
            length=10,
            color=INK,
            include_numbers=True,
            font_size=15,
            decimal_number_config={"num_decimal_places": 2},
            include_tip=False,
            stroke_width=2,
        )
        train_axis.move_to(UP * 1.0)
        
        # t=0 和 t=1 label
        t0_label = label_text("t = 0", size=12, color=INK_FAINT)
        t0_label.next_to(train_axis.n2p(0), DOWN, buff=0.3)
        t1_label = label_text("t = 1", size=12, color=INK_FAINT)
        t1_label.next_to(train_axis.n2p(1), DOWN, buff=0.3)
        
        self.play(Create(train_axis), FadeIn(t0_label), FadeIn(t1_label), run_time=0.8)
        self.wait(0.3)
        
        # 訓練樣本從天而降，隨機落在 t 軸 (前半部分: 10 個點)
        initial_positions = [0.15, 0.32, 0.48, 0.61, 0.74, 0.81, 0.93, 0.22, 0.55, 0.68]
        initial_dots = VGroup()
        initial_dots_targets = VGroup()
        
        for pos in initial_positions:
            dot = Dot(color=WARN, radius=0.08)
            dot.move_to(train_axis.n2p(pos) + UP * 3)  # 從上方降下
            target = Dot(color=WARN, radius=0.08)
            target.move_to(train_axis.n2p(pos))
            initial_dots.add(dot)
            initial_dots_targets.add(target)
        
        # 依序降下
        for i, (dot, target) in enumerate(zip(initial_dots, initial_dots_targets)):
            self.add(dot)
            self.play(dot.animate.move_to(target.get_center()), run_time=0.15)
        
        # 強調訊息
        sampling_note = mono_text("Each training step samples a random t", size=14, color=INK_SOFT)
        sampling_note.next_to(train_axis, DOWN, buff=0.7)
        self.play(FadeIn(sampling_note), run_time=0.5)
        self.wait(0.5)
        
        # 🔍 Zoom-in #1: 拉近 t 軸中段，強調連續分佈
        self.play(
            self.camera.frame.animate.move_to(UP * 1.0).scale(0.6),
            run_time=1.2,
            rate_func=smooth
        )
        
        # 再撒 ~20 個點，密集分佈
        dense_positions = [random.uniform(0.05, 0.95) for _ in range(20)]
        dense_dots = VGroup()
        for pos in dense_positions:
            dot = Dot(color=WARN, radius=0.05)
            dot.move_to(train_axis.n2p(pos))
            dense_dots.add(dot)
        
        self.play(
            LaggedStart(*[FadeIn(d, scale=2) for d in dense_dots], lag_ratio=0.05),
            run_time=2.0
        )
        
        # 浮現 "no discrete steps" 強調
        no_steps_note = mono_text("No discrete steps · ratio is a real number", size=13, color=WARN)
        no_steps_note.next_to(train_axis, UP, buff=0.5)
        self.play(FadeIn(no_steps_note, shift=DOWN * 0.1), run_time=0.6)
        self.wait(1.0)
        
        # Zoom out
        self.play(
            self.camera.frame.animate.move_to(ORIGIN).scale(1/0.6),
            FadeOut(no_steps_note),
            FadeOut(sampling_note),
            run_time=1.0,
            rate_func=smooth
        )
        
        # 把所有 dots 合併成一組以便後續操作
        all_train_dots = VGroup(initial_dots, dense_dots)
        
        # ============ Scene 2: Inference side (18-34s) ============
        infer_label = title_text("Inference", size=22, color=ACCENT)
        infer_label.move_to(LEFT * 5.5 + DOWN * 0.6)
        infer_sub = label_text("T = config  ·  any value works", size=13)
        infer_sub.next_to(infer_label, DOWN, buff=0.15, aligned_edge=LEFT)
        
        self.play(FadeIn(infer_label, shift=RIGHT * 0.2), FadeIn(infer_sub), run_time=0.6)
        
        # 三條 inference schedule
        schedule_configs = [
            ("T = 4", 4, DOWN * 1.5, ACCENT),
            ("T = 16", 16, DOWN * 2.3, ACCENT),
            ("T = 64", 64, DOWN * 3.1, ACCENT),
        ]
        
        all_schedules = []
        for T_label_str, T, y_pos, color in schedule_configs:
            schedule_axis = NumberLine(
                x_range=[0, 1, 1],
                length=10,
                color=INK,
                include_numbers=False,
                include_tip=False,
                stroke_width=1.5,
            )
            schedule_axis.move_to(y_pos)
            
            # T 標籤
            T_text = mono_text(T_label_str, size=14, color=color, )
            T_text.next_to(schedule_axis, LEFT, buff=0.4)
            
            # tick marks
            ticks = VGroup()
            for k in range(T + 1):
                t_pos = k / T
                tick = Line(
                    schedule_axis.n2p(t_pos) + UP * 0.12,
                    schedule_axis.n2p(t_pos) + DOWN * 0.12,
                    color=color,
                    stroke_width=2 if T <= 16 else 1
                )
                ticks.add(tick)
            
            all_schedules.append((T_label_str, schedule_axis, T_text, ticks, color))
        
        # 依序創建三條 schedule
        for T_label_str, axis, T_text, ticks, color in all_schedules:
            self.play(
                Create(axis),
                FadeIn(T_text),
                run_time=0.4
            )
            self.play(Create(ticks), run_time=0.6)
            self.wait(0.15)
        
        # 🔍 Zoom-in #2: 拉近三條 schedule 並排處
        self.play(
            self.camera.frame.animate.move_to(DOWN * 2.3).scale(0.65),
            run_time=1.2,
            rate_func=smooth
        )
        
        # 在放大狀態下，為 T=16 的某幾個 tick 旁邊浮現對應的 mask ratio 數字
        T16_axis = all_schedules[1][1]
        T16_ticks = all_schedules[1][3]
        sample_tick_indices = [0, 4, 8, 12, 16]
        ratio_labels = VGroup()
        for idx in sample_tick_indices:
            ratio = 1.0 - idx / 16  # mask ratio 從 1.0 → 0.0
            label = mono_text(f"{ratio:.2f}", size=10, color=ACCENT_SOFT)
            label.next_to(T16_ticks[idx], UP, buff=0.1)
            ratio_labels.add(label)
        
        self.play(
            LaggedStart(*[FadeIn(l) for l in ratio_labels], lag_ratio=0.15),
            run_time=1.0
        )
        
        # 強調訊息
        config_note = mono_text("Same checkpoint  ·  T is just a runtime parameter", 
                                 size=13, color=ACCENT)
        config_note.next_to(all_schedules[2][1], DOWN, buff=0.5)
        self.play(FadeIn(config_note, shift=UP * 0.1), run_time=0.6)
        self.wait(1.2)
        
        # Zoom out
        self.play(
            self.camera.frame.animate.move_to(ORIGIN).scale(1/0.65),
            FadeOut(ratio_labels),
            FadeOut(config_note),
            run_time=1.0,
            rate_func=smooth
        )
        
        # ============ Scene 3: 連接訓練與推理 (34-40s) ============
        # 在訓練 t 軸右側出現一個 checkpoint icon
        checkpoint_icon = VGroup(
            Rectangle(width=1.2, height=0.6, 
                      fill_color=BG_CARD, fill_opacity=1,
                      stroke_color=ACCENT, stroke_width=2),
            mono_text("ckpt", size=14, color=ACCENT)
        )
        checkpoint_icon.move_to(RIGHT * 5.8 + UP * 1.0)
        
        self.play(FadeIn(checkpoint_icon, scale=1.2), run_time=0.5)
        
        # 三條箭頭從 checkpoint 指向三條 inference schedule
        arrows = VGroup()
        for _, axis, _, _, color in all_schedules:
            arrow = Arrow(
                checkpoint_icon.get_bottom() + DOWN * 0.05,
                axis.get_right() + RIGHT * 0.15,
                buff=0.1, color=ACCENT_SOFT, stroke_width=2,
                max_tip_length_to_length_ratio=0.04
            )
            arrows.add(arrow)
        
        self.play(
            LaggedStart(*[Create(a) for a in arrows], lag_ratio=0.2),
            run_time=1.0
        )
        
        # 最終 takeaway
        takeaway = body_text("One model · any T at inference · no retraining", 
                              size=18, color=INK, italic=True)
        takeaway.next_to(all_schedules[2][1], DOWN, buff=0.8)
        self.play(FadeIn(takeaway, shift=UP * 0.2), run_time=0.7)
        self.wait(2.0)
        
        # 收尾淡出
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=0.8)
