import os
import json
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib

# 设置中文字体
from matplotlib.font_manager import FontProperties, findfont, fontManager

# 设置中文字体
def set_chinese_font():
    plt.rcParams['axes.unicode_minus'] = False
    
    # Common Chinese fonts on Windows/Mac/Linux
    candidates = [
        'SimHei', 'Microsoft YaHei', 'SimSun', 'Malgun Gothic', 
        'PingFang SC', 'Heiti TC', 'WenQuanYi Micro Hei', 'Droid Sans Fallback'
    ]
    
    detected_font = None
    
    # Check what's actually available in fontManager
    available_fonts = set(f.name for f in fontManager.ttflist)
    
    for font in candidates:
        if font in available_fonts:
            detected_font = font
            break
            
    if detected_font:
        print(f"[Visualizer] 使用字体: {detected_font}")
        plt.rcParams['font.sans-serif'] = [detected_font] + plt.rcParams['font.sans-serif']
        return True
    else:
        # Fallback: Try to find any font file containing 'Hei' or 'Sun' or 'YaHei'
        print("[Visualizer] 未在标准列表中找到常用中文字体，尝试搜索系统字体...")
        try:
            import matplotlib.font_manager as fm
            # Simple heuristic: scan ttflist for likely candidates if exact match failed
            for f in fontManager.ttflist:
                if 'Hei' in f.name or 'Sun' in f.name or 'YaHei' in f.name:
                     print(f"[Visualizer] 找到系统字体: {f.name}")
                     plt.rcParams['font.sans-serif'] = [f.name] + plt.rcParams['font.sans-serif']
                     return True
        except Exception as e:
            print(f"搜索字体出错: {e}")

    print("[Visualizer] 警告: 未能自动配置中文字体，图表可能显示乱码。")
    return False

def generate_all_plots(processed_dir, output_dir_base):
    """
    Generate charts based on summary.json and processed data.
    """
    print("=== 开始生成可视化图表 ===")
    
    output_dir = os.path.join(output_dir_base, "plots")
    if not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)
        
    summary_path = os.path.join(processed_dir, "summary.json")
    if not os.path.exists(summary_path):
        print("未找到 summary.json，跳过可视化。")
        return

    try:
        with open(summary_path, 'r', encoding='utf-8') as f:
            summary = json.load(f)
    except Exception as e:
        print(f"读取摘要失败: {e}")
        return

    sns.set_style("whitegrid")
    # 设置字体必须在 set_style 之后，否则会被 seaborn 覆盖
    set_chinese_font()
    
    # 1. 话题分布 (Topic Distribution)
    topic_data = summary.get('topic_distribution', {})
    if topic_data:
        try:
           plot_horizontal_bar(topic_data, "热门话题分布", "次数", "话题", 
                             os.path.join(output_dir, "topic_distribution.png"), color='skyblue')
        except Exception as e:
            print(f"绘制话题图表失败: {e}")

    # 2. 用户类型分布 (User Type)
    user_data = summary.get('user_type_distribution', {})
    if user_data:
        try:
            plot_pie_chart(user_data, "用户类型占比", 
                         os.path.join(output_dir, "user_distribution.png"))
        except Exception as e:
            print(f"绘制用户图表失败: {e}")
            
    # 3. 情感分布 (Sentiment)
    sentiment_data = summary.get('sentiment_distribution', {})
    if sentiment_data:
        try:
            plot_bar_chart(sentiment_data, "情感分布", "类型", "数量",
                         os.path.join(output_dir, "sentiment_distribution.png"), color='salmon')
        except Exception as e:
            print(f"绘制情感图表失败: {e}")

    # 4. 月度趋势 (Monthly Trend)
    monthly_counts = summary.get('monthly_counts', {})
    if monthly_counts:
        try:
            plot_line_chart(monthly_counts, "月度对话量趋势", "月份", "对话数",
                          os.path.join(output_dir, "monthly_trend.png"))
        except Exception as e:
             print(f"绘制趋势图表失败: {e}")

    print(f"图表已保存至: {output_dir}")

def plot_horizontal_bar(data, title, xlabel, ylabel, save_path, color='skyblue'):
    # Sort data
    sorted_items = sorted(data.items(), key=lambda x: x[1], reverse=False) # Ascending for hbar
    keys = [k.replace('_', ' ').capitalize() for k, v in sorted_items]
    values = [v for k, v in sorted_items]
    
    plt.figure(figsize=(10, 6))
    bars = plt.barh(keys, values, color=color)
    plt.title(title, fontsize=14)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()

def plot_pie_chart(data, title, save_path):
    labels = [k.replace('_', ' ').capitalize() for k in data.keys()]
    sizes = list(data.values())
    
    plt.figure(figsize=(8, 8))
    plt.pie(sizes, labels=labels, autopct='%1.1f%%', startangle=140, 
            pctdistance=0.85, colors=sns.color_palette("pastel"))
    
    # Draw circle for Donut chart
    centre_circle = plt.Circle((0,0),0.70,fc='white')
    fig = plt.gcf()
    fig.gca().add_artist(centre_circle)
    
    plt.title(title, fontsize=14)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()

def plot_bar_chart(data, title, xlabel, ylabel, save_path, color='skyblue'):
    keys = list(data.keys())
    values = list(data.values())
    
    plt.figure(figsize=(8, 6))
    sns.barplot(x=keys, y=values, hue=keys, palette="viridis", legend=False)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()

def plot_line_chart(data, title, xlabel, ylabel, save_path):
    # Sort by date
    sorted_items = sorted(data.items())
    keys = [k for k, v in sorted_items]
    values = [v for k, v in sorted_items]
    
    plt.figure(figsize=(12, 6))
    sns.lineplot(x=keys, y=values, marker='o', linewidth=2.5)
    plt.title(title)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.xticks(rotation=45)
    plt.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300)
    plt.close()

if __name__ == "__main__":
    # Test run
    generate_all_plots("processed_data", "output")
