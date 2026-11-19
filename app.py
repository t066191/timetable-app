import streamlit as st
import pulp
import pandas as pd
import openpyxl
import io

st.set_page_config(page_title="小学校 時間割自動作成アプリ", layout="wide")
st.title("🏫 小学校 時間割自動作成アプリ")
st.write("左側のメニューで条件を設定して「時間割を作成する」ボタンを押すと、ルールをすべて満たした時間割を自動生成します。")

# ==========================================
# サイドバー（画面左側の条件設定パネル）
# ==========================================
st.sidebar.header("⚙️ 追加ルールの設定")

music_ng = st.sidebar.multiselect("音楽専科の休み（NG曜日）", ['月', '火', '水', '木', '金'], default=[])
science_ng = st.sidebar.multiselect("理科専科の休み（NG曜日）", ['月', '火', '水', '木', '金'], default=[])
art_ng = st.sidebar.multiselect("図工専科の休み（NG曜日）", ['月', '火', '水', '木', '金'], default=[])
home_ng = st.sidebar.multiselect("家庭科専科の休み（NG曜日）", ['月', '火', '水', '木', '金'], default=[])

max_pe = st.sidebar.slider("同じ時間に体育ができる最大クラス数（体育館・運動場）", 1, 5, 2)
no_same_subj_day = st.sidebar.checkbox("1日に同じ教科を2回入れない（国語・算数も含む）", value=True)
katei_renzoku = st.sidebar.checkbox("5・6年の家庭科（週2時間）を2時間連続にする", value=False)

# ==========================================
# 基本データ定義
# ==========================================
CLASSES = [
    {'id': '1A', 'name': '1年A組', 'grade': 1}, {'id': '1B', 'name': '1年B組', 'grade': 1},
    {'id': '2A', 'name': '2年A組', 'grade': 2}, {'id': '2B', 'name': '2年B組', 'grade': 2}, {'id': '2C', 'name': '2年C組', 'grade': 2},
    {'id': '3A', 'name': '3年A組', 'grade': 3}, {'id': '3B', 'name': '3年B組', 'grade': 3},
    {'id': '4A', 'name': '4年A組', 'grade': 4}, {'id': '4B', 'name': '4年B組', 'grade': 4}, {'id': '4C', 'name': '4年C組', 'grade': 4},
    {'id': '5A', 'name': '5年A組', 'grade': 5}, {'id': '5B', 'name': '5年B組', 'grade': 5},
    {'id': '6A', 'name': '6年A組', 'grade': 6}, {'id': '6B', 'name': '6年B組', 'grade': 6},
]

DAYS = ['月', '火', '水', '木', '金']
SLOTS_PER_DAY = {1:, 2:, 3:, 4:, 5:, 6:}

CURRICULUM = {
    1: {'国語':7, '算数':4, '生活':3, '体育':3, '音楽':2, '図工':2, '道徳':1, '学活':1, '図書':1, '書写':1},
    2: {'国語':7, '算数':4, '生活':3, '体育':3, '音楽':2, '図工':2, '道徳':1, '学活':1, '図書':1, '書写':1, '空き':1},
    3: {'国語':5, '算数':5, '社会':2, '理科':2, '体育':3, '音楽':2, '図工':2, '英語':1, '総合':2, '道徳':1, '学活':1, '図書':1, '書写':1},
    4: {'国語':5, '算数':5, '社会':2, '理科':3, '体育':3, '音楽':2, '図工':2, '英語':1, '総合':1, '道徳':1, '学活':1, 'クラブ':1, '山手タイム':1, '図書':1, '書写':1},
    5: {'国語':3, '算数':5, '社会':3, '理科':3, '体育':2, '音楽':2, '図工':2, '家庭':2, '英語':2, '道徳':1, '学活':1, 'クラブ':1, '山手タイム':1, '図書':1, '書写':1},
    6: {'国語':3, '算数':5, '社会':3, '理科':3, '体育':2, '音楽':2, '図工':2, '家庭':2, '英語':2, '道徳':1, '学活':1, 'クラブ':1, '山手タイム':1, '図書':1, '書写':1},
}

def is_senka(grade, subj):
    if subj == '英語' and grade >= 3: return '英語'
    if subj == '音楽' and grade >= 3: return '音楽'
    if subj == '理科' and grade >= 3: return '理科'
    if subj == '図工' and grade >= 3: return '図工'
    if subj == '家庭' and grade >= 5: return '家庭'
    return None

TOKUSHI_A = ['1A', '2A', '4A', '6A']
TOKUSHI_B = ['2B', '3B', '5B', '6B']
TOKUSHI_SUBJ = ['国語', '算数', '社会']

if st.button("🚀 時間割を自動作成する", type="primary"):
    with st.spinner("AIがパズルを計算中です...（約5〜10秒）"):
        prob = pulp.LpProblem("Timetable", pulp.LpMinimize)
        x = {}
        for c in CLASSES:
            cid, g = c['id'], c['grade']
            for d in range(5):
                for p in range(SLOTS_PER_DAY[g][d]):
                    for s in CURRICULUM[g].keys():
                        x[(cid, d, p, s)] = pulp.LpVariable(f"x_{cid}_{d}_{p}_{s}", cat='Binary')

        # 1コマ1教科
        for c in CLASSES:
            cid, g = c['id'], c['grade']
            for d in range(5):
                for p in range(SLOTS_PER_DAY[g][d]):
                    prob += pulp.lpSum([x[(cid, d, p, s)] for s in CURRICULUM[g].keys()]) == 1

        # 週時数
        for c in CLASSES:
            cid, g = c['id'], c['grade']
            for s, req in CURRICULUM[g].items():
                prob += pulp.lpSum([x[(cid, d, p, s)] for d in range(5) for p in range(SLOTS_PER_DAY[g][d])]) == req

        # 火曜6限クラブ
        for c in CLASSES:
            if c['grade'] >= 4:
                prob += x[(c['id'], 1, 5, 'クラブ')] == 1

        # 5・6年英語（水・木に2時間）
        for cid in ['5A', '5B', '6A', '6B']:
            prob += pulp.lpSum([x[(cid, d, p, '英語')] for d in for p in range(6)]) == 2

        # 専科重複禁止
        for senka_type in ['英語', '音楽', '理科', '図工', '家庭']:
            for d in range(5):
                for p in range(6):
                    vars_in_slot = [x[(c['id'], d, p, senka_type)] for c in CLASSES if p < SLOTS_PER_DAY[c['grade']][d] and senka_type in CURRICULUM[c['grade']] and is_senka(c['grade'], senka_type)]
                    if vars_in_slot:
                        prob += pulp.lpSum(vars_in_slot) <= 1

        # 専科NG曜日
        ng_map = {'音楽': music_ng, '理科': science_ng, '図工': art_ng, '家庭': home_ng}
        for subj, ng_days in ng_map.items():
            for d_name in ng_days:
                d_idx = DAYS.index(d_name)
                for c in CLASSES:
                    if is_senka(c['grade'], subj):
                        for p in range(SLOTS_PER_DAY[c['grade']][d_idx]):
                            prob += x[(c['id'], d_idx, p, subj)] == 0

        # 特支3重なり禁止
        for group in [TOKUSHI_A, TOKUSHI_B]:
            for d in range(5):
                for p in range(6):
                    vars_t = [x[(cid, d, p, s)] for cid in group for c in [next(cl for cl in CLASSES if cl['id']==cid)] if p < SLOTS_PER_DAY[c['grade']][d] for s in TOKUSHI_SUBJ if s in CURRICULUM[c['grade']]]
                    if vars_t:
                        prob += pulp.lpSum(vars_t) <= 2

        # 体育同時クラス数制限
        for d in range(5):
            for p in range(6):
                vars_pe = [x[(c['id'], d, p, '体育')] for c in CLASSES if p < SLOTS_PER_DAY[c['grade']][d]]
                prob += pulp.lpSum(vars_pe) <= max_pe

        # 家庭科2時間連続
        if katei_renzoku:
            for cid in ['5A', '5B', '6A', '6B']:
                for d in range(5):
                    prob += x[(cid, d, 0, '家庭')] <= x[(cid, d, 1, '家庭')]
                    prob += x[(cid, d, 5, '家庭')] <= x[(cid, d, 4, '家庭')]
                    for p in range(1, 5):
                        prob += x[(cid, d, p, '家庭')] <= x[(cid, d, p-1, '家庭')] + x[(cid, d, p+1, '家庭')]

        # 1日同教科制限
        penalties = []
        for c in CLASSES:
            cid, g = c['id'], c['grade']
            for d in range(5):
                for s in CURRICULUM[g].keys():
                    if s == '空き' or (s == '家庭' and katei_renzoku): continue
                    if no_same_subj_day and not (g <= 2 and s == '国語'):
                        prob += pulp.lpSum([x[(cid, d, p, s)] for p in range(SLOTS_PER_DAY[g][d])]) <= 1
                    else:
                        over = pulp.LpVariable(f"over_{cid}_{d}_{s}", lowBound=0)
                        prob += pulp.lpSum([x[(cid, d, p, s)] for p in range(SLOTS_PER_DAY[g][d])]) - 1 <= over
                        penalties.append(over)

        prob += pulp.lpSum(penalties)
        status = prob.solve(pulp.PULP_CBC_CMD(msg=0))

        if pulp.LpStatus[status] != 'Optimal':
            st.error("⚠️ 条件が厳しすぎて時間割を作れませんでした。左側の条件を少し緩めて再度お試しください。")
        else:
            st.success("✅ 完璧な時間割が完成しました！")
            rows = []
            for d in range(5):
                for p in range(6):
                    r = {'曜日': DAYS[d], '時限': f"{p+1}限"}
                    for c in CLASSES:
                        cid, g = c['id'], c['grade']
                        if p >= SLOTS_PER_DAY[g][d]:
                            r[c['name']] = "―"
                        else:
                            r[c['name']] = next(s for s in CURRICULUM[g].keys() if pulp.value(x[(cid, d, p, s)]) == 1)
                    rows.append(r)
            df = pd.DataFrame(rows)
            st.dataframe(df, use_container_width=True, height=600)

            # Excel出力
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='全校時間割')
            st.download_button(
                label="📥 完成した時間割をExcelでダウンロード",
                data=output.getvalue(),
                file_name="小学校_全校時間割.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
