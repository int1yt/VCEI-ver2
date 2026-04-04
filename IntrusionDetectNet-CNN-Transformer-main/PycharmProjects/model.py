# model.py
import math
import torch
import torch.nn as nn

class TransformerClassifier(nn.Module):
    def __init__(self, ninp, nhead, nhid, nlayers, dropout=0.5):
        super(TransformerClassifier, self).__init__()
        from torch.nn import TransformerEncoder, TransformerEncoderLayer
        
        self.model_type = 'Transformer'
        encoder_layers = TransformerEncoderLayer(ninp, nhead, nhid, dropout)
        self.transformer_encoder = TransformerEncoder(encoder_layers, nlayers)
        self.ninp = ninp
        self.dropout = nn.Dropout(0.3)
        
        # CNN 部分
        self.convs = nn.ModuleList([nn.Conv2d(1, 100, (K, ninp)) for K in [3, 4, 5]])
        self.fc1 = nn.Linear(len([3, 4, 5]) * 100, 2)
        
        # 非卷积分类头（原 forward 中使用）
        self.classifier = nn.Linear(ninp, 2)
        self.dense = nn.Linear(ninp, 2)   # 注意：原代码中未在 __init__ 定义，这里补充避免报错
        
        self.init_weights()

    def init_weights(self):
        initrange = 0.1
        self.classifier.bias.data.zero_()
        self.classifier.weight.data.uniform_(-initrange, initrange)

    def forward2(self, src):   # 带 CNN 的前向传播（训练中使用）
        src = src * math.sqrt(self.ninp)
        x = self.transformer_encoder(src)
        x = x.unsqueeze(1)                    # (N, Ci, W, D)
        x = [torch.relu(conv(x)).squeeze(3) for conv in self.convs]
        x = [torch.max_pool1d(i, i.size(2)).squeeze(2) for i in x]
        x = torch.cat(x, 1)
        x = self.dropout(x)
        logit = self.fc1(x)
        return logit

    def forward(self, src):    # 简单版前向（未使用）
        src = src * math.sqrt(self.ninp)
        output = self.transformer_encoder(src)
        output = output.permute(0, 2, 1)
        output = torch.mean(output, -1)
        output = self.dropout(output)
        output = torch.relu(self.dense(output))
        output = self.dropout(output)
        output = self.classifier(output)
        return output

    def predict(self, x):
        pred = torch.sigmoid(self.forward2(x))
        ans = []
        for t in pred:
            ans.append(1 if t[1] > t[0] else 0)
        return torch.tensor(ans)