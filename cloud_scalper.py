import os
import sys
import time
import json
import requests
import pandas as pd
import yfinance as yf
from datetime import datetime, timezone, timedelta

# Configuration from Environment Variables (set in GitHub Secrets)
API_KEY = os.getenv("LLM_API_KEY")
API_BASE_URL = os.getenv("LLM_API_BASE_URL", "https://api.openai.com/v1")
MODEL_NAME = os.getenv("LLM_MODEL_NAME", "gpt-4o")
SERVERCHAN_KEY = os.getenv("SERVERCHAN_KEY")

TARGET_TIME_STR = os.getenv("TARGET_TIME") # e.g. "15:30:00"

def wait_for_target_time():
    """Anti-Jitter Mechanism: Wait exactly until the target time."""
    if not TARGET_TIME_STR:
        print("No target time specified, running immediately.")
        return

    print(f"Target execution time: {TARGET_TIME_STR}")
    # Get current UTC time, convert to Beijing Time (UTC+8)
    now_utc = datetime.now(timezone.utc)
    now_bj = now_utc + timedelta(hours=8)
    
    target_time_parts = TARGET_TIME_STR.split(":")
    target_bj = now_bj.replace(
        hour=int(target_time_parts[0]),
        minute=int(target_time_parts[1]),
        second=int(target_time_parts[2]) if len(target_time_parts) > 2 else 0,
        microsecond=0
    )

    diff = (target_bj - now_bj).total_seconds()
    if diff > 0:
        print(f"Early wakeup detected. Waiting {diff} seconds for precision strike...")
        time.sleep(diff)
    else:
        print("Target time reached or passed. Executing immediately.")

def fetch_xau_data():
    """Fetch XAU/USD 30m K-line data from Yahoo Finance and calculate EMA/MACD."""
    print("Fetching market data from Yahoo Finance...")
    try:
        # Fetch last 7 days of 30m interval data for Gold Futures (GC=F, COMEX)
        df = yf.download(tickers='GC=F', interval='30m', period='7d')
        if df.empty:
            raise ValueError("Yahoo Finance returned empty data for GC=F")
        
        # Handle yfinance MultiIndex output structure
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        df = df.rename(columns=lambda x: x.lower()) # Make columns lowercase: open, high, low, close
        
    except Exception as e:
        print(f"Error: Could not fetch K-line data. {e}")
        raise ValueError("Failed to fetch K-line data from Yahoo Finance")
    
    # Calculate EMA
    df['EMA_12'] = df['close'].ewm(span=12, adjust=False).mean()
    df['EMA_26'] = df['close'].ewm(span=26, adjust=False).mean()
    
    # Calculate MACD
    df['MACD'] = df['EMA_12'] - df['EMA_26']
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']
    
    latest = df.iloc[-1]
    
    market_context = f"""
    XAU/USD (Gold Futures COMEX) 30m Real-time Data:
    - Current Price: {float(latest['close']):.2f}
    - EMA(12): {float(latest['EMA_12']):.2f}
    - EMA(26): {float(latest['EMA_26']):.2f}
    - MACD Line: {float(latest['MACD']):.2f}
    - MACD Signal: {float(latest['MACD_Signal']):.2f}
    - MACD Histogram: {float(latest['MACD_Hist']):.2f}
    """
    print(market_context)
    return market_context

def analyze_with_llm(market_data):
    """Send data to the LLM for analysis based on Iron Rules."""
    print(f"Requesting analysis from {MODEL_NAME} at {API_BASE_URL}...")
    
    prompt = f"""
    # Role: 全球宏观外汇与现货黄金 (XAU) 极短线（30分钟）高频量化专家 (High-Win Scalper)

    ## Core Objective
    基于以下获取的最新国际现货黄金 (XAU/USD) 30分钟级别量价数据，结合你对当前全球宏观经济、美联储政策和地缘政治的了解，输出一份极具确定性的短线交易计划。核心哲学是“极度厌恶风险”。

    ## Execution Principles (The Iron Rules)
    1. 绝对确定性：明确给出“做多 (LONG)”、“做空 (SHORT)”或“观望 (WAIT)”。
    2. 顺利进场 (Easy Entry)：寻找重叠区域（Confluence Area）。
    3. 宁缺毋滥（最高铁律）：如果图表无序或无强烈宏观共振，直接判定“观望 WAIT”。
    
    ## 实时数据输入
    {market_data}
    
    ## Output Format
    严格使用以下Markdown输出：
    ### 1. 终极交易决策
    - 方向判定：[做多 LONG / 做空 SHORT / 观望 WAIT]
    - 决策置信度：[0% - 100%]
    - 核心触发源：[简述决定性因素]

    ### 2. 定性看板摘要
    (用一句话概括宏观、资金、技术面的综合情况)
    """

    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2
    }
    
    try:
        response = requests.post(f"{API_BASE_URL}/chat/completions", headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()
        report = result['choices'][0]['message']['content']
        return report
    except Exception as e:
        print(f"LLM API Error: {e}")
        if response is not None:
            print(response.text)
        return "【系统故障】调用大模型分析失败，请检查 API 密钥或网络限制。"

def send_wechat(title, content):
    """Send notification via ServerChan."""
    print("Pushing to WeChat via ServerChan...")
    if not SERVERCHAN_KEY:
        print("Warning: SERVERCHAN_KEY not set. Skipping push.")
        return
        
    url = f"https://sctapi.ftqq.com/{SERVERCHAN_KEY}.send"
    data = {"title": title, "desp": content}
    try:
        res = requests.post(url, data=data)
        print(f"ServerChan Response: {res.text}")
    except Exception as e:
        print(f"ServerChan Push Failed: {e}")

if __name__ == "__main__":
    print("--- High-Win Cloud Scalper Initiated ---")
    wait_for_target_time()
    
    market_data = fetch_xau_data()
    report = analyze_with_llm(market_data)
    
    target_label = TARGET_TIME_STR if TARGET_TIME_STR else "手动触发"
    title = f"【实时行情】黄金 XAU 狙击手 ({target_label})"
    
    send_wechat(title, report)
    print("--- Execution Complete ---")
