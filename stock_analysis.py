#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions股票分析脚本 - 完整版（北京时间修复）
集成DeepSeek分析和微信推送功能
"""

import os
import sys
import json
import requests
import pandas as pd
import akshare as ak
from datetime import datetime, timedelta
import traceback
import time

# 配置参数
WECHAT_TOKEN = os.getenv('WECHAT_TOKEN', '')
print(f"微信Token状态: {'已设置' if WECHAT_TOKEN else '未设置'}")
if WECHAT_TOKEN:
    print(f"Token前几位: {WECHAT_TOKEN[:10]}...")
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# 监控的股票列表（可根据需要修改）
YOUR_STOCKS = [
    {'code': '000001', 'name': '平安银行'},
    {'code': '002594', 'name': '比亚迪'},
    {'code': '603688', 'name': '石英股份'},
    {'code': '601567', 'name': '三星医疗'},
    {'code': '601318', 'name': '中国平安'}
]

def get_beijing_time():
    """获取北京时间（UTC+8）"""
    # 获取当前UTC时间
    utc_now = datetime.utcnow()
    # 转换为北京时间（UTC+8）
    beijing_time = utc_now + timedelta(hours=8)
    return beijing_time

def format_beijing_time(format_str='%Y-%m-%d %H:%M:%S'):
    """格式化北京时间"""
    return get_beijing_time().strftime(format_str)

def get_beijing_timestamp():
    """获取用于文件名的北京时间戳"""
    return get_beijing_time().strftime('%Y%m%d_%H%M%S')

def log_error(message):
    """记录错误日志"""
    beijing_time = format_beijing_time()
    with open("error.log", "a", encoding='utf-8') as f:
        f.write(f"[{beijing_time}] {message}\n")
    print(f"错误: {message}")

def get_stock_data(stock_code):
    """获取股票实时数据"""
    try:
        # 获取实时数据
        df = ak.stock_zh_a_spot_em()
        stock_data = df[df['代码'] == stock_code]
        
        if not stock_data.empty:
            stock = stock_data.iloc[0]
            return {
                'code': stock_code,
                'name': stock['名称'],
                'price': stock['最新价'],
                'change': stock['涨跌幅'],
                'change_amount': stock['涨跌额'],
                'volume': stock['成交量'],
                'turnover': stock['成交额'],
                'high': stock['最高'],
                'low': stock['最低'],
                'open': stock['今开'],
                'close': stock['昨收']
            }
        return None
    except Exception as e:
        log_error(f"获取股票{stock_code}数据失败: {e}")
        return None

def get_historical_data(stock_code, days=30):
    """获取股票历史数据"""
    try:
        # 获取历史K线数据
        end_date = get_beijing_time().strftime('%Y%m%d')  # 使用北京时间
        start_date = (get_beijing_time() - timedelta(days=days)).strftime('%Y%m%d')
        
        df = ak.stock_zh_a_hist(symbol=stock_code, period="daily", 
                               start_date=start_date, end_date=end_date, 
                               adjust="qfq")
        return df
    except Exception as e:
        log_error(f"获取股票{stock_code}历史数据失败: {e}")
        return None

def analyze_with_deepseek(stock_data, historical_data):
    """使用DeepSeek分析股票数据"""
    if not DEEPSEEK_API_KEY:
        return "DeepSeek API密钥未配置，跳过AI分析"
    
    try:
        # 准备分析数据
        analysis_prompt = f"""
请作为专业股票分析师，对以下股票进行技术分析：

股票信息：
- 股票代码：{stock_data['code']}
- 股票名称：{stock_data['name']}
- 当前价格：{stock_data['price']}元
- 涨跌幅：{stock_data['change']}%
- 涨跌额：{stock_data['change_amount']}元
- 成交量：{stock_data['volume']}
- 成交额：{stock_data['turnover']}元
- 最高价：{stock_data['high']}元
- 最低价：{stock_data['low']}元
- 开盘价：{stock_data['open']}元
- 昨收价：{stock_data['close']}元

近期走势关键数据（最近5个交易日）：
{historical_data.tail()[['日期', '开盘', '收盘', '最高', '最低', '成交量']].to_string() if historical_data is not None else '无历史数据'}

请从以下角度进行分析：
1. 当前技术面状况
2. 短期走势预测
3. 关键支撑位和阻力位
4. 交易建议（买入/持有/卖出）
5. 风险提示

要求分析简洁专业，不超过200字。
"""
        
        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }
        
        data = {
            "model": "deepseek-chat",
            "messages": [
                {
                    "role": "system",
                    "content": "你是一个专业的股票分析师，擅长技术分析和市场趋势判断。请用中文回答，分析要客观专业。"
                },
                {
                    "role": "user",
                    "content": analysis_prompt
                }
            ],
            "temperature": 0.7,
            "max_tokens": 1000
        }
        
        response = requests.post(DEEPSEEK_API_URL, headers=headers, 
                                json=data, timeout=60)
        response.raise_for_status()
        
        result = response.json()
        analysis = result['choices'][0]['message']['content']
        
        return analysis.strip()
        
    except Exception as e:
        log_error(f"DeepSeek分析失败: {e}")
        return f"AI分析暂时不可用: {str(e)}"

def split_long_message(message, max_length=800):
    """
    将长消息智能分割为多个片段
    参数:
        message: 原始消息
        max_length: 每个片段的最大长度（PushPlus建议小于1000）
    返回: 消息片段列表
    """
    if len(message) <= max_length:
        return [message]
    
    fragments = []
    # 优先按股票分割（查找 '##' 开头的股票标题）
    lines = message.split('\n')
    current_fragment = ""
    
    for line in lines:
        # 如果遇到新的股票标题，且当前片段已有内容，则保存当前片段
        if line.startswith('## ') and current_fragment and len(current_fragment) + len(line) > max_length:
            fragments.append(current_fragment.strip())
            current_fragment = line + "\n"
        else:
            # 如果当前片段即将超长，也保存它
            if len(current_fragment) + len(line) + 1 > max_length:
                fragments.append(current_fragment.strip())
                current_fragment = line + "\n"
            else:
                current_fragment += line + "\n"
    
    # 添加最后一个片段
    if current_fragment.strip():
        fragments.append(current_fragment.strip())
    
    # 如果分割后片段仍然太长，进行二次分割（按段落）
    final_fragments = []
    for fragment in fragments:
        if len(fragment) <= max_length:
            final_fragments.append(fragment)
        else:
            # 按句号、换行等简单分割
            sentences = fragment.replace('。', '。\n').split('\n')
            temp_text = ""
            for sentence in sentences:
                if len(temp_text) + len(sentence) + 1 > max_length:
                    final_fragments.append(temp_text.strip())
                    temp_text = sentence + "\n"
                else:
                    temp_text += sentence + "\n"
            if temp_text.strip():
                final_fragments.append(temp_text.strip())
    
    return final_fragments

def send_wechat_message(message, title="股票分析报告", max_retries=2):
    """
    发送微信消息（支持分条推送）
    参数:
        message: 要发送的消息内容
        title: 消息标题
        max_retries: 失败重试次数
    """
    if not WECHAT_TOKEN:
        print("❌ 微信Token未配置，跳过推送")
        return False
    
    # 检查Token格式
    token_clean = WECHAT_TOKEN.strip()
    if not token_clean or len(token_clean) < 10:
        print(f"❌ Token格式异常: {token_clean}")
        return False
    
    print(f"🔍 Token检查: 长度{len(token_clean)}，前5位: {token_clean[:5]}...")
    
    # 1. 分割长消息
    message_fragments = split_long_message(message, max_length=800)
    print(f"📤 消息被分割为 {len(message_fragments)} 条发送")
    
    if len(message_fragments) > 5:
        print(f"⚠️  警告: 消息被分割为 {len(message_fragments)} 条，可能过多，考虑精简内容")
    
    # 2. 逐条发送
    success_count = 0
    beijing_time = format_beijing_time('%H:%M')
    
    for i, fragment in enumerate(message_fragments):
        fragment_title = f"{title} ({i+1}/{len(message_fragments)}) {beijing_time}"
        
        for retry in range(max_retries + 1):
            try:
                # 最后一条重试时不添加序号，避免重复
                if retry > 0:
                    fragment_title = f"{title} {beijing_time} (重试{retry})"
                
                # PushPlus API地址
                url = "http://www.pushplus.plus/send"
                
                # 清理消息内容
                import re
                clean_fragment = re.sub(r'[^\w\s\u4e00-\u9fff\.,!?;:(){}<>/\\|@#$%^&*+=-]', '', fragment)
                
                # 添加分段指示
                if len(message_fragments) > 1:
                    segment_info = f"\n\n--- 第 {i+1}/{len(message_fragments)} 部分 ---\n"
                    if i == 0:
                        clean_fragment = segment_info + clean_fragment
                    elif i == len(message_fragments) - 1:
                        clean_fragment = clean_fragment + f"\n\n--- 报告完，共{len(message_fragments)}条 ---"
                    else:
                        clean_fragment = segment_info + clean_fragment
                
                data = {
                    "token": token_clean,
                    "title": fragment_title,
                    "content": clean_fragment.replace('\n', '<br>'),
                    "template": "html",
                    "channel": "wechat"
                }
                
                print(f"  发送第 {i+1}/{len(message_fragments)} 条...")
                print(f"    长度: {len(clean_fragment)} 字符")
                
                response = requests.post(url, json=data, timeout=15)
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('code') == 200:
                        print(f"  ✅ 第 {i+1} 条发送成功")
                        success_count += 1
                        break  # 本条发送成功，跳出重试循环
                    else:
                        print(f"  ❌ 第 {i+1} 条失败: {result.get('msg')}")
                        if retry < max_retries:
                            print(f"    等待{2**retry}秒后重试...")
                            time.sleep(2 ** retry)
                        else:
                            print(f"  ⏭️  放弃第 {i+1} 条")
                else:
                    print(f"  ❌ 第 {i+1} 条HTTP错误: {response.status_code}")
                    if retry < max_retries:
                        time.sleep(2 ** retry)
                
            except requests.exceptions.Timeout:
                print(f"  ⏱️  第 {i+1} 条超时")
                if retry < max_retries:
                    time.sleep(2 ** retry)
            except Exception as e:
                print(f"  ❌ 第 {i+1} 条异常: {e}")
                if retry < max_retries:
                    time.sleep(2 ** retry)
        
        # 每条消息之间间隔1秒，避免发送过快
        if i < len(message_fragments) - 1:
            time.sleep(1)
    
    # 3. 发送汇总提示
    if success_count > 0 and len(message_fragments) > 1:
        summary_msg = f"📊 股票分析报告推送完成\n\n共发送 {success_count}/{len(message_fragments)} 条消息\n北京时间: {beijing_time}"
        try:
            summary_data = {
                "token": token_clean,
                "title": f"报告推送汇总 {beijing_time}",
                "content": summary_msg.replace('\n', '<br>'),
                "template": "html"
            }
            requests.post("http://www.pushplus.plus/send", json=summary_data, timeout=10)
            print("📨 汇总提示已发送")
        except:
            pass  # 汇总提示失败不影响主流程
    
    success_rate = success_count / len(message_fragments) if message_fragments else 0
    if success_rate >= 0.8:  # 80%以上成功即视为整体成功
        print(f"✅ 微信推送完成 ({success_count}/{len(message_fragments)} 条成功)")
        return True
    else:
        print(f"⚠️  微信推送部分失败 ({success_count}/{len(message_fragments)} 条成功)")
        return success_count > 0

        
def generate_stock_report(stock_list):
    """生成股票分析报告"""
    reports = []
    
    for stock_info in stock_list:
        stock_code = stock_info['code']
        stock_name = stock_info['name']
        
        print(f"\n正在分析 {stock_name}({stock_code})...")

        # 获取实时数据
        stock_data = get_stock_data(stock_code)
        if not stock_data:
            reports.append(f"❌❌ {stock_name}({stock_code}): 数据获取失败")
            continue
        # 获取历史数据
        historical_data = get_historical_data(stock_code)
        
        # DeepSeek分析
        ai_analysis = "AI分析跳过"  # 默认值
        if DEEPSEEK_API_KEY:
            print("正在进行AI分析...")
            ai_analysis = analyze_with_deepseek(stock_data, historical_data)
            time.sleep(1)  # 避免API限制
        
        # 生成单个股票报告
        change_icon = "📈📈" if stock_data['change'] > 0 else "📉📉" if stock_data['change'] < 0 else "➡➡️"
        
        report = f"""
## {stock_name} ({stock_code}) {change_icon}

**实时数据：**
- 当前价格: {stock_data['price']}元
- 涨跌幅: {stock_data['change']}%
- 涨跌额: {stock_data['change_amount']}元
- 成交量: {stock_data['volume']}
- 振幅: {((stock_data['high'] - stock_data['low']) / stock_data['close'] * 100):.2f}%  # 修复：确保close不为0

**AI分析：**
{ai_analysis}

{'='*50}
"""
        reports.append(report)
    
    return "\n".join(reports)

def main():
    print("=" * 60)
    print("🚀🚀 股票分析脚本启动 - DeepSeek增强版（北京时间）")
    print("=" * 60)
    
    try:
        # 环境检查（使用北京时间）
        beijing_time = format_beijing_time()
        print(f"1. 环境检查...")
        print(f"   当前北京时间: {beijing_time}")
        print(f"   Python版本: {sys.version}")
        print(f"   监控股票数量: {len(YOUR_STOCKS)}")
        
        # 检查API配置
        if not DEEPSEEK_API_KEY:
            print("⚠️ DeepSeek API密钥未设置，AI分析功能将不可用")
        if not WECHAT_TOKEN:
            print("⚠️ 微信未设置，消息推送功能将不可用")
        
        # 生成分析报告
        print("\n2. 开始股票分析...")
        report_content = generate_stock_report(YOUR_STOCKS)
        
        # 添加报告头部（使用北京时间）
        current_time = format_beijing_time()
        full_report = f"""# 📊📊 股票分析报告
**生成时间 (北京时间):** {current_time}
**分析股票数:** {len(YOUR_STOCKS)}

{report_content}

---
*本报告由AI生成，仅供参考，不构成投资建议*
"""
        
        # 保存报告到文件（使用北京时间文件名）
        filename = f"stock_report_{get_beijing_timestamp()}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(full_report)
        print(f"✓ 报告已保存: {filename} (北京时间)")
        
        # 发送微信消息（截断前2000字符避免超限）
        if WECHAT_TOKEN:
            print("\n3. 发送微信通知...")
            short_report = full_report[:2000] + "..." if len(full_report) > 2000 else full_report
            send_wechat_message(short_report, f"股票分析报告 {current_time}")
        
        print("\n" + "=" * 60)
        print("✅ 脚本执行完成！")
        print("=" * 60)
        
        return 0
        
    except Exception as e:
        error_msg = f"脚本执行异常: {e}"
        log_error(error_msg)
        print(f"详细错误: {traceback.format_exc()}")
        
        return 1

if __name__ == "__main__":
    sys.exit(main())
