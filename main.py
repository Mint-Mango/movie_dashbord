
# ============================================
# 영화진흥위원회(KOBIS) 일별 박스오피스 조회 앱
# 날짜 선택, 순위 변화, 누적관객 트로피 표시
# ============================================

import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import plotly.express as px
import requests
import streamlit as st


# 1. 웹페이지 기본 설정
st.set_page_config(
    page_title="일별 박스오피스",
    page_icon="🎬",
    layout="wide",
)

# 2. 한국 시간 기준으로 날짜 계산
# 서버 시간이 한국 시간이 아니어도 정확하게 계산한다.
KST = ZoneInfo("Asia/Seoul")
today_kst = datetime.datetime.now(KST).date()
yesterday = today_kst - datetime.timedelta(days=1)

# 3. KOBIS API 주소
API_URL = (
    "https://www.kobis.or.kr/kobisopenapi/webservice/rest/"
    "boxoffice/searchDailyBoxOfficeList.json"
)

# 4. Secrets에서 인증키 가져오기
# 인증키를 소스 코드에 직접 작성하지 않는다.
try:
    API_KEY = st.secrets["KOBIS_KEY"]
except (KeyError, FileNotFoundError):
    st.error(
        "KOBIS 인증키를 찾을 수 없습니다. "
        "Streamlit Cloud의 앱 설정 → Secrets에서 "
        "KOBIS_KEY를 등록해 주세요."
    )
    st.code('KOBIS_KEY = "발급받은_인증키"')
    st.stop()


# 5. API에서 선택한 날짜의 박스오피스 가져오기
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_boxoffice(date_str, api_key):
    response = requests.get(
        API_URL,
        params={
            "key": api_key,
            "targetDt": date_str,
        },
        timeout=20,
    )

    # HTTP 4xx, 5xx 오류 확인
    response.raise_for_status()

    # HTTP 200이어도 인증키 오류 등이 있을 수 있다.
    return response.json()


# 6. 화면 제목과 날짜 선택 달력
st.title("🎬 일별 박스오피스")
st.caption("영화진흥위원회 KOBIS 공식 일별 박스오피스 자료")

st.subheader("조회 날짜 선택")

selected_date = st.date_input(
    "박스오피스를 확인할 날짜",
    value=yesterday,
    min_value=datetime.date(2004, 11, 1),
    max_value=yesterday,
    format="YYYY-MM-DD",
)

# 선택한 날짜를 API 요청용 YYYYMMDD 형식으로 변환한다.
target_dt = selected_date.strftime("%Y%m%d")
display_date = selected_date.strftime("%Y-%m-%d")

st.info(f"선택한 조회 날짜: **{display_date}**")

st.divider()


# 7. API 요청 및 오류 처리
try:
    with st.spinner("박스오피스 데이터를 불러오는 중입니다..."):
        data = fetch_boxoffice(target_dt, API_KEY)

except requests.exceptions.Timeout:
    st.error(
        "KOBIS 서버의 응답 시간이 초과되었습니다. "
        "인터넷 연결을 확인하고 잠시 후 다시 시도해 주세요."
    )
    st.stop()

except requests.exceptions.HTTPError as e:
    st.error(f"KOBIS 서버 HTTP 오류: {e}")
    st.info("API 요청 주소와 서버 상태를 확인해 주세요.")
    st.stop()

except requests.exceptions.RequestException as e:
    st.error(f"KOBIS 서버에 연결하지 못했습니다: {e}")
    st.info("네트워크 연결과 KOBIS 서버 상태를 확인해 주세요.")
    st.stop()

except ValueError:
    st.error("API 응답을 JSON으로 해석하지 못했습니다.")
    st.info("잠시 후 다시 시도해 주세요.")
    st.stop()


# 8. API가 반환한 오류 상자 확인
if not isinstance(data, dict):
    st.error("API 응답 형식이 올바르지 않습니다.")
    st.info("KOBIS API 응답을 확인해 주세요.")
    st.stop()

if "faultInfo" in data:
    fault = data.get("faultInfo") or {}

    st.error("KOBIS API에서 오류를 반환했습니다.")
    st.write(f"**오류 코드:** {fault.get('errorCode', '확인 불가')}")
    st.write(f"**오류 내용:** {fault.get('message', '확인 불가')}")

    st.info(
        "다음 사항을 확인해 주세요.\n\n"
        "- Secrets에 KOBIS_KEY가 정확하게 등록되어 있는지\n"
        "- 인증키가 유효한지\n"
        "- API 이용 한도를 초과하지 않았는지"
    )
    st.stop()


# 9. 영화 목록 가져오기
box_office_result = data.get("boxOfficeResult")

if not isinstance(box_office_result, dict):
    st.error("응답에 boxOfficeResult가 없습니다.")
    st.info("KOBIS API 응답 구조를 확인해 주세요.")
    st.stop()

movies = box_office_result.get("dailyBoxOfficeList", [])

# 영화 목록이 비어 있으면 날짜별 안내를 표시한다.
if not isinstance(movies, list) or len(movies) == 0:
    st.warning("그날은 아직 집계 전입니다")
    st.info(
        f"{display_date}의 박스오피스 영화 목록이 비어 있습니다. "
        "아직 집계되지 않았거나 해당 날짜의 자료가 제공되지 않을 수 있습니다. "
        "KOBIS 공식 사이트에서 해당 날짜의 집계 여부를 확인해 주세요."
    )
    st.stop()


# 10. 영화 목록을 데이터프레임으로 변환
df = pd.DataFrame(movies)

# API 숫자 값은 문자열이므로 숫자형으로 변환한다.
numeric_columns = [
    "rank",
    "rankInten",
    "audiCnt",
    "audiAcc",
    "scrnCnt",
]

for col in numeric_columns:
    if col not in df.columns:
        df[col] = 0

    df[col] = (
        pd.to_numeric(df[col], errors="coerce")
        .fillna(0)
        .astype(int)
    )

# 영화명과 개봉일이 누락된 경우를 대비한다.
for col in ["movieNm", "openDt"]:
    if col not in df.columns:
        df[col] = ""

    df[col] = df[col].fillna("").astype(str)

df.loc[
    df["movieNm"].str.strip() == "",
    "movieNm",
] = "영화명 미제공"

# 순위 숫자를 기준으로 정렬한다.
df = df.sort_values("rank", ascending=True).reset_index(drop=True)


# 11. 영화명에 트로피 표시
# 누적 관객수가 100만 명을 초과한 영화에 트로피를 붙인다.
df["표시 영화명"] = df.apply(
    lambda row: (
        f"🏆 {row['movieNm']}"
        if row["audiAcc"] > 1_000_000
        else row["movieNm"]
    ),
    axis=1,
)


# 12. 전날 대비 순위 변화 표시
# KOBIS의 rankInten 양수는 순위 상승, 음수는 순위 하락으로 표시한다.
def format_rank_change(value):
    if value > 0:
        return f"▲ {value}"
    elif value < 0:
        return f"▼ {abs(value)}"
    else:
        return "-"


df["순위 변화"] = df["rankInten"].apply(format_rank_change)


# 13. 1위 영화 지표 카드 3개
first_movie = df.iloc[0]

st.subheader(f"🥇 오늘의 조회 결과 1위: {first_movie['표시 영화명']}")

col1, col2, col3 = st.columns(3)

with col1:
    st.metric(
        label="관객수",
        value=f"{first_movie['audiCnt']:,}명",
    )

with col2:
    st.metric(
        label="누적관객",
        value=f"{first_movie['audiAcc']:,}명",
    )

with col3:
    st.metric(
        label="스크린수",
        value=f"{first_movie['scrnCnt']:,}개",
    )

st.divider()


# 14. 전체 박스오피스 표
st.subheader("📋 일별 박스오피스 순위표")

table = df[
    [
        "rank",
        "순위 변화",
        "표시 영화명",
        "openDt",
        "audiCnt",
        "audiAcc",
        "scrnCnt",
    ]
].copy()

table.columns = [
    "순위",
    "순위 변화",
    "영화명",
    "개봉일",
    "관객수",
    "누적관객",
    "스크린수",
]

# 관객수와 스크린수에 천 단위 쉼표를 표시한다.
for col in ["관객수", "누적관객", "스크린수"]:
    table[col] = table[col].map(lambda value: f"{value:,}")


# 순위 변화 화살표에 색상을 지정한다.
def rank_arrow_color(value):
    if isinstance(value, str) and value.startswith("▲"):
        return "color: red; font-weight: bold"
    elif isinstance(value, str) and value.startswith("▼"):
        return "color: blue; font-weight: bold"
    return ""


styled_table = table.style.map(
    rank_arrow_color,
    subset=["순위 변화"],
)

st.dataframe(
    styled_table,
    hide_index=True,
    use_container_width=True,
)


st.caption(
    "▲ 빨간색: 순위 상승 · "
    "▼ 파란색: 순위 하락 · "
    "- : 순위 변동 없음 또는 변동 정보 없음 · "
    "🏆 : 누적관객 100만 명 초과"
)

st.divider()


# 15. 관객수 상위 5편 막대그래프
st.subheader("📊 관객수 상위 5편")

top5 = (
    df.sort_values("audiCnt", ascending=False)
    .head(5)
    .sort_values("audiCnt", ascending=True)
)

fig = px.bar(
    top5,
    x="audiCnt",
    y="표시 영화명",
    orientation="h",
    labels={
        "audiCnt": "관객수(명)",
        "표시 영화명": "영화명",
    },
    text="audiCnt",
)

# 막대 끝에 관객수를 표시한다.
fig.update_traces(
    texttemplate="%{x:,.0f}명",
    textposition="outside",
    cliponaxis=False,
)

fig.update_layout(
    xaxis_title="관객수(명)",
    yaxis_title="영화명",
    xaxis=dict(tickformat=","),
    showlegend=False,
    margin=dict(l=10, r=80, t=20, b=10),
)

st.plotly_chart(fig, use_container_width=True)


# 16. 자료 출처
st.caption(
    f"조회 기준일: {display_date} · "
    "자료 출처: 영화진흥위원회(KOBIS) 일별 박스오피스 Open API"
)
