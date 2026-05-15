"""Minimal multi-head self-attention in PyTorch.

A teaching reference: one forward pass, no dropout, no masking, no caches.
Shape annotations use:
    B = batch size
    L = sequence length
    D = model dim (embed_dim)
    H = num heads
    Dh = D // H = per-head dim
"""

import math
import torch
import torch.nn as nn


class MultiHeadAttention(nn.Module):
    def __init__(self, embed_dim: int, num_heads: int):
        super().__init__()
        assert embed_dim % num_heads == 0, "embed_dim must be divisible by num_heads"
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads

        self.q_proj = nn.Linear(embed_dim, embed_dim, bias=False)
        self.k_proj = nn.Linear(embed_dim, embed_dim, bias=False)
        self.v_proj = nn.Linear(embed_dim, embed_dim, bias=False)
        self.out_proj = nn.Linear(embed_dim, embed_dim, bias=False)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        # x: (B, L, D)
        B, L, D = x.shape
        H, Dh = self.num_heads, self.head_dim

        # 1. Project to Q, K, V and split into heads.
        # (B, L, D) -> (B, L, H, Dh) -> (B, H, L, Dh)
        q = self.q_proj(x).view(B, L, H, Dh).transpose(1, 2)
        k = self.k_proj(x).view(B, L, H, Dh).transpose(1, 2)
        v = self.v_proj(x).view(B, L, H, Dh).transpose(1, 2)

        # 2. Scaled dot-product scores.
        # (B, H, L, Dh) @ (B, H, Dh, L) -> (B, H, L, L)
        scores = q @ k.transpose(-2, -1) / math.sqrt(Dh)

        # 3. Softmax along the key dimension.
        attn = torch.softmax(scores, dim=-1)

        # 4. Weighted sum of values.
        # (B, H, L, L) @ (B, H, L, Dh) -> (B, H, L, Dh)
        ctx = attn @ v

        # 5. Concatenate heads and project out.
        # (B, H, L, Dh) -> (B, L, H, Dh) -> (B, L, D)
        ctx = ctx.transpose(1, 2).contiguous().view(B, L, D)
        return self.out_proj(ctx)


if __name__ == "__main__":
    torch.manual_seed(0)
    mha = MultiHeadAttention(embed_dim=64, num_heads=8)
    x = torch.randn(2, 10, 64)  # B=2, L=10, D=64
    y = mha(x)
    print(f"input  {tuple(x.shape)}")
    print(f"output {tuple(y.shape)}")
