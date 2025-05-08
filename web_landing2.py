import streamlit as st
import pandas as pd
import datetime
import pyodbc

# === ACCESS DATABASE SETUP ===
DB_PATH = r"work_log.accdb"
CONN_STR = (
    r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};'
    rf'DBQ={DB_PATH};'
)
conn = pyodbc.connect(CONN_STR, autocommit=True)
cursor = conn.cursor()

# Ensure Notes column exists
try:
    cursor.execute("SELECT Notes FROM logs")
except:
    try:
        cursor.execute("ALTER TABLE logs ADD COLUMN [Notes] MEMO")
        conn.commit()
    except:
        pass

# Ensure TD_event column exists
try:
    cursor.execute("SELECT TD_event FROM logs")
except:
    try:
        cursor.execute("ALTER TABLE logs ADD COLUMN TD_event TEXT")
        conn.commit()
    except:
        pass

# === UI STYLING ===
st.markdown("""
<style>
div.stButton > button { white-space: nowrap; min-width: 100px; }
.button-inline > div { display: inline-block; margin-right: 10px; }
.stButton > button { min-width: 90px; white-space: nowrap; }
</style>
""", unsafe_allow_html=True)

# === Load External Files ===
design_sheets = pd.read_excel('Design Group Tracking.xlsx', sheet_name=None)
design_df = design_sheets['Project Work']
projects_df = pd.read_csv('ProjectswithTEWorktypesEventDateSort-LongRange.csv')

st.title("🛠️ Design Group Task Tracker")

# === Work Type Selection ===
work_type = st.radio("Select Work Type:", ["Project Work", "Non-Project Work"])

if work_type == "Project Work":
    # === User Selection ===
    employee_names = sorted(design_df['Name'].dropna().unique())
    selected_name = st.selectbox("Select your name:", employee_names)

    # === TD Event Selection ===
    td_event_options = sorted(projects_df['Task_Code'].str.extract(r'TD(\d+)')[0].dropna().unique().astype(int))
    selected_td_number = st.selectbox("Select your TD Event Number:", td_event_options)
    selected_td_code = f"TD{int(selected_td_number):02}"

    # === Filter projects based on selected TD event
    matched_tasks = projects_df[projects_df['Task_Code'] == selected_td_code]

    if matched_tasks.empty:
        st.warning("No tasks found for the selected TD event.")
        if st.checkbox("Manually select from all available projects"):
            matched_tasks = projects_df.copy()
    else:
        st.subheader("📋 Tasks for Selected TD Event")
        st.dataframe(matched_tasks)

    # === View User Logs ===
    st.subheader("🗕️ Your Logged Hours")
    cursor.execute("SELECT * FROM logs WHERE [Name] = ? ORDER BY [Date]", (selected_name,))
    rows = cursor.fetchall()
    columns = [col[0] for col in cursor.description]
    user_log_df = pd.DataFrame.from_records(rows, columns=columns)

    if user_log_df.empty:
        st.info("No hours logged yet.")
    else:
        for i, row in user_log_df.iterrows():
            with st.container():
                col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 2, 2, 2, 3, 2, 2])
                edit_key = f"edit_pending_{row['id']}"
                delete_key = f"delete_pending_{row['id']}"

                if st.session_state.get(edit_key, False):
                    with col1:
                        new_date = st.date_input(f"Edit Date_{i}", pd.to_datetime(row["Date"]), key=f"date_{i}")
                    with col2:
                        new_hours = st.number_input(f"Edit Hours_{i}", value=row["Hours"], step=0.5, key=f"hours_{i}")
                    with col3:
                        st.markdown(f"`{row['ProjectCode']}`")
                    with col4:
                        st.markdown(f"`{row['PhaseNumber']}`")
                    with col5:
                        new_notes = st.text_area("Edit Notes", value=row.get("Notes", ""), key=f"notes_{i}")
                        confirm = st.checkbox("✔ Confirm update", key=f"confirm_edit_{i}")
                    with col6:
                        td_display = row.get("TD_event", "-")
                        st.markdown(f"`{td_display}`")
                    with col7:
                        if confirm:
                            save_clicked = st.button("📏 Save", key=f"save_{i}")
                            cancel_clicked = st.button("❌ Cancel", key=f"cancel_edit_{i}")
                            if save_clicked:
                                cursor.execute("""
                                    UPDATE logs
                                    SET [Date] = ?, [Hours] = ?, [Notes] = ?
                                    WHERE id = ?
                                """, (new_date, new_hours, new_notes, row["id"]))
                                conn.commit()
                                st.session_state[edit_key] = False
                                st.rerun()
                            if cancel_clicked:
                                st.session_state[edit_key] = False
                else:
                    with col1:
                        st.markdown(f"**{pd.to_datetime(row['Date']).date()}**")
                    with col2:
                        st.markdown(f"{row['Hours']} hrs")
                    with col3:
                        st.markdown(f"`{row['ProjectCode']}`")
                    with col4:
                        st.markdown(f"`{row['PhaseNumber']}`")
                    with col5:
                        notes = row.get("Notes", "")
                        short_notes = notes[:50] + "..." if notes and len(notes) > 50 else notes or "-"
                        st.markdown(f"<span title='{notes}'>{short_notes}</span>", unsafe_allow_html=True)
                    with col6:
                        td_event = row.get("TD_event", "-")
                        st.markdown(f"`{td_event}`")
                    with col7:
                        if st.button("✏️ Edit", key=f"edit_{i}"):
                            st.session_state[edit_key] = True
                        elif st.session_state.get(delete_key, False):
                            if st.button("✅ Confirm", key=f"confirm_delete_{i}"):
                                cursor.execute("DELETE FROM logs WHERE id = ?", (row["id"],))
                                conn.commit()
                                st.session_state[delete_key] = False
                                st.rerun()
                            elif st.button("❌ Cancel", key=f"cancel_delete_{i}"):
                                st.session_state[delete_key] = False
                        else:
                            if st.button("🗑️", key=f"delete_{i}"):
                                st.session_state[delete_key] = True

    # === Add New Entry ===
    st.divider()
    st.subheader("➕ Add New Hour Entry")

    if matched_tasks.empty:
        st.info("Please manually select a project code.")
        project_codes = sorted(projects_df['ProjectCode'].dropna().unique())
    else:
        project_codes = sorted(matched_tasks['ProjectCode'].dropna().unique())

    selected_project = st.selectbox("Select Project Code:", project_codes, placeholder="Choose a project...")
    filtered_phases = matched_tasks[matched_tasks["ProjectCode"] == selected_project]['PhaseNumber'].dropna().unique()
    selected_phase = st.selectbox("Select Phase Number:", sorted(filtered_phases), placeholder="Choose a phase...")
    selected_date = st.date_input("Select Date:", datetime.date.today())
    entered_hours = st.number_input("Enter Hours Worked:", min_value=0.0, step=0.5, format="%.1f")
    entered_notes = st.text_area("Optional Notes (e.g. follow-up or comments)")

    if st.button("➕ Add Entry"):
        cursor.execute("""
            INSERT INTO logs ([Name], [Date], [ProjectCode], [PhaseNumber], [Hours], [Notes], [TD_event])
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (selected_name, selected_date, selected_project, selected_phase, entered_hours, entered_notes, selected_td_code))
        conn.commit()
        st.success("✅ New entry added successfully!")
        st.rerun()

# === NON-PROJECT WORK (unchanged, continue from your existing code after this line)


else:
    # Ensure table exists and has Notes column
    try:
        cursor.execute("SELECT TOP 1 * FROM non_project_logs")
    except:
        cursor.execute("""
            CREATE TABLE non_project_logs (
                id COUNTER PRIMARY KEY,
                Name TEXT(255),
                Date DATETIME,
                Task TEXT(255),
                Customer TEXT(255),
                Hours DOUBLE,
                Notes MEMO
            )
        """)
        conn.commit()
    try:
        cursor.execute("SELECT Notes FROM non_project_logs")
    except:
        try:
            cursor.execute("ALTER TABLE non_project_logs ADD COLUMN [Notes] MEMO")
            conn.commit()
        except:
            st.error("❌ Could not add Notes column. Please check Access DB permissions.")

    # Load data from Excel
    non_proj_df = design_sheets['Non-project work']
    name_list = non_proj_df['Name'].dropna().unique().tolist()
    task_list = non_proj_df['Task'].dropna().unique().tolist()
    customer_list = non_proj_df['Customer'].dropna().unique().tolist()

    st.subheader("🗃️ Log Your Non-Project Work")

    selected_name = st.selectbox("Select your name:", sorted(name_list))
    selected_task = st.selectbox("Select Task:", sorted(task_list))
    selected_customer = st.selectbox("Select Customer:", sorted(customer_list))
    selected_date = st.date_input("Select Date:", datetime.date.today())
    entered_hours = st.number_input("Enter Hours Worked:", min_value=0.0, step=0.5, format="%.1f")
    entered_notes = st.text_area("Optional Notes (comments, follow-up, etc.):")

    if st.button("➕ Add Non-Project Entry"):
        cursor.execute("""
            INSERT INTO non_project_logs ([Name], [Date], [Task], [Customer], [Hours], [Notes])
            VALUES (?, ?, ?, ?, ?, ?)
        """, (selected_name, selected_date, selected_task, selected_customer, entered_hours, entered_notes))
        conn.commit()
        st.success("✅ Non-project entry added successfully!")
        st.rerun()

    # View logs
    st.divider()
    st.subheader("📅 All Logged Non-Project Work")

    df = pd.read_sql("SELECT * FROM non_project_logs ORDER BY [Date] DESC", conn)

    # Filters
    colf1, colf2, colf3 = st.columns(3)
    with colf1:
        name_filter = st.multiselect("Filter by Name:", sorted(df["Name"].dropna().unique()))
    with colf2:
        task_filter = st.multiselect("Filter by Task:", sorted(df["Task"].dropna().unique()))
    with colf3:
        customer_filter = st.multiselect("Filter by Customer:", sorted(df["Customer"].dropna().unique()))

    if name_filter:
        df = df[df["Name"].isin(name_filter)]
    if task_filter:
        df = df[df["Task"].isin(task_filter)]
    if customer_filter:
        df = df[df["Customer"].isin(customer_filter)]

    def format_notes(note):
        if not note:
            return "-"
        if len(note) > 50:
            return f"<span title='{note}'>{note[:50]}...</span>"
        return note

    if df.empty:
        st.info("No matching records found.")
    else:
        for i, row in df.iterrows():
            with st.container():
                col1, col2, col3, col4, col5, col6, col7 = st.columns([2.5, 2.5, 2.5, 2.5, 2.5, 6, 2])
                edit_key = f"np_edit_{row['id']}"
                delete_key = f"np_delete_{row['id']}"

                if st.session_state.get(edit_key, False):
                    with col1:
                        new_date = st.date_input("Edit Date", pd.to_datetime(row["Date"]), key=f"date_{row['id']}")
                    with col2:
                        new_hours = st.number_input("Edit Hours", value=row["Hours"], step=0.5, key=f"hours_{row['id']}")
                    with col3:
                        new_task = st.selectbox("Edit Task", task_list, index=task_list.index(row["Task"]), key=f"task_{row['id']}")
                    with col4:
                        new_customer = st.selectbox("Edit Customer", customer_list, index=customer_list.index(row["Customer"]), key=f"cust_{row['id']}")
                    with col5:
                        new_name = st.selectbox("Edit Name", name_list, index=name_list.index(row["Name"]), key=f"name_{row['id']}")
                    with col6:
                        new_notes = st.text_area("Edit Notes", value=row.get("Notes", ""), key=f"notes_{row['id']}")
                    with col7:
                        st.markdown('<div class="inline-buttons">', unsafe_allow_html=True)
                        save_clicked = st.button("💾 Save", key=f"save_{row['id']}")
                        cancel_clicked = st.button("❌ Cancel", key=f"cancel_{row['id']}")
                        st.markdown('</div>', unsafe_allow_html=True)

                        if save_clicked:
                            cursor.execute("""
                                UPDATE non_project_logs
                                SET [Date]=?, [Hours]=?, [Task]=?, [Customer]=?, [Name]=?, [Notes]=?
                                WHERE id=?
                            """, (new_date, new_hours, new_task, new_customer, new_name, new_notes, row["id"]))
                            conn.commit()
                            del st.session_state[edit_key]
                            st.success("✅ Entry updated.")
                            st.rerun()

                        if cancel_clicked:
                            del st.session_state[edit_key]

                else:
                    with col1:
                        st.markdown(f"**{row['Name']}**")
                    with col2:
                        st.markdown(f"**{pd.to_datetime(row['Date']).date()}**")
                    with col3:
                        st.markdown(f"{row['Hours']} hrs")
                    with col4:
                        st.markdown(f"`{row['Task']}`")
                    with col5:
                        st.markdown(f"`{row['Customer']}`")
                    with col6:
                        st.markdown(format_notes(row.get("Notes", "")), unsafe_allow_html=True)
                    with col7:
                        if st.button("✏️", key=f"edit_btn_{row['id']}"):
                            st.session_state[edit_key] = True
                        elif st.session_state.get(delete_key, False):
                            if st.button("✅ Confirm", key=f"del_yes_{row['id']}"):
                                cursor.execute("DELETE FROM non_project_logs WHERE id=?", (row["id"],))
                                conn.commit()
                                del st.session_state[delete_key]
                                st.success("✅ Entry deleted.")
                                st.rerun()
                            elif st.button("❌ Cancel", key=f"del_no_{row['id']}"):
                                del st.session_state[delete_key]
                        else:
                            if st.button("🗑️", key=f"delete_btn_{row['id']}"):
                                st.session_state[delete_key] = True
