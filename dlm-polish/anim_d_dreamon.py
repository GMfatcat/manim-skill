"""
動畫 D: DreamOn expand/delete 機制
總時長 ~65 秒

核心 message: dLM 不能變長 → DreamOn 用兩個 sentinel token 解決
- Scene 1 (0-12s): 痛點呈現
- Scene 2 (12-24s): 引入兩個新 token [zoom in vocab]
- Scene 3 (24-40s): 演示 expand [zoom in expand 動作]
- Scene 4 (40-52s): 演示 delete [zoom in delete 動作]
- Scene 5 (52-65s): 同步展示 (Fig 6 風格)

執行: manim -pqh anim_d_dreamon.py SceneD
"""

from manim import *
from shared import *


class SceneD(MovingCameraScene):
    def construct(self):
        setup_scene_background(self)
        
        title = title_text("DreamOn — Dynamic Length via Sentinel Tokens", size=28)
        title.to_edge(UP, buff=0.4)
        self.play(Write(title), run_time=0.8)
        self.wait(0.3)
        
        # ============ Scene 1: 痛點呈現 (0-12s) ============
        # prefix + 8 個 mask + suffix
        prefix_box = make_token_box(text="def foo(x):", width=1.8, height=0.7, font_size=13)
        prefix_box.move_to(LEFT * 4.5 + UP * 0.5)
        
        mask_boxes = VGroup()
        for i in range(8):
            box = make_token_box(text="?", masked=True, width=0.55, height=0.7, font_size=14)
            box.move_to(LEFT * 2.5 + RIGHT * (i * 0.6) + UP * 0.5)
            mask_boxes.add(box)
        
        suffix_box = make_token_box(text="return r", width=1.5, height=0.7, font_size=13)
        suffix_box.move_to(RIGHT * 3.5 + UP * 0.5)
        
        self.play(
            FadeIn(prefix_box, shift=RIGHT * 0.1),
            FadeIn(mask_boxes),
            FadeIn(suffix_box, shift=LEFT * 0.1),
            run_time=0.8
        )
        
        # 註記: 8 mask 不夠 (假設要 12 個 token)
        need_label = mono_text("Need ~12 tokens, but only 8 mask slots", size=14, color=WARN)
        need_label.next_to(mask_boxes, DOWN, buff=0.6)
        self.play(FadeIn(need_label), run_time=0.5)
        
        # 文字溢出視覺: 在 mask 區強行擠入過長文字
        overflow_text = mono_text("r = compute_long_result_x", size=12, color=WARN)
        overflow_text.move_to(mask_boxes.get_center())
        
        # 紅色警告框圍繞 mask 區
        warning_rect = SurroundingRectangle(mask_boxes, color=WARN, stroke_width=3, buff=0.05)
        
        self.play(
            FadeIn(overflow_text),
            Create(warning_rect),
            run_time=0.6
        )
        self.wait(0.4)
        
        # Pass@1 ↓ 數據
        pass_drop = mono_text("Pass@1 ↓ 35.5% (when length mismatch)", size=14, color=WARN)
        pass_drop.next_to(need_label, DOWN, buff=0.3)
        self.play(FadeIn(pass_drop, shift=UP * 0.1), run_time=0.5)
        self.wait(1.5)
        
        # 清除痛點場景
        self.play(
            FadeOut(prefix_box), FadeOut(mask_boxes), FadeOut(suffix_box),
            FadeOut(overflow_text), FadeOut(warning_rect),
            FadeOut(need_label), FadeOut(pass_drop),
            run_time=0.6
        )
        
        # ============ Scene 2: 引入兩個新 token (12-24s) ============
        # Vocabulary 展示
        vocab_title = label_text("Vocabulary", size=14, color=INK_FAINT)
        vocab_title.move_to(LEFT * 4 + UP * 1.8)
        
        # 普通 token (灰色排列)
        normal_tokens = ["def", "return", "x", "+1", "if", "while", "..."]
        normal_token_group = VGroup()
        for i, tok in enumerate(normal_tokens):
            box = Rectangle(width=0.9, height=0.45,
                            fill_color=BG_CODE, fill_opacity=1,
                            stroke_color=RULE, stroke_width=1)
            label = mono_text(tok, size=12, color=INK_FAINT)
            label.move_to(box.get_center())
            grp = VGroup(box, label)
            grp.move_to(LEFT * 4.7 + RIGHT * (i * 1.0) + UP * 1.0)
            normal_token_group.add(grp)
        
        self.play(FadeIn(normal_token_group), run_time=0.8)
        
        # 兩個新 token 高亮浮現
        expand_token_box = Rectangle(width=1.7, height=0.6,
                                      fill_color=EXPAND_BG, fill_opacity=1,
                                      stroke_color=EXPAND, stroke_width=2.5)
        expand_label = mono_text("<|expand|>", size=14, color=EXPAND, )
        expand_label.move_to(expand_token_box.get_center())
        expand_group = VGroup(expand_token_box, expand_label)
        expand_group.move_to(LEFT * 2.5 + DOWN * 0.3)
        
        delete_token_box = Rectangle(width=1.7, height=0.6,
                                      fill_color=DELETE_BG, fill_opacity=1,
                                      stroke_color=WARN, stroke_width=2.5)
        delete_label = mono_text("<|delete|>", size=14, color=WARN, )
        delete_label.move_to(delete_token_box.get_center())
        delete_group = VGroup(delete_token_box, delete_label)
        delete_group.move_to(RIGHT * 2.5 + DOWN * 0.3)
        
        # 🔍 Zoom-in #1: 拉近 vocab 區
        self.play(
            self.camera.frame.animate.move_to(DOWN * 0.3).scale(0.7),
            run_time=1.0,
            rate_func=smooth
        )
        
        self.play(
            FadeIn(expand_group, shift=UP * 0.2, scale=1.2),
            FadeIn(delete_group, shift=UP * 0.2, scale=1.2),
            run_time=0.8
        )
        
        # 詳細註解
        expand_note = body_text("展開為 2 個新 mask", size=14, color=EXPAND, italic=True)
        expand_note.next_to(expand_group, DOWN, buff=0.25)
        
        delete_note = body_text("從序列中移除", size=14, color=WARN, italic=True)
        delete_note.next_to(delete_group, DOWN, buff=0.25)
        
        self.play(FadeIn(expand_note), FadeIn(delete_note), run_time=0.5)
        self.wait(0.8)
        
        key_insight = body_text(
            "Just 2 more tokens in vocab · loss & architecture unchanged",
            size=15, color=INK, italic=True
        )
        key_insight.move_to(DOWN * 1.7)
        self.play(FadeIn(key_insight, shift=UP * 0.1), run_time=0.6)
        self.wait(1.2)
        
        # Zoom out
        self.play(
            self.camera.frame.animate.move_to(ORIGIN).scale(1/0.7),
            run_time=1.0,
            rate_func=smooth
        )
        
        # 清除 scene 2 (保留 expand/delete group 作為 reference)
        self.play(
            FadeOut(normal_token_group),
            FadeOut(vocab_title),
            FadeOut(expand_note),
            FadeOut(delete_note),
            FadeOut(key_insight),
            expand_group.animate.scale(0.7).move_to(LEFT * 5.5 + UP * 3),
            delete_group.animate.scale(0.7).move_to(RIGHT * 5.5 + UP * 3),
            run_time=0.7
        )
        
        # ============ Scene 3: 演示 expand (24-40s) ============
        section_label = label_text("Case A: initial mask too short → expand", size=14, color=EXPAND)
        section_label.move_to(UP * 1.8)
        self.play(FadeIn(section_label), run_time=0.4)
        
        # 5 個初始 mask (太短)
        seq_boxes = VGroup()
        for i in range(5):
            box = make_token_box(text="?", masked=True, width=0.7, height=0.7, font_size=14)
            box.move_to(LEFT * 1.5 + RIGHT * (i * 0.8))
            seq_boxes.add(box)
        seq_boxes.move_to(ORIGIN)
        
        # 序列長度顯示
        len_label = mono_text("len = 5", size=16, color=INK_SOFT)
        len_label.next_to(seq_boxes, DOWN, buff=0.5)
        
        self.play(FadeIn(seq_boxes), FadeIn(len_label), run_time=0.6)
        self.wait(0.3)
        
        # 🔍 Zoom-in #2: 拉近 sequence 區，展示 expand 動作
        self.play(
            self.camera.frame.animate.move_to(ORIGIN + DOWN * 0.2).scale(0.7),
            run_time=1.0,
            rate_func=smooth
        )
        
        # 第一輪: 預測結果 - 2 個普通 token, 1 個 expand, 2 個 defer
        # idx 0: "x" (普通)
        # idx 1: defer
        # idx 2: <|expand|> (黃色閃爍 → 分裂)
        # idx 3: defer  
        # idx 4: "1" (普通)
        
        commit_round1 = [
            (0, "x", "filled"),
            (2, "EXP", "expand"),
            (4, "1", "filled"),
        ]
        
        # Step 1: 顯示預測結果 (先把 expand 位置標黃)
        round1_animations = []
        for idx, text, action in commit_round1:
            if action == "filled":
                new_box = make_token_box(text=text, width=0.7, height=0.7, font_size=14)
            elif action == "expand":
                new_box = make_token_box(text="EXP", expand=True, width=0.7, height=0.7, font_size=10)
            new_box.move_to(seq_boxes[idx].get_center())
            round1_animations.append(Transform(seq_boxes[idx], new_box))
        
        self.play(*round1_animations, run_time=0.7)
        self.wait(0.4)
        
        # 黃色 expand 框 pulse
        expand_idx = 2
        pulse = Circle(radius=0.5, color=EXPAND, stroke_width=3)
        pulse.move_to(seq_boxes[expand_idx].get_center())
        self.play(Create(pulse), rate_func=there_and_back, run_time=0.8)
        self.play(FadeOut(pulse), run_time=0.2)
        
        # Expand 動作: 原地分裂為 2 個 mask, 右邊的格子向右滑動
        new_mask_1 = make_token_box(text="?", masked=True, width=0.7, height=0.7, font_size=14)
        new_mask_2 = make_token_box(text="?", masked=True, width=0.7, height=0.7, font_size=14)
        
        # 新位置: 原本 idx=2 變成兩格、idx 3,4 向右移
        expand_target_pos = seq_boxes[expand_idx].get_center()
        new_mask_1.move_to(expand_target_pos + LEFT * 0.4)
        new_mask_2.move_to(expand_target_pos + RIGHT * 0.4)
        
        # 右邊兩格向右滑動 0.8 距離
        original_idx3_pos = seq_boxes[3].get_center()
        original_idx4_pos = seq_boxes[4].get_center()
        
        self.play(
            FadeOut(seq_boxes[expand_idx], scale=0.5),
            seq_boxes[3].animate.move_to(original_idx3_pos + RIGHT * 0.8),
            seq_boxes[4].animate.move_to(original_idx4_pos + RIGHT * 0.8),
            run_time=0.6
        )
        self.play(
            FadeIn(new_mask_1, scale=1.3),
            FadeIn(new_mask_2, scale=1.3),
            run_time=0.5
        )
        
        # 更新長度顯示
        new_len_label = mono_text("len = 6", size=16, color=EXPAND)
        new_len_label.move_to(len_label.get_center())
        self.play(Transform(len_label, new_len_label), run_time=0.4)
        self.wait(0.5)
        
        self.wait(1.0)
        
        # Zoom out
        self.play(
            self.camera.frame.animate.move_to(ORIGIN).scale(1/0.7),
            run_time=1.0,
            rate_func=smooth
        )
        
        # 清除 expand scene
        self.play(
            FadeOut(seq_boxes[0]), FadeOut(seq_boxes[1]),
            FadeOut(seq_boxes[3]), FadeOut(seq_boxes[4]),
            FadeOut(new_mask_1), FadeOut(new_mask_2),
            FadeOut(len_label), FadeOut(section_label),
            run_time=0.6
        )
        
        # ============ Scene 4: 演示 delete (40-52s) ============
        section_label_2 = label_text("Case B: initial mask too long → delete", size=14, color=WARN)
        section_label_2.move_to(UP * 1.8)
        self.play(FadeIn(section_label_2), run_time=0.4)
        
        # 8 個初始 mask (太多)
        seq_boxes_2 = VGroup()
        for i in range(8):
            box = make_token_box(text="?", masked=True, width=0.6, height=0.7, font_size=14)
            box.move_to(LEFT * 2.45 + RIGHT * (i * 0.7))
            seq_boxes_2.add(box)
        seq_boxes_2.move_to(ORIGIN)
        
        len_label_2 = mono_text("len = 8 (too many)", size=16, color=INK_SOFT)
        len_label_2.next_to(seq_boxes_2, DOWN, buff=0.5)
        
        self.play(FadeIn(seq_boxes_2), FadeIn(len_label_2), run_time=0.6)
        self.wait(0.3)
        
        # 🔍 Zoom-in #3: 拉近 delete 動作
        self.play(
            self.camera.frame.animate.move_to(ORIGIN + DOWN * 0.2).scale(0.7),
            run_time=1.0,
            rate_func=smooth
        )
        
        # 預測: 5 個 token + 3 個 delete (idx 2, 5, 7)
        delete_indices = [2, 5, 7]
        commit_round2 = [
            (0, "x"),
            (1, "+"),
            (3, "y"),
            (4, "*"),
            (6, "2"),
        ]
        
        # Step 1: 顯示預測結果
        round2_animations = []
        for idx, text in commit_round2:
            new_box = make_token_box(text=text, width=0.6, height=0.7, font_size=14)
            new_box.move_to(seq_boxes_2[idx].get_center())
            round2_animations.append(Transform(seq_boxes_2[idx], new_box))
        
        for idx in delete_indices:
            new_box = make_token_box(text="DEL", delete=True, width=0.6, height=0.7, font_size=10)
            new_box.move_to(seq_boxes_2[idx].get_center())
            round2_animations.append(Transform(seq_boxes_2[idx], new_box))
        
        self.play(*round2_animations, run_time=0.8)
        self.wait(0.4)
        
        # 紅色 delete pulse
        delete_pulses = VGroup()
        for idx in delete_indices:
            pulse = Circle(radius=0.4, color=WARN, stroke_width=2.5)
            pulse.move_to(seq_boxes_2[idx].get_center())
            delete_pulses.add(pulse)
        
        self.play(*[Create(p) for p in delete_pulses], 
                  rate_func=there_and_back, run_time=0.7)
        self.play(FadeOut(delete_pulses), run_time=0.2)
        
        # Delete 動作: 3 個格子溶解 + 右邊格子向左塌縮填補
        # 收集存活的 boxes 和它們的目標位置
        survivors = []
        survivor_targets = []
        survivor_idx_counter = 0
        for i in range(8):
            if i not in delete_indices:
                survivors.append(seq_boxes_2[i])
                # 新位置: 從左到右重新排列
                new_pos = LEFT * 1.4 + RIGHT * (survivor_idx_counter * 0.7)
                survivor_targets.append(new_pos)
                survivor_idx_counter += 1
        
        # 同時: delete 格子淡出 + survivors 向左移動
        delete_fades = [FadeOut(seq_boxes_2[i], scale=0.3) for i in delete_indices]
        survivor_moves = [
            survivor.animate.move_to(target)
            for survivor, target in zip(survivors, survivor_targets)
        ]
        
        self.play(*delete_fades, *survivor_moves, run_time=0.9)
        
        # 更新長度
        new_len_label_2 = mono_text("len = 5", size=16, color=WARN)
        new_len_label_2.move_to(len_label_2.get_center())
        self.play(Transform(len_label_2, new_len_label_2), run_time=0.4)
        
        delete_done_note = mono_text("✓ -3 slots · sequence cleaner", size=12, color=WARN)
        delete_done_note.next_to(len_label_2, DOWN, buff=0.3)
        self.play(FadeIn(delete_done_note), run_time=0.4)
        self.wait(1.0)
        
        # Zoom out
        self.play(
            self.camera.frame.animate.move_to(ORIGIN).scale(1/0.7),
            run_time=1.0,
            rate_func=smooth
        )
        
        # 清除
        self.play(
            *[FadeOut(s) for s in survivors],
            FadeOut(len_label_2), FadeOut(section_label_2), FadeOut(delete_done_note),
            run_time=0.6
        )
        
        # ============ Scene 5: 同步展示 (52-65s) ============
        sync_label = label_text("All four commit paths in ONE forward pass", size=16, color=INK)
        sync_label.move_to(UP * 2.0)
        self.play(FadeIn(sync_label), run_time=0.5)
        
        # Step n
        step_n_label = mono_text("Step n", size=14, color=INK_SOFT)
        step_n_label.move_to(LEFT * 5 + UP * 0.8)
        
        step_n_boxes = VGroup()
        # A(filled), ?(mask), ?(mask), B(filled), ?(mask), ?(mask), C(filled)
        step_n_pattern = [("A", "filled"), ("?", "masked"), ("?", "masked"), 
                          ("B", "filled"), ("?", "masked"), ("?", "masked"), ("C", "filled")]
        for i, (text, state) in enumerate(step_n_pattern):
            if state == "filled":
                box = make_token_box(text=text, width=0.55, height=0.65, font_size=14)
            else:
                box = make_token_box(text=text, masked=True, width=0.55, height=0.65, font_size=14)
            box.move_to(LEFT * 3 + RIGHT * (i * 0.62) + UP * 0.5)
            step_n_boxes.add(box)
        
        self.play(FadeIn(step_n_label), FadeIn(step_n_boxes), run_time=0.6)
        self.wait(0.3)
        
        # Predict 標籤: 對每個 mask 位置顯示預測結果
        # idx 1: 預測為 "x" (filled)
        # idx 2: 預測為 EXPAND
        # idx 4: defer (信心不足)
        # idx 5: 預測為 DEL
        
        predict_labels = VGroup()
        # idx 1
        label_1 = mono_text("→ x", size=11, color=ACCENT)
        label_1.next_to(step_n_boxes[1], DOWN, buff=0.15)
        predict_labels.add(label_1)
        # idx 2
        label_2 = mono_text("→ EXP", size=11, color=EXPAND)
        label_2.next_to(step_n_boxes[2], DOWN, buff=0.15)
        predict_labels.add(label_2)
        # idx 4
        label_4 = mono_text("→ defer", size=11, color=INK_FAINT)
        label_4.next_to(step_n_boxes[4], DOWN, buff=0.15)
        predict_labels.add(label_4)
        # idx 5
        label_5 = mono_text("→ DEL", size=11, color=WARN)
        label_5.next_to(step_n_boxes[5], DOWN, buff=0.15)
        predict_labels.add(label_5)
        
        self.play(FadeIn(predict_labels), run_time=0.6)
        self.wait(0.8)
        
        # Step n+1: 結果展示在下方
        step_n1_label = mono_text("Step n+1", size=14, color=INK_SOFT)
        step_n1_label.move_to(LEFT * 5 + DOWN * 1.5)
        
        # 結果: A, x, [新mask1], [新mask2], B, ?(defer 仍是 mask), C
        # (idx 2 expand → 兩個新 mask, idx 5 delete → 移除)
        step_n1_pattern = [
            ("A", "filled"),
            ("x", "filled"),
            ("?", "new_mask"),
            ("?", "new_mask"),
            ("B", "filled"),
            ("?", "masked"),  # defer 還是 mask
            ("C", "filled"),
        ]
        # 注意: 長度仍為 7 (expand +1, delete -1 互相抵銷, defer 不變)
        
        step_n1_boxes = VGroup()
        for i, (text, state) in enumerate(step_n1_pattern):
            if state == "new_mask":
                # 用 expand 顏色的 mask 區分新生
                box = make_token_box(masked=True, width=0.55, height=0.65, font_size=14)
                # 但用棕黃色邊框暗示這是 expand 生成的
                box[0].set_stroke(color=EXPAND, width=1.5)
                box[1].set_stroke(color=EXPAND, width=1.5)
            elif state == "filled":
                box = make_token_box(text=text, width=0.55, height=0.65, font_size=14)
            else:
                box = make_token_box(text=text, masked=True, width=0.55, height=0.65, font_size=14)
            box.move_to(LEFT * 3 + RIGHT * (i * 0.62) + DOWN * 1.5)
            step_n1_boxes.add(box)
        
        # 箭頭從 step n 到 step n+1
        transition_arrow = Arrow(
            UP * 0.0, DOWN * 0.8,
            buff=0.1, color=ACCENT, stroke_width=2,
            max_tip_length_to_length_ratio=0.15
        )
        transition_arrow.move_to(LEFT * 5 + DOWN * 0.5)
        
        self.play(
            Create(transition_arrow),
            FadeIn(step_n1_label),
            FadeIn(step_n1_boxes),
            run_time=1.0
        )
        
        # 註記: 長度不變
        len_note = mono_text("len: 7 → 7  (expand +1, delete -1 cancel out)", 
                              size=13, color=INK_SOFT)
        len_note.next_to(step_n1_boxes, DOWN, buff=0.4)
        self.play(FadeIn(len_note), run_time=0.6)
        self.wait(2.5)
        
        # 收尾淡出
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=0.8)
