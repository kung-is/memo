import streamlit as st
import pandas as pd
from datetime import date, timedelta
import gspread
import time
import streamlit.components.v1 as components
import json

# --- 챌린지 설정 ---
MEMBERS = [
    "김가희", "김예슬", "김은비", "김지아", "양태임", "연다은", "용경빈", "윤혜진",
    "이강희", "이지형", "이현민", "임소희", "장상희", "전혜성", "최한빛", "호주김지아", "홍의경"
]
TODAY_PASSWORD_SUFFIX = "컹"
WEEKLY_GOAL = 5
TOTAL_CHALLENGE_GOAL = 20

CHALLENGE_WEEKS = [
    {"name": "보너스 주차", "start": date(2025, 12, 3), "end": date(2025, 12, 7), "goal": 0, "is_challenge": False},
    {"name": "1주차", "start": date(2025, 12, 8), "end": date(2025, 12, 14), "goal": WEEKLY_GOAL, "is_challenge": True},
    {"name": "2주차", "start": date(2025, 12, 15), "end": date(2025, 12, 21), "goal": WEEKLY_GOAL, "is_challenge": True},
    {"name": "3주차", "start": date(2025, 12, 22), "end": date(2025, 12, 28), "goal": WEEKLY_GOAL, "is_challenge": True},
    {"name": "4주차", "start": date(2025, 12, 29), "end": date(2026, 1, 4), "goal": WEEKLY_GOAL, "is_challenge": True},
]

CHALLENGE_START_DATE = CHALLENGE_WEEKS[0]["start"]
CHALLENGE_END_DATE = CHALLENGE_WEEKS[-1]["end"]

# 🎨 디자인 색상 및 폰트 설정 (MZ/Growth Tracker 컨셉)
PRIMARY_COLOR = "#FF6B35"     # 코랄 오렌지 (주요 액션, 성공 강조)
SECONDARY_COLOR = "#262361"    # 딥 퍼플/네이비 (헤더, 텍스트)
ACCENT_COLOR = "#3ABBF8"      # 스카이 블루 (현재 주차, 동기 부여)
BACKGROUND_LIGHT = "#FFEFEB"   # 아주 연한 블루 그레이 (클린 배경)
CARD_BG = "#FFFFFF"            # 흰색 (카드 배경)
TEXT_DARK = "#333333"          # 일반 텍스트
SUCCESS_COLOR = "#1BBF00"      # 그린 (완료)
SUCCESS_BG = "#e6ffec"        # 연한 초록색 (성공 배경)
SUCCESS_BORDER = "#1BBF00"    # 진한 초록색 (성공 테두리)


# --- Google Sheets 연결 (Resource 캐싱 유지) ---
@st.cache_resource(ttl=600)
def init_connection():
    # Google Sheets 연결 객체를 캐시합니다. (10분 TTL)
    try:
        gcp_secrets = st.secrets["gsheets"]
        private_key = gcp_secrets["private_key"].replace('\\n', '\n')
        credentials = {
            "type": gcp_secrets["type"],
            "project_id": gcp_secrets["project_id"],
            "private_key_id": gcp_secrets["private_key_id"],
            "private_key": private_key,
            "client_email": gcp_secrets["client_email"],
            "token_uri": gcp_secrets["token_uri"]
        }
        gc = gspread.service_account_from_dict(credentials)
        # gc_spreadsheet를 전역 변수로 유지하지 않고, 연결된 스프레드시트를 직접 반환합니다.
        return gc.open_by_url(st.secrets["gsheets"]["spreadsheet_url"])
    except Exception as e:
        st.error("🚨 Google Sheets 연결 오류! secrets.toml 파일과 시트 공유 권한을 확인해 주세요.")
        st.error(f"상세 오류: {e}")
        return None

# --- 데이터 로드 함수 (DATA 쿼터 초과 방지) ---
@st.cache_data(ttl=300) # 300초(5분)마다 데이터 새로고침
def load_data(member_name):
    # 캐시된 연결 객체를 가져옵니다.
    gc_spreadsheet = init_connection()
    if not gc_spreadsheet:
        return pd.DataFrame({'날짜': [], '글 내용': []})
    
    try:
        # Sheets API 호출
        ws = gc_spreadsheet.worksheet(member_name)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        if not df.empty:
            df['날짜'] = pd.to_datetime(df['날짜'], errors='coerce').dt.normalize()
            df = df.dropna(subset=['날짜'])
            df['날짜'] = df['날짜'].apply(lambda x: x.date())
            if '글 내용' not in df.columns:
                df['글 내용'] = ""
            df = df[['날짜', '글 내용']]
        else:
            df = pd.DataFrame(columns=['날짜', '글 내용'])
        
        return df
    except gspread.WorksheetNotFound:
        st.error(f"시트 탭 오류! '{member_name}' 탭이 없습니다.")
        return pd.DataFrame({'날짜': [], '글 내용': []})
    except Exception as e:
        st.error(f"데이터 로드 오류 ({member_name}): {e}")
        return pd.DataFrame({'날짜': [], '글 내용': []})

def get_motivation_message(total_written, total_goal):
    if total_written >= total_goal:
        return f"🔥 너무 잘하고 계십니다! 최종 목표({total_goal}일)를 이미 달성하셨습니다. 추가 기록은 보너스 포인트!"
    
    today = date.today()
    elapsed_challenge_days = (today - CHALLENGE_WEEKS[1]["start"]).days + 1
    main_challenge_days = (CHALLENGE_WEEKS[-1]["end"] - CHALLENGE_WEEKS[1]["start"]).days + 1 
    
    if elapsed_challenge_days < 0: 
        elapsed_challenge_days = 0 
        
    # 경과 일수에 따른 기대 목표치를 계산합니다.
    expected_goal_to_date = int(TOTAL_CHALLENGE_GOAL * (elapsed_challenge_days / main_challenge_days))
    expected_goal_to_date = max(0, expected_goal_to_date) 

    if total_written >= expected_goal_to_date:
        return f"👍 계획대로 잘 진행 중입니다! (기대 목표 {expected_goal_to_date}일 대비 +{total_written - expected_goal_to_date}일 초과)"
    else:
        remaining_to_catch_up = expected_goal_to_date - total_written
        return f"⏰ 조금 더 속도를 내볼까요? 현재 기대 목표 대비 {remaining_to_catch_up}일 부족합니다."


# --- 데이터 저장 함수 (Cache Clear 최적화) ---
def update_data(member_name, target_date, new_content):
    gc_spreadsheet = init_connection()
    if not gc_spreadsheet:
        return
    try:
        ws = gc_spreadsheet.worksheet(member_name)
        target_date_str = target_date.strftime('%Y-%m-%d')
        ws.append_row([target_date_str, new_content], value_input_option='USER_ENTERED')
        
        # 최적화: 모든 리소스 캐시 대신, 모든 DATA 캐시만 무효화합니다. (부하 감소)
        st.cache_data.clear() 
        
        # 캐시가 지워졌으므로 load_data는 최신 데이터를 다시 로드합니다.
        df_member = load_data(member_name)
        _, _, total_written, total_goal, _, _ = calculate_challenge_status(df_member)
        motivation_msg = get_motivation_message(total_written, total_goal)
        
        # 커스텀 팝업(모달)을 띄우기 위한 세션 상태 저장
        st.session_state['show_custom_modal'] = True
        st.session_state['modal_date'] = target_date_str
        st.session_state['modal_motivation'] = motivation_msg
        
        st.session_state['writing_area_content'] = ""
        st.session_state['writing_area_key'] = time.time()
        
        time.sleep(0.5)
        st.rerun()
    except Exception as e:
        st.error(f"데이터 저장 오류: {e}")

# --- 챌린지 달성률 계산 ---
def calculate_challenge_status(df_member):
    today = date.today()
    
    df_filtered = df_member[
        (df_member['날짜'] >= CHALLENGE_START_DATE) & 
        (df_member['날짜'] <= CHALLENGE_END_DATE)
    ].copy()
    
    # 참가자가 글을 쓴 '날짜'의 목록을 추출 (하루에 여러 개를 써도 1일로 카운트)
    df_grouped = df_filtered.groupby('날짜')['글 내용'].apply(
        lambda x: (x.astype(str).str.strip() != '').any()
    ).reset_index(name='작성 여부')
    df_written_days = df_grouped[df_grouped['작성 여부'] == True]
    
    written_dates = [
        d.date() if hasattr(d, 'date') else d 
        for d in df_written_days['날짜'].tolist()
    ]
    written_dates_set = set(written_dates)
    
    weekly_status = []
    total_written_challenge = 0
    
    for week_data in CHALLENGE_WEEKS:
        week_start = week_data["start"]
        week_end = week_data["end"]
        goal = week_data["goal"]
        is_challenge = week_data["is_challenge"]
        effective_week_end = min(week_end, today)
        
        if week_start > today:
            written_count = 0
            is_current = False
            is_finished = False
        else:
            # written_count: 해당 주차 내의 유니크한 작성 일수만 카운트합니다.
            written_count = sum(1 for d in written_dates if week_start <= d <= effective_week_end)
            is_finished = week_end < today
            is_current = week_start <= today <= week_end and not is_finished
        
        if is_challenge:
            total_written_challenge += written_count
        
        achievement_rate = min(written_count / goal * 100, 100) if goal > 0 else 0
        
        weekly_status.append({
            "name": week_data["name"],
            "start": week_start,
            "end": week_end,
            "written": written_count,
            "goal": goal,
            "rate": achievement_rate,
            "is_current": is_current,
            "is_finished": is_finished,
            "is_challenge": is_challenge
        })
    
    overall_completion_rate = min(total_written_challenge / TOTAL_CHALLENGE_GOAL * 100, 100)
    
    return weekly_status, overall_completion_rate, total_written_challenge, TOTAL_CHALLENGE_GOAL, written_dates_set, written_dates

# --- 그라데이션 막대 렌더링 (디자인 개선) ---
def render_gradient_bar(label, value, max_value, is_challenge=True, is_current=False):
    percentage = min((value / max_value) * 100, 100)
    
    # 그라데이션 및 색상 설정
    if is_challenge:
        if percentage >= 100:
            # 100% 달성 시 강렬한 성공 그라데이션
            bar_gradient = "linear-gradient(90deg, #10C65A, #1BBF00)"
            bar_shadow = "0 0 10px rgba(27, 191, 0, 0.5)"
        elif is_current:
            # 현재 진행 중인 주차는 ACCENT_COLOR 사용
            bar_gradient = f"linear-gradient(90deg, {ACCENT_COLOR}, #00a4e4)"
            bar_shadow = "0 0 8px rgba(58, 187, 248, 0.4)"
        else:
            # 일반적인 진행 바 (PRIMARY_COLOR 계열)
            bar_gradient = f"linear-gradient(90deg, #FF9966, {PRIMARY_COLOR})"
            bar_shadow = "0 0 5px rgba(255, 107, 53, 0.3)"
    else:
        # 보너스 주차나 챌린지 외 기록
        bar_gradient = "linear-gradient(90deg, #C0C0C0, #808080)"
        bar_shadow = "none"

    bar_style = f"background: {bar_gradient}; box-shadow: {bar_shadow};"

    # 주차 정보 스타일 (주차별 기록 카드 내부에 사용)
    # >>>>> 여기서 st.markdown을 한 번만 사용하여 모든 내용을 출력하도록 변경 <<<<<
    html_content = f'''
        <div style="font-weight: 600; color: {TEXT_DARK}; margin-top: 15px; font-size: 1.05em; display: flex; justify-content: space-between; align-items: center;">
            <span style="font-weight: bold; color: {SECONDARY_COLOR};">{label}</span>
            <span style="font-weight: 900; color: {PRIMARY_COLOR}; font-size: 1.1em;">{value}일 / {max_value}일 ({percentage:.1f}%)</span>
        </div>
        <div style="background-color: {BACKGROUND_LIGHT}; border-radius: 6px; height: 10px; margin-bottom: 15px; overflow: hidden;">
            <div style="width: {percentage}%; {bar_style} height: 100%; transition: width 0.6s ease-out; border-radius: 6px;"></div>
        </div>
    '''
    # 한 번의 st.markdown 호출로 렌더링을 확정합니다.
    st.markdown(html_content, unsafe_allow_html=True)

# --- 달력 렌더링 및 팝업 기능 추가 (기존 유지) ---
def render_table_calendar(written_dates_set, today, df_member):
    
    # 캘린더 데이터 (날짜와 해당 날짜의 전체 기록을 JSON 문자열로 저장)
    calendar_data = {}
    for day in pd.date_range(CHALLENGE_START_DATE, CHALLENGE_END_DATE, freq='D'):
        day_date = day.date()
        df_day = df_member[df_member['날짜'] == day_date]
        contents = [str(c).strip() for c in df_day['글 내용'] if str(c).strip()]
        
        calendar_data[day_date.strftime('%Y-%m-%d')] = {
            "is_written": day_date in written_dates_set,
            "contents": contents
        }
    
    js_calendar_data = json.dumps(calendar_data)

    start_date = CHALLENGE_START_DATE
    end_date = CHALLENGE_END_DATE
    start_weekday = (start_date.weekday() + 1) % 7 # 0: 일요일, 6: 토요일
    
    # CSS 스타일 (달력도 새 디자인에 맞게 업데이트)
    css = f'''
    <style>
        .cal-container {{ max-width: 900px; margin: 20px auto 0 auto; border: 1px solid #ddd; border-radius: 12px; overflow: hidden; font-family: 'Inter', sans-serif; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08); background-color: {CARD_BG}; }}
        .cal-header {{ background-color: {SECONDARY_COLOR}; color: white; text-align: center; padding: 15px; font-size: 1.3em; font-weight: 700; font-family: 'GmarketSans', sans-serif !important; }}
        .cal-table {{ width: 100%; border-collapse: collapse; table-layout: fixed; }}
        .cal-table th {{ text-align: center; font-weight: bold; color: {PRIMARY_COLOR}; padding: 10px 0; border-bottom: 2px solid #eee; }}
        .cal-table td {{ background-color: {CARD_BG}; padding: 5px; height: 75px; border: 1px solid #eee; vertical-align: top; text-align: right; position: relative; cursor: pointer; transition: background-color 0.2s, box-shadow 0.2s; }}
        .cal-table td:hover {{ background-color: #f7f7f7; box-shadow: inset 0 0 0 2px {PRIMARY_COLOR}; }}
        
        .day-num {{ font-size: 1.1em; font-weight: bold; color: {SECONDARY_COLOR}; line-height: 1; }}
        .day-content {{ font-size: 0.7em; color: {TEXT_DARK}; padding: 2px 4px; position: absolute; bottom: 5px; left: 5px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 90%; font-weight: 500; }}

        /* 상태별 색상 */
        .complete {{ background-color: #e6ffec; border-left: 5px solid {SUCCESS_COLOR}; }}
        .missed {{ background-color: #fff0eb; border-left: 5px solid {PRIMARY_COLOR}; }}
        .encourage {{ background-color: #ebf9ff; border-left: 5px solid {ACCENT_COLOR}; }}
        .future {{ background-color: #f7f7f7; color: #aaa; cursor: default; }}
        .empty {{ background-color: transparent; border: none; cursor: default; }}
        
        /* 팝업 모달 스타일 */
        .modal-overlay {{ position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-color: rgba(0, 0, 0, 0.7); z-index: 2000; display: none; align-items: center; justify-content: center; }}
        .modal-content {{ background-color: white; padding: 30px; border-radius: 12px; max-width: 500px; width: 90%; box-shadow: 0 10px 30px rgba(0, 0, 0, 0.3); max-height: 80vh; overflow-y: auto; }}
        .modal-header {{ display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid {PRIMARY_COLOR}; padding-bottom: 10px; margin-bottom: 20px; }}
        .modal-header h3 {{ color: {SECONDARY_COLOR}; margin: 0; font-family: 'GmarketSans', sans-serif !important; }}
        .modal-close {{ background: none; border: none; font-size: 1.5em; cursor: pointer; color: {SECONDARY_COLOR}; }}
        .modal-entry {{ margin-bottom: 15px; padding: 10px; border-left: 3px solid {PRIMARY_COLOR}; background-color: #fefefe; border-radius: 4px; white-space: pre-wrap; box-shadow: 0 1px 3px rgba(0, 0, 0, 0.05); }}
        .modal-entry-num {{ font-weight: bold; color: {PRIMARY_COLOR}; margin-bottom: 5px; font-size: 0.9em;}}

        @media screen and (max-width: 600px) {{
            .cal-table td {{ height: 50px; padding: 2px; }}
            .day-num {{ font-size: 0.9em; }}
            .day-content {{ font-size: 0.6em; bottom: 2px; left: 2px; max-width: 95%; }}
        }}
    </style>
    '''
    
    html = f'''
    {css}
    <div class="cal-container">
        <div class="cal-header">기록 상세 달력</div>
        <table class="cal-table">
            <thead><tr><th>일</th><th>월</th><th>화</th><th>수</th><th>목</th><th>금</th><th>토</th></tr></thead>
            <tbody><tr>
    '''
    
    current_day = start_date
    day_counter = start_weekday
    
    for _ in range(start_weekday):
        html += '<td class="empty"></td>'
    
    while current_day <= end_date:
        if day_counter % 7 == 0 and day_counter > start_weekday:
            html += '</tr><tr>'
        
        day_str = current_day.strftime('%Y-%m-%d')
        is_written = day_str in [d.strftime('%Y-%m-%d') for d in written_dates_set]
        
        if current_day < today:
            cell_class = 'complete' if is_written else 'missed'
            content_display = '기록 완료' if is_written else '미작성'
        elif current_day == today:
            cell_class = 'complete' if is_written else 'encourage'
            content_display = '기록 완료' if is_written else '오늘의 메모'
        else:
            cell_class = 'future'
            content_display = ''
        
        click_handler = f"showModal('{day_str}');" if current_day <= today else ""

        first_content = ""
        if is_written:
            df_day = df_member[df_member['날짜'] == current_day]
            contents = [str(c).strip() for c in df_day['글 내용'] if str(c).strip()]
            if contents:
                # 첫 번째 기록의 내용을 10자까지만 표시
                first_content = f"'{contents[0][:10]}...'" if len(contents[0]) > 10 else contents[0]
                content_display = first_content


        html += f'''
            <td class="{cell_class}" data-date="{day_str}" onclick="{click_handler}">
                <div class="day-num">{current_day.day}</div>
                <div class="day-content">{content_display}</div>
            </td>
        '''
        
        current_day += timedelta(days=1)
        day_counter += 1
    
    remaining = 7 - (day_counter % 7)
    if remaining < 7:
        for _ in range(remaining):
            html += '<td class="empty"></td>'
    
    html += '</tr></tbody></table></div>'
    
    # 팝업 모달 HTML 및 JavaScript 추가
    html += '''
        <div id="calendar-modal" class="modal-overlay" onclick="closeModal(event)">
            <div class="modal-content" onclick="event.stopPropagation()">
                <div class="modal-header">
                    <h3 id="modal-date-title">기록 상세</h3>
                    <button class="modal-close" onclick="closeModal()">×</button>
                </div>
                <div id="modal-body"></div>
            </div>
        </div>
        <script>
            const CALENDAR_DATA = ''' + js_calendar_data + ''';
            const modal = document.getElementById('calendar-modal');
            const modalBody = document.getElementById('modal-body');
            const modalTitle = document.getElementById('modal-date-title');

            function showModal(dateStr) {
                const data = CALENDAR_DATA[dateStr];
                
                modalTitle.textContent = `${dateStr} 기록 상세`;
                modalBody.innerHTML = '';

                if (data && data.is_written && data.contents.length > 0) {
                    data.contents.forEach((content, index) => {
                        const entry = document.createElement('div');
                        entry.className = 'modal-entry';
                        entry.innerHTML = `<div class="modal-entry-num">📝 기록 #${index + 1}</div> ${content}`;
                        modalBody.appendChild(entry);
                    });
                } else {
                    modalBody.innerHTML = `<p style="color: #666; font-family: 'GmarketSans', sans-serif;">선택하신 날짜에는 작성된 기록이 없습니다.</p>`;
                }

                modal.style.display = 'flex';
            }

            function closeModal(event) {
                if (event && event.target.id === 'calendar-modal') {
                    modal.style.display = 'none';
                } else if (!event) {
                    modal.style.display = 'none';
                }
            }
        </script>
    '''
    
    components.html(html, height=550, scrolling=True)

# ----------------------------------------------------
# --- Streamlit 내장 기능으로 Modal 구현 (HTML/CSS 문제 해결용) ---
# ----------------------------------------------------
def show_streamlit_modal(modal_date, motivation_msg):
    # 페이지의 빈 공간(Placeholder)을 잡아, 여기에 팝업을 강제로 띄웁니다.
    modal_placeholder = st.empty()
    
    with modal_placeholder.container():
        # CSS를 사용하여 Modal 오버레이와 중앙 정렬을 구현합니다.
        # Streamlit 앱의 HTML 구조를 활용하여 z-index를 높입니다.
        st.markdown(
            """
            <style>
                /* 전체 화면을 덮는 오버레이 */
                .modal-overlay-custom {
                    position: fixed;
                    top: 0;
                    left: 0;
                    width: 100vw;
                    height: 100vh;
                    background-color: rgba(0, 0, 0, 0.6);
                    z-index: 9999999; /* 매우 높은 z-index */
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }
                /* Modal 박스 스타일 */
                .modal-content-custom {
                    background-color: #e6ffec;
                    padding: 30px;
                    border-radius: 12px;
                    max-width: 400px;
                    width: 90%;
                    border: 3px solid #1BBF00;
                    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.4);
                    text-align: center;
                    font-family: 'GmarketSans', sans-serif;
                }
                .modal-content-custom h3 {
                    color: #262361;
                    font-weight: bold;
                    margin-top: 0 !important;
                    margin-bottom: 5px !important;
                }
                .modal-button-custom {
                    background-color: #1BBF00;
                    color: white;
                    border: none;
                    padding: 10px 20px;
                    border-radius: 6px;
                    margin-top: 20px;
                    cursor: pointer;
                    font-size: 1.1em;
                    font-family: 'GmarketSans', sans-serif;
                }
            </style>
            """,
            unsafe_allow_html=True
        )

        with st.form("success_modal_form", clear_on_submit=False):
            st.markdown(
                f"""
                <div class="modal-overlay-custom">
                    <div class="modal-content-custom">
                        <div style="font-size: 2.8em; margin-bottom: 10px;">🏆</div>
                        <h3 style="font-size: 1.6em;">기록 저장 완료!</h3>
                        <div style="font-size: 1.1em; color: #333; margin-bottom: 15px;">"{modal_date}"에 새로운 글을 기록했습니다.</div>
                        <div style="font-size: 1.2em; color: #262361; line-height: 1.4; font-weight: 700;">{motivation_msg}</div>
                        <br>
                        </div>
                </div>
                """,
                unsafe_allow_html=True
            )
            
            # Modal을 닫기 위한 버튼 (Form submit 시 Modal 제거)
            if st.form_submit_button("닫기", type="primary"):
                modal_placeholder.empty()
                st.session_state['show_custom_modal'] = False
                st.rerun() # Modal 제거 후 페이지를 새로고침하여 Modal 상태를 확실히 지웁니다.
            
    # Modal을 3초 후 자동으로 제거하는 로직 추가
    time.sleep(2)
    modal_placeholder.empty()
    st.session_state['show_custom_modal'] = False


# --- CSS 주입 (기존 유지) ---
def inject_custom_css():
    st.markdown(f'''
        <style>
            /* GmarketSans 폰트 로드 */
            @font-face {{
                font-family: 'GmarketSans';
                src: url('https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_2001@1.1/GmarketSansMedium.woff') format('woff');
                font-weight: normal;
                font-style: normal;
            }}
            
            /* GmarketSans Bold 버전 */
            @font-face {{
                font-family: 'GmarketSans';
                src: url('https://cdn.jsdelivr.net/gh/projectnoonnu/noonfonts_2001@1.1/GmarketSansBold.woff') format('woff');
                font-weight: bold;
                font-style: normal;
            }}
            
            /* 전체 페이지 스타일 */
            html, body, [data-testid="stApp"] {{ font-family: 'GmarketSans', sans-serif; background-color: {BACKGROUND_LIGHT}; }}
            
            /* 최상단 불필요한 여백/빈 공간 제거 */
            .main .block-container {{ padding-top: 1.5rem; padding-bottom: 2rem; max-width: 1200px; }}
            
            /* Heading 스타일 */
            h1, h2, h3, h4, [data-testid="stHeader"] {{ 
                font-family: 'GmarketSans', sans-serif !important; 
                color: {SECONDARY_COLOR}; 
                margin-top: 0em !important; 
                margin-bottom: 0.5em !important; 
            }}
            h1 {{ font-weight: bold; font-size: 2.8em; }}
            h2 {{ font-weight: bold; font-size: 2.2em; }}
            h3 {{ font-weight: bold; font-size: 1.8em; margin-bottom: 15px !important; }}
            
            /* 일반 버튼 스타일 (코랄 오렌지, 그림자, 트렌디) */
            div.stButton > button, 
            div.stDownloadButton > button {{
                background-color: {PRIMARY_COLOR}; color: white; border-radius: 10px;
                border: none; padding: 0.7rem 1.4rem; font-weight: bold;
                font-family: 'GmarketSans', sans-serif;
                box-shadow: 0 6px 15px rgba(255, 107, 53, 0.4); /* 밝은 그림자 */
                transition: all 0.2s;
                letter-spacing: 1px;
            }}
            div.stButton > button:hover,
            div.stDownloadButton > button:hover {{ 
                background-color: #E05A2D; 
                transform: translateY(-2px);
                box-shadow: 0 8px 20px rgba(255, 107, 53, 0.5);
            }}
            
            /* 텍스트 영역 및 인풋 박스 스타일 (흰색 카드 느낌) */
            .stTextArea, .stTextInput, .stDateInput > div:first-child {{
                border-radius: 10px;
                border: 1px solid #ddd;
                padding: 10px;
                background-color: {CARD_BG};
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.05);
                font-family: 'Inter', sans-serif;
            }}
            .stTextArea label, .stTextInput label, .stDateInput label {{
                font-weight: bold; color: {SECONDARY_COLOR};
            }}
            
            /* 알림/정보 박스 */
            .stAlert {{ border-radius: 8px; font-family: 'GmarketSans', sans-serif; }}
            .stInfo {{ background-color: #ebf9ff !important; border-left: 5px solid {ACCENT_COLOR} !important; color: {TEXT_DARK} !important;}}
            .stSuccess {{ background-color: {SUCCESS_BG} !important; border-left: 5px solid {SUCCESS_COLOR} !important; color: {TEXT_DARK} !important;}}
            .stWarning {{ background-color: #fff0eb !important; border-left: 5px solid {PRIMARY_COLOR} !important; color: {TEXT_DARK} !important;}}

            /* 🌟 새로운 카드 스타일 - Streamlit 컨테이너를 직접 타겟팅 */
            [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] {{
                background-color: {CARD_BG};
                border-radius: 16px;
                padding: 30px;
                margin-bottom: 25px;
                box-shadow: 0 10px 30px rgba(0, 0, 0, 0.1);
                border: 1px solid #f0f0f0;
                transition: box-shadow 0.3s;
            }}
            
            [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"] > [data-testid="stVerticalBlock"]:hover {{
                box-shadow: 0 15px 40px rgba(0, 0, 0, 0.15);
            }}

            /* 헤더의 홈으로 돌아가기 버튼 */
            #go_home_btn {{
                background-color: #A0A0A0;
                box-shadow: none;
            }}
            #go_home_btn:hover {{
                background-color: #808080;
                transform: none;
                box-shadow: none;
            }}
            
            /* 주최자 버튼 스타일 */
            .admin-secret-button > button {{
                background-color: #E0E0E0 !important; 
                color: {SECONDARY_COLOR} !important; 
                box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1) !important; 
                border: 1px solid #C0C0C0; 
                margin-top: 20px;
            }}
            
            /* 기타 여백 제거 및 통일 */
            div[data-testid="stVerticalBlock"] > div:empty {{
                padding-top: 0px !important;
                padding-bottom: 0px !important;
                min-height: 0px !important;
                height: 0px !important;
                visibility: hidden;
            }}
            
            .stMarkdown > p {{ 
                color: {TEXT_DARK}; 
                line-height: 1.6;
            }}

            /* 달성률 강조 텍스트 */
            .highlight-text {{
                font-size: 1.2em;
                font-weight: 900;
                color: {SECONDARY_COLOR};
                text-align: center;
                margin-top: 10px;
            }}
            
            /* 참가자 헤더 타이틀 폰트 */
            .participant-header {{
                font-family: 'GmarketSans', sans-serif !important;
                font-size: 2.2em;
                font-weight: 900;
                color: {SECONDARY_COLOR};
                margin-bottom: 5px;
            }}
        </style>
    ''', unsafe_allow_html=True)

# --- 메인 페이지 (랜딩 페이지) ---
def main_page():
    
    st.markdown('<div class="center-container">', unsafe_allow_html=True)
    
    # 헤더 영역
    st.markdown(f'''
        <div style="padding-top: 10px; padding-bottom: 20px; text-align: center;">
            <h1 style="font-weight: 900; font-size: 3em; color:{SECONDARY_COLOR}; margin-bottom: 0.1rem; letter-spacing: -1px;">
                <span style="color:{PRIMARY_COLOR};">📖</span> 책 한권 꼭 만들기 모임
            </h1>
            <h2 style="font-weight: 700; font-size: 2.2em; color:{TEXT_DARK}; margin-top: 0; letter-spacing: -0.5px;">
                쓰는 습관 만드는 메모 챌린지
            </h2>
        </div>
    ''', unsafe_allow_html=True)
    
    # 카드 1: 챌린지 개요
    with st.container():
        st.markdown(f"### <span style='color:{PRIMARY_COLOR};'>✨ 챌린지 소개</span>", unsafe_allow_html=True)
        st.markdown(f"""
            <p style='font-size: 1.1em;'>
                모두 작가가 되는 목표를 꼭 달성하기 위해 
                <span style='font-weight: bold; color:{PRIMARY_COLOR};'>메모 챌린지</span>를 시작합니다!
            </p>
        """, unsafe_allow_html=True)
        
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"🗓️ 본 챌린지 기간: {CHALLENGE_WEEKS[1]['start'].strftime('%y.%m.%d')} ~ {CHALLENGE_END_DATE.strftime('%y.%m.%d')} (총 4주)\n*(보너스 주차: 12/3 ~ 12/7)*")
        with col2:
            st.success(f"🎯 규칙: 주 {WEEKLY_GOAL}일 작성\n🏆 최종 목표: 4주간 총 {TOTAL_CHALLENGE_GOAL}일 이상 메모!")

    # 카드 2: 사용 방법 & 시작
    with st.container():
        st.markdown(f"### <span style='color:{SECONDARY_COLOR};'>🚀 챌린지 시작하기</span>", unsafe_allow_html=True)
        st.markdown('''
        <ol style="font-size: 1.05em; line-height: 1.8; color: #444;">
            <li>아래에서 이름을 선택하고 '챌린지 시작하기' 버튼을 누르세요.</li>
            <li>글을 쓰고 '글 저장하기'를 누르면 기록이 저장됩니다!</li>
            <li>하루에 여러 번 쓰셔도 모두 기록되지만, 달성 현황은 일일 1일만 카운트됩니다.</li>
            <li>매일 23시에 자동으로 하루 기록이 마감됩니다. (그 이후 작성 시 다음 날짜로 카운트)</li>
        </ol>
        ''', unsafe_allow_html=True)
        
        st.markdown("#### 참가자 페이지로 이동")
        selected = st.selectbox("당신의 이름을 선택하세요", ["-- 선택 --"] + MEMBERS, key="jump_select")
        
        if st.button("🚀 챌린지 시작하기", type="primary", use_container_width=True):
            if selected == "-- 선택 --":
                st.warning("먼저 이름을 선택해 주세요!")
            else:
                st.session_state.view = 'challenge'
                st.session_state.selected_member = selected
                st.rerun()

    # 주최자 점검 모드 버튼
    st.markdown('<div style="text-align: center; margin-top: 30px; border-top: 1px dashed #CCC; padding-top: 20px;">', unsafe_allow_html=True)
    if st.button("🔑 관리자 점검 모드", key="admin_jump_btn_footer"):
        st.session_state.view = 'admin_login'
        st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)

    # 저작권 문구 추가
    st.markdown('<div class="footer-copyright" style="text-align: center; color: #999; font-size: 0.85em; margin-top: 50px;">Copyright © Kungis All rights reserved.</div>', unsafe_allow_html=True)
            
    st.markdown('</div>', unsafe_allow_html=True) # 중앙 정렬 컨테이너 끝

# --- 참가자 뷰 ---
def challenge_participant_view(selected_member):
    # 현재 날짜를 정확히 가져옵니다.
    today = date.today()
    
    col_header, col_home_btn = st.columns([8, 2])
    with col_header:
        st.markdown(f'''
            <div class="participant-header">
                ✨ {selected_member} 님의 성장 기록
            </div>
        ''', unsafe_allow_html=True)

    with col_home_btn:
        st.markdown("<div style='height: 1.5rem;'></div>", unsafe_allow_html=True)
        if st.button("🏠 홈으로 돌아가기", key="go_home_btn", use_container_width=True):
            st.session_state.view = 'home'
            st.rerun()

    df_member = load_data(selected_member)
    
    if 'writing_area_content' not in st.session_state:
        st.session_state['writing_area_content'] = ""
    if 'writing_area_key' not in st.session_state:
        st.session_state['writing_area_key'] = 'initial_key'
        
    
    # ----------------------------------------------------
    # Modal 렌더링 위치: 모든 콘텐츠 렌더링 전에 Modal을 띄웁니다.
    # st.empty()를 사용하여 Modal이 페이지 콘텐츠 흐름을 방해하지 않고
    # 위에 덮이도록 구현합니다.
    if st.session_state.get('show_custom_modal', False):
        show_streamlit_modal(
            st.session_state.get('modal_date', ''),
            st.session_state.get('modal_motivation', '')
        )
    # ----------------------------------------------------


    weekly_status, overall_rate, total_written, total_goal, written_dates_set, _ = calculate_challenge_status(df_member)
    
    st.markdown("<div style='margin-bottom: 25px;'></div>", unsafe_allow_html=True)

    # 2. 챌린지 달성 현황 섹션 (카드 1)
    with st.container():
        st.markdown(f"### <span style='color:{SECONDARY_COLOR};'>📊 챌린지 달성 현황 (주 목표: {WEEKLY_GOAL}일)</span>", unsafe_allow_html=True)
        
        # 전체 달성률을 중앙에 크게 표시하는 섹션
        col_total_status, col_total_progress = st.columns([1, 2])
        
        with col_total_status:
            st.markdown(f'''
                <div style="text-align: center; margin: 10px 0 20px 0; padding: 10px; border: 2px solid {PRIMARY_COLOR}; border-radius: 12px; background-color: #fff8f5;">
                    <div style="font-size: 1.2em; color: {SECONDARY_COLOR}; font-weight: 700;">총 목표 달성률</div>
                    <div style="font-size: 3em; font-weight: 900; color: {PRIMARY_COLOR}; line-height: 1.2; margin: 5px 0;">
                        {overall_rate:.1f}%
                    </div>
                </div>
            ''', unsafe_allow_html=True)

        with col_total_progress:
            # 총 목표 달성 프로그레스 바를 호출하여 컬럼 내에 확실하게 렌더링
            render_gradient_bar(f"총 목표 달성 (본 챌린지 4주, 목표 {total_goal}일)", total_written, total_goal)
            st.write("")

            # 동기 부여 메시지 표시
            motivation_msg = get_motivation_message(total_written, total_goal)
            st.markdown(f'<p class="highlight-text" style="text-align: left; color: {ACCENT_COLOR}; font-size: 1.1em; margin-top: -5px; margin-bottom: 0;">{motivation_msg}</p>', unsafe_allow_html=True)

        st.markdown("#### 🗓️ 주차별 기록 상세")
        for status in weekly_status:
            week_label = f"[{status['name']}] {status['start'].strftime('%m/%d')} ~ {status['end'].strftime('%m/%d')}"
            
            if status['is_challenge']:
                # 챌린지 주차는 역동적인 프로그레스 바 사용
                is_current = status['is_current']
                if status['start'] > today:
                    week_label += " (예정)"
                elif is_current:
                    week_label = f"**{week_label} (현재 주차)**"
                
                render_gradient_bar(week_label, status['written'], status['goal'], is_current=is_current)
            else:
                # 보너스 주차는 단순 정보 블록으로 처리
                st.markdown(f'''
                    <div style="font-weight: 500; color: {TEXT_DARK}; margin: 10px 0 15px 0; padding: 10px; border-left: 5px solid {ACCENT_COLOR}; background-color: #f7f7f7; border-radius: 6px; box-shadow: inset 0 0 5px rgba(58, 187, 248, 0.1);">
                        {week_label}: 기록 {status['written']}일 (챌린지 적응 기록)
                    </div>
                ''', unsafe_allow_html=True)
    
    # 글쓰기 영역 (카드 2 - CTA 강조)
    with st.container():
        st.markdown(f"### <span style='color:{PRIMARY_COLOR};'>✏️ 오늘의 기록 남기기</span>", unsafe_allow_html=True)
        
        selected_date = st.date_input("글을 작성할 날짜를 선택하세요", value=date.today(), max_value=date.today())
        
        st.info(f"선택 날짜: {selected_date.strftime('%Y년 %m월 %d일')}\n\n⚠️ 글을 저장할 때마다 새로운 행에 기록이 추가되며, 챌린지 달성 현황은 일일 1일만 카운트 됩니다. 글 저장 버튼을 꼭 눌러주세요!")
        
        new_content = st.text_area("오늘의 글을 여기에 작성하세요. (메모, 아이디어, 초안 등 자유롭게)",
                                   value=st.session_state['writing_area_content'],
                                   height=350,
                                   key=st.session_state['writing_area_key'])
        
        if st.button("✅ 글 저장하기", use_container_width=True, type="primary"):
            if new_content.strip() == "":
                st.warning("글 내용을 입력해 주세요!")
            else:
                update_data(selected_member, selected_date, new_content)

    # 달력 시각화 (카드 3)
    with st.container():
        st.markdown(f"### <span style='color:{SECONDARY_COLOR};'>📅 글쓰기 기록 달력</span>", unsafe_allow_html=True)
        render_table_calendar(written_dates_set, today, df_member)

    # 메모 아카이브 검색 기능 (카드 4)
    with st.container():
        st.markdown(f"### <span style='color:{ACCENT_COLOR};'>🔎 {selected_member} 님의 메모 아카이브 검색</span>", unsafe_allow_html=True)
        
        search_query = st.text_input("찾고 싶은 키워드를 입력하세요 (예: '아이디어', '1장', '트레바리')")
        
        if search_query:
            df_search = df_member[
                df_member['글 내용'].astype(str).str.contains(search_query, case=False)
            ].copy()
            
            if not df_search.empty:
                df_search = df_search.rename(columns={'날짜': '기록일', '글 내용': '내용'})
                # 인덱스를 숨기고 깔끔하게 출력
                st.dataframe(df_search.sort_values(by='기록일', ascending=False)[['기록일', '내용']].reset_index(drop=True), use_container_width=True, height=300)
                st.success(f"'{search_query}'(으)로 총 {len(df_search)}개의 기록을 찾았습니다.")
            else:
                st.warning(f"'{search_query}'와 일치하는 기록이 없습니다.")
        else:
            st.info("키워드를 입력하시면 과거 메모 기록을 찾아볼 수 있습니다.")


# --- 관리자 로그인 뷰 ---
def admin_login_view():
    st.header("🔑 주최자 점검 모드")
    st.warning("이 모드는 챌린지 운영진만 접근할 수 있습니다.")
    st.markdown(f"접속일: {date.today().strftime('%Y년 %m월 %d일')}")
    
    today_password = date.today().strftime('%Y%m%d') + TODAY_PASSWORD_SUFFIX
    
    with st.container():
        input_pwd = st.text_input(f"관리자 비밀번호 (오늘의 조합:{date.today().strftime('%Y%m%d')} + ****)", type="password", key="admin_pwd")
        
        col1, col2 = st.columns([1, 4])
        with col1:
            if st.button("로그인", type="primary", use_container_width=True):
                if input_pwd == today_password:
                    st.session_state.view = 'admin_dashboard'
                    st.rerun()
                else:
                    st.error("비밀번호가 일치하지 않습니다. 오늘 날짜와 비밀번호를 조합하여 입력해 주세요.")
        with col2:
            if st.button("🏠 홈으로 돌아가기", key="admin_login_home_btn"):
                st.session_state.view = 'home'
                st.rerun()

# --- 관리자 대시보드 뷰 ---
def challenge_admin_view():
    st.header("👑 전체 챌린지 점검 대시보드")
    today = date.today()
    
    if st.button("🏠 홈으로 돌아가기", key="admin_dash_home_btn"):
        st.session_state.view = 'home'
        st.rerun()

    st.markdown("---")
    
    all_status = []
    
    gc_spreadsheet = init_connection() 

    with st.spinner('전체 참가자 데이터 로딩 중 및 상태 계산 중...'):
        for member in MEMBERS:
            df = load_data(member)
            weekly_status, overall_rate, total_written, total_goal, _, _ = calculate_challenge_status(df) 
            
            today_group = df[df['날짜'] == today]
            is_written_today = (today_group['글 내용'].astype(str).str.strip() != '').any()
            
            weekly_rates = {w['name']: w['written'] for w in weekly_status if w['is_challenge']} # 달성률 대신 일수로 변경 (표 보기 쉽게)
            
            status_entry = {
                "참가자": member,
                "오늘 작성": "✅" if is_written_today else "❌",
                f"총 목표({total_goal}일)": total_written,
                "달성률": f"{overall_rate:.1f}%",
                **weekly_rates
            }
            all_status.append(status_entry)
    
    df_status = pd.DataFrame(all_status)
    
    # 카드 1: 오늘 및 총 달성 현황
    with st.container():
        st.subheader(f"📅 오늘({today.strftime('%Y-%m-%d')}) 작성 현황")
        st.dataframe(df_status[["참가자", "오늘 작성", f"총 목표({total_goal}일)", "달성률"]].set_index("참가자").sort_values(by="오늘 작성", ascending=False), use_container_width=True)

    # 카드 2: 주차별 랭킹
    with st.container():
        st.subheader("🏆 주차별 달성 현황 (누적 일수)")
        
        week_cols_for_sort = [w['name'] for w in CHALLENGE_WEEKS if w['is_challenge']]
        week_select = st.selectbox("점검할 주차를 선택하세요", ["총 목표 달성률"] + week_cols_for_sort)
        
        if week_select == "총 목표 달성률":
            rank_df = df_status.sort_values(by="달성률", ascending=False)
            st.dataframe(rank_df[["참가자", "달성률", f"총 목표({total_goal}일)"]].set_index("참가자"), use_container_width=True)
        else:
            rank_df = df_status.sort_values(by=week_select, ascending=False)
            st.dataframe(rank_df[["참가자", week_select, f"총 목표({total_goal}일)"]].set_index("참가자"), use_container_width=True)

    # 카드 3: 개인별 상세 기록
    with st.container():
        st.subheader("개인별 상세 기록")
        detail_member = st.selectbox("상세 점검할 참가자", ["-- 선택 --"] + MEMBERS)
        
        if detail_member != "-- 선택 --":
            df_detail = load_data(detail_member)
            st.markdown(f"### {detail_member} 님의 전체 기록")
            st.dataframe(df_detail.sort_values(by='날짜', ascending=False), use_container_width=True, height=400)

# --- 메인 실행 ---
st.set_page_config(
    layout="wide", 
    page_title="1일 1글쓰기 챌린지", 
    initial_sidebar_state="collapsed" 
)

inject_custom_css()

if 'view' not in st.session_state:
    st.session_state.view = 'home'
if 'selected_member' not in st.session_state:
    st.session_state.selected_member = MEMBERS[0]
if 'writing_area_key' not in st.session_state:
    st.session_state['writing_area_key'] = 'initial_key'
if 'show_custom_modal' not in st.session_state:
    st.session_state['show_custom_modal'] = False
if 'modal_date' not in st.session_state:
    st.session_state['modal_date'] = ''
if 'modal_motivation' not in st.session_state:
    st.session_state['modal_motivation'] = ''


if st.session_state.view == 'home':
    main_page()
elif st.session_state.view == 'admin_login':
    admin_login_view()
elif st.session_state.view == 'admin_dashboard':
    if not init_connection(): # 연결 확인
        st.warning("Google Sheets 연결 오류를 먼저 해결해 주세요.")
    else:
        challenge_admin_view()
elif st.session_state.view == 'challenge':
    if not init_connection(): # 연결 확인
        st.warning("Google Sheets 연결 오류를 먼저 해결해 주세요.")
    elif st.session_state.selected_member in MEMBERS:
        challenge_participant_view(st.session_state.selected_member)
    else:
        st.session_state.view = 'home'
        st.rerun()