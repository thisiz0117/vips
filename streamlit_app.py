import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import io
from datetime import datetime, timezone
from scipy.signal import savgol_filter

# --- 1. 공식 공개 데이터 대시보드 (전 지구 이산화탄소 농도) ---

# 데이터 출처: Scripps Institution of Oceanography, UC San Diego
# URL: https://scrippsco2.ucsd.edu/data/atmospheric_co2/primary_mlo_co2_record.html
DATA_URL = "https://scrippsco2.ucsd.edu/assets/data/atmospheric/stations/in_situ_co2/monthly/monthly_in_situ_co2_mlo.csv"

@st.cache_data(ttl=3600)  # 1시간 동안 캐시
def load_public_data():
    """Scripps CO2 데이터를 로드하고 전처리합니다."""
    try B
        # 1. 먼저 requests로 파일 내용을 텍스트로 가져옵니다.
        response = requests.get(DATA_URL)
        response.raise_for_status()
        lines = response.text.splitlines()

        # 2. 주석이 아닌, 실제 데이터가 시작되는 첫 번째 줄을 찾습니다.
        data_start_line = 0
        for i, line in enumerate(lines):
            if line.strip() and not line.strip().startswith('"'):
                data_start_line = i
                break
        
        # 3. 데이터 부분만 추출하여 pandas로 읽습니다.
        csv_data = "\n".join(lines[data_start_line:])
        df = pd.read_csv(
            io.StringIO(csv_data),
            delim_whitespace=True, 
            header=None,
            on_bad_lines='skip' 
        )
        
        # 열 이름 지정
        df.columns = ["year", "month", "date_excel", "date_decimal", "value", "seasonally_adjusted", "fit", "seasonally_adjusted_fit", "co2_filled", "seasonally_adjusted_filled"]
        
        df = df[['year', 'month', 'value']].copy()

        # -99.99는 결측치를 의미하므로 제거합니다.
        df = df[df['value'] != -99.99]

        # 날짜(date) 열 생성
        df['date'] = pd.to_datetime(df['year'].astype(str) + '-' + df['month'].astype(str))
        
        # 필요한 열만 선택
        df = df[['date', 'value']]
        
        # 오늘(로컬 자정) 이후 데이터 제거 (현재 시간 기준)
        today = datetime.now(timezone.utc).date()
        df = df[df['date'].dt.date < today]
        
        return df, None # 성공 시 데이터프레임과 None 반환

    except Exception as e:
        error_message = f"데이터를 불러오는 데 실패했습니다: {e}"
        # 예시 데이터 생성
        date_rng = pd.date_range(start='1958-03-01', end='2024-01-01', freq='MS')
        co2_data = [315.71 + 0.005 * i**2 + 2 * (i % 12) for i in range(len(date_rng))]
        example_df = pd.DataFrame(date_rng, columns=['date'])
        example_df['value'] = co2_data
        return example_df, error_message

def create_public_data_dashboard(df):
    """공개 데이터로 대시보드를 생성합니다."""
    st.subheader("Scripps 기관의 전 지구 CO2 농도 변화 🌎")
    st.markdown("""
    하와이 마우나로아 관측소에서 측정한 월별 대기 중 이산화탄소(CO2) 농도 데이터입니다. 
    산업화 이후 급격히 증가하는 CO2 농도 추세를 확인할 수 있습니다.
    """)

    # --- 사이드바 옵션 ---
    st.sidebar.header("공개 데이터 옵션")
    min_date = df['date'].min().date()
    max_date = df['date'].max().date()
    
    start_date, end_date = st.sidebar.date_input(
        "기간 선택",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        key="public_date_range"
    )

    if start_date > end_date:
        st.sidebar.error("시작일이 종료일보다 늦을 수 없습니다.")
        return

    # 데이터 필터링
    filtered_df = df[(df['date'].dt.date >= start_date) & (df['date'].dt.date <= end_date)].copy()

    use_smoothing = st.sidebar.checkbox("추세선 스무딩", value=True, key="public_smoothing")
    if use_smoothing and len(filtered_df) > 11:
        # Savitzky-Golay 필터 적용
        filtered_df['smoothed'] = savgol_filter(filtered_df['value'], window_length=11, polyorder=2)
    
    # --- 시각화 (Plotly) ---
    fig = go.Figure()

    # 원본 데이터
    fig.add_trace(go.Scatter(
        x=filtered_df['date'], 
        y=filtered_df['value'], 
        mode='lines', 
        name='월별 CO2 농도',
        line=dict(color='lightblue', width=1)
    ))

    # 스무딩된 추세선
    if use_smoothing and 'smoothed' in filtered_df.columns:
        fig.add_trace(go.Scatter(
            x=filtered_df['date'], 
            y=filtered_df['smoothed'], 
            mode='lines', 
            name='추세선 (Smoothed)',
            line=dict(color='royalblue', width=3)
        ))

    fig.update_layout(
        title="월별 CO2 농도 변화 추이 (킬링 곡선)",
        xaxis_title="연도",
        yaxis_title="CO2 농도 (ppm)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=40, r=40, t=80, b=40)
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # --- 데이터 내보내기 ---
    st.markdown("##### 데이터 확인 및 다운로드")
    download_df = filtered_df.copy()
    if 'smoothed' in download_df.columns:
        download_df['smoothed'] = download_df['smoothed'].round(2)
    download_df['value'] = download_df['value'].round(2)
    st.dataframe(download_df, use_container_width=True)
    
    csv = download_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="처리된 데이터(CSV) 다운로드",
        data=csv,
        file_name='co2_concentration_processed.csv',
        mime='text/csv',
    )


# --- 2. 사용자 입력 데이터 대시보드 ---

@st.cache_data
def load_user_data():
    """사용자가 제공한 CSV 데이터를 로드하고 전처리합니다."""
    csv_string = """year,temp_anomaly,co2_concentration
2001,0.54,370.57
2002,0.63,372.45
2003,0.62,375.04
2004,0.54,376.82
2005,0.68,378.92
2006,0.64,381.08
2007,0.66,382.72
2008,0.54,384.99
2009,0.66,386.37
2010,0.72,388.57
2011,0.61,390.52
2012,0.65,392.52
2013,0.68,395.27
2014,0.74,397.14
2015,0.9,399.99
2016,1.02,403.3
2017,0.93,405.5
2018,0.85,407.4
2019,0.98,409.8
2020,1.02,412.5
2021,0.85,414.7
2022,0.86,417.2
2023,1.18,419.3
"""
    df = pd.read_csv(io.StringIO(csv_string))
    df.rename(columns={'year': 'date', 'temp_anomaly': 'value', 'co2_concentration': 'group'}, inplace=True)
    df['date'] = pd.to_datetime(df['date'], format='%Y')
    
    # 오늘(로컬 자정) 이후 데이터 제거 (연도 기준)
    current_year = datetime.now(timezone.utc).year
    df = df[df['date'].dt.year < current_year]
    
    return df

def create_user_data_dashboard(df):
    """사용자 데이터로 대시보드를 생성합니다."""
    st.subheader("지구 온도 편차와 CO2 농도 비교 🌡️")
    st.markdown("""
    사용자가 제공한 데이터를 기반으로, 연간 지구 온도 편차(1951-1980년 평균 대비)와 
    대기 중 CO2 농도의 관계를 시각화합니다. 두 지표가 강한 상관관계를 보임을 알 수 있습니다.
    """)

    # --- 사이드바 옵션 ---
    st.sidebar.header("사용자 데이터 옵션")
    min_year = df['date'].dt.year.min()
    max_year = df['date'].dt.year.max()
    
    start_year, end_year = st.sidebar.slider(
        "연도 선택",
        min_value=min_year,
        max_value=max_year,
        value=(min_year, max_year),
        key="user_year_range"
    )

    filtered_df = df[(df['date'].dt.year >= start_year) & (df['date'].dt.year <= end_year)]
    
    # --- 시각화 (Plotly 이중 축) ---
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 온도 편차 (막대 그래프)
    fig.add_trace(go.Bar(
        x=filtered_df['date'], 
        y=filtered_df['value'],
        name='온도 편차 (°C)',
        marker_color='crimson',
        opacity=0.7
    ), secondary_y=False)

    # CO2 농도 (선 그래프)
    fig.add_trace(go.Scatter(
        x=filtered_df['date'], 
        y=filtered_df['group'],
        name='CO2 농도 (ppm)',
        mode='lines+markers',
        line=dict(color='darkblue', width=3)
    ), secondary_y=True)

    # 레이아웃 설정
    fig.update_layout(
        title_text="연도별 온도 편차 및 CO2 농도",
        xaxis_title="연도",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )

    # Y축 제목 설정
    fig.update_yaxes(title_text="온도 편차 (°C)", secondary_y=False)
    fig.update_yaxes(title_text="CO2 농도 (ppm)", secondary_y=True)
    
    st.plotly_chart(fig, use_container_width=True)
    
    # --- 데이터 내보내기 ---
    st.markdown("##### 데이터 확인 및 다운로드")
    
    # 표시용 데이터프레임 (열 이름 원복 및 연도만 표시)
    display_df = filtered_df.copy()
    display_df['date'] = display_df['date'].dt.year
    display_df.rename(columns={'date': 'year', 'value': 'temp_anomaly', 'group': 'co2_concentration'}, inplace=True)
    st.dataframe(display_df.style.format({'temp_anomaly': '{:.2f}', 'co2_concentration': '{:.2f}'}), use_container_width=True)
    
    csv = display_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="처리된 데이터(CSV) 다운로드",
        data=csv,
        file_name='temp_co2_processed.csv',
        mime='text/csv',
        key='user_download'
    )

# --- 메인 앱 실행 ---
def main():
    st.set_page_config(page_title="탄소중립 데이터 대시보드", layout="wide")
    st.title("🌱 탄소중립 데이터 대시보드")
    
    st.markdown("---")
    st.header("1. 공식 공개 데이터 대시보드")
    public_df, error = load_public_data()
    if error:
        st.error(f"**데이터 로딩 오류:** {error}\n\n**참고:** 네트워크 문제로 실제 데이터를 가져올 수 없어, 내장된 예시 데이터로 대시보드를 표시합니다.")
    create_public_data_dashboard(public_df)
    
    st.markdown("---")
    st.header("2. 사용자 입력 데이터 대시보드")
    user_df = load_user_data()
    create_user_data_dashboard(user_df)

if __name__ == "__main__":
    main()