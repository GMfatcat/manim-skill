# DLM 動畫系列 — Manim 程式碼

7 個 Manim 動畫檔案，搭配 dLM 研究報告使用，組內報告講解輔助。

## 檔案說明

| 檔案 | 動畫 | 時長 | 主題 |
|------|------|------|------|
| `shared.py` | (共用) | - | 樣式、顏色、helpers |
| `anim_a_ar_vs_dlm.py` | A | ~45s | AR vs dLM 生成對比 |
| `anim_b_forward_backward.py` | B | ~55s | Forward/Backward Masking |
| `anim_c_t_vs_T.py` | C | ~40s | 訓練連續 t vs 推理離散 T |
| `anim_d_dreamon.py` | D | ~65s | DreamOn expand/delete 機制 |
| `anim_e_ar_to_dlm.py` | E | ~55s | AR-to-dLM attention mask 轉換 |
| `anim_f_flops_blowup.py` | F | ~55s | 長序列 FLOPs 爆炸 |
| `anim_full.py` | 合成 | ~5:45 | 全部串接 + 過場 |

## 環境準備

```bash
# Python 3.10+
pip install manim

# 系統字型 (IBM Plex 系列) - macOS / Linux
# 從 https://www.ibm.com/plex/ 下載並安裝
# 或在 shared.py 改用系統字型 fallback
```

## 執行單一動畫

```bash
# 進入目錄
cd manim_dlm

# 高品質 (1920x1080 @ 60fps)
manim -pqh anim_a_ar_vs_dlm.py SceneA
manim -pqh anim_b_forward_backward.py SceneB
manim -pqh anim_c_t_vs_T.py SceneC
manim -pqh anim_d_dreamon.py SceneD
manim -pqh anim_e_ar_to_dlm.py SceneE
manim -pqh anim_f_flops_blowup.py SceneF

# 快速預覽 (480p, 適合 iteration)
manim -pql anim_a_ar_vs_dlm.py SceneA

# 4K (簡報投影或保存)
manim -pqk anim_a_ar_vs_dlm.py SceneA
```

## 執行合成影片

`anim_full.py` 的 `FullVideo` class 用「camera 重用 + construct 直接呼叫」的方式串接，這在現行 Manim (v0.20.x) 會撞到 `property 'camera' of '...' object has no setter` 而失敗。實務上的合成流程是**個別 render 各 scene + ffmpeg concat**：

```bash
# 1. render Opening / Closing / 6 個 chapter transition (各 ~3-5s)
manim -qh anim_full.py Opening
manim -qh anim_full.py Closing
manim -qh anim_full.py TransitionCh1   # AR vs Diffusion
manim -qh anim_full.py TransitionCh2   # 訓練與推理
manim -qh anim_full.py TransitionCh3   # 連續 t 與離散 T
manim -qh anim_full.py TransitionCh4   # AR 轉 dLM
manim -qh anim_full.py TransitionCh5   # DreamOn 變長機制
manim -qh anim_full.py TransitionCh6   # 長序列吞吐瓶頸

# 2. render 6 個主 scene (SceneA-F)，見上一節

# 3. ffmpeg concat (注意章節順序：A B C E D F)
cat > concat.txt <<EOF
file 'media/videos/anim_full/1080p60/Opening.mp4'
file 'media/videos/anim_full/1080p60/TransitionCh1.mp4'
file 'media/videos/anim_a_ar_vs_dlm/1080p60/SceneA.mp4'
file 'media/videos/anim_full/1080p60/TransitionCh2.mp4'
file 'media/videos/anim_b_forward_backward/1080p60/SceneB.mp4'
file 'media/videos/anim_full/1080p60/TransitionCh3.mp4'
file 'media/videos/anim_c_t_vs_T/1080p60/SceneC.mp4'
file 'media/videos/anim_full/1080p60/TransitionCh4.mp4'
file 'media/videos/anim_e_ar_to_dlm/1080p60/SceneE.mp4'
file 'media/videos/anim_full/1080p60/TransitionCh5.mp4'
file 'media/videos/anim_d_dreamon/1080p60/SceneD.mp4'
file 'media/videos/anim_full/1080p60/TransitionCh6.mp4'
file 'media/videos/anim_f_flops_blowup/1080p60/SceneF.mp4'
file 'media/videos/anim_full/1080p60/Closing.mp4'
EOF
ffmpeg -f concat -safe 0 -i concat.txt -c copy dlm_full.mp4
```

合成時長約 3:25 @ 1080p60（~16 MB）。所有片段直接 stream-copy，concat 本身 <1 秒。

## 設計慣例

- **顏色**: 與 HTML 報告一致
  - AR / 已敲定 token: `#1E4F5C` (深青)
  - dLM / 警告: `#8B3A2E` (磚紅)
  - expand: `#8B7A35` (棕黃) + `#FAF1D7` 底
  - delete: `#8B3A2E` (磚紅) + `#F4D2CC` 底
  - 背景: `#FBF8F1` (米黃)
- **字型**: IBM Plex Sans TC (標題) / IBM Plex Serif (內文) / IBM Plex Mono (程式碼)
- **Zoom 慣例**: 1.6×-2.0× 倍率, smooth rate_func, 每次 zoom in 後必 zoom out
- **過場**: 3 秒，黑底 + 章節編號 + 中英文標題

## 後續調整建議

每個動畫獨立可改，建議流程:
1. 先用 `-pql` 快速跑過看效果
2. 鎖定要調整的 Scene 和時間點
3. 修改對應 `.py` 檔
4. 重新 render
5. 確認後再跑 `anim_full.py` 合成

zoom 效果若需調整 (放大倍率、時機點)，搜尋 `🔍 Zoom-in` 標記在程式碼中的位置。

## 已知限制 / TODO

- 字型 fallback: 系統若沒有 IBM Plex，會 fallback 到 Sans Serif / Monospace，視覺會不太一致。建議裝好字型
- `anim_full.py` 的 `FullVideo` class 在現行 Manim 失敗（camera read-only），實務改用上面的 ffmpeg concat 流程。`TransitionCh1`–`TransitionCh6` 已內建在 `anim_full.py`，可直接用 manim CLI 渲染。
- 動畫節奏: 每個 Scene 的 `wait()` 時長都是固定值，講解節奏不同的話可以個別調整
- `anim_f_flops_blowup.py` 已修正 `slowdown_arrow` 的 `RIGHT * 0.5` shift → `RIGHT * 1.8`，避免雙箭頭尾端遮到 FLOPs 標籤的數字
