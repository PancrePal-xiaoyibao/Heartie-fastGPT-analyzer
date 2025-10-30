import pandas as pd
import json
import numpy as np
from datetime import datetime
import re
from collections import Counter
import os

def convert_numpy_types(obj):
    """转换numpy类型为Python原生类型，用于JSON序列化"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_types(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_types(item) for item in obj]
    else:
        return obj

class MonthlyAnalyzer:
    def __init__(self, month_data):
        self.df = month_data
        self.analysis_result = {}
    
    def basic_metrics(self):
        """基础指标"""
        # 检查列名并使用正确的列
        user_col = 'user_id' if 'user_id' in self.df.columns else None
        dialogue_col = 'clean_dialogue' if 'clean_dialogue' in self.df.columns else None
        time_col = 'timestamp' if 'timestamp' in self.df.columns else None
        
        metrics = {
            'total_dialogues': int(len(self.df)),
            'unique_users': int(self.df[user_col].nunique()) if user_col else 'N/A',
            'avg_dialogue_length': float(self.df[dialogue_col].str.len().mean()) if dialogue_col else 0.0,
        }
        
        if time_col and not self.df[time_col].isna().all():
            metrics['date_range'] = {
                'start': str(self.df[time_col].min()),
                'end': str(self.df[time_col].max())
            }
        else:
            metrics['date_range'] = {'start': 'N/A', 'end': 'N/A'}
            
        return metrics
    
    def time_distribution(self):
        """时间分布：按小时、按星期、按日聚合数量"""
        if 'timestamp' not in self.df.columns or self.df['timestamp'].isna().all():
            return {
                'by_hour': {},
                'by_weekday': {},
                'by_date': {}
            }
        ts = pd.to_datetime(self.df['timestamp'], errors='coerce')
        by_hour = ts.dt.hour.value_counts().sort_index()
        by_weekday = ts.dt.weekday.value_counts().sort_index()
        by_date = ts.dt.date.value_counts().sort_index()
        return {
            'by_hour': {int(k): int(v) for k, v in by_hour.items()},
            'by_weekday': {int(k): int(v) for k, v in by_weekday.items()},
            'by_date': {str(k): int(v) for k, v in by_date.items()}
        }

    def estimated_turns(self):
        """轮次估计：粗略以标点和换行分段估计一条对话中的轮次（无原始分条时）"""
        if 'clean_dialogue' not in self.df.columns:
            return {'avg_turns': 0, 'distribution': {}}
        def estimate_turns(text: str) -> int:
            if not isinstance(text, str):
                return 0
            # 以问号、句号、换行等为分隔估算轮次
            parts = re.split(r'[\n。！？!?]+', text)
            parts = [p.strip() for p in parts if p.strip()]
            return max(1, len(parts))
        turns = self.df['clean_dialogue'].apply(estimate_turns)
        dist = turns.value_counts().sort_index()
        return {
            'avg_turns': float(turns.mean()),
            'distribution': {int(k): int(v) for k, v in dist.items()}
        }

    def keyword_extraction(self, top_k: int = 30):
        """关键词/短语提取：基于频次与2-gram/3-gram共现的简单提取（中文）"""
        if 'clean_dialogue' not in self.df.columns:
            return {'unigrams': [], 'bigrams': [], 'trigrams': []}
        texts = self.df['clean_dialogue'].astype(str).tolist()
        # 基于汉字与词边界的简单分词（极简法：按中文字符或词语间空白）
        # 为减少噪音，先移除常见停用词
        stopwords = set(['的','了','和','是','在','我','我们','你','您','他','她','它','与','及','或','而且','但是','因为','所以','如果','那么','这个','那个','还有','以及','对','请','谢谢','您好','吗','呢','啊','吧'])
        def tokenize(text: str):
            text = re.sub(r'[^\u4e00-\u9fffA-Za-z0-9\s]', ' ', text)
            tokens = re.split(r'\s+', text)
            tokens = [t for t in tokens if t and t not in stopwords and len(t) >= 2]
            return tokens
        tokens_all = []
        for t in texts:
            tokens_all.extend(tokenize(t))
        uni_counts = Counter(tokens_all)
        # n-grams
        def ngrams(tokens, n):
            return [''.join(tokens[i:i+n]) for i in range(len(tokens)-n+1)]
        bi_all, tri_all = [], []
        for t in texts:
            toks = tokenize(t)
            bi_all.extend(ngrams(toks, 2))
            tri_all.extend(ngrams(toks, 3))
        bi_counts = Counter(bi_all)
        tri_counts = Counter(tri_all)
        return {
            'unigrams': [{'term': k, 'count': int(v)} for k, v in uni_counts.most_common(top_k)],
            'bigrams': [{'term': k, 'count': int(v)} for k, v in bi_counts.most_common(top_k)],
            'trigrams': [{'term': k, 'count': int(v)} for k, v in tri_counts.most_common(top_k)]
        }

    def conversation_analysis(self):
        """对话主题分析"""
        # 定义主题关键词（支持 .env 中 JSON 覆盖）
        themes_env = os.getenv('CONVERSATION_THEMES', '').strip()
        themes = None
        if themes_env:
            try:
                data = json.loads(themes_env)
                if isinstance(data, dict):
                    # 确保所有值为列表
                    themes = {str(k): list(v) for k, v in data.items()}
            except Exception:
                pass
        if themes is None:
            themes = {
                'symptom_management': ['症状', '疼痛', '难受', '副作用', '化疗', '放疗'],
                'emotional_support': ['担心', '害怕', '焦虑', '支持', '陪伴', '心理'],
                'treatment_info': ['治疗', '方案', '药物', '医院', '医生', '检查'],
                'daily_care': ['饮食', '休息', '运动', '护理', '生活', '建议'],
                'family_support': ['家属', '家人', '照顾', '帮助', '陪伴', '支持']
            }
        
        theme_counts = {}
        for theme, keywords in themes.items():
            count = 0
            for keyword in keywords:
                count += self.df['clean_dialogue'].str.contains(keyword, na=False).sum()
            theme_counts[theme] = count
        
        return theme_counts
    
    def user_journey_analysis(self):
        """用户旅程分析"""
        user_col = 'user_id' if 'user_id' in self.df.columns else None
        sentiment_col = 'sentiment' if 'sentiment' in self.df.columns else None
        
        if user_col and sentiment_col:
            # 分析用户首次对话vs后续对话
            user_first_dialogue = self.df.groupby(user_col).first()
            user_last_dialogue = self.df.groupby(user_col).last()
            
            # 简单的情感变化分析
            first_sentiment = convert_numpy_types(user_first_dialogue[sentiment_col].value_counts().to_dict())
            last_sentiment = convert_numpy_types(user_last_dialogue[sentiment_col].value_counts().to_dict())
        else:
            # 如果没有用户ID，使用整体情感分布
            if sentiment_col:
                sentiment_dist = convert_numpy_types(self.df[sentiment_col].value_counts().to_dict())
                first_sentiment = sentiment_dist
                last_sentiment = sentiment_dist
            else:
                first_sentiment = {'neutral': len(self.df)}
                last_sentiment = {'neutral': len(self.df)}
        
        return {
            'first_interaction_sentiment': first_sentiment,
            'last_interaction_sentiment': last_sentiment
        }
    
    def pain_points_identification(self):
        """痛点识别"""
        pain_indicators = [
            '不懂', '不知道', '不明白', '困惑', '迷茫',
            '急', '紧急', '严重', '危险', '害怕',
            '等', '等待', '时间长', '慢', '效率低'
        ]
        
        pain_points = []
        for indicator in pain_indicators:
            mask = self.df['clean_dialogue'].str.contains(indicator, na=False)
            if mask.any():
                sample_dialogues = self.df[mask]['clean_dialogue'].head(3).tolist()
                pain_points.append({
                    'indicator': indicator,
                    'count': mask.sum(),
                    'examples': sample_dialogues
                })
        
        return sorted(pain_points, key=lambda x: x['count'], reverse=True)[:10]
    
    def volunteer_effectiveness(self):
        """志愿者效果分析"""
        user_type_col = 'user_type' if 'user_type' in self.df.columns else None
        user_col = 'user_id' if 'user_id' in self.df.columns else None
        
        if user_type_col:
            volunteer_messages = self.df[self.df[user_type_col] == 'volunteer']
            
            if len(volunteer_messages) > 0:
                if user_col:
                    # 分析志愿者参与的对话
                    volunteer_sessions = volunteer_messages.groupby(user_col)
                    session_count = len(volunteer_sessions)
                    avg_messages = len(volunteer_messages) / session_count if session_count > 0 else 0
                else:
                    session_count = len(volunteer_messages)
                    avg_messages = 1
                
                return {
                    'total_volunteer_sessions': int(session_count),
                    'avg_volunteer_messages_per_session': float(avg_messages),
                    'volunteer_response_time': 'N/A'  # 需要更复杂的时间分析
                }
            else:
                return {
                    'total_volunteer_sessions': 0,
                    'message': '本月无志愿者参与记录'
                }
        else:
            return {
                'total_volunteer_sessions': 0,
                'message': '无用户类型数据'
            }
    
    def generate_insights(self):
        """生成洞察"""
        insights = []
        
        # 基于主题分析的洞察
        themes = self.conversation_analysis()
        top_theme = max(themes, key=themes.get)
        insights.append(f"本月用户最关注的问题是：{top_theme.replace('_', ' ')}")
        
        # 基于痛点的洞察
        pain_points = self.pain_points_identification()
        if pain_points:
            top_pain = pain_points[0]
            insights.append(f"用户最大痛点是：{top_pain['indicator']}，出现了{top_pain['count']}次")
        
        # 基于情感的洞察
        sentiment_dist = self.df['sentiment'].value_counts().to_dict()
        if 'negative' in sentiment_dist and sentiment_dist['negative'] > len(self.df) * 0.3:
            insights.append("本月负面情绪较高，需要加强心理支持服务")
        
        return insights
    
    def comprehensive_analysis(self):
        """综合分析"""
        # 安全获取月份信息
        month_info = 'unknown'
        if 'year_month' in self.df.columns and len(self.df) > 0:
            try:
                month_info = str(self.df['year_month'].iloc[0])
            except:
                pass
        elif 'timestamp' in self.df.columns and len(self.df) > 0:
            try:
                first_date = pd.to_datetime(self.df['timestamp'].iloc[0])
                month_info = first_date.strftime('%Y-%m')
            except:
                pass
        
        # 执行所有分析并转换数据类型
        self.analysis_result = convert_numpy_types({
            'month': month_info,
            'basic_metrics': self.basic_metrics(),
            'time_distribution': self.time_distribution(),
            'estimated_turns': self.estimated_turns(),
            'keywords': self.keyword_extraction(),
            'conversation_themes': self.conversation_analysis(),
            'user_journey': self.user_journey_analysis(),
            'pain_points': self.pain_points_identification(),
            'volunteer_effectiveness': self.volunteer_effectiveness(),
            'insights': self.generate_insights(),
            'recommendations': self.generate_recommendations()
        })
        
        return self.analysis_result
    
    def generate_recommendations(self):
        """生成改进建议"""
        recommendations = []
        
        themes = self.conversation_analysis()
        pain_points = self.pain_points_identification()
        
        # 基于主题的建议
        if themes.get('symptom_management', 0) > len(self.df) * 0.2:
            recommendations.append("建议增加症状管理的标准化回复模板")
        
        if themes.get('emotional_support', 0) > len(self.df) * 0.15:
            recommendations.append("建议培训更多心理咨询志愿者")
        
        # 基于痛点的建议
        for pain in pain_points[:3]:
            if pain['indicator'] in ['等', '等待', '时间长']:
                recommendations.append("优化响应时间，考虑增加智能回复功能")
            elif pain['indicator'] in ['不懂', '不知道', '不明白']:
                recommendations.append("简化医疗术语，增加科普内容")
        
        return recommendations

# 批量处理所有月份
def process_all_months(input_dir):
    import os
    import glob
    
    # 找到所有月度文件
    monthly_files = glob.glob(f"{input_dir}/data_*.csv")
    
    all_monthly_reports = []
    
    for file_path in monthly_files:
        print(f"处理文件: {file_path}")
        
        try:
            month_data = pd.read_csv(file_path)
            analyzer = MonthlyAnalyzer(month_data)
            report = analyzer.comprehensive_analysis()
            
            # 保存月度报告
            month = report['month']
            with open(f"{input_dir}/report_{month}.json", 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            
            all_monthly_reports.append(report)
            
        except Exception as e:
            print(f"处理文件失败 {file_path}: {e}")
    
    return all_monthly_reports

if __name__ == "__main__":
    # 处理所有月度数据
    reports = process_all_months("processed_data")
    
    # 生成季度汇总
    if reports:
        quarterly_summary = {
            'total_months': len(reports),
            'total_dialogues': sum(r['basic_metrics']['total_dialogues'] for r in reports),
            'key_trends': [r['insights'][:2] for r in reports],
            'priority_recommendations': list(set(sum([r['recommendations'] for r in reports], [])))[:5]
        }
        
        with open("processed_data/quarterly_summary.json", 'w', encoding='utf-8') as f:
            json.dump(quarterly_summary, f, ensure_ascii=False, indent=2)
        
        print("季度汇总完成!")