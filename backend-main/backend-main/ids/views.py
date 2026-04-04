import csv
import json

import pandas as pd
import os.path
import random
import numpy as np

from django.http import JsonResponse
from django.shortcuts import render


# Create your views here.
def read_csv(request):
    # 返回响应
    data = read_csv_fun()
    json_data = data_to_json(data)
    # return JsonResponse({"data": json.loads(json_data)})
    return JsonResponse(json.loads(json_data),safe=False)

def test_read_csv(request):
    data = read_csv_fun()
    json_data = data_to_json(data)
    return render(request, "test.html", json.loads(json_data)[0])

def get_total_lines(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        total_lines = sum(1 for line in f)
    return total_lines
def read_csv_fun():
    """
    读取速度快，格式为行列，缺失数据为NaN
    """

    num_lines = 100
    file = os.path.join(os.getcwd(), r'ids\data\data.csv')
    total_lines = get_total_lines(file)
    print(f"Total lines in file: {total_lines}")

    # 检查文件是否存在
    if not os.path.exists(file):
        raise FileNotFoundError(f"The file {file} does not exist")

    # 检查文件是否为空
    if os.path.getsize(file) == 0:
        raise ValueError("The file is empty")

    # 检查文件总行数
    with open(file, 'r', encoding='utf-8') as f:
        total_lines = sum(1 for line in f)

    # 尝试读取文件
    try:
        data = pd.read_csv(file, nrows=num_lines, dtype=str, header=None, encoding='utf-8')
    except pd.errors.EmptyDataError:
        raise ValueError("No columns to parse from file")
    except Exception as e:
        raise ValueError(f"An error occurred while reading the file: {e}")

    print(data)
    return data


def data_to_json(data):
    df = None
    try:
        df = data.apply(move_last_valid_to_first, axis=1)
    except ValueError:
        print(f"ValueError{df}")
    json_data = df.to_json(orient='records')
    return json_data


def move_last_valid_to_first(row):
    new_column_index = 11
    last_valid_idx = row.last_valid_index()  # 获取最后一个非NaN值的列索引
    if last_valid_idx is not None:
        last_valid_value = row[last_valid_idx]  # 获取最后一个非NaN值
        row = row.drop(labels=[last_valid_idx])  # 删除最后一个非NaN值所在的列
        if new_column_index in row.index:
            row = row.drop(labels = [new_column_index])
        row = pd.concat([pd.Series([last_valid_value], index=[11]), row])  # 将最后一个非NaN值添加到第一列
    return row
