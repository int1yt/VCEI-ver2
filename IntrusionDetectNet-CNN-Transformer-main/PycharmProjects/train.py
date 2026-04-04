# python PycharmProjects/train.py
import torch
import torch.optim as optim
import torch.nn as nn
import pandas as pd

from model import TransformerClassifier

# 加载预处理后的数据
train_X = torch.from_numpy(pd.read_csv('PycharmProjects/train_X.csv').values.reshape(-1, 10, 80)).float()
train_Y = torch.from_numpy(pd.read_csv('PycharmProjects/train_Y.csv').values.reshape(-1)).long()
test_X = torch.from_numpy(pd.read_csv('PycharmProjects/test_X.csv').values.reshape(-1, 10, 80)).float()
test_Y = torch.from_numpy(pd.read_csv('PycharmProjects/test_Y.csv').values.reshape(-1)).long()

print(f"训练集形状: {train_X.shape}, 测试集形状: {test_X.shape}")

# 初始化模型
model = TransformerClassifier(ninp=80, nhead=4, nhid=1024, nlayers=3)

criterion = nn.CrossEntropyLoss()
optimizer = optim.Adam(model.parameters(), lr=0.001)

# 训练参数
BATCH_SIZE = 512
epochs = 10
losses = []
test_losses = []

for epoch in range(epochs):
    loss_total = 0
    test_lost_total = 0
    
    permutation = torch.randperm(train_X.size(0))
    
    for j in range(0, train_X.size(0), BATCH_SIZE):
        optimizer.zero_grad()
        
        indices = permutation[j: j + BATCH_SIZE]
        batch_x = train_X[indices]
        batch_y = train_Y[indices]
        
        train_y_pred = model.forward2(batch_x)
        test_y_pred = model.forward2(test_X[:100])   # 只取前100个做验证
        
        loss = criterion(train_y_pred, batch_y)
        test_loss = criterion(test_y_pred, test_Y[:100])
        
        loss_total += loss.item()
        test_lost_total += test_loss.item()
        
        loss.backward()
        optimizer.step()
    
    print(f"Epoch {epoch+1}/{epochs} | Loss: {loss_total:.4f} | Test Loss: {test_lost_total:.4f}")
    losses.append(loss_total)
    test_losses.append(test_lost_total)

print("训练完成！")
torch.save(model.state_dict(), 'transformer_ids_model.pth')