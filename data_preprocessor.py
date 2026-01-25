import pandas as pd
import numpy as np
from datetime import datetime
import json
import re
import re
import os
try:
    import yaml
except ImportError:
    yaml = None

try:
    # 允许通过 .env 覆盖关键词配置
    from dotenv import load_dotenv  # type: ignore
    load_dotenv()
except Exception:
    # 可选依赖，不存在时忽略
    pass

class XiaoXinBaoDataProcessor:
    def __init__(self, file_path):
        self.file_path = file_path
        self.df = None
        
    def load_data(self):
        """加载并修复编码问题"""
        try:
            # 尝试多种编码方式
            encodings = ['utf-8', 'gbk', 'gb2312', 'cp936']
            for encoding in encodings:
                try:
                    self.df = pd.read_csv(self.file_path, encoding=encoding)
                    print(f"成功使用 {encoding} 编码加载数据")
                    break
                except UnicodeDecodeError:
                    continue
            
            if self.df is None:
                # 如果都失败，使用二进制模式读取并修复
                with open(self.file_path, 'rb') as f:
                    content = f.read()
                # 尝试修复乱码
                content = content.decode('utf-8', errors='ignore')
                from io import StringIO
                self.df = pd.read_csv(StringIO(content))
                
        except Exception as e:
            print(f"加载数据失败: {e}")
            return False
        return True
    
    def clean_column_names(self):
        """清理和标准化列名"""
        # 如果已经是解析后的日志格式，跳过重命名
        if 'dialogue_content' in self.df.columns and 'timestamp' in self.df.columns:
            print("检测到已解析的日志格式，跳过列重命名")
            return self.df.columns.tolist()

        # 修复乱码列名，提供标准化的列名映射
        original_columns = self.df.columns.tolist()
        
        # 基于常见CSV结构定义标准列名
        standard_columns = [
            'timestamp', 'source', 'user_id', 'contact_type', 
            'title', 'message_type', 'user_agreement', 'user_reply',
            'auto_reply', 'notes', 'dialogue_content'
        ]
        
        # 创建列名映射
        column_mapping = {}
        for i, col in enumerate(original_columns):
            if i < len(standard_columns):
                column_mapping[col] = standard_columns[i]
            else:
                # 对于超出预期的列，进行清理
                clean_name = re.sub(r'[^\w\u4e00-\u9fff]', '', str(col))
                column_mapping[col] = clean_name or f'column_{i}'
        
        self.df = self.df.rename(columns=column_mapping)
        print(f"列名映射: {dict(list(column_mapping.items())[:5])}")
        return self.df.columns.tolist()
    
    def parse_timestamp(self):
        """解析时间戳"""
        # 使用标准化的时间戳列名
        if 'timestamp' in self.df.columns:
            # 先尝试多种时间格式
            time_formats = ['%Y/%m/%d %H:%M', '%Y-%m-%d %H:%M:%S', '%Y/%m/%d', '%Y-%m-%d']
            
            for fmt in time_formats:
                try:
                    self.df['parsed_timestamp'] = pd.to_datetime(self.df['timestamp'], format=fmt, errors='coerce')
                    if self.df['parsed_timestamp'].notna().sum() > 0:
                        break
                except:
                    continue
            
            # 如果格式化失败，使用通用解析
            if 'parsed_timestamp' not in self.df.columns or self.df['parsed_timestamp'].notna().sum() == 0:
                self.df['parsed_timestamp'] = pd.to_datetime(self.df['timestamp'], errors='coerce')
            
            # 替换原时间戳列
            self.df['timestamp'] = self.df['parsed_timestamp']
            self.df = self.df.drop('parsed_timestamp', axis=1)
            
        self.df['year_month'] = self.df['timestamp'].dt.to_period('M')
        valid_timestamps = self.df['timestamp'].notna().sum()
        print(f"成功解析时间戳: {valid_timestamps}/{len(self.df)}")
        return valid_timestamps
    
    def extract_dialogue_content(self):
        """提取对话内容"""
        # 使用标准化的对话内容列名
        dialogue_col = 'dialogue_content'
        
        def clean_dialogue(text):
            if pd.isna(text):
                return ""
            
            text = str(text)
            
            # 移除常见的乱码字符
            text = re.sub(r'[→ʱ��]', '', text)
            
            # 尝试从JSON格式中提取内容
            try:
                # 提取所有content字段的内容
                content_pattern = r'"content"\s*:\s*"([^"]*)"'
                content_matches = re.findall(content_pattern, text)
                
                if content_matches:
                    # 合并所有找到的内容
                    extracted_content = ' '.join(content_matches)
                    # 移除转义字符
                    extracted_content = extracted_content.replace('\\n', ' ').replace('\\"', '"')
                    return extracted_content
                
                # 如果没有找到JSON格式，尝试提取纯文本
                # 移除JSON结构字符，保留中文内容
                text_only = re.sub(r'[\[\]{}",:]', ' ', text)
                text_only = re.sub(r'type|text|content|interactive|userSelect|params|description|value|key', '', text_only)
                text_only = re.sub(r'\s+', ' ', text_only).strip()
                
                # 提取中文文本段落
                chinese_pattern = r'[\u4e00-\u9fff\w\s，。！？；：、（）]+'
                chinese_matches = re.findall(chinese_pattern, text_only)
                
                if chinese_matches:
                    return ' '.join(chinese_matches).strip()
                
                return text_only
                
            except Exception as e:
                print(f"对话提取错误: {e}")
                return str(text)
        
        self.df['clean_dialogue'] = self.df[dialogue_col].apply(clean_dialogue)
        avg_length = self.df['clean_dialogue'].str.len().mean()
        print(f"对话内容提取完成，平均长度: {avg_length:.2f}字符")
        
        # 显示一些样本用于验证
        print("对话内容样本:")
        for i, content in enumerate(self.df['clean_dialogue'].head(3)):
            print(f"样本{i+1}: {content[:100]}{'...' if len(content) > 100 else ''}")
        
        return avg_length
    
    def categorize_users(self):
        """用户分类"""
        # 从环境变量读取用户分类关键词，优先 JSON，其次逗号分隔列表，最后使用内置默认值
        def load_user_keywords():
            # JSON 结构：{"patient_family": [...], "volunteer": [...], "medical_professional": [...]}
            json_str = os.getenv('USER_CATEGORY_KEYWORDS', '').strip()
            if json_str:
                try:
                    data = json.loads(json_str)
                    # 基本校验
                    if isinstance(data, dict):
                        return {
                            'patient_family': list(data.get('patient_family', [])),
                            'volunteer': list(data.get('volunteer', [])),
                            'medical_professional': list(data.get('medical_professional', [])),
                        }
                except Exception:
                    pass
            # 兼容逗号分隔的独立变量
            def split_list(value):
                if not value:
                    return []
                # 支持中文逗号、顿号
                parts = [p.strip() for p in re.split(r'[，,、]', value) if p.strip()]
                return parts
            return {
                'patient_family': split_list(os.getenv('PATIENT_KEYWORDS', '')) or ['患者', '病人', '家属', '家人', '老公', '老婆', '妈妈', '爸爸', '儿子', '女儿', '确诊', '化疗', '放疗', '手术', '癌症', '肿瘤', '检查', '治疗'],
                'volunteer': split_list(os.getenv('VOLUNTEER_KEYWORDS', '')) or ['志愿者', '志愿', '帮助', '陪伴', '支持', '倾听', '服务', '援助'],
                'medical_professional': split_list(os.getenv('MEDICAL_KEYWORDS', '')) or ['医生', '医师', '护士', '专业', '医疗', '临床', '诊断', '用药', '医院'],
            }

        user_keywords = load_user_keywords()

        def classify_user(dialogue):
            dialogue_str = str(dialogue)
            
            # 关键词匹配（支持 .env 覆盖）
            patient_keywords = user_keywords.get('patient_family', [])
            volunteer_keywords = user_keywords.get('volunteer', [])
            medical_keywords = user_keywords.get('medical_professional', [])
            
            # 计算匹配度
            patient_score = sum(1 for word in patient_keywords if word in dialogue_str)
            volunteer_score = sum(1 for word in volunteer_keywords if word in dialogue_str)
            medical_score = sum(1 for word in medical_keywords if word in dialogue_str)
            
            # 根据最高得分分类
            if patient_score > 0 and patient_score >= volunteer_score and patient_score >= medical_score:
                return 'patient_family'
            elif volunteer_score > 0 and volunteer_score >= medical_score:
                return 'volunteer'
            elif medical_score > 0:
                return 'medical_professional'
            else:
                return 'other'
        
        self.df['user_type'] = self.df['clean_dialogue'].apply(classify_user)
        user_distribution = self.df['user_type'].value_counts().to_dict()
        print(f"用户类型分布: {user_distribution}")
        return user_distribution

    def load_breast_cancer_config(self):
        """加载乳腺癌分析专用配置"""
        config_path = os.path.join(os.path.dirname(__file__), 'config', 'breast_cancer_analyz_config.json')
        if os.path.exists(config_path):
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"加载配置文件失败: {e}")
        return None

    def categorize_topics(self):
        """按话题分类 (优选.env配置, 其次JSON)"""
        topics = {}
        
        # 1. 尝试从环境变量读取 (COMPATIBILITY with monthly_analyzer)
        themes_env = os.getenv('CONVERSATION_THEMES', '').strip()
        if themes_env:
            try:
                data = json.loads(themes_env)
                if isinstance(data, dict):
                    topics = {str(k): list(v) for k, v in data.items()}
            except Exception:
                pass
        
        # 2. 如果环境变量未设置，尝试读取 JSON 配置文件
        if not topics:
            config = self.load_breast_cancer_config()
            if config and 'topics' in config:
                topics = config['topics']
        
        if not topics:
            print("未找到话题配置(.env CONVERSATION_THEMES 或 JSON)，跳过话题分类")
            return {}
        
        def get_topic(text):
            text_str = str(text)
            matched_topics = []
            for topic, keywords in topics.items():
                if any(keyword in text_str for keyword in keywords):
                    matched_topics.append(topic)
            
            if not matched_topics:
                return 'other'
            return ','.join(matched_topics) # Allow multi-label or just pick first? Picking join for now.

        self.df['topics'] = self.df['clean_dialogue'].apply(get_topic)
        
        # Split multi-label for counting
        all_topics = []
        for t in self.df['topics']:
            if t:
                all_topics.extend(t.split(','))
        
        from collections import Counter
        topic_distribution = dict(Counter(all_topics))
        print(f"话题分布: {topic_distribution}")
        return topic_distribution
    
    def analyze_sentiment(self):
        """情感分析"""
        # 从环境变量读取情感词库，优先 JSON，其次逗号分隔，最后默认
        def load_sentiment_words():
            # JSON 结构：{"positive": [...], "negative": [...], "neutral": [...]}
            json_str = os.getenv('SENTIMENT_WORDS', '').strip()
            if json_str:
                try:
                    data = json.loads(json_str)
                    if isinstance(data, dict):
                        return (
                            list(data.get('positive', [])),
                            list(data.get('negative', [])),
                            list(data.get('neutral', [])),
                        )
                except Exception:
                    pass
            def split_list(value):
                if not value:
                    return []
                return [p.strip() for p in re.split(r'[，,、]', value) if p.strip()]
            positive = split_list(os.getenv('POSITIVE_WORDS', '')) or ['谢谢', '感谢', '帮助', '有用', '好', '棒', '专业', '安慰', '支持', '鼓励', '温暖', '理解', '陪伴', '放心', '舒服', '开心', '满意', '赞']
            negative = split_list(os.getenv('NEGATIVE_WORDS', '')) or ['担心', '害怕', '痛苦', '难受', '焦虑', '不好', '没用', '绝望', '沮丧', '恐惧', '抑郁', '烦躁', '失望', '无助', '孤独', '崩溃', '压抑']
            neutral = split_list(os.getenv('NEUTRAL_WORDS', '')) or ['咨询', '询问', '了解', '知道', '请教', '想问', '如何', '什么', '怎么']
            return (positive, negative, neutral)

        positive_words_default, negative_words_default, neutral_words_default = load_sentiment_words()

        def get_sentiment(text):
            text_str = str(text)
            
            # 情感词汇（支持 .env 覆盖）
            positive_words = positive_words_default
            negative_words = negative_words_default
            neutral_words = neutral_words_default
            
            # 计算情感得分
            positive_score = sum(1 for word in positive_words if word in text_str)
            negative_score = sum(1 for word in negative_words if word in text_str)
            neutral_score = sum(1 for word in neutral_words if word in text_str)
            
            # 情感判断逻辑
            if positive_score > negative_score and positive_score > 0:
                return 'positive'
            elif negative_score > positive_score and negative_score > 0:
                return 'negative'
            elif neutral_score > 0 or len(text_str.strip()) > 10:  # 有内容但无明显情感倾向
                return 'neutral'
            else:
                return 'neutral'
        
        self.df['sentiment'] = self.df['clean_dialogue'].apply(get_sentiment)
        sentiment_distribution = self.df['sentiment'].value_counts().to_dict()
        print(f"情感分布: {sentiment_distribution}")
        return sentiment_distribution
    
    def split_by_month(self):
        """按月份分割数据"""
        monthly_data = {}
        for month, group in self.df.groupby('year_month'):
            monthly_data[str(month)] = group
        return monthly_data
    
    def save_processed_data(self, output_dir, format='csv'):
        """保存处理后的数据"""
        import os
        os.makedirs(output_dir, exist_ok=True)
        
        # 保存完整清洗数据
        if format == 'yaml':
            # Convert DF to list of dicts for YAML dump
            data_dict = self.df.to_dict(orient='records')
            # Handle timestamps for YAML serialization
            for row in data_dict:
                for k, v in row.items():
                    if pd.isna(v):
                        row[k] = None
                    elif hasattr(v, 'isoformat'):
                        row[k] = v.isoformat()
            
            output_file = f"{output_dir}/cleaned_data.yaml"
            if yaml:
                with open(output_file, 'w', encoding='utf-8') as f:
                    yaml.dump(data_dict, f, allow_unicode=True, sort_keys=False)
                print(f"已保存 YAML 数据: {output_file}")
            else:
                print("未安装 PyYAML，无法保存为 YAML 格式。")
        else:
            self.df.to_csv(f"{output_dir}/cleaned_data.csv", index=False, encoding='utf-8')
        
        # 按月份分割保存
        monthly_data = self.split_by_month()
        for month, data in monthly_data.items():
            filename = f"{output_dir}/data_{month.replace('/', '-')}.csv"
            data.to_csv(filename, index=False, encoding='utf-8')
            print(f"保存月份数据: {filename}, 记录数: {len(data)}")
        
        # 生成摘要统计
        summary = {
            'total_records': len(self.df),
            'date_range': {
                'start': str(self.df['timestamp'].min()),
                'end': str(self.df['timestamp'].max())
            },
            'user_type_distribution': self.categorize_users(),
            'sentiment_distribution': self.analyze_sentiment(),
            'topic_distribution': self.categorize_topics(), # Added
            'monthly_counts': {str(k): len(v) for k, v in monthly_data.items()}
        }
        
        with open(f"{output_dir}/summary.json", 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
            
        if format == 'yaml' and yaml:
             with open(f"{output_dir}/summary.yaml", 'w', encoding='utf-8') as f:
                yaml.dump(summary, f, allow_unicode=True, sort_keys=False)
        
        return summary

# 使用示例
if __name__ == "__main__":
    processor = XiaoXinBaoDataProcessor("input/filtered_data.csv")
    
    if processor.load_data():
        print("原始数据形状:", processor.df.shape)
        
        # 数据清洗
        processor.clean_column_names()
        processor.parse_timestamp()
        processor.extract_dialogue_content()
        
        # 保存处理结果
        summary = processor.save_processed_data("processed_data")
        print("处理完成!")
        print("摘要统计:", summary)