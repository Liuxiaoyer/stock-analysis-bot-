#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions股票分析脚本 - 完整版
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
 #  WECHAT_WEBHOOK_URL = os.getenv('WECHAT_WEBHOOK_URL', '')



# 监控的股票列表（可根据需要修改）
YOUR_STOCKS = [
    {'code': '000001', 'name': '平安银行'},
    {'code': '002594', 'name': '比亚迪'},
    {'code': '603688', 'name': '石英股份'},
    {'code': '601567', 'name': '三星医疗'},
    {'code': '601318', 'name': '中国平安'}
]

def log_error(message):
    """记录错误日志"""
    with open("error.log", "a", encoding="utf-8") as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"[{timestamp}] {message}\n")
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
        end_date = datetime.now().strftime('%Y%m%d')
        start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
        
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
{historical_data.tail()[['日期', '开盘', '收盘', '最高', '最低', '成交量']].to_string()}

请从以下角度进行分析：
1. 当前技术面状况
2. 短期走势预测
3. 关键支撑位和阻力位
4. 交易建议（买入/持有/卖出）
5. 风险提示

要求分析简洁专业，不超过300字。
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

def send_wechat_message(message, title="股票分析报告"):
    """发送微信消息（使用PushPlus）"""
    if not WECHAT_TOKEN:
        print("微信Token未配置，跳过推送")
        return False
    
    try:
        # PushPlus API格式
        url = "http://www.pushplus.plus/send"
        
        data = {
            "token": WECHAT_TOKEN,  # 使用PushPlus的token
            "title": title,
            "content": message.replace('\n', '<br>'),  # 将换行符转换为HTML换行
            "template": "html",  # 使用HTML模板
            "topic": "stock"  # 可选：消息分组
        }
        
        print(f"正在发送微信消息，标题: {title}")
        print(f"消息内容长度: {len(message)} 字符")
        
        response = requests.post(url, json=data, timeout=10)
        print(f"HTTP状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 200:
                print("✅ 微信消息发送成功！")
                return True
            else:
                error_msg = result.get('msg', '未知错误')
                print(f"❌ 推送失败: {error_msg}")
                return False
        else:
            print(f"❌ HTTP请求失败: {response.status_code}")
            print(f"响应内容: {response.text[:200]}")
            return False
            
    except Exception as e:
        log_error(f"微信消息发送失败: {e}")
        print(f"详细错误: {traceback.format_exc()}")
        return False
        
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
            reports.append(f"❌ {stock_name}({stock_code}): 数据获取失败")
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
        change_icon = "📈" if stock_data['change'] > 0 else "📉" if stock_data['change'] < 0 else "➡️"
        
        report = f"""
## {stock_name} ({stock_code}) {change_icon}

**实时数据：**
- 当前价格: {stock_data['price']}元
- 涨跌幅: {stock_data['change']}%
- 涨跌额: {stock_data['change_amount']}元
- 成交量: {stock_data['volume']}
- 振幅: {((stock_data['high'] - stock_data['low']) / stock_data['close'] * 100):.2f}%

**AI分析：**
{ai_analysis}

{'='*50}
"""
        reports.append(report)
    
    return "\n".join(reports)

def main():
    print("=" * 60)
    print("🚀 股票分析脚本启动 - DeepSeek增强版")
    print("=" * 60)
    
    try:
        # 环境检查
        print("1. 环境检查...")
        print(f"Python版本: {sys.version}")
        print(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"监控股票数量: {len(YOUR_STOCKS)}")
        
        # 检查API配置
        if not DEEPSEEK_API_KEY:
            print("⚠️ DeepSeek API密钥未设置，AI分析功能将不可用")
        if not WECHAT_TOKEN:
            print("⚠️ 微信未设置，消息推送功能将不可用")
        
        # 生成分析报告
        print("\n2. 开始股票分析...")
        report_content = generate_stock_report(YOUR_STOCKS)
        
        # 添加报告头部
        current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        full_report = f"""# 📊 股票分析报告
**生成时间:** {current_time}
**分析股票数:** {len(YOUR_STOCKS)}

{report_content}

---
*本报告由AI生成，仅供参考，不构成投资建议*
"""
        
        # 保存报告到文件
        filename = f"stock_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(full_report)
        print(f"✓ 报告已保存: {filename}")
        
        # 发送微信消息（截断前2000字符避免超限）
        if WECHAT_WEBHOOK_URL:
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
        
        # 发送错误通知
        
        return 1

if __name__ == "__main__":
    sys.exit(main())
