#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions股票分析脚本 - GitHub Pages版本
生成HTML报告并自动部署
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
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY', '')
GITHUB_REPOSITORY = os.getenv('GITHUB_REPOSITORY', 'your-username/your-repo')
DEEPSEEK_API_URL = "https://api.deepseek.com/v1/chat/completions"

# 监控的股票列表
YOUR_STOCKS = [
    {'code': '000001', 'name': '平安银行'},
    {'code': '002594', 'name': '比亚迪'},
    {'code': '603688', 'name': '石英股份'},
    {'code': '601567', 'name': '三星医疗'},
    {'code': '601318', 'name': '中国平安'}
]

def get_beijing_time():
    """获取北京时间（UTC+8）"""
    utc_now = datetime.utcnow()
    beijing_time = utc_now + timedelta(hours=8)
    return beijing_time

def format_beijing_time(format_str='%Y-%m-%d %H:%M:%S'):
    """格式化北京时间"""
    return get_beijing_time().strftime(format_str)

def get_stock_data(stock_code):
    """获取股票实时数据 - 优化版本"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            # 方法1: 尝试新版接口
            try:
                df = ak.stock_zh_a_spot_em()
                print(f"尝试使用 stock_zh_a_spot_em() 接口...")
            except Exception as e1:
                print(f"接口1失败: {e1}")
                # 方法2: 备用接口
                df = ak.stock_zh_a_spot()
                print(f"回退到 stock_zh_a_spot() 接口...")
            
            # 检查列名，处理可能的列名差异
            if '代码' in df.columns:
                code_col = '代码'
            elif 'symbol' in df.columns:
                code_col = 'symbol'
            elif '代码' in [col.strip() for col in df.columns]:
                # 处理可能的空格
                for col in df.columns:
                    if '代码' in col:
                        code_col = col
                        break
                else:
                    code_col = df.columns[0]  # 使用第一列
            else:
                code_col = df.columns[0]
            
            # 股票代码可能需要添加前缀
            search_code = stock_code
            if len(stock_code) == 6:
                if stock_code.startswith(('600', '601', '603', '605', '688')):
                    search_code = f"sh{stock_code}"
                elif stock_code.startswith(('000', '001', '002', '003', '300')):
                    search_code = f"sz{stock_code}"
                elif stock_code.startswith(('400', '430', '831', '832', '833')):
                    search_code = f"bj{stock_code}"
            
            # 查找股票
            stock_data = df[df[code_col] == search_code]
            
            if stock_data.empty:
                # 尝试不带前缀
                stock_data = df[df[code_col].str.contains(stock_code)]
            
            if not stock_data.empty:
                stock = stock_data.iloc[0]
                
                # 列名映射
                column_mapping = {
                    'code': ['代码', 'symbol', 'code'],
                    'name': ['名称', 'name'],
                    'price': ['最新价', 'current', 'price'],
                    'change': ['涨跌幅', '涨跌%', 'pct_chg'],
                    'change_amount': ['涨跌额', 'change'],
                    'volume': ['成交量', 'volume', 'vol'],
                    'turnover': ['成交额', 'amount'],
                    'high': ['最高', 'high'],
                    'low': ['最低', 'low'],
                    'open': ['今开', 'open'],
                    'close': ['昨收', 'pre_close']
                }
                
                result = {'code': stock_code}
                for field, possible_columns in column_mapping.items():
                    value_found = None
                    for col in possible_columns:
                        if col in stock.index:
                            value_found = stock[col]
                            break
                    
                    if value_found is not None:
                        result[field] = value_found
                    else:
                        # 如果找不到，使用默认值
                        result[field] = 0
                
                # 确保名称字段
                if 'name' not in result or not result['name']:
                    result['name'] = stock_code
                
                print(f"成功获取股票 {stock_code} 数据")
                return result
                
            return None
            
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"第{attempt+1}次获取股票{stock_code}数据失败，{retry_delay}秒后重试: {e}")
                time.sleep(retry_delay)
            else:
                print(f"获取股票{stock_code}数据最终失败: {e}")
                return None

def analyze_with_deepseek(stock_data, historical_data):
    """使用DeepSeek分析股票数据"""
    if not DEEPSEEK_API_KEY:
        return "DeepSeek API密钥未配置，跳过AI分析"
    
    try:
        analysis_prompt = f"""
请作为专业股票分析师，对以下股票进行技术分析：

股票信息：
- 股票代码：{stock_data['code']}
- 股票名称：{stock_data['name']}
- 当前价格：{stock_data['price']}元
- 涨跌幅：{stock_data['change']}%
- 涨跌额：{stock_data['change_amount']}元

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
         # "model": "deepseek-chat",
        data = {
           "model": "deepseek-v4-pro",
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
        return f"AI分析暂时不可用: {str(e)}"

def generate_html_report(stock_reports):
    """生成HTML格式的报告"""
    beijing_time = format_beijing_time()
    
    html_template = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>股票分析报告 - {beijing_time}</title>
    <link rel="stylesheet" href="style.css">
    <style>
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
        }}
        .stock-card {{
            background: white;
            border-radius: 10px;
            padding: 25px;
            margin: 20px 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            border-left: 5px solid #3498db;
        }}
        .stock-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
        }}
        .stock-name {{
            font-size: 1.4em;
            font-weight: bold;
            color: #2c3e50;
        }}
        .price-info {{
            text-align: right;
        }}
        .current-price {{
            font-size: 1.8em;
            font-weight: bold;
        }}
        .change-up {{ color: #e74c3c; }}
        .change-down {{ color: #27ae60; }}
        .change-neutral {{ color: #95a5a6; }}
        .change-percent {{
            font-size: 1.2em;
            font-weight: bold;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin: 15px 0;
        }}
        .stat-item {{
            background: #f8f9fa;
            padding: 10px;
            border-radius: 5px;
            text-align: center;
        }}
        .stat-label {{
            font-size: 0.9em;
            color: #7f8c8d;
        }}
        .stat-value {{
            font-weight: bold;
            color: #2c3e50;
        }}
        .ai-analysis {{
            background: #e8f4fd;
            border-left: 4px solid #3498db;
            padding: 15px;
            margin: 15px 0;
            border-radius: 5px;
        }}
        .timestamp {{
            text-align: center;
            color: #7f8c8d;
            margin: 30px 0;
            font-size: 0.9em;
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            padding: 20px;
            border-top: 1px solid #ddd;
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        @media (max-width: 768px) {{
            body {{ padding: 10px; }}
            .stock-header {{ flex-direction: column; text-align: center; }}
            .price-info {{ text-align: center; margin-top: 10px; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 股票分析报告</h1>
        <p>生成时间: {beijing_time} (北京时间)</p>
        <p>分析股票数: {len(YOUR_STOCKS)} 支</p>
    </div>

    {stock_reports}

    <div class="timestamp">
        最后更新时间: {beijing_time}
    </div>
    
    <div class="footer">
        <p>本报告由AI自动生成，仅供参考，不构成投资建议</p>
        <p>数据来源: Akshare | 分析引擎: DeepSeek AI</p>
    </div>
</body>
</html>
"""
    return html_template

def generate_stock_reports():
    """生成所有股票的报告"""
    reports = []
    
    for stock_info in YOUR_STOCKS:
        stock_code = stock_info['code']
        stock_name = stock_info['name']
        
        print(f"分析 {stock_name}({stock_code})...")
        
        # 获取实时数据
        stock_data = get_stock_data(stock_code)
        if not stock_data:
            continue
        
        # AI分析
        ai_analysis = analyze_with_deepseek(stock_data, None)
        time.sleep(1)  # 避免API限制
        
        # 确定涨跌样式
        if stock_data['change'] > 0:
            change_class = "change-up"
            change_icon = "📈"
        elif stock_data['change'] < 0:
            change_class = "change-down"
            change_icon = "📉"
        else:
            change_class = "change-neutral"
            change_icon = "➡️"
        
        # 生成单个股票的HTML
        stock_html = f"""
    <div class="stock-card">
        <div class="stock-header">
            <div class="stock-name">{stock_name} ({stock_code}) {change_icon}</div>
            <div class="price-info">
                <div class="current-price {change_class}">{stock_data['price']} 元</div>
                <div class="change-percent {change_class}">
                    {stock_data['change']:+.2f}% ({stock_data['change_amount']:+.2f}元)
                </div>
            </div>
        </div>
        
        <div class="stats-grid">
            <div class="stat-item">
                <div class="stat-label">开盘价</div>
                <div class="stat-value">{stock_data['open']} 元</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">最高价</div>
                <div class="stat-value">{stock_data['high']} 元</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">最低价</div>
                <div class="stat-value">{stock_data['low']} 元</div>
            </div>
            <div class="stat-item">
                <div class="stat-label">成交量</div>
                <div class="stat-value">{stock_data['volume']}</div>
            </div>
        </div>
        
        <div class="ai-analysis">
            <strong>🤖 AI分析:</strong><br>
            {ai_analysis.replace(chr(10), '<br>')}
        </div>
    </div>
"""
        reports.append(stock_html)
    
    return "".join(reports)

def send_wechat_message(message, title="股票分析报告"):
    """发送微信消息（包含网页链接）"""
    if not WECHAT_TOKEN:
        print("微信Token未配置，跳过推送")
        return False
    
    try:
        # 构建GitHub Pages链接
        repo_name = GITHUB_REPOSITORY.split('/')[1]
        pages_url = f"https://{GITHUB_REPOSITORY.split('/')[0]}.github.io/{repo_name}/"
        
        beijing_time = format_beijing_time('%H:%M')
        
        # 创建包含链接的消息
        link_message = f"""
{message}

📊 完整报告已发布到网页版：
🔗 {pages_url}

⏰ 更新时间: {beijing_time} (北京时间)
"""
        
        url = "http://www.pushplus.plus/send"
        data = {
            "token": WECHAT_TOKEN.strip(),
            "title": f"股票分析报告 {beijing_time}",
            "content": link_message.replace('\n', '<br>'),
            "template": "html"
        }
        
        response = requests.post(url, json=data, timeout=15)
        
        if response.status_code == 200:
            result = response.json()
            if result.get('code') == 200:
                print("✅ 微信消息发送成功！")
                return True
        return False
        
    except Exception as e:
        print(f"发送消息异常: {e}")
        return False

def main():
    print("🚀 股票分析脚本启动 - GitHub Pages版本")
    
    try:
        beijing_time = format_beijing_time()
        print(f"当前北京时间: {beijing_time}")
        
        # 生成股票报告
        print("开始生成股票分析...")
        stock_reports_html = generate_stock_reports()
        
        # 生成完整HTML报告
        full_html = generate_html_report(stock_reports_html)
        
        # 保存HTML文件
        html_filename = f"stock_report_{get_beijing_time().strftime('%Y%m%d_%H%M%S')}.html"
        with open(html_filename, 'w', encoding='utf-8') as f:
            f.write(full_html)
        print(f"✅ HTML报告已保存: {html_filename}")
        
        # 发送微信通知
        if WECHAT_TOKEN:
            summary = f"✅ 股票分析完成！共分析 {len(YOUR_STOCKS)} 支股票"
            send_wechat_message(summary)
        
        print("✅ 脚本执行完成！")
        return 0
        
    except Exception as e:
        print(f"❌ 脚本执行异常: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
