"""
動畫 E: AR-to-dLM Attention Mask 轉換
總時長 ~55 秒

核心 message: 從 AR checkpoint 連續變形成 dLM，關鍵在 attention pattern 演化
- Scene 1 (0-10s): AR baseline [zoom in matrix]
- Scene 2 (10-25s): 階段 1 Fully bidirectional (粗暴版)
- Scene 3 (25-48s): 階段 2 Block-wise (聰明版) [zoom in block]
- Scene 4 (48-55s): 三種模式並列

執行: manim -pqh anim_e_ar_to_dlm.py SceneE
"""

from manim import *
from shared import *


def make_attention_matrix(N=8, cell_size=0.42):
    """建立 N×N attention mask 矩陣 (預設全空)"""
    cells = []
    grid_group = VGroup()
    
    for i in range(N):
        row = []
        for j in range(N):
            cell = Rectangle(
                width=cell_size, height=cell_size,
                fill_color=BG_COLOR, fill_opacity=1,
                stroke_color=RULE_SOFT, stroke_width=0.5
            )
            cell.move_to(
                RIGHT * (j - N/2 + 0.5) * cell_size +
                DOWN * (i - N/2 + 0.5) * cell_size
            )
            row.append(cell)
            grid_group.add(cell)
        cells.append(row)
    
    return cells, grid_group


class SceneE(MovingCameraScene):
    def construct(self):
        setup_scene_background(self)
        
        title = title_text("AR-to-dLM — Attention Pattern Evolution", size=28)
        title.to_edge(UP, buff=0.4)
        self.play(Write(title), run_time=0.8)
        self.wait(0.3)
        
        # ============ Scene 1: AR baseline (0-10s) ============
        N = 8
        cell_size = 0.42
        
        # 建立 attention 矩陣
        cells, grid_group = make_attention_matrix(N=N, cell_size=cell_size)
        grid_group.move_to(LEFT * 0.5 + DOWN * 0.3)
        
        # 重新計算 cells 的位置 (因為 grid_group 整體移動了)
        center_offset = LEFT * 0.5 + DOWN * 0.3
        for i in range(N):
            for j in range(N):
                cells[i][j].move_to(
                    center_offset +
                    RIGHT * (j - N/2 + 0.5) * cell_size +
                    DOWN * (i - N/2 + 0.5) * cell_size
                )
        
        # 矩陣標籤
        matrix_label = mono_text("Attention Mask Matrix (8×8)", size=14, color=INK_FAINT)
        matrix_label.move_to(LEFT * 0.5 + UP * 2.5)
        
        # 標籤
        stage_label = title_text("Stage 0: Qwen2.5 AR (Causal)", size=20, color=ACCENT)
        stage_label.move_to(RIGHT * 4.5 + UP * 2)
        
        loss_label = mono_text("Loss: Next-Token Prediction", size=13, color=INK_SOFT)
        loss_label.move_to(RIGHT * 4.5 + UP * 1.4)
        
        self.play(
            FadeIn(matrix_label),
            FadeIn(grid_group),
            FadeIn(stage_label),
            FadeIn(loss_label),
            run_time=0.8
        )
        
        # 把下三角填上 causal 色 (深青)
        causal_animations = []
        for i in range(N):
            for j in range(N):
                if j <= i:
                    causal_animations.append(
                        cells[i][j].animate.set_fill(ACCENT, opacity=1).set_stroke(ACCENT, width=0.8)
                    )
        
        self.play(
            LaggedStart(*causal_animations, lag_ratio=0.015),
            run_time=1.5
        )
        
        # 🔍 Zoom-in #1: 拉近矩陣中央
        self.play(
            self.camera.frame.animate.move_to(LEFT * 0.5 + DOWN * 0.3).scale(0.6),
            run_time=1.0,
            rate_func=smooth
        )
        
        # 標示下三角
        triangle_note = mono_text("Lower triangular", size=10, color=ACCENT_SOFT)
        triangle_note.move_to(LEFT * 1.0 + DOWN * 1.5)
        triangle_arrow = Arrow(
            triangle_note.get_top() + UP * 0.05,
            cells[6][1].get_center(),
            buff=0.1, color=ACCENT_SOFT, stroke_width=1.5,
            max_tip_length_to_length_ratio=0.15
        )
        
        self.play(FadeIn(triangle_note), Create(triangle_arrow), run_time=0.6)
        self.wait(1.2)
        
        # Zoom out
        self.play(
            self.camera.frame.animate.move_to(ORIGIN).scale(1/0.6),
            FadeOut(triangle_note), FadeOut(triangle_arrow),
            run_time=0.9,
            rate_func=smooth
        )
        
        # ============ Scene 2: 階段 1 Fully bidirectional (10-25s) ============
        # 更新 stage label
        new_stage_label = title_text("Stage 1: Fully Bidirectional", size=20, color=EXPAND)
        new_stage_label.move_to(RIGHT * 4.5 + UP * 2)
        
        new_loss_label = mono_text("Loss: Masked Diffusion", size=13, color=INK_SOFT)
        new_loss_label.move_to(RIGHT * 4.5 + UP * 1.4)
        
        self.play(
            Transform(stage_label, new_stage_label),
            Transform(loss_label, new_loss_label),
            run_time=0.5
        )
        
        # 上三角格子一格一格亮起 (用 expand 黃)
        upper_animations = []
        for i in range(N):
            for j in range(N):
                if j > i:
                    upper_animations.append(
                        cells[i][j].animate.set_fill(EXPAND_BG, opacity=1).set_stroke(EXPAND, width=0.8)
                    )
        
        self.play(
            LaggedStart(*upper_animations, lag_ratio=0.012),
            run_time=2.0
        )
        
        # 警告浮現
        warning_text = mono_text("⚠ AR weights distribution disrupted", size=14, color=WARN)
        warning_text.move_to(RIGHT * 4.5 + UP * 0.5)
        
        accuracy_label = mono_text("Accuracy ↓", size=13, color=WARN)
        accuracy_label.move_to(RIGHT * 4.5 + DOWN * 0.0)
        
        # Accuracy bar (mini)
        acc_bar_bg = Rectangle(width=2, height=0.18,
                                fill_color=BG_CODE, fill_opacity=1,
                                stroke_color=RULE, stroke_width=1)
        acc_bar_bg.move_to(RIGHT * 4.5 + DOWN * 0.4)
        acc_bar = Rectangle(width=1.3, height=0.18,
                             fill_color=WARN, fill_opacity=0.7,
                             stroke_width=0)
        acc_bar.align_to(acc_bar_bg, LEFT)
        acc_bar.move_to(RIGHT * 4.5 + LEFT * 0.35 + DOWN * 0.4)
        
        self.play(
            FadeIn(warning_text, shift=UP * 0.1),
            FadeIn(accuracy_label),
            FadeIn(acc_bar_bg),
            run_time=0.6
        )
        self.play(GrowFromEdge(acc_bar, LEFT), run_time=0.5)
        self.wait(1.5)
        
        # ============ Scene 3: 階段 2 Block-wise (25-48s) ============
        # 先把矩陣重置回 causal 狀態
        reset_animations = []
        for i in range(N):
            for j in range(N):
                if j > i:
                    reset_animations.append(
                        cells[i][j].animate.set_fill(BG_COLOR, opacity=1).set_stroke(RULE_SOFT, width=0.5)
                    )
                else:
                    # causal 部分先變回原色
                    pass
        
        new_stage_label_2 = title_text("Stage 2: Block-wise (Smart)", size=20, color=ACCENT_SOFT)
        new_stage_label_2.move_to(RIGHT * 4.5 + UP * 2)
        
        self.play(
            *reset_animations,
            Transform(stage_label, new_stage_label_2),
            FadeOut(warning_text), FadeOut(accuracy_label),
            FadeOut(acc_bar_bg), FadeOut(acc_bar),
            run_time=0.8
        )
        
        # 把矩陣切成 4 個 block (block_size = 2)
        block_size = 2
        num_blocks = N // block_size
        
        # 畫粗的 block 分界線
        block_dividers = VGroup()
        for k in range(1, num_blocks):
            # 垂直線
            v_line = Line(
                cells[0][k*block_size - 1].get_corner(UR) + UP * 0.02,
                cells[N-1][k*block_size - 1].get_corner(DR) + DOWN * 0.02,
                color=INK, stroke_width=3
            )
            # 水平線
            h_line = Line(
                cells[k*block_size - 1][0].get_corner(DL) + LEFT * 0.02,
                cells[k*block_size - 1][N-1].get_corner(DR) + RIGHT * 0.02,
                color=INK, stroke_width=3
            )
            block_dividers.add(v_line, h_line)
        
        self.play(Create(block_dividers), run_time=1.2)
        
        # 🔍 Zoom-in #2: 拉近某個 block 區
        # 聚焦在第 2 個 block (idx 2-3) 與它和前一個 block 的關係
        focus_center = (cells[2][2].get_center() + cells[3][3].get_center()) / 2
        self.play(
            self.camera.frame.animate.move_to(focus_center).scale(0.45),
            run_time=1.2,
            rate_func=smooth
        )
        
        # Block 內: bidirectional (block 內所有格子變綠色)
        # 對於每個 block diagonal, 內部所有格子都亮
        block_inner_animations = []
        for block_idx in range(num_blocks):
            i_start = block_idx * block_size
            for i in range(i_start, i_start + block_size):
                for j in range(i_start, i_start + block_size):
                    block_inner_animations.append(
                        cells[i][j].animate.set_fill(ACCENT_SOFT, opacity=0.9).set_stroke(ACCENT, width=0.8)
                    )
        
        self.play(LaggedStart(*block_inner_animations, lag_ratio=0.02), run_time=1.5)
        
        # Block 間: causal (block 下方的所有 block 也亮起，用較深 ACCENT 色)
        block_between_animations = []
        for block_i in range(num_blocks):
            for block_j in range(block_i):  # block_j < block_i (下方 block 看上方)
                i_start, j_start = block_i * block_size, block_j * block_size
                for i in range(i_start, i_start + block_size):
                    for j in range(j_start, j_start + block_size):
                        block_between_animations.append(
                            cells[i][j].animate.set_fill(ACCENT, opacity=1).set_stroke(ACCENT, width=0.8)
                        )
        
        self.play(LaggedStart(*block_between_animations, lag_ratio=0.02), run_time=1.5)
        
        # 好處浮現 (在放大狀態下)
        # Zoom out 一點以容納註解
        self.play(
            self.camera.frame.animate.move_to(LEFT * 0.5 + DOWN * 0.3).scale(1.4),
            run_time=0.8,
            rate_func=smooth
        )
        
        benefit_note = mono_text("KV cache reusable across blocks ✓", size=13, color=ACCENT)
        benefit_note.next_to(grid_group, DOWN, buff=0.3)
        
        weight_note = mono_text("AR weights preserved ✓", size=12, color=ACCENT)
        weight_note.next_to(benefit_note, DOWN, buff=0.15)
        
        self.play(FadeIn(benefit_note), FadeIn(weight_note), run_time=0.6)
        self.wait(1.5)
        
        # Zoom out 完全回到正常視角
        self.play(
            self.camera.frame.animate.move_to(ORIGIN).scale(1/(0.45 * 1.4)),
            run_time=1.0,
            rate_func=smooth
        )
        
        # 在 right side 加上正向指標
        result_note_1 = mono_text("Accuracy: preserved", size=13, color=ACCENT)
        result_note_1.move_to(RIGHT * 4.5 + UP * 0.5)
        result_note_2 = mono_text("Throughput: 4.5× faster", size=13, color=ACCENT)
        result_note_2.move_to(RIGHT * 4.5 + DOWN * 0.0)
        
        # 引用註記
        source_note = label_text("Efficient-DLM 8B vs Dream 7B", size=10, color=INK_FAINT)
        source_note.move_to(RIGHT * 4.5 + DOWN * 0.4)
        
        self.play(
            FadeIn(result_note_1),
            FadeIn(result_note_2),
            FadeIn(source_note),
            run_time=0.7
        )
        self.wait(1.2)
        
        # ============ Scene 4: 三種模式並列 (48-55s) ============
        # 清除右側資訊
        self.play(
            FadeOut(stage_label), FadeOut(loss_label),
            FadeOut(result_note_1), FadeOut(result_note_2), FadeOut(source_note),
            FadeOut(matrix_label),
            FadeOut(benefit_note), FadeOut(weight_note),
            FadeOut(block_dividers),
            run_time=0.6
        )
        
        # 把當前矩陣縮小到右側
        current_matrix = VGroup(grid_group)
        # 我們要保留 cells 結構但縮放整個 group
        self.play(
            grid_group.animate.scale(0.55).move_to(RIGHT * 4 + DOWN * 0.3),
            run_time=1.0
        )
        
        # 在左邊建立兩個新的矩陣 (causal + fully bi)
        # Causal matrix
        causal_cells, causal_grid = make_attention_matrix(N=N, cell_size=cell_size * 0.55)
        causal_grid.move_to(LEFT * 4 + DOWN * 0.3)
        for i in range(N):
            for j in range(N):
                if j <= i:
                    causal_cells[i][j].set_fill(ACCENT, opacity=1).set_stroke(ACCENT, width=0.6)
        
        # Fully bi matrix
        fullbi_cells, fullbi_grid = make_attention_matrix(N=N, cell_size=cell_size * 0.55)
        fullbi_grid.move_to(LEFT * 0 + DOWN * 0.3)
        for i in range(N):
            for j in range(N):
                fullbi_cells[i][j].set_fill(EXPAND_BG, opacity=1).set_stroke(EXPAND, width=0.6)
        
        # 三個標籤
        label_causal = mono_text("Causal", size=14, color=ACCENT)
        label_causal.next_to(causal_grid, UP, buff=0.3)
        
        label_fullbi = mono_text("Fully Bidirectional", size=14, color=EXPAND)
        label_fullbi.next_to(fullbi_grid, UP, buff=0.3)
        
        label_block = mono_text("Block-wise", size=14, color=ACCENT_SOFT)
        label_block.next_to(grid_group, UP, buff=0.3)
        
        self.play(
            FadeIn(causal_grid),
            FadeIn(fullbi_grid),
            FadeIn(label_causal),
            FadeIn(label_fullbi),
            FadeIn(label_block),
            run_time=1.0
        )
        
        # 下方對照
        comparison_text = body_text(
            "Block-wise = production-ready choice", size=16, color=INK, italic=True
        )
        comparison_text.move_to(DOWN * 2.5)
        self.play(FadeIn(comparison_text), run_time=0.6)
        self.wait(2.0)
        
        # 收尾淡出
        self.play(*[FadeOut(m) for m in self.mobjects], run_time=0.8)
