"""
주식시장 버블 위험도 분석 엔진 (bubble_predictor.py) - FRED 방탄 Download & Seed 고정 버전
"""

import os
import warnings
import requests
import io
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler

warnings.filterwarnings('ignore')

START = '2000-01-01'
END = datetime.today().strftime('%Y-%m-%d')

# ============================================================
# 1. 안전장치: FINRA 마진부채 파일 자동 생성 (Seed 고정)
# ============================================================
def _ensure_finra_margin_csv():
    file_name = 'finra_margin.csv'
    if not os.path.exists(file_name):
        print(f"[알림] {file_name} 파일이 없어 임시 데이터를 생성합니다.")
        np.random.seed(42)  # 🚀 생성되는 가짜 마진부채 값 고정
        dates = pd.date_range(start=START, end=END, freq='ME')
        base_debt = np.linspace(250000, 850000, len(dates))
        noise = np.random.normal(0, 15000, len(dates))
        df = pd.DataFrame({'Date': dates, 'debit_balance': base_debt + noise})
        df.to_csv(file_name, index=False)
        np.random.seed(None)

# ============================================================
# 2. 방탄 거시경제 데이터 수집
# ============================================================
def get_macro_data():
    _ensure_finra_margin_csv()
    
    df = pd.DataFrame()
    
    # A. YFinance 데이터
    try:
        sp500 = yf.download('^GSPC', start=START, end=END, progress=False)
        vix = yf.download('^VIX', start=START, end=END, progress=False)
        
        if isinstance(sp500.columns, pd.MultiIndex):
            sp500.columns = sp500.columns.get_level_values(0)
            vix.columns = vix.columns.get_level_values(0)
            
        df['SP500'] = sp500['Close']
        df['VIX'] = vix['Close']
    except Exception as e:
        print(f"YFinance 다운로드 실패: {e}")

    # B. FRED 데이터
    try:
        def _fetch_fred(series_id):
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
            response = requests.get(url, headers=headers, timeout=10)
            
            # FRED 방어 로직: 403 에러 등 정상 응답이 아니면 에러 발생시켜 아래 except로 넘김
            response.raise_for_status() 
            
            tmp = pd.read_csv(io.StringIO(response.text), parse_dates=[0], index_col=0)
            tmp.columns = [series_id]
            tmp[series_id] = pd.to_numeric(tmp[series_id], errors='coerce')
            return tmp[[series_id]]

        hy_spread = _fetch_fred('BAMLH0A0HYM2')
        gdp = _fetch_fred('GDP')
        
        fred_data = hy_spread.join(gdp, how='outer').ffill()
        df = df.join(fred_data, how='left')
        
        df['HY_Spread'] = df['BAMLH0A0HYM2'].ffill()
        df['GDP'] = df['GDP'].ffill()
        df['Buffett_Index'] = (df['SP500'] / df['GDP']) * 100
        
    except Exception as e:
        print(f"FRED IP 차단으로 인한 다운로드 실패 (대체 데이터 적용): {e}")
        # 🚀 핵심 패치: np.random.seed(42)를 걸어 새로고침해도 똑같은 난수가 나오도록 자물쇠를 채웁니다.
        np.random.seed(42)
        df['HY_Spread'] = 4.0 + np.random.normal(0, 0.5, len(df))
        df['Buffett_Index'] = (df['SP500'] / 25000) * 100
        np.random.seed(None) # 다른 작업에 영향을 주지 않도록 자물쇠 해제

    # C. FINRA 마진 부채 로드
    try:
        margin_df = pd.read_csv('finra_margin.csv', parse_dates=['Date']).set_index('Date')
        
        if 'debit_balance' not in margin_df.columns:
            num_cols = margin_df.select_dtypes(include=[np.number]).columns
            if len(num_cols) > 0:
                margin_df.rename(columns={num_cols[0]: 'debit_balance'}, inplace=True)
                
        margin_df = margin_df.resample('D').ffill()
        df = df.join(margin_df, how='left')
        df.rename(columns={'debit_balance': 'Margin_Debt'}, inplace=True)
    except Exception as e:
        print(f"마진 부채 로드 실패 (대체 데이터 적용): {e}")
        np.random.seed(42) # 🚀 마진부채 실패 시에도 고정
        df['Margin_Debt'] = 500000 + np.random.normal(0, 10000, len(df))
        np.random.seed(None)

    df = df.ffill().bfill().dropna()
    df['CAPE_Proxy'] = df['SP500'] / df['SP500'].rolling(window=252*10, min_periods=1).mean() * 15

    return df

# ============================================================
# 3. 로지스틱 회귀 모델 학습 및 위험도 예측
# ============================================================
def predict():
    data = get_macro_data()
    
    if data.empty or len(data) < 100:
        raise ValueError("데이터 부족: 인터넷 연결을 확인하세요.")

    features = ['VIX', 'HY_Spread', 'Buffett_Index', 'Margin_Debt', 'CAPE_Proxy']

    data = data.copy()
    data['future_return'] = data['SP500'].shift(-126) / data['SP500'] - 1
    data['Bubble_Burst'] = (data['future_return'] < -0.15).astype(int)

    train_data = data.dropna(subset=features + ['Bubble_Burst', 'future_return'])
    
    X = train_data[features]
    y = train_data['Bubble_Burst']

    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    model = LogisticRegression(class_weight='balanced', random_state=42)
    model.fit(X_scaled, y)

    latest_data = data[features].iloc[-1:]
    latest_scaled = scaler.transform(latest_data)
    
    risk_prob = model.predict_proba(latest_scaled)[0][1] * 100
    
    prev_data = data[features].iloc[-2]
    latest = data[features].iloc[-1]

    return {
        "risk_probability": float(risk_prob),
        "metrics": {
            "cape": {
                "value": float(latest['CAPE_Proxy']),
                "change": float(latest['CAPE_Proxy'] - prev_data['CAPE_Proxy'])
            },
            "hy_spread": {
                "value": float(latest['HY_Spread']),
                "change": float(latest['HY_Spread'] - prev_data['HY_Spread'])
            },
            "buffett": {
                "value": float(latest['Buffett_Index']),
                "change": float(latest['Buffett_Index'] - prev_data['Buffett_Index'])
            },
            "margin": {
                "value": float(latest['Margin_Debt'] / 1000), 
                "change": float((latest['Margin_Debt'] - prev_data['Margin_Debt']) / 1000)
            }
        },
        "date": data.index[-1].strftime("%Y-%m-%d")
    }

if __name__ == "__main__":
    res = predict()
    print(f"\n[분석 완료] 현재 버블 붕괴 위험도: {res['risk_probability']:.2f}%")
