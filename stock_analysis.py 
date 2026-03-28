#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Actions股票分析脚本 - 修复版
"""

import os
import sys
import json
import requests
from datetime import datetime
import traceback

# 添加详细日志
def log_error(message):
    with open("error.log", "a", encoding="utf-8") as f:
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        f.write(f"[{timestamp}] {message}\n")
    print(f"错误: {message}")

def main():
    print("=" * 60)
    print("股票分析脚本启动")
    print("=" * 60)
    
    try:
        # 1. 先测试基本环境
        print("1. 测试Python环境...")
        print(f"Python版本: {sys.version}")
        print(f"当前目录: {os.getcwd()}")
        print(f"文件列表: {os.listdir('.')}")
        
        # 2. 尝试导入模块
        print("\n2. 测试模块导入...")
        try:
            import pandas as pd
            print(f"✓ pandas版本: {pd.__version__}")
        except ImportError as e:
            log_error(f"pandas导入失败: {e}")
            return 1
            
        try:
            import requests
            print(f"✓ requests版本: {requests.__version__}")
        except ImportError as e:
            log_error(f"requests导入失败: {e}")
            return 1
            
        try:
            import akshare as ak
            print("✓ akshare导入成功")
        except ImportError as e:
            log_error(f"akshare导入失败: {e}")
            print("尝试安装akshare...")
            os.system("pip install akshare --upgrade")
            try:
                import akshare as ak
                print("✓ akshare安装成功")
            except:
                log_error("akshare安装失败")
                return 1
        
        # 3. 测试获取股票数据
        print("\n3. 测试股票数据获取...")
        YOUR_STOCKS = ['000001', '002594']  # 先测试两只
        
        try:
            # 测试获取数据
            print("正在获取股票数据...")
            df = ak.stock_zh_a_spot_em()
            print(f"✓ 获取成功，数据形状: {df.shape}")
            
            # 筛选测试股票
            for code in YOUR_STOCKS:
                stock_df = df[df['代码'] == code]
                if not stock_df.empty:
                    stock = stock_df.iloc[0]
                    print(f"✓ {stock['名称']}({code}): {stock['最新价']}")
                else:
                    print(f"✗ 未找到股票: {code}")
            
            # 4. 生成测试报告
            print("\n4. 生成报告...")
            report = f"""📈 测试报告
生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
测试股票: {YOUR_STOCKS}
状态: ✅ 测试成功
"""
            
            # 保存报告
            filename = f"stock_report_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(report)
            
            print(f"✓ 报告已保存: {filename}")
            print("\n" + "=" * 60)
            print("✅ 脚本执行成功！")
            print("=" * 60)
            
            return 0
            
        except Exception as e:
            log_error(f"获取股票数据失败: {e}")
            print(f"详细错误: {traceback.format_exc()}")
            return 1
            
    except Exception as e:
        log_error(f"脚本执行异常: {e}")
        print(f"详细错误: {traceback.format_exc()}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
