#!/usr/bin/env python3
"""
数据处理测试脚本
测试数据预处理和分析的各个环节
"""

import pandas as pd
import json
from data_preprocessor import XiaoXinBaoDataProcessor
from monthly_analyzer import MonthlyAnalyzer, convert_numpy_types

def test_data_loading():
    """测试数据加载"""
    print("=== 测试数据加载 ===")
    processor = XiaoXinBaoDataProcessor("input/filtered_data.csv")
    
    if processor.load_data():
        print(f"✓ 数据加载成功: {processor.df.shape}")
        print(f"原始列名: {processor.df.columns.tolist()}")
        return processor
    else:
        print("✗ 数据加载失败")
        return None

def test_column_cleaning(processor):
    """测试列名清理"""
    print("\n=== 测试列名清理 ===")
    try:
        cleaned_columns = processor.clean_column_names()
        print(f"✓ 列名清理成功: {cleaned_columns}")
        return True
    except Exception as e:
        print(f"✗ 列名清理失败: {e}")
        return False

def test_timestamp_parsing(processor):
    """测试时间戳解析"""
    print("\n=== 测试时间戳解析 ===")
    try:
        valid_count = processor.parse_timestamp()
        print(f"✓ 时间戳解析成功: {valid_count}/{len(processor.df)}")
        
        # 显示时间范围
        if 'timestamp' in processor.df.columns:
            min_time = processor.df['timestamp'].min()
            max_time = processor.df['timestamp'].max()
            print(f"时间范围: {min_time} 到 {max_time}")
        
        return True
    except Exception as e:
        print(f"✗ 时间戳解析失败: {e}")
        return False

def test_dialogue_extraction(processor):
    """测试对话内容提取"""
    print("\n=== 测试对话内容提取 ===")
    try:
        avg_length = processor.extract_dialogue_content()
        print(f"✓ 对话内容提取成功，平均长度: {avg_length:.2f}")
        
        # 检查提取质量
        if 'clean_dialogue' in processor.df.columns:
            non_empty = processor.df['clean_dialogue'].str.len() > 0
            print(f"非空对话比例: {non_empty.sum()}/{len(processor.df)} ({non_empty.mean()*100:.1f}%)")
        
        return True
    except Exception as e:
        print(f"✗ 对话内容提取失败: {e}")
        return False

def test_user_classification(processor):
    """测试用户分类"""
    print("\n=== 测试用户分类 ===")
    try:
        user_dist = processor.categorize_users()
        print(f"✓ 用户分类成功: {user_dist}")
        return True
    except Exception as e:
        print(f"✗ 用户分类失败: {e}")
        return False

def test_sentiment_analysis(processor):
    """测试情感分析"""
    print("\n=== 测试情感分析 ===")
    try:
        sentiment_dist = processor.analyze_sentiment()
        print(f"✓ 情感分析成功: {sentiment_dist}")
        return True
    except Exception as e:
        print(f"✗ 情感分析失败: {e}")
        return False

def test_monthly_split(processor):
    """测试月度数据分割"""
    print("\n=== 测试月度数据分割 ===")
    try:
        monthly_data = processor.split_by_month()
        print(f"✓ 月度分割成功: {len(monthly_data)} 个月")
        for month, data in monthly_data.items():
            print(f"  {month}: {len(data)} 条记录")
        return monthly_data
    except Exception as e:
        print(f"✗ 月度分割失败: {e}")
        return None

def test_monthly_analysis(monthly_data):
    """测试月度分析"""
    print("\n=== 测试月度分析 ===")
    
    if not monthly_data:
        print("✗ 无月度数据可供分析")
        return False
    
    success_count = 0
    for month, data in monthly_data.items():
        try:
            print(f"\n分析月份: {month}")
            analyzer = MonthlyAnalyzer(data)
            report = analyzer.comprehensive_analysis()
            
            # 测试JSON序列化
            json_str = json.dumps(report, ensure_ascii=False, indent=2)
            print(f"✓ {month} 分析成功，JSON长度: {len(json_str)}")
            
            # 显示关键指标
            metrics = report.get('basic_metrics', {})
            print(f"  对话数: {metrics.get('total_dialogues', 0)}")
            print(f"  平均长度: {metrics.get('avg_dialogue_length', 0):.1f}")
            
            success_count += 1
        except Exception as e:
            print(f"✗ {month} 分析失败: {e}")
    
    print(f"\n月度分析总结: {success_count}/{len(monthly_data)} 成功")
    return success_count > 0

def test_json_serialization():
    """测试JSON序列化功能"""
    print("\n=== 测试JSON序列化 ===")
    
    import numpy as np
    
    # 测试数据
    test_data = {
        'int64_value': np.int64(42),
        'float64_value': np.float64(3.14),
        'array_value': np.array([1, 2, 3]),
        'nested_dict': {
            'inner_int': np.int64(100),
            'inner_list': [np.int64(1), np.int64(2)]
        }
    }
    
    try:
        converted = convert_numpy_types(test_data)
        json_str = json.dumps(converted)
        print("✓ JSON序列化成功")
        print(f"转换结果: {converted}")
        return True
    except Exception as e:
        print(f"✗ JSON序列化失败: {e}")
        return False

def main():
    """主测试函数"""
    print("开始数据处理测试\n")
    
    # 测试序列
    tests_passed = 0
    total_tests = 0
    
    # 1. 数据加载
    total_tests += 1
    processor = test_data_loading()
    if processor:
        tests_passed += 1
    else:
        print("数据加载失败，终止测试")
        return
    
    # 2. 列名清理
    total_tests += 1
    if test_column_cleaning(processor):
        tests_passed += 1
    
    # 3. 时间戳解析
    total_tests += 1
    if test_timestamp_parsing(processor):
        tests_passed += 1
    
    # 4. 对话内容提取
    total_tests += 1
    if test_dialogue_extraction(processor):
        tests_passed += 1
    
    # 5. 用户分类
    total_tests += 1
    if test_user_classification(processor):
        tests_passed += 1
    
    # 6. 情感分析
    total_tests += 1
    if test_sentiment_analysis(processor):
        tests_passed += 1
    
    # 7. 月度分割
    total_tests += 1
    monthly_data = test_monthly_split(processor)
    if monthly_data:
        tests_passed += 1
    
    # 8. 月度分析
    total_tests += 1
    if test_monthly_analysis(monthly_data):
        tests_passed += 1
    
    # 9. JSON序列化
    total_tests += 1
    if test_json_serialization():
        tests_passed += 1
    
    # 总结
    print(f"\n=== 测试总结 ===")
    print(f"通过: {tests_passed}/{total_tests}")
    print(f"成功率: {tests_passed/total_tests*100:.1f}%")
    
    if tests_passed == total_tests:
        print("🎉 所有测试通过！数据处理管道正常工作。")
    else:
        print("⚠️  部分测试失败，需要进一步修复。")

if __name__ == "__main__":
    main()
