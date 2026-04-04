# python PycharmProjects/evaluate.py
import torch
import pandas as pd
import numpy as np
from sklearn import metrics
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, auc, precision_recall_curve, confusion_matrix
from sklearn.metrics import classification_report

from model import TransformerClassifier

# 加载数据和模型
test_X = torch.from_numpy(pd.read_csv('PycharmProjects/test_X.csv').values.reshape(-1, 10, 80)).float()
test_Y = torch.from_numpy(pd.read_csv('PycharmProjects/test_Y.csv').values.reshape(-1)).long()

model = TransformerClassifier(ninp=80, nhead=4, nhid=1024, nlayers=3)
model.load_state_dict(torch.load('transformer_ids_model.pth'))
model.eval()

# 预测（分批次避免内存问题，修复批次索引问题）
results = []
probabilities = []  # 存储预测概率用于ROC曲线

with torch.no_grad():
    batch_size = 5
    for i in range(0, len(test_X), batch_size):
        batch = test_X[i:min(i+batch_size, len(test_X))]
        ret = model.predict(batch)
        results.append(ret)
        
        # 获取预测概率
        prob = torch.sigmoid(model.forward2(batch))
        probabilities.append(prob)

# 拼接所有预测结果
dd = torch.cat(results)[:len(test_Y)]
all_probs = torch.cat(probabilities)[:len(test_Y)]

print(f"\n{'='*80}")
print(f"评估结果")
print(f"{'='*80}")

# 展示每一条测试结果是否分类正确
print(f"\n{'序号':<6} {'真实标签':<10} {'预测标签':<10} {'分类结果':<10} {'预测概率(异常类)':<15}")
print(f"{'-'*80}")

correct_count = 0
for i in range(len(dd)):
    is_correct = (dd[i] == test_Y[i])
    if is_correct:
        correct_count += 1
        status = "✓ 正确"
    else:
        status = "✗ 错误"
    
    prob_anomaly = all_probs[i, 1].item() if len(all_probs.shape) > 1 else all_probs[i].item()
    
    print(f"{i+1:<6} {test_Y[i].item():<10} {dd[i].item():<10} {status:<10} {prob_anomaly:.6f}")

print(f"{'-'*80}")
print(f"总样本数: {len(dd)}")
print(f"正确分类数: {correct_count}")
print(f"错误分类数: {len(dd) - correct_count}")
print(f"正确率: {correct_count/len(dd)*100:.2f}%")

# 找出分类错误的样本
error_indices = [i for i in range(len(dd)) if dd[i] != test_Y[i]]
if error_indices:
    print(f"\n分类错误的样本序号: {error_indices[:20]}")  # 只显示前20个
    if len(error_indices) > 20:
        print(f"... 还有 {len(error_indices)-20} 个错误样本")

# 按标签分类统计
print(f"\n{'='*80}")
print(f"分类结果统计")
print(f"{'='*80}")

# 真阳性、假阳性、真阴性、假阴性统计
tp = sum((dd[i] == 1 and test_Y[i] == 1) for i in range(len(dd)))
tn = sum((dd[i] == 0 and test_Y[i] == 0) for i in range(len(dd)))
fp = sum((dd[i] == 1 and test_Y[i] == 0) for i in range(len(dd)))
fn = sum((dd[i] == 0 and test_Y[i] == 1) for i in range(len(dd)))

print(f"真阳性 (TP - 正确识别异常): {tp}")
print(f"真阴性 (TN - 正确识别正常): {tn}")
print(f"假阳性 (FP - 正常误判为异常): {fp}")
print(f"假阴性 (FN - 异常漏判为正常): {fn}")

# 计算各项指标
accuracy = (tp + tn) / len(dd)
precision = tp / (tp + fp) if (tp + fp) > 0 else 0
recall = tp / (tp + fn) if (tp + fn) > 0 else 0
f1 = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0

print(f"\n{'='*80}")
print(f"详细指标")
print(f"{'='*80}")
print(f"准确率 (Accuracy): {accuracy:.6f} ({accuracy*100:.2f}%)")
print(f"精确率 (Precision): {precision:.6f} ({precision*100:.2f}%)")
print(f"召回率 (Recall): {recall:.6f} ({recall*100:.2f}%)")
print(f"F1分数 (F1-Score): {f1:.6f}")

# 使用sklearn的分类报告
print(f"\n分类报告 (Classification Report):")
print(classification_report(test_Y[:len(dd)], dd, target_names=['正常(0)', '异常(1)']))

# 混淆矩阵
cm = confusion_matrix(test_Y[:len(dd)], dd)
print(f"\n混淆矩阵 (Confusion Matrix):")
print(cm)

# 修复ROC曲线 - 使用预测概率而不是预测标签
print(f"\n{'='*80}")
print(f"ROC曲线分析")
print(f"{'='*80}")

# 获取异常类的预测概率
if len(all_probs.shape) == 2:
    y_score = all_probs[:, 1].numpy()  # 异常类的概率
else:
    y_score = all_probs.numpy()

y_true = test_Y[:len(dd)].numpy()

fpr, tpr, thresholds = roc_curve(y_true, y_score)
roc_auc = auc(fpr, tpr)

print(f"AUC (Area Under Curve): {roc_auc:.6f}")

# 找出最佳阈值（Youden指数）
youden_j = tpr - fpr
best_threshold_idx = np.argmax(youden_j)
best_threshold = thresholds[best_threshold_idx]
best_tpr = tpr[best_threshold_idx]
best_fpr = fpr[best_threshold_idx]

print(f"最佳阈值 (Best Threshold): {best_threshold:.6f}")
print(f"最佳阈值对应的 TPR (Recall): {best_tpr:.6f}")
print(f"最佳阈值对应的 FPR: {best_fpr:.6f}")

plt.figure(figsize=(10, 8))
plt.plot(fpr, tpr, color='darkorange', lw=2, label=f'ROC curve (AUC = {roc_auc:.4f})')
plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
plt.scatter(best_fpr, best_tpr, color='red', marker='o', s=100, 
           label=f'Best Threshold (FPR={best_fpr:.3f}, TPR={best_tpr:.3f})')
plt.xlim([0.0, 1.0])
plt.ylim([0.0, 1.05])
plt.xlabel('False Positive Rate (假阳性率)')
plt.ylabel('True Positive Rate (召回率)')
plt.title('Receiver Operating Characteristic (ROC) Curve')
plt.legend(loc="lower right")
plt.grid(alpha=0.3)
plt.show()

# Precision-Recall 曲线
precision_vals, recall_vals, pr_thresholds = precision_recall_curve(y_true, y_score)
pr_auc = auc(recall_vals, precision_vals)

print(f"\nPrecision-Recall AUC: {pr_auc:.6f}")

plt.figure(figsize=(10, 8))
plt.plot(recall_vals, precision_vals, color='green', lw=2, label=f'PR curve (AUC = {pr_auc:.4f})')
plt.xlabel('Recall (召回率)')
plt.ylabel('Precision (精确率)')
plt.title('Precision-Recall Curve')
plt.legend(loc="best")
plt.grid(alpha=0.3)
plt.show()

# 保存错误分类的样本到CSV
error_data = []
for i in error_indices:
    error_data.append({
        '序号': i + 1,
        '真实标签': test_Y[i].item(),
        '预测标签': dd[i].item(),
        '异常类概率': all_probs[i, 1].item() if len(all_probs.shape) > 1 else all_probs[i].item(),
        '分类结果': '错误'
    })

if error_data:
    error_df = pd.DataFrame(error_data)
    error_df.to_csv('classification_errors.csv', index=False)
    print(f"\n错误分类样本已保存到 'classification_errors.csv'")

print(f"\n{'='*80}")
print(f"评估完成！")
print(f"{'='*80}")