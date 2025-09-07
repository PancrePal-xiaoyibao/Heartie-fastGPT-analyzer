#!/usr/bin/env python3
"""
小馨宝运营分析 - 单元测试模块
测试各个组件的功能和边界情况
"""

import unittest
import pandas as pd
import json
import tempfile
import os
from io import StringIO
from data_preprocessor import XiaoXinBaoDataProcessor
from monthly_analyzer import MonthlyAnalyzer, convert_numpy_types
import numpy as np

class TestDataPreprocessor(unittest.TestCase):
    """测试数据预处理器"""
    
    def setUp(self):
        """设置测试数据"""
        # 创建测试CSV数据
        self.test_csv_content = """时间,来源,使用者,联系方式,标题,消息总数,用户赞同反馈,用户反对反馈,自定义反馈,标注答案,对话详情
2025/7/28 14:32,外部接入单点,shareChat-123,'-,测试标题,4,[],[],[],[],"[{""type"":""text"",""text"":{""content"":""您好，我是患者家属，需要帮助""}}]"
2025/7/29 15:30,外部接入单点,shareChat-456,'-,咨询问题,6,[],[],[],[],"[{""type"":""text"",""text"":{""content"":""我感到很担心和焦虑，化疗很痛苦""}}]"
2025/7/30 10:15,外部接入单点,shareChat-789,'-,志愿者咨询,3,[],[],[],[],"[{""type"":""text"",""text"":{""content"":""我是志愿者，想帮助患者""}}]"
"""
        
        # 创建临时文件
        self.temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8')
        self.temp_file.write(self.test_csv_content)
        self.temp_file.close()
        
        self.processor = XiaoXinBaoDataProcessor(self.temp_file.name)
    
    def tearDown(self):
        """清理测试数据"""
        os.unlink(self.temp_file.name)
    
    def test_load_data(self):
        """测试数据加载"""
        result = self.processor.load_data()
        self.assertTrue(result)
        self.assertEqual(len(self.processor.df), 3)
        self.assertEqual(len(self.processor.df.columns), 11)
    
    def test_clean_column_names(self):
        """测试列名清理"""
        self.processor.load_data()
        cleaned_columns = self.processor.clean_column_names()
        
        # 检查标准化列名
        expected_columns = ['timestamp', 'source', 'user_id', 'contact_type', 'title', 
                          'message_type', 'user_agreement', 'user_reply', 'auto_reply', 
                          'notes', 'dialogue_content']
        self.assertEqual(cleaned_columns, expected_columns)
    
    def test_parse_timestamp(self):
        """测试时间戳解析"""
        self.processor.load_data()
        self.processor.clean_column_names()
        valid_count = self.processor.parse_timestamp()
        
        self.assertEqual(valid_count, 3)
        self.assertIn('timestamp', self.processor.df.columns)
        self.assertIn('year_month', self.processor.df.columns)
    
    def test_extract_dialogue_content(self):
        """测试对话内容提取"""
        self.processor.load_data()
        self.processor.clean_column_names()
        avg_length = self.processor.extract_dialogue_content()
        
        self.assertGreater(avg_length, 0)
        self.assertIn('clean_dialogue', self.processor.df.columns)
        
        # 检查内容提取质量
        dialogues = self.processor.df['clean_dialogue'].tolist()
        self.assertIn('您好', dialogues[0])
        self.assertIn('担心', dialogues[1])
        self.assertIn('志愿者', dialogues[2])
    
    def test_categorize_users(self):
        """测试用户分类"""
        self.processor.load_data()
        self.processor.clean_column_names()
        self.processor.extract_dialogue_content()
        user_dist = self.processor.categorize_users()
        
        self.assertIn('user_type', self.processor.df.columns)
        self.assertIn('volunteer', user_dist)
        self.assertIn('patient_family', user_dist)
    
    def test_analyze_sentiment(self):
        """测试情感分析"""
        self.processor.load_data()
        self.processor.clean_column_names()
        self.processor.extract_dialogue_content()
        sentiment_dist = self.processor.analyze_sentiment()
        
        self.assertIn('sentiment', self.processor.df.columns)
        self.assertIn('negative', sentiment_dist)  # "担心和焦虑"应该被识别为负面
        self.assertIn('positive', sentiment_dist)   # "帮助"应该被识别为正面

class TestMonthlyAnalyzer(unittest.TestCase):
    """测试月度分析器"""
    
    def setUp(self):
        """设置测试数据"""
        # 创建测试DataFrame
        self.test_data = pd.DataFrame({
            'timestamp': pd.to_datetime(['2025-07-15 10:00', '2025-07-15 11:00', '2025-07-15 12:00']),
            'user_id': ['user1', 'user2', 'user1'],
            'clean_dialogue': [
                '我很担心治疗效果',
                '谢谢医生的帮助',
                '症状管理很重要'
            ],
            'user_type': ['patient_family', 'patient_family', 'volunteer'],
            'sentiment': ['negative', 'positive', 'neutral'],
            'year_month': pd.Period('2025-07')
        })
        
        self.analyzer = MonthlyAnalyzer(self.test_data)
    
    def test_basic_metrics(self):
        """测试基础指标计算"""
        metrics = self.analyzer.basic_metrics()
        
        self.assertEqual(metrics['total_dialogues'], 3)
        self.assertEqual(metrics['unique_users'], 2)
        self.assertIsInstance(metrics['avg_dialogue_length'], float)
        self.assertIn('date_range', metrics)
    
    def test_conversation_analysis(self):
        """测试对话主题分析"""
        themes = self.analyzer.conversation_analysis()
        
        self.assertIsInstance(themes, dict)
        self.assertIn('symptom_management', themes)
        self.assertIn('emotional_support', themes)
        self.assertGreater(themes['symptom_management'], 0)  # "症状管理"应该被识别
    
    def test_user_journey_analysis(self):
        """测试用户旅程分析"""
        journey = self.analyzer.user_journey_analysis()
        
        self.assertIn('first_interaction_sentiment', journey)
        self.assertIn('last_interaction_sentiment', journey)
        self.assertIsInstance(journey['first_interaction_sentiment'], dict)
    
    def test_pain_points_identification(self):
        """测试痛点识别"""
        pain_points = self.analyzer.pain_points_identification()
        
        self.assertIsInstance(pain_points, list)
        # 每个痛点应该有指定的结构
        if pain_points:
            pain_point = pain_points[0]
            self.assertIn('indicator', pain_point)
            self.assertIn('count', pain_point)
            self.assertIn('examples', pain_point)
    
    def test_comprehensive_analysis(self):
        """测试综合分析"""
        report = self.analyzer.comprehensive_analysis()
        
        required_keys = ['month', 'basic_metrics', 'conversation_themes', 
                        'user_journey', 'pain_points', 'volunteer_effectiveness',
                        'insights', 'recommendations']
        
        for key in required_keys:
            self.assertIn(key, report)
        
        # 测试JSON序列化
        try:
            json.dumps(report, ensure_ascii=False)
        except TypeError:
            self.fail("Report contains non-serializable data")

class TestConvertNumpyTypes(unittest.TestCase):
    """测试numpy类型转换"""
    
    def test_convert_numpy_int(self):
        """测试numpy整数转换"""
        result = convert_numpy_types(np.int64(42))
        self.assertEqual(result, 42)
        self.assertIsInstance(result, int)
    
    def test_convert_numpy_float(self):
        """测试numpy浮点数转换"""
        result = convert_numpy_types(np.float64(3.14))
        self.assertEqual(result, 3.14)
        self.assertIsInstance(result, float)
    
    def test_convert_numpy_array(self):
        """测试numpy数组转换"""
        result = convert_numpy_types(np.array([1, 2, 3]))
        self.assertEqual(result, [1, 2, 3])
        self.assertIsInstance(result, list)
    
    def test_convert_nested_dict(self):
        """测试嵌套字典转换"""
        test_data = {
            'int_val': np.int64(100),
            'float_val': np.float64(2.71),
            'nested': {
                'array_val': np.array([4, 5, 6]),
                'normal_val': 'text'
            }
        }
        
        result = convert_numpy_types(test_data)
        
        self.assertIsInstance(result['int_val'], int)
        self.assertIsInstance(result['float_val'], float)
        self.assertIsInstance(result['nested']['array_val'], list)
        self.assertEqual(result['nested']['normal_val'], 'text')

class TestEndToEnd(unittest.TestCase):
    """端到端测试"""
    
    def test_full_pipeline(self):
        """测试完整数据处理管道"""
        # 创建测试数据
        test_csv = """时间,来源,使用者,联系方式,标题,消息总数,用户赞同反馈,用户反对反馈,自定义反馈,标注答案,对话详情
2025/6/15 10:00,测试,user1,'-,测试,1,[],[],[],[],"[{""type"":""text"",""text"":{""content"":""我是癌症患者，感到很焦虑""}}]"
2025/7/15 11:00,测试,user2,'-,测试,1,[],[],[],[],"[{""type"":""text"",""text"":{""content"":""我是志愿者，想要帮助别人""}}]"
2025/7/16 12:00,测试,user3,'-,测试,1,[],[],[],[],"[{""type"":""text"",""text"":{""content"":""谢谢医生的专业建议""}}]"
"""
        
        # 创建临时文件
        temp_file = tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8')
        temp_file.write(test_csv)
        temp_file.close()
        
        try:
            # 数据预处理
            processor = XiaoXinBaoDataProcessor(temp_file.name)
            self.assertTrue(processor.load_data())
            
            processor.clean_column_names()
            processor.parse_timestamp()
            processor.extract_dialogue_content()
            processor.categorize_users()
            processor.analyze_sentiment()
            
            # 按月分割
            monthly_data = processor.split_by_month()
            self.assertGreater(len(monthly_data), 0)
            
            # 月度分析
            for month, data in monthly_data.items():
                analyzer = MonthlyAnalyzer(data)
                report = analyzer.comprehensive_analysis()
                
                # 验证报告结构
                self.assertIn('month', report)
                self.assertIn('basic_metrics', report)
                
                # 验证JSON序列化
                json_str = json.dumps(report, ensure_ascii=False)
                self.assertIsInstance(json_str, str)
                
        finally:
            os.unlink(temp_file.name)

def run_unit_tests():
    """运行所有单元测试"""
    # 创建测试套件
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()
    
    # 添加测试类
    suite.addTests(loader.loadTestsFromTestCase(TestDataPreprocessor))
    suite.addTests(loader.loadTestsFromTestCase(TestMonthlyAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestConvertNumpyTypes))
    suite.addTests(loader.loadTestsFromTestCase(TestEndToEnd))
    
    # 运行测试
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    
    # 返回测试结果
    return result.wasSuccessful()

if __name__ == '__main__':
    print("=== 小馨宝运营分析 - 单元测试 ===\n")
    
    success = run_unit_tests()
    
    if success:
        print("\n🎉 所有单元测试通过！")
    else:
        print("\n❌ 部分单元测试失败，请检查代码。")
