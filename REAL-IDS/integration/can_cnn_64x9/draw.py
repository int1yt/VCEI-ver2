import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches
from matplotlib.path import Path

# ================= 全局学术排版配置 =================
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'axes.linewidth': 0.8,
    'figure.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.labelsize': 9,
    'xtick.labelsize': 8,
    'ytick.labelsize': 8,
    'mathtext.fontset': 'stix',
    'axes.unicode_minus': False,
    'figure.facecolor': '#FFFFFF',
    'axes.facecolor': '#FFFFFF',
    'grid.alpha': 0.15,
    'grid.linestyle': ':'
})


def _add_bg_panel(ax, x, y, w, h, color='#F8FAFC', edge='#E2E8F0', lw=0.6):
    ax.add_patch(mpatches.FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.12",
                                         facecolor=color, edgecolor=edge, lw=lw, zorder=0))


def _safe_text(ax, x, y, text, fs=9, color='#0F172A', bold=False, bg=None):
    kwargs = dict(ha='center', va='center', fontsize=fs, color=color, zorder=5)
    if bold: kwargs['fontweight'] = 'bold'
    if bg: kwargs['bbox'] = dict(facecolor=bg, alpha=0.85, edgecolor='none', pad=2.5)
    ax.text(x, y, text, **kwargs)


# ================= 图1：64×9 输入张量设计 =================
def fig1_input_tensor():
    fig, ax = plt.subplots(figsize=(5.8, 4.2))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis('off')
    _add_bg_panel(ax, 0.3, 0.3, 9.4, 9.4)

    np.random.seed(42)
    payload = np.random.rand(64, 8) * 0.45 + 0.1
    payload[22:42, :] = 0.18 + np.random.rand(20, 8) * 0.06  # DoS 模式
    dt = np.random.exponential(3.2, 64)
    dt[22:42] = 0.15
    dt_norm = np.clip(dt / 8.5, 0, 1)
    data = np.hstack([payload, dt_norm.reshape(-1, 1)])

    # 修复：extent 使用 0.5~9.5，使 9 列中心严格落在 1,2,...,9
    im = ax.imshow(data, aspect='auto', cmap='viridis', interpolation='nearest',
                   extent=[0.5, 9.5, 0.5, 9.5], vmin=0, vmax=1)

    # 修复：严格生成 9 个刻度，与 9 个标签 1:1 匹配
    ax.set_xticks(np.arange(1, 10))
    ax.set_xticklabels([f'D{i}' for i in range(8)] + [r'$\Delta t$'], fontsize=8.5, color='#334155')
    ax.set_yticks(np.arange(1, 10, 2))
    ax.set_yticklabels(['t-64', 't-48', 't-32', 't-16', 't'], fontsize=8, color='#475569')

    # Δt 高亮线（位于第8列和第9列之间）
    ax.axvline(x=8.5, color='#F59E0B', linewidth=1.8, linestyle='--', alpha=0.9)
    _safe_text(ax, 9.2, 5, 'Temporal\nRhythm', fs=8, color='#B45309', bold=True, bg='#FEF3C7')

    # 滑动窗口标注
    ax.add_patch(mpatches.FancyArrowPatch((0.5, 9.6), (9.5, 9.6), arrowstyle='<->', color='#64748B', lw=1.2))
    _safe_text(ax, 5, 9.85, r'Sliding Window: $W=64,\; S=32$', fs=9, color='#334155', bg='#F1F5F9')

    _safe_text(ax, 5, 8.2, r'① Input Tensor $X \in \mathbb{R}^{64 \times 9}$', fs=10.5, bold=True, color='#0F172A')
    _safe_text(ax, 5, 0.6, r'$dt_{norm}=\text{clip}(\Delta t/dt_{max},0,1)$', fs=8.5, color='#475569', bg='#F8FAFC')

    plt.savefig('Fig1_Input_Tensor.pdf', format='pdf', dpi=300)
    print("✅ 已生成: Fig1_Input_Tensor.pdf")
    plt.show()


# ================= 图2：卷积联合提取机制 =================
def fig2_convolution_mechanism():
    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 10)
    ax.axis('off')
    _add_bg_panel(ax, 0.3, 0.3, 11.4, 9.4)

    np.random.seed(88)
    patch = np.random.rand(9, 9) * 0.6
    patch[3:6, 3:6] = 0.85  # 模拟局部异常
    ax.imshow(patch, extent=[1.5, 4.5, 1.5, 4.5], cmap='viridis', alpha=0.9)
    ax.add_patch(mpatches.Rectangle((2.5, 2.5), 1, 1, facecolor='none', edgecolor='#EF4444', linewidth=2.2))
    _safe_text(ax, 3, 2.1, '3×3 Kernel', fs=8, color='#EF4444', bold=True)

    # 输出特征图
    feat = np.random.rand(7, 7) * 0.4
    feat[2:5, 2:5] = 0.9
    ax.imshow(feat, extent=[7.5, 10.5, 1.5, 4.5], cmap='plasma', alpha=0.85)
    _safe_text(ax, 9, 5.0, 'Feature Map', fs=8.5, color='#7C3AED', bold=True, bg='#EDE9FE')

    # 平滑数据流
    p1 = Path([(4.5, 3.0), (5.5, 4.2), (6.5, 4.8), (7.5, 3.0)],
              [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4])
    p2 = Path([(4.5, 3.0), (5.8, 2.0), (6.8, 1.5), (7.5, 3.0)],
              [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4])
    ax.add_patch(mpatches.PathPatch(p1, facecolor='none', edgecolor='#3B82F6', lw=1.8, alpha=0.85))
    ax.add_patch(mpatches.PathPatch(p2, facecolor='none', edgecolor='#8B5CF6', lw=1.8, alpha=0.85))

    _safe_text(ax, 6, 8.5, r'② Joint Content-Temporal Extraction', fs=10.5, bold=True, color='#0F172A')
    _safe_text(ax, 6, 0.8, r'$F_{i,j} = \sum_{m,n} K_{m,n} \odot X_{i+m, j+n}$', fs=9, color='#334155', bg='#F8FAFC')

    plt.savefig('Fig2_Conv_Mechanism.pdf', format='pdf', dpi=300)
    print("✅ 已生成: Fig2_Conv_Mechanism.pdf")
    plt.show()


# ================= 图3：分层特征抽象 =================
def fig3_hierarchical_abstraction():
    fig, ax = plt.subplots(figsize=(6.5, 4.0))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 10)
    ax.axis('off')
    _add_bg_panel(ax, 0.3, 0.3, 11.4, 9.4)

    # Stage 1: 局部字节模式
    l1 = np.sin(np.linspace(0, 4 * np.pi, 16)).reshape(4, 4) @ np.cos(np.linspace(0, 4 * np.pi, 16)).reshape(4, 4).T
    ax.imshow(l1, cmap='Blues', alpha=0.7, extent=[1.5, 4.5, 6.5, 9.5])
    _safe_text(ax, 3, 10.0, 'Stage 1: Byte-Level Patterns', fs=9, color='#1E3A8A', bold=True, bg='#DBEAFE')

    # Stage 2: 时序节律纹理
    l2 = np.random.rand(16, 16)
    l2 = np.convolve(l2.ravel(), np.ones(9) / 9, mode='same').reshape(16, 16)
    ax.imshow(l2, cmap='Purples', alpha=0.6, extent=[4.5, 7.5, 3.5, 6.5])
    _safe_text(ax, 6, 7.0, 'Stage 2: Temporal Rhythm', fs=9, color='#581C87', bold=True, bg='#EDE9FE')

    # Stage 3: 攻击语义聚类
    l3 = np.zeros((16, 16))
    l3[4:12, 4:12] = 1.0
    l3 = np.convolve(l3.ravel(), np.ones(25) / 25, mode='same').reshape(16, 16)
    ax.imshow(l3, cmap='Reds', alpha=0.6, extent=[7.5, 10.5, 0.5, 3.5])
    _safe_text(ax, 9, 4.0, 'Stage 3: Attack Semantics', fs=9, color='#7F1D1D', bold=True, bg='#FEE2E2')

    # 抽象流
    p1 = Path([(4.5, 8.0), (5.5, 7.0), (6.5, 5.5), (7.5, 5.0)],
              [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4])
    p2 = Path([(7.5, 5.0), (8.5, 4.0), (9.5, 3.0), (10.5, 2.0)],
              [Path.MOVETO, Path.CURVE4, Path.CURVE4, Path.CURVE4])
    ax.add_patch(mpatches.PathPatch(p1, facecolor='none', edgecolor='#94A3B8', lw=1.5, alpha=0.7))
    ax.add_patch(mpatches.PathPatch(p2, facecolor='none', edgecolor='#94A3B8', lw=1.5, alpha=0.7))

    _safe_text(ax, 6, 10.5, r'③ Hierarchical Feature Abstraction', fs=10.5, bold=True, color='#0F172A')
    _safe_text(ax, 6, 0.8, r'Progressive receptive field expansion enables multi-scale attack discrimination',
               fs=8.5, color='#475569', bg='#F8FAFC')

    plt.savefig('Fig3_Hierarchical_Abstraction.pdf', format='pdf', dpi=300)
    print("✅ 已生成: Fig3_Hierarchical_Abstraction.pdf")
    plt.show()


if __name__ == "__main__":
    fig1_input_tensor()
    fig2_convolution_mechanism()
    fig3_hierarchical_abstraction()
