#!/usr/bin/env python3
"""
小馨宝运营数据分析完整流程

使用方法：
1. 数据预处理：python run_analysis.py --preprocess
2. 月度分析：python run_analysis.py --analyze-monthly
3. 完整流程：python run_analysis.py --full

新增：
- 支持 --input-file 自定义输入（默认 input/chat_logs.csv，兼容 input/filtered_data.csv）
- 支持 --output-dir 自定义输出目录（默认 processed_data）
- 完整流程会额外生成 Markdown 报告到 output/analysis_report.md（可用 --report-dir 指定目录）
"""

import argparse
import os
import sys
import json
import requests
from typing import List, Dict
from data_preprocessor import XiaoXinBaoDataProcessor
from monthly_analyzer import process_all_months

def resolve_input_file(cli_input: str = None) -> str:
    """解析输入文件路径，优先顺序：
    1) 命令行 --input-file
    2) input/chat_logs.csv
    3) input/filtered_data.csv
    4) 根目录兼容（向后兼容）
    """
    if cli_input:
        return cli_input
    
    # 优先检查 input/ 目录
    if os.path.exists('input/chat_logs.csv'):
        return 'input/chat_logs.csv'
    if os.path.exists('input/filtered_data.csv'):
        return 'input/filtered_data.csv'
    
    # 兼容根目录（向后兼容）
    if os.path.exists('chat_logs.csv'):
        return 'chat_logs.csv'
    if os.path.exists('filtered_data.csv'):
        return 'filtered_data.csv'
    
    return ''

def ensure_dir(path: str) -> None:
    if path and not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def preprocess_data(input_file: str, output_dir: str) -> bool:
    """数据预处理"""
    print("=== 开始数据预处理 ===")
    if not input_file or not os.path.exists(input_file):
        print("未找到输入文件。请在 input/ 目录放置 chat_logs.csv 或使用 --input-file 指定。")
        return False
    processor = XiaoXinBaoDataProcessor(input_file)
    
    if processor.load_data():
        print("原始数据形状:", processor.df.shape)
        
        # 执行数据清洗
        processor.clean_column_names()
        print("列名已清洗")
        
        valid_rows = processor.parse_timestamp()
        print(f"有效时间戳: {valid_rows}/{len(processor.df)}")
        
        avg_length = processor.extract_dialogue_content()
        print(f"平均对话长度: {avg_length:.2f}字符")
        
        user_types = processor.categorize_users()
        print("用户类型分布:", user_types)
        
        sentiments = processor.analyze_sentiment()
        print("情感分布:", sentiments)
        
        # 保存处理结果
        ensure_dir(output_dir)
        summary = processor.save_processed_data(output_dir)
        print("\n=== 处理完成 ===")
        print("摘要统计:")
        for key, value in summary.items():
            print(f"  {key}: {value}")
        
        return True
    else:
        print("数据加载失败")
        return False

def run_monthly_analysis(processed_dir: str) -> List[Dict]:
    """运行月度分析"""
    print("=== 开始月度分析 ===")
    if not os.path.exists(processed_dir):
        print("请先运行数据预处理")
        return []
    try:
        reports = process_all_months(processed_dir)
        
        print(f"\n=== 分析完成，共处理 {len(reports)} 个月的数据 ===")
        
        # 打印每个月的关键指标
        for report in reports:
            month = report['month']
            metrics = report['basic_metrics']
            print(f"\n{month}:")
            print(f"  对话数: {metrics['total_dialogues']}")
            print(f"  洞察: {'; '.join(report['insights'])}")
            print(f"  建议: {'; '.join(report['recommendations'][:2])}")
        
        return reports
        
    except Exception as e:
        print(f"分析失败: {e}")
        return []

def render_markdown_report(reports: List[Dict], summary_json_path: str) -> str:
    """将分析结果渲染为 Markdown 文本。"""
    lines: List[str] = []
    lines.append('# 小馨宝运营分析报告')
    lines.append('')
    lines.append('## 月度概览')
    lines.append('')
    for report in reports:
        month = report.get('month', '')
        metrics = report.get('basic_metrics', {})
        time_dist = report.get('time_distribution', {})
        est_turns = report.get('estimated_turns', {})
        keywords = report.get('keywords', {})
        insights = report.get('insights', [])
        recs = report.get('recommendations', [])
        lines.append(f'### {month}')
        lines.append('')
        lines.append(f'- 总对话数: {metrics.get("total_dialogues", 0)}')
        lines.append(f'- 唯一用户数: {metrics.get("unique_users", 0)}')
        lines.append(f'- 平均对话长度: {metrics.get("avg_dialogue_length", 0)}')
        date_range = metrics.get('date_range', {})
        if date_range:
            lines.append(f'- 时间范围: {date_range.get("start", "")} ~ {date_range.get("end", "")}')
        if insights:
            lines.append('- 关键洞察: ' + '; '.join(insights))
        if recs:
            lines.append('- 建议: ' + '; '.join(recs[:3]))
        lines.append('')
        # 新增：时间分布
        if time_dist:
            lines.append('#### 时间分布')
            lines.append('')
            lines.append(f'- 按小时: {time_dist.get("by_hour", {})}')
            lines.append(f'- 按星期: {time_dist.get("by_weekday", {})}  (0=周一)')
            lines.append(f'- 按日期: {list(time_dist.get("by_date", {}).items())[:10]} ...')
            lines.append('')
        # 新增：轮次估计
        if est_turns:
            lines.append('#### 轮次估计')
            lines.append('')
            lines.append(f'- 平均轮次: {est_turns.get("avg_turns", 0):.2f}')
            lines.append(f'- 轮次分布: {est_turns.get("distribution", {})}')
            lines.append('')
        # 新增：关键词/短语
        if keywords:
            lines.append('#### 关键词与短语')
            lines.append('')
            def format_terms(items):
                return ', '.join([f"{i['term']}({i['count']})" for i in items[:15]])
            lines.append(f'- 关键词: {format_terms(keywords.get("unigrams", []))}')
            lines.append(f'- 2-gram: {format_terms(keywords.get("bigrams", []))}')
            lines.append(f'- 3-gram: {format_terms(keywords.get("trigrams", []))}')
            lines.append('')
    if os.path.exists(summary_json_path):
        lines.append('## 数据摘要')
        lines.append('')
        lines.append(f'> 详见 `{summary_json_path}`')
        lines.append('')
    return '\n'.join(lines)

def load_env_key(env_path: str, key: str) -> str:
    """从 .env 加载指定键，优先读取系统环境变量。"""
    val = os.getenv(key)
    if val:
        return val
    if not env_path or not os.path.exists(env_path):
        return ''
    try:
        with open(env_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' in line:
                    k, v = line.split('=', 1)
                    if k.strip() == key:
                        return v.strip().strip('"').strip("'")
    except Exception:
        return ''
    return ''

def estimate_tokens(text: str) -> int:
    """粗略估计文本的token数量（中文按字数，英文按词数）"""
    chinese_chars = len([c for c in text if '\u4e00' <= c <= '\u9fff'])
    english_words = len(text.replace('\n', ' ').split()) - chinese_chars
    return chinese_chars + english_words // 3

def split_content_by_tokens(content: str, max_tokens: int) -> list:
    """按token限制分割内容"""
    chunks = []
    lines = content.split('\n')
    current_chunk = []
    current_tokens = 0
    
    for line in lines:
        line_tokens = estimate_tokens(line)
        if current_tokens + line_tokens > max_tokens and current_chunk:
            chunks.append('\n'.join(current_chunk))
            current_chunk = [line]
            current_tokens = line_tokens
        else:
            current_chunk.append(line)
            current_tokens += line_tokens
    
    if current_chunk:
        chunks.append('\n'.join(current_chunk))
    
    return chunks

def call_deepseek_chat(api_key: str, system_prompt: str, user_content: str,
                       model: str = 'deepseek-chat', base_url: str = 'https://api.deepseek.com',
                       timeout_sec: int = 60, stream: bool = False, max_tokens: int = 0,
                       chunk_size: int = 0) -> str:
    """调用 AI Chat Completions API，支持分块处理，返回文本内容。"""
    
    # 如果需要分块处理
    if chunk_size > 0 and estimate_tokens(user_content) > chunk_size:
        print(f"内容过长({estimate_tokens(user_content)} tokens)，启用分块处理...")
        chunks = split_content_by_tokens(user_content, chunk_size)
        print(f"分为 {len(chunks)} 块处理")
        
        all_responses = []
        conversation_history = []
        
        for i, chunk in enumerate(chunks, 1):
            print(f"\n=== 处理第 {i}/{len(chunks)} 块 ===")
            
            # 构建对话历史
            messages = [{'role': 'system', 'content': system_prompt}]
            messages.extend(conversation_history)
            
            # 添加当前块的问题
            if i == 1:
                chunk_prompt = f"请分析以下运营数据（第{i}部分，共{len(chunks)}部分）：\n\n{chunk}"
            else:
                chunk_prompt = f"继续分析运营数据（第{i}部分，共{len(chunks)}部分）：\n\n{chunk}"
            
            messages.append({'role': 'user', 'content': chunk_prompt})
            
            # 调用API处理当前块
            response = _single_api_call(messages, model, base_url, api_key, timeout_sec, stream)
            all_responses.append(response)
            
            # 更新对话历史
            conversation_history.extend([
                {'role': 'user', 'content': chunk_prompt},
                {'role': 'assistant', 'content': response}
            ])
        
        # 最终整合
        final_prompt = f"基于前面 {len(chunks)} 部分的分析，请生成最终的完整运营分析报告，遵循之前的Markdown格式要求。"
        messages = [{'role': 'system', 'content': system_prompt}]
        messages.extend(conversation_history)
        messages.append({'role': 'user', 'content': final_prompt})
        
        print(f"\n=== 生成最终整合报告 ===")
        final_response = _single_api_call(messages, model, base_url, api_key, timeout_sec, stream)
        return final_response
    
    else:
        # 单次处理
        messages = [
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': user_content}
        ]
        return _single_api_call(messages, model, base_url, api_key, timeout_sec, stream)

def _single_api_call(messages: list, model: str, base_url: str, api_key: str, 
                     timeout_sec: int, stream: bool) -> str:
    """执行单次API调用"""
    # 兼容带/不带v1，自动规范化
    base = base_url.rstrip('/')
    if base.endswith('/v1'):
        url = f"{base}/chat/completions"
    else:
        url = f"{base}/chat/completions"
    headers = {
        'Content-Type': 'application/json; charset=utf-8',
        'Authorization': f'Bearer {api_key}',
        'Accept': 'application/json; charset=utf-8'
    }
    payload = {
        'model': model,
        'messages': messages,
        'stream': bool(stream)
    }
    if stream:
        # 流式打印到终端，同时聚合内容
        with requests.post(url, headers=headers, data=json.dumps(payload, ensure_ascii=False), timeout=timeout_sec, stream=True) as r:
            r.raise_for_status()
            r.encoding = 'utf-8'  # 强制设置编码
            full_text_parts: List[str] = []
            for line in r.iter_lines(decode_unicode=True):
                if not line:
                    continue
                # 确保line是正确编码的字符串
                if isinstance(line, bytes):
                    line = line.decode('utf-8', errors='ignore')
                
                if line.startswith('data: '):
                    data_str = line[len('data: '):].strip()
                    if data_str == '[DONE]':
                        break
                    try:
                        obj = json.loads(data_str)
                        delta = obj.get('choices', [{}])[0].get('delta', {}).get('content', '')
                        if delta:
                            # 确保delta是正确的UTF-8字符串
                            if isinstance(delta, bytes):
                                delta = delta.decode('utf-8', errors='ignore')
                            print(delta, end='', flush=True)
                            full_text_parts.append(delta)
                    except Exception as e:
                        print(f"\n[DEBUG] JSON解析错误: {e}, 原始数据: {data_str[:100]}")
                        continue
            print()  # 换行
            return ''.join(full_text_parts)
    else:
        resp = requests.post(url, headers=headers, data=json.dumps(payload, ensure_ascii=False), timeout=timeout_sec)
        resp.raise_for_status()
        resp.encoding = 'utf-8'  # 强制设置编码
        
        try:
            data = resp.json()
            content = data.get('choices', [{}])[0].get('message', {}).get('content', '')
            # 确保返回的内容是正确编码
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='ignore')
            return content
        except Exception as e:
            print(f"[DEBUG] 响应解析错误: {e}")
            print(f"[DEBUG] 原始响应: {resp.text[:200]}")
            return ""

def full_analysis(input_file: str, processed_dir: str, report_dir: str,
                  *, enable_ai: bool = False,
                  system_prompt_path: str = 'agent/REPORT_ANALYST_SYSTEM_PROMPT.md',
                  env_path: str = '.env',
                  ai_output_path: str = 'output/ops_summary.md',
                  model: str = 'deepseek-chat',
                  base_url: str = '',
                  timeout_sec: int = 60,
                  stream: bool = True) -> bool:
    """完整分析流程，含 Markdown 报告输出。"""
    print("=== 开始完整分析流程 ===")
    ok = preprocess_data(input_file, processed_dir)
    if not ok:
        return False
    reports = run_monthly_analysis(processed_dir)
    if not reports:
        return False
    ensure_dir(report_dir)
    md_text = render_markdown_report(reports, os.path.join(processed_dir, 'summary.json'))
    report_path = os.path.join(report_dir, 'analysis_report.md')
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(md_text)
    print(f"Markdown 报告已生成: {report_path}")
    # 可选：AI 运营摘要
    if enable_ai:
        print("=== 调用 DeepSeek API 生成运营摘要 ===")
        if not os.path.exists(system_prompt_path):
            print(f"未找到系统提示词: {system_prompt_path}")
            return True
        with open(system_prompt_path, 'r', encoding='utf-8') as f:
            system_prompt = f.read()
        with open(report_path, 'r', encoding='utf-8') as f:
            user_content = f.read()
        api_key = load_env_key(env_path, 'DEEPSEEK_API_KEY')
        # 读取可配置的 BASE_URL 和 TIMEOUT
        cfg_base_url = base_url or load_env_key(env_path, 'DEEPSEEK_BASE_URL') or 'https://api.deepseek.com'
        cfg_timeout = timeout_sec
        try:
            env_timeout = load_env_key(env_path, 'DEEPSEEK_TIMEOUT_SEC')
            if env_timeout:
                cfg_timeout = int(env_timeout)
        except Exception:
            pass
        # 新增：支持 LMStudio 本地服务
        cfg_max_tokens = 0
        cfg_chunk_size = 0
        if model and model.lower().startswith('lmstudio'):
            cfg_base_url = base_url or load_env_key(env_path, 'LMSTUDIO_BASE_URL') or cfg_base_url
            # 如果模型名是 lmstudio，则从环境变量读取实际模型名
            if model.lower() == 'lmstudio':
                env_model = load_env_key(env_path, 'LMSTUDIO_MODEL_NAME')
                if env_model:
                    model = env_model
            api_key = api_key or load_env_key(env_path, 'LMSTUDIO_API_KEY')
            try:
                lm_timeout = load_env_key(env_path, 'LMSTUDIO_TIMEOUT_SEC')
                if lm_timeout:
                    cfg_timeout = int(lm_timeout)
            except Exception:
                pass
            
            # 读取token限制配置
            try:
                lm_max_tokens = load_env_key(env_path, 'LMSTUDIO_MAX_TOKENS')
                if lm_max_tokens:
                    cfg_max_tokens = int(lm_max_tokens)
                
                lm_chunk_size = load_env_key(env_path, 'LMSTUDIO_CHUNK_SIZE')
                if lm_chunk_size:
                    cfg_chunk_size = int(lm_chunk_size)
            except Exception:
                pass
                
            print(f"使用 LMStudio 配置: {cfg_base_url}, 模型: {model}")
            if cfg_max_tokens > 0:
                print(f"上下文限制: {cfg_max_tokens} tokens, 分块大小: {cfg_chunk_size} tokens")
        if not api_key:
            print("未在环境或 .env 中找到 DEEPSEEK_API_KEY，跳过AI摘要生成。")
            return True
        try:
            ai_text = call_deepseek_chat(api_key, system_prompt, user_content,
                                         model=model, base_url=cfg_base_url,
                                         timeout_sec=cfg_timeout, stream=stream,
                                         max_tokens=cfg_max_tokens, chunk_size=cfg_chunk_size)
            ai_dir = os.path.dirname(ai_output_path)
            if ai_dir:
                ensure_dir(ai_dir)
            with open(ai_output_path, 'w', encoding='utf-8') as f:
                # 确保写入文件的内容是正确的UTF-8编码
                if ai_text:
                    # 如果内容包含乱码，尝试修复
                    try:
                        # 检测并修复可能的编码问题
                        if isinstance(ai_text, bytes):
                            ai_text = ai_text.decode('utf-8', errors='ignore')
                        # 移除可能的控制字符
                        ai_text = ''.join(char for char in ai_text if ord(char) >= 32 or char in '\n\r\t')
                        f.write(ai_text)
                    except Exception as e:
                        print(f"[WARNING] 文件写入编码错误: {e}")
                        f.write(str(ai_text))
                else:
                    f.write('')
            print(f"AI 摘要报告已生成: {ai_output_path}")
        except Exception as e:
            print(f"DeepSeek API 调用失败: {e}")
    return True

def main():
    parser = argparse.ArgumentParser(description='小馨宝运营数据分析工具')
    parser.add_argument('--preprocess', action='store_true', help='仅数据预处理')
    parser.add_argument('--analyze-monthly', action='store_true', help='仅月度分析')
    parser.add_argument('--full', action='store_true', help='完整流程')
    parser.add_argument('--input-file', type=str, default=None, help='输入CSV，默认自动查找 input/chat_logs.csv 或 input/filtered_data.csv')
    parser.add_argument('--output-dir', type=str, default='processed_data', help='预处理输出目录，默认 processed_data')
    parser.add_argument('--report-dir', type=str, default='output', help='Markdown 报告输出目录，默认 output')
    # AI 分析相关
    parser.add_argument('--ai', action='store_true', help='启用 AI 摘要（DeepSeek 或本地 LMStudio 端点）')
    parser.add_argument('--system-prompt', type=str, default='agent/REPORT_ANALYST_SYSTEM_PROMPT.md', help='系统提示词路径')
    parser.add_argument('--env-file', type=str, default='.env', help='包含 DEEPSEEK_API_KEY 的 .env 文件路径')
    parser.add_argument('--ai-output', type=str, default='output/ops_summary.md', help='AI 摘要输出文件路径')
    parser.add_argument('--ai-model', type=str, default='deepseek-chat', help='AI 模型名称，如 deepseek-chat、lmstudio（从环境变量读取）或具体模型名')
    parser.add_argument('--ai-base-url', type=str, default=None, help='AI Base URL，可指向 DeepSeek 或本地 LMStudio，例如 http://localhost:1234/v1')
    parser.add_argument('--ai-timeout', type=int, default=60, help='DeepSeek 请求超时秒，默认 60，可用 .env 的 DEEPSEEK_TIMEOUT_SEC 覆盖')
    parser.add_argument('--ai-stream', action='store_true', help='启用流式输出，实时打印模型生成内容')
    
    args = parser.parse_args()
    input_file = resolve_input_file(args.input_file)
    processed_dir = args.output_dir
    report_dir = args.report_dir

    if not any([args.preprocess, args.analyze_monthly, args.full]):
        # 如果没有参数，运行完整流程
        full_analysis(input_file, processed_dir, report_dir,
                      enable_ai=args.ai,
                      system_prompt_path=args.system_prompt,
                      env_path=args.env_file,
                      ai_output_path=args.ai_output,
                      model=args.ai_model,
                      base_url=(args.ai_base_url or ''),
                      timeout_sec=args.ai_timeout,
                      stream=args.ai_stream)
    elif args.preprocess:
        preprocess_data(input_file, processed_dir)
    elif args.analyze_monthly:
        run_monthly_analysis(processed_dir)
    elif args.full:
        full_analysis(input_file, processed_dir, report_dir,
                      enable_ai=args.ai,
                      system_prompt_path=args.system_prompt,
                      env_path=args.env_file,
                      ai_output_path=args.ai_output,
                      model=args.ai_model,
                      base_url=(args.ai_base_url or ''),
                      timeout_sec=args.ai_timeout,
                      stream=args.ai_stream)

if __name__ == "__main__":
    main()