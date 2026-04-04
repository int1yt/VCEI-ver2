# data_preprocess.py
from __future__ import absolute_import, division, print_function
import pandas as pd
import numpy as np
import torch
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

# 读取数据文件
resampled_ab_df = pd.read_csv('data_8000_abnormal.csv', encoding='cp1252')
resampled_nor_df = pd.read_csv('data_8000_normal.csv', encoding='cp1252')

print("样本数量（resampled_ab_df）：", resampled_ab_df.shape[0])
print("样本数量（resampled_nor_df）：", resampled_nor_df.shape[0])

# 数据整合与清理
df = pd.concat([resampled_nor_df, resampled_ab_df])
print("整合后的样本数量：", df.shape[0])

df = df.drop(columns=[' Source IP', ' Destination IP', ' Timestamp', 'Flow ID'])

if 'Unnamed: 0' in df.columns:
    df = df.drop(columns=['Unnamed: 0'])

# 标签转换为二进制
def label_transfer(d):
    return 1 if d != 'BENIGN' else 0

df = df.replace([np.inf, -np.inf], np.nan)
df = df.dropna()
df[' Label'] = df[' Label'].apply(label_transfer)

# 数据标准化
scaler = StandardScaler()
column_size = len(df.columns)
values = df.values[:, :column_size - 1]
scaler.fit(values)
values = scaler.transform(values)
targets = df.values[:, column_size - 1: column_size]

# 按每10个样本组成一个序列
num_samples = len(values) // 10 * 10
grouped_data_x = np.zeros((num_samples // 10, 10, 80))
grouped_data_y = np.zeros(num_samples // 10)

for i in range(0, num_samples, 10):
    locs = np.arange(i, i + 10, 1)
    token_list = values[locs]
    grouped_data_x[int(i/10)] = token_list
    grouped_data_y[int(i/10)] = targets[i][0]

# 拆分训练集和测试集 (80%/20%)
permutation = torch.randperm(len(grouped_data_x))
train_indices = list(permutation[0: int(len(grouped_data_x) * 0.8)])
test_indices = list(permutation[int(len(grouped_data_x) * 0.8): len(grouped_data_x)])

train_x = grouped_data_x[train_indices]
train_y = grouped_data_y[train_indices]
test_x = grouped_data_x[test_indices]
test_y = grouped_data_y[test_indices]

# 转换为 Tensor
train_X = torch.from_numpy(train_x).type(torch.FloatTensor)
test_X = torch.from_numpy(test_x).type(torch.FloatTensor)
train_Y = torch.from_numpy(train_y).type(torch.LongTensor)
test_Y = torch.from_numpy(test_y).type(torch.LongTensor)

print("测试集样本数量:", len(test_X))
print("特征维度:", len(df.columns))

# 保存为 CSV 文件
train_X_df = pd.DataFrame(train_X.numpy().reshape(-1, 80))
train_Y_df = pd.DataFrame(train_Y.numpy().reshape(-1, 1))
test_X_df = pd.DataFrame(test_X.numpy().reshape(-1, 80))
test_Y_df = pd.DataFrame(test_Y.numpy().reshape(-1, 1))

train_X_df.to_csv('train_X.csv', index=False)
train_Y_df.to_csv('train_Y.csv', index=False)
test_X_df.to_csv('test_X.csv', index=False)
test_Y_df.to_csv('test_Y.csv', index=False)

print("数据预处理完成，已保存 train_X.csv, train_Y.csv, test_X.csv, test_Y.csv")