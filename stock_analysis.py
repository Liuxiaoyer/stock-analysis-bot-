import akshare as ak
import pandas as pd
import time
import random
import requests
import json
import os
import sys
import traceback
from datetime import datetime

# ====================== 配置参数 ======================
YOUR_STOCKS = ["000001", "002594", "603688", "002475", "601318", "000400"]  # 你的股票代码列表
WECHAT_TOKEN = os.getenv("WECHAT_TOKEN")  # 微信推送Token（可选）
LLM_API_KEY = os.getenv("LLM_API_KEY")    # 大模型API Key（如智谱AI）
LLM_API_URL = "https://open.bigmodel.cn/api/paas/v4/chat/completions"  # 智谱AI接口（可替换）

# ====================== 工具函数 ======================
def format_beijing_time():
    """格式化北京时间为字符串"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def get_market_data():
    """获取全市场实时数据（带重试和随机延时，避免反爬）"""
    max_retries = 3
    retry_delay = 2
    for attempt in range(max_retries):
        try:
            # 随机延时1-3秒，降低请求频率
            time.sleep(random.uniform(1, 3))
            df = ak.stock_zh_a_spot()
            print(f"✅ 成功获取全市场数据，共 {len(df)} 条，列名：{df.columns.tolist()}")
            return df
        except Exception as e:
            print(f"❌ 第{attempt+1}次获取全市场数据失败：{e}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
    print("❌ 全市场数据获取失败，终止程序")
    return None

def find_stock_in_market(market_df, stock_code):
    """在全市场数据中查找股票（支持多种代码格式匹配）"""
    if market_df is None or market_df.empty:
        return None
    
    # 生成可能的代码格式（如000001 -> 000001.SZ）
    possible_codes = [
        stock_code,                  # 原始格式（如000001）
        f"{stock_code}.SZ",          # 深交所（如000001.SZ）
        f"{stock_code}.SH",          # 上交所（如600000.SH）
        stock_code.lstrip("0")       # 去除前导零（如000001 -> 1）
    ]
    
    # 遍历所有可能的代码格式匹配
    for code in possible_codes:
        mask = market_df["代码"] == code
        if mask.any():
            stock_data = market_df[mask].iloc[0].to_dict()
            print(f"✅ 找到股票 {stock_code}（匹配格式：{code}）：{stock_data.get('名称')}")
            return stock_data
    
    # 尝试模糊匹配（代码包含在数据中）
    for _, row in market_df.iterrows():
        market_code = str(row["代码"])
        if stock_code in market_code or market_code in stock_code:
            print(f"✅ 模糊匹配到股票 {stock_code}：{row.get('名称')}")
            return row.to_dict()
    
    print(f"❌ 未找到股票 {stock_code} 的数据（全市场数据长度：{len(market_df)}）")
    return None

def get_ai_analysis(stock_data):
    """调用大模型生成股票分析（带调试信息）"""
    if not LLM_API_KEY:
        print("⚠️ 未配置LLM_API_KEY，跳过AI分析")
        return "（未配置AI接口，无法生成分析）"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LLM_API_KEY}"
    }
    
    # 构造Prompt（可根据需求调整）
    prompt = f"请分析股票 {stock_data.get('代码')}（{stock_data.get('名称')}）的当前行情：\n"
    prompt += f"价格：{stock_data.get('最新价')}元，涨跌幅：{stock_data.get('涨跌幅')}%，成交量：{stock_data.get('成交量')}\n"
    prompt += "请给出简短的投资建议或行情解读（不超过100字）。"
    
    payload = {
        "model": "glm-4",  # 可替换为其他模型（如glm-3-turbo）
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 150,
        "temperature": 0.7
    }
    
    try:
        response = requests.post(LLM_API_URL, headers=headers, json=payload, timeout=15)
        response.raise_for_status()  # 检查HTTP错误（如401、500）
        result = response.json()
        
        # 增加响应结构调试打印
        print(f"🔍 AI接口原始响应：{json.dumps(result, ensure_ascii=False)[:500]}...")
        
        # 解析响应（适配智谱AI格式）
        if "choices" in result and len(result["choices"]) > 0:
            content = result["choices"][0]["message"]["content"]
            print(f"✅ AI分析生成成功：{content[:50]}...")
            return content.strip()
        else:
            print(f"⚠️ AI响应无有效内容，原始响应：{result}")
            return "（AI分析生成失败，响应格式错误）"
    except requests.exceptions.RequestException as e:
        print(f"❌ AI分析请求异常：{e}")
        return f"（AI分析请求失败：{str(e)})"
    except (KeyError, IndexError) as e:
        print(f"❌ AI响应解析失败：{e}，原始响应：{response.text[:500]}")
        return "（AI分析解析失败，请联系管理员）"

def generate_stock_reports(market_df):
    """生成所有股票的分析报告（带调试信息）"""
    reports = []
    success_count = 0
    fail_count = 0
    
    for stock_code in YOUR_STOCKS:
        print(f"\n===== 处理股票：{stock_code} =====")
        # 1. 从全市场数据查找股票
        stock_data = find_stock_in_market(market_df, stock_code)
        if not stock_data:
            fail_count += 1
            # 生成错误卡片（避免页面空白）
            error_card = f"""
            <div class="stock-card error">
                <h3>❌ 股票 {stock_code} 数据获取失败</h3>
                可能原因：代码错误、数据源无此股票、网络波动
            </div>
            """
            reports.append(error_card)
            continue
        
        # 2. 获取AI分析
        ai_analysis = get_ai_analysis(stock_data)
        
        # 3. 生成股票卡片（即使AI分析为空，也保留基础数据）
        price = stock_data.get("最新价", 0)
        change = stock_data.get("涨跌幅", 0)
        change_class = "up" if change > 0 else "down"
        
        stock_html = f"""
        <div class="stock-card">
            <h3>{stock_data.get('名称', stock_code)} ({stock_code})</h3>
            <div class="price-change {change_class}">
                {price:.2f}元 <span class="change">{change:+.2f}%</span>
            </div>
            <div class="stats">
                成交量：{stock_data.get('成交量', 0)} | 成交额：{stock_data.get('成交额', 0)}
                最高：{stock_data.get('最高', 0)} | 最低：{stock_data.get('最低', 0)}
            </div>
            <div class="ai-analysis">
                <strong>🤖 AI分析：</strong>
                {ai_analysis or "（AI分析为空，请联系管理员）"}
            </div>
        </div>
        """
        reports.append(stock_html)
        success_count += 1
        print(f"✅ 股票 {stock_code} 处理完成")
    
    print(f"\n===== 统计：成功 {success_count} 支，失败 {fail_count} 支 =====")
    return "".join(reports)

def generate_html_report(stock_reports):
    """生成最终HTML报告（含基础CSS样式）"""
    html = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8" />
        <title>股票分析报告 - {format_beijing_time()}</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                margin: 20px;
                line-height: 1.6;
            }}
            .stock-card {{
                border: 1px solid #ddd;
                border-radius: 8px;
                padding: 16px;
                margin-bottom: 16px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }}
            .stock-card.error {{
                background-color: #fff3f3;
                border-color: #ffcccc;
            }}
            .price-change {{
                font-size: 24px;
                font-weight: bold;
                margin: 8px 0;
            }}
            .up {{ color: red; }}
            .down {{ color: green; }}
            .stats {{
                color: #666;
                margin: 8px 0;
            }}
            .ai-analysis {{
                margin-top: 12px;
                padding-top: 12px;
                border-top: 1px dashed #eee;
                white-space: pre-line; /* 保留换行 */
            }}
            h3 {{
                margin: 0 0 8px;
                color: #333;
            }}
        </style>
    </head>
    <body>
        <h1>股票分析报告（{format_beijing_time()}）</h1>
        {stock_reports}
        <p style="margin-top: 20px; color: #999; font-size: 14px;">
            报告生成时间：{format_beijing_time()} | 数据来源：AkShare
        
    </body>
    </html>
    """
    return html

def send_wechat_message(message):
    """发送微信通知（Server酱/企业微信，需配置WECHAT_TOKEN）"""
    if not WECHAT_TOKEN:
        return False
    try:
        url = f"https://sctapi.ftqq.com/{WECHAT_TOKEN}.send"
        data = {"title": "股票分析完成", "desp": message}
        response = requests.post(url, data=data, timeout=10)
        return response.json().get("code") == 0
    except Exception as e:
        print(f"微信通知发送失败：{e}")
        return False

def main():
    print("🚀 股票分析脚本启动（优化版）")
    try:
        # 1. 获取全市场数据
        market_df = get_market_data()
        if market_df is None:
            return 1
        
        # 2. 生成股票报告
        stock_reports = generate_stock_reports(market_df)
        
        # 3. 生成HTML并保存
        html_content = generate_html_report(stock_reports)
        filename = "stock_report.html"
        with open(filename, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"✅ HTML报告已保存：{filename}")
        
        # 4. 微信通知（可选）
        if WECHAT_TOKEN:
            msg = f"股票分析完成！成功 {len([s for s in YOUR_STOCKS if find_stock_in_market(market_df, s)])} 支，失败 {len(YOUR_STOCKS) - len([s for s in YOUR_STOCKS if find_stock_in_market(market_df, s)])} 支"
            send_wechat_message(msg)
        
        print("✅ 脚本执行完成！")
        return 0
    except Exception as e:
        print(f"❌ 脚本执行异常：{e}")
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())

