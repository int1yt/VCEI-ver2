import matplotlib.pyplot as plt
import numpy as np
import matplotlib.patches as mpatches
from matplotlib.patches import FancyArrowPatch

# ================= 顶刊级全局配置 =================
plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans'],
    'axes.linewidth': 0.8,
    'figure.dpi': 300,
    'savefig.bbox': 'tight',
    'axes.labelsize': 10,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'mathtext.fontset': 'stix',
    'axes.unicode_minus': False,
    'figure.facecolor': '#FFFFFF',
    'axes.facecolor': '#FFFFFF'
})


def _draw_layer_bg(ax, y_start, y_end, label, color):
    ax.add_patch(mpatches.Rectangle((0.2, y_start), 12.6, y_end - y_start,
                                    facecolor=color, alpha=0.08, zorder=0))
    ax.text(0.4, (y_start + y_end) / 2, label, ha='left', va='center',
            fontsize=9.5, fontweight='bold', color='#475569', rotation=90, alpha=0.8)


def _draw_node(ax, x, y, w, h, text, color, fs=10, bg='#FFFFFF', bold=True):
    ax.add_patch(mpatches.FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.1",
                                         facecolor=bg, edgecolor=color, lw=1.8, zorder=2))
    ax.text(x, y, text, ha='center', va='center', fontsize=fs, color=color,
            fontweight='bold' if bold else 'normal', zorder=3)


def _draw_arrow(ax, x1, y1, x2, y2, color, lw=2.5, style='->'):
    ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2),
                                 connectionstyle="arc3,rad=0.15",
                                 arrowstyle=style, color=color, lw=lw, zorder=1))


def _draw_mini_grid(ax, x, y, w, h, rows, cols, highlight_col=None):
    cell_w, cell_h = w / cols, h / rows
    for r in range(rows):
        for c in range(cols):
            fc = '#F97316' if highlight_col is not None and c == highlight_col else '#CBD5E1'
            ax.add_patch(mpatches.Rectangle((x - w / 2 + c * cell_w, y - h / 2 + r * cell_h), cell_w, cell_h,
                                            facecolor=fc, alpha=0.25, edgecolor='#94A3B8', lw=0.4, zorder=2))


def plot_workflow_pro():
    fig, ax = plt.subplots(figsize=(13, 6.5))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 7)
    ax.axis('off')

    # ================= 1. 分层背景与标签 =================
    _draw_layer_bg(ax, 5.8, 6.8, 'TIME SYNC', '#E0F2FE')
    _draw_layer_bg(ax, 3.6, 5.6, 'PROTOCOL ANALYTICS', '#F1F5F9')
    _draw_layer_bg(ax, 1.8, 3.4, 'TEMPORAL FUSION', '#FEF3C7')
    _draw_layer_bg(ax, 0.3, 1.6, 'DECISION OUTPUT', '#D1FAE5')

    # ================= 2. Layer 1: gPTP =================
    _draw_node(ax, 2.0, 6.3, 2.6, 0.7, 'gPTP Global Time Sync', '#3B82F6', fs=11)
    ax.text(2.0, 5.7, 'Unified ms/μs Timestamps', ha='center', va='center', fontsize=9, color='#64748B', style='italic')

    # ================= 3. Layer 2: 三分支并行 =================
    # 分支A: CAN Clock Skew
    _draw_node(ax, 4.5, 5.0, 2.4, 0.8, 'CAN Clock Skew IDS', '#3B82F6', fs=10.5)
    ax.text(4.5, 4.3, 'skew_score / anomaly_flag', ha='center', va='center', fontsize=9, color='#475569')
    # 分支B: CAN CNN 64x9
    _draw_node(ax, 7.5, 5.0, 2.4, 0.8, 'CAN-CNN 64×9', '#8B5CF6', fs=10.5)
    _draw_mini_grid(ax, 7.5, 5.0, 1.2, 0.5, 8, 9, highlight_col=8)
    ax.text(7.5, 4.3, 'class_probs / confidence', ha='center', va='center', fontsize=9, color='#475569')
    # 分支C: Ethernet ML
    _draw_node(ax, 10.5, 5.0, 2.4, 0.8, 'Ethernet ML', '#059669', fs=10.5)
    for i in range(5):
        ax.add_patch(mpatches.Rectangle((9.8 + i * 0.28, 4.75), 0.2, 0.45, facecolor='#10B981', alpha=0.2 + i * 0.1,
                                        edgecolor='#059669', lw=0.5, zorder=2))
    ax.text(10.5, 4.3, 'anomaly_prob / embedding', ha='center', va='center', fontsize=9, color='#475569')

    # ================= 4. Layer 3: 中央融合核心 =================
    _draw_node(ax, 7.5, 2.6, 3.2, 0.9, '2D Temporal Transformer', '#F97316', fs=11)
    ax.text(7.5, 1.9, r'$X_{fused} \in \mathbb{R}^{T \times D}$  |  Multi-Head Attention', ha='center', va='center',
            fontsize=9.5, color='#B45309', style='italic')
    ax.text(7.5, 1.4, 'Learns cross-protocol dependencies (Eth → CAN)', ha='center', va='center', fontsize=9,
            color='#64748B')

    # ================= 5. Layer 4: 决策输出 =================
    _draw_node(ax, 5.5, 0.95, 2.2, 0.6, 'Attack Stage Prob.', '#10B981', fs=10)
    _draw_node(ax, 9.5, 0.95, 2.2, 0.6, 'Full Attack Chain', '#10B981', fs=10)
    # 阶段概率条
    for i, c in enumerate(['#3B82F6', '#8B5CF6', '#F97316', '#10B981']):
        ax.add_patch(mpatches.Rectangle((4.8 + i * 0.45, 0.5), 0.35, 0.25, facecolor=c, alpha=0.85, zorder=2))
    # 攻击链序列
    chain = ['N', 'R', 'P', 'I', 'C']
    for i, (st, c) in enumerate(zip(chain, ['#10B981', '#3B82F6', '#8B5CF6', '#F97316', '#10B981'])):
        ax.add_patch(mpatches.FancyBboxPatch((8.8 + i * 0.45, 0.55), 0.35, 0.25, boxstyle="round,pad=0.05",
                                             facecolor=c, alpha=0.85, zorder=2))
        ax.text(8.975 + i * 0.45, 0.675, st, ha='center', va='center', fontsize=7.5, color='#FFFFFF', fontweight='bold',
                zorder=3)

    # ================= 6. 核心数据流箭头 (加粗突出) =================
    # gPTP -> 三分支
    _draw_arrow(ax, 3.3, 6.3, 4.5, 5.4, '#64748B', lw=2.8)
    _draw_arrow(ax, 3.3, 6.3, 7.5, 5.4, '#64748B', lw=2.8)
    _draw_arrow(ax, 3.3, 6.3, 10.5, 5.4, '#64748B', lw=2.8)

    # 三分支 -> 融合核心
    _draw_arrow(ax, 5.7, 5.0, 7.5, 3.1, '#3B82F6', lw=2.8)
    _draw_arrow(ax, 7.5, 4.6, 7.5, 3.1, '#8B5CF6', lw=2.8)
    _draw_arrow(ax, 9.3, 5.0, 7.5, 3.1, '#059669', lw=2.8)

    # 融合核心 -> 输出
    _draw_arrow(ax, 6.5, 2.15, 5.5, 1.25, '#F97316', lw=2.8)
    _draw_arrow(ax, 8.5, 2.15, 9.5, 1.25, '#F97316', lw=2.8)

    # 跨协议依赖标注
    ax.annotate('', xy=(9.0, 4.2), xytext=(6.0, 4.2),
                arrowprops=dict(arrowstyle='<->', color='#F97316', lw=2.0, linestyle='--', alpha=0.8))
    ax.text(7.5, 4.45, 'Cross-Protocol Temporal Alignment', ha='center', va='center',
            fontsize=9, color='#B45309', style='italic', fontweight='bold')

    # ================= 7. 全局标题与数据流标注 =================
    fig.text(0.5, 0.97, 'ChronoIDS System Workflow: Cross-Protocol Temporal Intelligence',
             ha='center', va='center', fontsize=13, fontweight='bold', color='#0F172A')
    fig.text(0.5, 0.01, 'Data Flow: CAN Raw → 64×9 Tensor / Eth Window → Fusion Seq (T×D) → Stage Prob + Attack Chain',
             ha='center', va='center', fontsize=9.5, color='#64748B', style='italic')

    plt.savefig('ChronoIDS_Workflow_Pro.pdf', format='pdf', dpi=300)
    print("✅ 已生成: ChronoIDS_Workflow_Pro.pdf (13×6.5 in, 顶刊标准)")
    plt.show()


if __name__ == "__main__":
    plot_workflow_pro()
