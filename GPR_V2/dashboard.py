import streamlit as st
import pandas as pd
import os
import predictor          # 페이지2: 변동성 예측 엔진
import bubble_predictor   # 페이지1: 버블 예측 엔진
import news_updater

# 페이지 기본 설정
st.set_page_config(page_title="AI-GPR Market Risk Dashboard", layout="wide")

if "page" not in st.session_state:
    st.session_state.page = 1
if "news_page" not in st.session_state:
    st.session_state.news_page = 0

st.title("🌐 AI-GPR Market Risk Dashboard")

# ==========================================
# 📄 페이지 1: 종합 위험 상황판 (뉴스 + 버블)
# ==========================================
if st.session_state.page == 1:
    col_title, col_btn = st.columns([8, 2])
    with col_title:
        st.subheader("Today’s Geopolitical Headlines & US Bubble Risk")
    with col_btn:
        if st.button("다음 페이지로 이동 ➡️ (변동성 예측)", use_container_width=True):
            st.session_state.page = 2
            st.rerun()

    # 상단 뉴스 업데이트 버튼
    if st.button("🚀 오늘의 지정학 뉴스 초고속 업데이트"):
        with st.spinner("최신 연합뉴스 국제망을 스캔 중입니다..."):
            try:
                news_updater.update_news()
                st.session_state.news_page = 0
                st.rerun()
            except Exception as e:
                st.error(f"뉴스 수집 중 오류 발생: {e}")

    # 좌우 2단 분할 (왼쪽: 가로 2칸 뉴스 / 오른쪽: 버블 진단)
    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("📰 실시간 핵심 뉴스 브리핑")
        if os.path.exists("today_geopolitical_news.csv"):
            news_df = pd.read_csv("today_geopolitical_news.csv")
            if not news_df.empty:
                news_df = news_df.sort_values(by="risk_score", ascending=False).reset_index(drop=True)
                items_per_page = 2
                total_news = len(news_df)
                max_pages = max(0, (total_news - 1) // items_per_page)
                
                if st.session_state.news_page > max_pages:
                    st.session_state.news_page = 0
                    
                start_idx = st.session_state.news_page * items_per_page
                paged_df = news_df.iloc[start_idx : start_idx + items_per_page]
                
                news_cols = st.columns(2)
                for i, (idx, row) in enumerate(paged_df.iterrows()):
                    with news_cols[i]:
                        level = str(row['risk_level']).upper()
                        score = row['risk_score']
                        if level == "HIGH": badge = f"🔴 HIGH (Score: {score})"
                        elif level == "MEDIUM": badge = f"🟡 MED (Score: {score})"
                        else: badge = f"🟢 LOW (Score: {score})"
                        
                        st.markdown(f"**{badge}** | **[{row['title']}]({row['url']})**")
                        st.caption(f"🎯 파급: `{row['expected_impact']}`")
                        st.caption(f"📝 {str(row['summary'])[:45]}...")
                
                st.markdown("---")
                p_col1, p_col2 = st.columns([1, 1])
                with p_col1:
                    if st.session_state.news_page > 0:
                        if st.button("⬅️ 이전 뉴스", use_container_width=True):
                            st.session_state.news_page -= 1
                            st.rerun()
                with p_col2:
                    if st.session_state.news_page < max_pages:
                        if st.button("다음 뉴스 ➡️", use_container_width=True):
                            st.session_state.news_page += 1
                            st.rerun()
            else:
                st.info("수집된 뉴스가 없습니다.")
        else:
            st.info("📢 상단 업데이트 버튼을 눌러 레이더를 가동하십시오.")

    with col2:
        st.subheader("🚨 US Market Bubble Risk Indicator")
        if st.button("버블 위험도 실시간 진단 시작", type="primary", use_container_width=True):
            with st.spinner("FRED 및 yfinance 매크로 데이터를 연산 중입니다..."):
                try:
                    bubble_res = bubble_predictor.predict()
                    st.session_state.bubble_result = bubble_res
                except Exception as e:
                    st.error(f"버블 진단 중 오류 발생: {e}")

        if "bubble_result" in st.session_state:
            res = st.session_state.bubble_result
            prob = res["risk_probability"]
            metrics = res["metrics"]
            
            if prob >= 80: status_text = "🔴 심각한 과열 (Bubble Burst Imminent)"
            elif prob >= 50: status_text = "🟠 경계 구간 (High Risk)"
            else: status_text = "🟢 안정 구간 (Normal Market)"
                
            st.markdown(f"### {status_text} | 확률: **{prob:.2f}%**")
            st.progress(int(prob))
            
            b_m1, b_m2 = st.columns(2)
            b_m1.metric("CAPE 프록시", f"{metrics['cape']['value']:.1f}", f"{metrics['cape']['change']:.2f}", delta_color="inverse")
            b_m2.metric("하이일드 스프레드", f"{metrics['hy_spread']['value']:.2f}%", f"{metrics['hy_spread']['change']:.2f}%", delta_color="inverse")
            b_m3, b_m4 = st.columns(2)
            b_m3.metric("버핏 지수", f"{metrics['buffett']['value']:.1f}%", f"{metrics['buffett']['change']:.1f}%", delta_color="inverse")
            b_m4.metric("FINRA 마진부채", f"${metrics['margin']['value']:.1f}B", f"${metrics['margin']['change']:.1f}B", delta_color="inverse")

# ============================================================
# 📄 페이지 2: S&P 500 변동성 예측 대시보드
# ============================================================
elif st.session_state.page == 2:
    col_title, col_btn = st.columns([8, 2])
    with col_title:
        st.subheader("S&P 500 Volatility Prediction (HAR-RV Model)")
    with col_btn:
        if st.button("⬅️ 이전 페이지로 돌아가기", use_container_width=True):
            st.session_state.page = 1
            st.rerun()

    if st.button("예측 엔진 가동 (최신 데이터 분석)", type="primary"):
        with st.spinner("야후 파이낸스 및 EPU 데이터를 분석 중입니다..."):
            try:
                result = predictor.predict(refresh_data=True)
                st.session_state.pred_result = result
            except Exception as e:
                st.error(f"엔진 가동 중 오류 발생: {e}")

    if "pred_result" in st.session_state:
        res = st.session_state.pred_result
        latest = res["latest"]
        metrics = res["metrics"]

        st.markdown("### 🎯 핵심 지표 (Latest Prediction)")
        kpi1, kpi2, kpi3 = st.columns(3)
        with kpi1:
            st.metric(label="예측 연환산 변동성", value=f"{latest['predicted_annualized_vol_pct']:.2f}%")
        with kpi2:
            st.metric(label="오늘의 일일 분산 (σ²)", value=f"{latest['predicted_sigma2']:.4f}")
        with kpi3:
            st.metric(label="모델 오차율 (RMSE)", value=f"{metrics['rmse']:.4f}")

        st.markdown("### 📈 모델 테스트 구간 시계열 추이")
        history_df = pd.DataFrame(res["history"])
        history_df.set_index("date", inplace=True)
        st.line_chart(history_df[["actual", "predicted"]], color=["#FF4B4B", "#0068C9"])