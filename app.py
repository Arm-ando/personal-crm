# app.py
import streamlit as st
import psycopg2
from psycopg2 import extras # For DictCursor
from connect_db import get_db_connection # Your working connection function
import datetime

# --- PAGE CONFIGURATION ---
st.set_page_config(
    page_title="Personal Job CRM",
    page_icon="🧠", # Updated Icon
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- DATABASE CONNECTION ---
@st.cache_resource # Cache the connection object for efficiency
def init_db_conn():
    db_conn = get_db_connection()
    return db_conn

conn = init_db_conn()

if conn is None:
    st.error("⚠️ Critical: Database Connection Error. Application cannot function. Please check .env file and console for detailed error from connect_db.py.")
    st.stop()


# --- DATA FETCHING FUNCTIONS ---

# --- General Helper Functions ---
@st.cache_data(ttl=300) # Cache these options for 5 minutes
def load_selectbox_options(_conn): # Pass actual conn object
    # Generic function to fetch ID-Name pairs for selectbox options
    def get_options(db_conn_local, table_name, id_col, name_col, default_option_text="--- Select ---", order_by_col=None):
        if not db_conn_local: return {default_option_text: None}
        options_map = {default_option_text: None}
        try:
            with db_conn_local.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                query = f"SELECT {id_col}, {name_col} FROM {table_name}"
                query += f" ORDER BY {order_by_col if order_by_col else name_col} ASC;"
                cur.execute(query)
                data = cur.fetchall()
                for row in data: # Ensure name_col is treated as string for dictionary keys
                    options_map[str(row[name_col])] = row[id_col]
            return options_map
        except (Exception, psycopg2.Error) as error:
            # st.error(f"DB Error (get_options for {table_name}): {error}") # Avoid showing too many errors if one fails
            print(f"DB Error (get_options for {table_name}): {error}")
            return {default_option_text: None}

    company_opts = get_options(_conn, "companies", "company_id", "company_name", "--- Select Company ---")
    job_opts = get_options(_conn, "jobs", "job_id", "job_title", "--- Select Job ---") # Assumes job_title is reasonably unique for display
    recruiter_opts = get_options(_conn, "recruiters", "recruiter_id", "name", "--- Select Recruiter ---")
    return company_opts, job_opts, recruiter_opts

# --- Job Functions ---
def get_total_jobs_count(db_conn):
    if not db_conn: return 0
    try:
        with db_conn.cursor() as cur: cur.execute("SELECT COUNT(*) FROM jobs;"); result = cur.fetchone(); return result[0] if result else 0
    except (Exception, psycopg2.Error) as e: st.error(f"DB Error (total_jobs): {e}"); return 0

def get_job_status_counts(db_conn):
    if not db_conn: return {}
    s = ["Not Applied", "Applied", "Interviewing", "Offer"]; c = {st_val: 0 for st_val in s}
    try:
        with db_conn.cursor() as cur:
            q = "SELECT status, COUNT(*) FROM jobs WHERE status = ANY(%s) GROUP BY status;"; cur.execute(q, (s,))
            for r_tuple in cur.fetchall(): # Use r_tuple to avoid conflict
                if r_tuple[0] in c: c[r_tuple[0]] = r_tuple[1]
        return c
    except (Exception, psycopg2.Error) as e: st.error(f"DB Error (job_status_counts): {e}"); return c

def get_all_jobs(db_conn):
    if not db_conn: return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT j.job_id, j.job_title, c.company_name, j.company_id, 
                       j.location, j.status, j.job_url, j.date_found, j.notes, j.created_at 
                FROM jobs j LEFT JOIN companies c ON j.company_id = c.company_id
                ORDER BY j.created_at DESC;
            """)
            return cur.fetchall()
    except (Exception, psycopg2.Error) as e: st.error(f"DB Error (get_all_jobs): {e}"); return []

def get_job_details(db_conn, job_id):
    if not db_conn: return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT j.*, c.company_name FROM jobs j LEFT JOIN companies c ON j.company_id = c.company_id WHERE j.job_id = %s;", (job_id,))
            return cur.fetchone()
    except (Exception, psycopg2.Error) as e: st.error(f"DB Error (job_details ID {job_id}): {e}"); return None

def add_new_job(db_conn, title, comp_id, loc, stat, url, notes_val, date_f):
    if not db_conn: st.error("DB not connected."); return False
    if not title: st.error("Job Title required."); return False
    if comp_id is None: st.error("Company required."); return False
    try:
        with db_conn.cursor() as cur:
            cur.execute("INSERT INTO jobs (job_title, company_id, location, status, job_url, notes, date_found) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                        (title, comp_id, loc, stat, url, notes_val, date_f))
            db_conn.commit()
        return True
    except (Exception, psycopg2.Error) as e:
        if db_conn: db_conn.rollback(); st.error(f"DB Error (add job): {e}"); return False

def update_job_details(db_conn, j_id, title, comp_id, loc, stat, url, notes_val, date_f):
    if not db_conn: st.error("DB not connected."); return False
    if not all([j_id, title, stat]): st.error("Job ID, Title, Status required for update."); return False
    if comp_id is None: st.error("Company required for update."); return False # Make company mandatory
    try:
        with db_conn.cursor() as cur:
            cur.execute("UPDATE jobs SET job_title=%s, company_id=%s, location=%s, status=%s, job_url=%s, notes=%s, date_found=%s WHERE job_id=%s",
                        (title, comp_id, loc, stat, url, notes_val, date_f, j_id))
            db_conn.commit()
        return True
    except (Exception, psycopg2.Error) as e:
        if db_conn: db_conn.rollback(); st.error(f"DB Error (update job ID {j_id}): {e}"); return False

def delete_job_record(db_conn, job_id):
    if not db_conn: st.error("DB not connected."); return False
    if not job_id: st.error("Job ID required for deletion."); return False
    try:
        with db_conn.cursor() as cur: cur.execute("DELETE FROM jobs WHERE job_id = %s;", (job_id,)); db_conn.commit()
        return True
    except (Exception, psycopg2.Error) as e:
        if db_conn: db_conn.rollback(); st.error(f"DB Error (delete job ID {job_id}): {e}"); return False

# --- Recruiter Functions ---
def get_recent_recruiters(db_conn, count=3):
    if not db_conn: return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT recruiter_id, name, created_at FROM recruiters ORDER BY created_at DESC LIMIT %s;", (count,))
            return cur.fetchall()
    except (Exception, psycopg2.Error) as e: st.error(f"DB Error (recent_recruiters): {e}"); return []

def get_all_recruiters(db_conn):
    if not db_conn: return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT r.recruiter_id, r.name, c.company_name AS agency_name, r.agency_company_id,
                       r.contact_info, r.notes, r.first_contact_date, r.created_at
                FROM recruiters r LEFT JOIN companies c ON r.agency_company_id = c.company_id
                ORDER BY r.name ASC;
            """) # Order by name
            return cur.fetchall()
    except (Exception, psycopg2.Error) as e: st.error(f"DB Error (recruiters): {e}"); return []

def add_new_recruiter(db_conn, name, agency_id, contact, notes_val, date_f):
    if not db_conn: st.error("DB not connected"); return False
    if not name: st.error("Recruiter name required"); return False
    try:
        with db_conn.cursor() as cur:
            cur.execute("INSERT INTO recruiters (name, agency_company_id, contact_info, notes, first_contact_date) VALUES (%s,%s,%s,%s,%s)",
                        (name, agency_id, contact, notes_val, date_f))
            db_conn.commit()
        return True
    except (Exception, psycopg2.Error) as e:
        if db_conn: db_conn.rollback(); st.error(f"DB Error (add recruiter): {e}"); return False

# --- Company Functions ---
def get_recent_companies(db_conn, count=3):
    if not db_conn: return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT company_id, company_name, created_at FROM companies ORDER BY created_at DESC LIMIT %s;", (count,))
            return cur.fetchall()
    except (Exception, psycopg2.Error) as e: st.error(f"DB Error (recent_companies): {e}"); return []

def get_all_companies(db_conn):
    if not db_conn: return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM companies ORDER BY company_name ASC;")
            return cur.fetchall()
    except (Exception, psycopg2.Error) as e: st.error(f"DB Error (companies): {e}"); return []

def add_new_company(db_conn, name, sector_val, web, notes_val, src):
    if not db_conn: st.error("DB not connected"); return False
    if not name: st.error("Company name required"); return False
    try:
        with db_conn.cursor() as cur:
            cur.execute("INSERT INTO companies (company_name, sector, website, notes, source) VALUES (%s,%s,%s,%s,%s)",
                        (name, sector_val, web, notes_val, src))
            db_conn.commit()
        return True
    except (Exception, psycopg2.Error) as e:
        if db_conn: db_conn.rollback(); st.error(f"DB Error (add company): {e}"); return False

# --- Task Functions ---
def get_upcoming_tasks(db_conn, count=5):
    if not db_conn: return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT t.task_id, t.task_description, t.due_date, t.status, t.priority,
                       j.job_title, r.name as recruiter_name, cy.company_name as related_company_name
                FROM tasks t
                LEFT JOIN jobs j ON t.job_id = j.job_id
                LEFT JOIN recruiters r ON t.recruiter_id = r.recruiter_id
                LEFT JOIN companies cy ON t.company_id = cy.company_id
                WHERE t.status NOT IN ('Completed', 'Cancelled') 
                ORDER BY t.due_date ASC NULLS LAST, t.priority ASC NULLS LAST, t.created_at ASC
                LIMIT %s;
            """, (count,))
            return cur.fetchall()
    except (Exception, psycopg2.Error) as e: st.error(f"DB Error (upcoming_tasks): {e}"); return []

def get_all_tasks(db_conn):
    if not db_conn: return []
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT t.task_id, t.task_description, t.due_date, t.status, t.priority, t.notes,
                       j.job_title, t.job_id,
                       r.name as recruiter_name, t.recruiter_id,
                       cy.company_name as related_company_name, t.company_id 
                       /* t.company_id instead of t.company_id as related_company_id_for_task */
                FROM tasks t
                LEFT JOIN jobs j ON t.job_id = j.job_id
                LEFT JOIN recruiters r ON t.recruiter_id = r.recruiter_id
                LEFT JOIN companies cy ON t.company_id = cy.company_id
                ORDER BY t.due_date ASC NULLS LAST, t.status ASC, t.priority DESC NULLS LAST, t.created_at DESC;
            """)
            return cur.fetchall()
    except (Exception, psycopg2.Error) as e: st.error(f"DB Error (get_all_tasks): {e}"); return []

def add_new_task(db_conn, desc, due, stat, prio, notes_val, j_id, rec_id, comp_id):
    if not db_conn: st.error("DB not connected"); return False
    if not desc or not stat: st.error("Task Description and Status are required"); return False
    try:
        with db_conn.cursor() as cur:
            cur.execute("INSERT INTO tasks (task_description, due_date, status, priority, notes, job_id, recruiter_id, company_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                        (desc, due, stat, prio, notes_val, j_id, rec_id, comp_id))
            db_conn.commit()
        return True
    except (Exception, psycopg2.Error) as e:
        if db_conn: db_conn.rollback(); st.error(f"DB Error (add task): {e}"); return False

def get_task_details(db_conn, task_id):
    if not db_conn: return None
    try:
        with db_conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("""
                SELECT t.*, j.job_title, r.name as recruiter_name, cy.company_name as related_company_name
                FROM tasks t
                LEFT JOIN jobs j ON t.job_id = j.job_id
                LEFT JOIN recruiters r ON t.recruiter_id = r.recruiter_id
                LEFT JOIN companies cy ON t.company_id = cy.company_id
                WHERE t.task_id = %s;
            """, (task_id,))
            return cur.fetchone()
    except (Exception, psycopg2.Error) as e: st.error(f"DB Error (task_details ID {task_id}): {e}"); return None

def update_task_details(db_conn, task_id, desc, due, stat, prio, notes_val, j_id, rec_id, comp_id): # Renamed update_task
    if not db_conn: st.error("DB not connected."); return False
    if not all([task_id, desc, stat]): st.error("Task ID, Description, Status required for update."); return False
    try:
        with db_conn.cursor() as cur:
            cur.execute("""
                UPDATE tasks SET task_description=%s, due_date=%s, status=%s, priority=%s, notes=%s, 
                                job_id=%s, recruiter_id=%s, company_id=%s 
                WHERE task_id=%s
            """, (desc, due, stat, prio, notes_val, j_id, rec_id, comp_id, task_id))
            db_conn.commit()
        return True
    except (Exception, psycopg2.Error) as e:
        if db_conn: db_conn.rollback(); st.error(f"DB Error (update task ID {task_id}): {e}"); return False

def delete_task_record(db_conn, task_id):
    if not db_conn: st.error("DB not connected."); return False
    if not task_id: st.error("Task ID required for deletion."); return False
    try:
        with db_conn.cursor() as cur: cur.execute("DELETE FROM tasks WHERE task_id = %s;", (task_id,)); db_conn.commit();
        return True
    except (Exception, psycopg2.Error) as e:
        if db_conn: db_conn.rollback(); st.error(f"DB Error (delete task ID {task_id}): {e}"); return False


# --- SIDEBAR ---
st.sidebar.markdown("## 🧠")
st.sidebar.title("Personal CRM")
st.sidebar.caption("Track your job hunting journey efficiently.")
page_options = ["Dashboard", "Job Tracker", "Recruiter Tracker", "Company Tracker", "Task Manager"]
page = st.sidebar.radio("Navigation", page_options, key="navigation_menu_main_v2") # Ensure unique key

# --- Initialize Session State ---
if 'selected_job_id_for_edit' not in st.session_state: st.session_state.selected_job_id_for_edit = None
if 'confirm_delete_job_id' not in st.session_state: st.session_state.confirm_delete_job_id = None
if 'selected_recruiter_id_for_edit' not in st.session_state: st.session_state.selected_recruiter_id_for_edit = None
if 'confirm_delete_recruiter_id' not in st.session_state: st.session_state.confirm_delete_recruiter_id = None
if 'selected_company_id_for_edit' not in st.session_state: st.session_state.selected_company_id_for_edit = None
if 'confirm_delete_company_id' not in st.session_state: st.session_state.confirm_delete_company_id = None
if 'selected_task_id_for_edit' not in st.session_state: st.session_state.selected_task_id_for_edit = None
if 'confirm_delete_task_id' not in st.session_state: st.session_state.confirm_delete_task_id = None

# --- Common Data for Selectboxes ---
company_options_map, job_options_map, recruiter_options_map = load_selectbox_options(conn)
actual_company_names = [name for name, id_val in company_options_map.items() if id_val is not None]
actual_job_titles = [name for name, id_val in job_options_map.items() if id_val is not None]
actual_recruiter_names = [name for name, id_val in recruiter_options_map.items() if id_val is not None]

# --- Common Lists for Options ---
job_status_options = ["Not Applied", "Applied", "Interviewing", "Rejected", "Offer"]
task_status_options = ["Open", "In Progress", "Awaiting Feedback", "Completed", "Cancelled"]
task_priority_options = ["---", "Low", "Medium", "High"] # "---" will map to NULL for priority


# --- Page Content ---
if page == "Dashboard":
    st.title("📊 My Job Hunt Dashboard")
    st.markdown("---")
    total_jobs_val = get_total_jobs_count(conn)
    job_statuses_val = get_job_status_counts(conn)
    recent_companies_val = get_recent_companies(conn, count=3)
    recent_recruiters_val = get_recent_recruiters(conn, count=3)
    upcoming_tasks_val = get_upcoming_tasks(conn, count=5)

    col1, col2, col3, col4 = st.columns(4)
    with col1: st.metric(label="Total Jobs Tracked", value=total_jobs_val)
    with col2: st.metric(label="Jobs Applied", value=job_statuses_val.get("Applied", 0))
    with col3: st.metric(label="Interviews Scheduled", value=job_statuses_val.get("Interviewing", 0))
    with col4: st.metric(label="Offers Received", value=job_statuses_val.get("Offer", 0))
    st.markdown("---")
    st.subheader("🚀 Recent Activity & Upcoming Tasks")
    activity_col, tasks_col = st.columns(2)
    with activity_col: # Recent Activity
        st.markdown("##### Recently Added Companies")
        if recent_companies_val:
            for company in recent_companies_val:
                st.markdown(f"- **{company.get('company_name', 'N/A')}** (Added: {company.get('created_at').strftime('%Y-%m-%d') if company.get('created_at') else 'N/A'})")
        else: st.caption("No recent companies.")
        st.markdown("##### Recently Added Recruiters")
        if recent_recruiters_val:
            for recruiter in recent_recruiters_val:
                st.markdown(f"- **{recruiter.get('name', 'N/A')}** (Added: {recruiter.get('created_at').strftime('%Y-%m-%d') if recruiter.get('created_at') else 'N/A'})")
        else: st.caption("No recent recruiters.")
    with tasks_col: # Upcoming Tasks
        st.markdown("##### Upcoming Tasks")
        if upcoming_tasks_val:
            for task_row in upcoming_tasks_val:
                due_str = task_row['due_date'].strftime('%Y-%m-%d') if task_row.get('due_date') else 'N/A'
                desc_str = task_row.get('task_description', 'No description')
                status_str = task_row.get('status','N/A')
                prio_str = f", Prio: {task_row.get('priority')}" if task_row.get('priority') else ""
                
                related_info = []
                if task_row.get('job_title'): related_info.append(f"Job: *{task_row['job_title']}*")
                if task_row.get('recruiter_name'): related_info.append(f"Rec: *{task_row['recruiter_name']}*")
                if task_row.get('related_company_name'): related_info.append(f"Co: *{task_row['related_company_name']}*")
                related_str = f"(Rel: {', '.join(related_info)})" if related_info else ""
                
                st.markdown(f"- **{desc_str}** (Due: {due_str}, Status: {status_str}{prio_str}) {related_str}")
        else: st.caption("No upcoming tasks.")

elif page == "Job Tracker":
    # --- JOB TRACKER PAGE ---
    st.title("💼 Job Tracker")
    st.markdown("Manage your job applications.")
    tab_view_jobs, tab_add_job, tab_edit_delete_job = st.tabs(["📋 View All Jobs", "➕ Add New Job", "✏️ Edit/Delete Job"])

    with tab_add_job:
        st.subheader("➕ Add New Job")
        with st.form("add_job_form_job_page_v2", clear_on_submit=True): # Ensure unique form key
            new_job_title = st.text_input("Job Title*", key="add_job_title_j")
            # --- Company selection or typing ---
            st.markdown("**Company**")
            col_comp_sel, col_comp_type = st.columns([2, 2])
            with col_comp_sel:
                sel_comp_name_add_job = st.selectbox(
                    "Select Existing Company", 
                    options=["--- Select Company ---"] + actual_company_names, 
                    index=0, 
                    key="add_job_comp_j"
                )
            with col_comp_type:
                new_comp_name_add_job = st.text_input("Or Type New Company Name", key="add_job_new_comp_j")
            # --- End company selection/typing ---
            new_loc_add_job = st.text_input("Location", key="add_job_loc_j")
            new_stat_add_job = st.selectbox("Application Status*", options=job_status_options, index=0, key="add_job_stat_j")
            new_url_add_job = st.text_input("Link to Job Post", key="add_job_url_j")
            new_notes_add_job = st.text_area("Notes", key="add_job_notes_j")
            new_date_f_add_job = st.date_input("Date Found", value=datetime.date.today(), key="add_job_date_j")
            submit_add_job = st.form_submit_button("Add Job to Tracker")
            if submit_add_job:
                is_valid_j = True
                sel_comp_id_add_job = None
                # --- Company validation logic ---
                if new_comp_name_add_job:
                    # User typed a new company name
                    if add_new_company(conn, new_comp_name_add_job, "", "", "", ""):
                        st.success(f"Company '{new_comp_name_add_job}' added!")
                        # Fetch the new company's ID directly from DB
                        try:
                            with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                                cur.execute("SELECT company_id FROM companies WHERE company_name = %s ORDER BY company_id DESC LIMIT 1;", (new_comp_name_add_job,))
                                row = cur.fetchone()
                                if row:
                                    sel_comp_id_add_job = row['company_id']
                                else:
                                    st.error("Could not retrieve new company ID."); is_valid_j = False
                        except Exception as e:
                            st.error(f"Error fetching new company ID: {e}"); is_valid_j = False
                    else:
                        st.error("Failed to add new company."); is_valid_j = False
                elif sel_comp_name_add_job and sel_comp_name_add_job != "--- Select Company ---":
                    sel_comp_id_add_job = company_options_map.get(sel_comp_name_add_job)
                else:
                    st.error("Please select or type a company."); is_valid_j = False
                # --- End company validation ---
                if not new_job_title: st.error("Title required"); is_valid_j = False
                if is_valid_j and sel_comp_id_add_job:
                    if add_new_job(conn, new_job_title, sel_comp_id_add_job, new_loc_add_job, new_stat_add_job, new_url_add_job, new_notes_add_job, new_date_f_add_job):
                        st.success("Job added!"); st.rerun()
    
    with tab_edit_delete_job:
        st.subheader("✏️ Edit or 🗑️ Delete Job")
        all_jobs_data_for_sel = get_all_jobs(conn)
        if not all_jobs_data_for_sel: st.info("No jobs to edit/delete.")
        else:
            job_map_for_sel = {f"{j['job_title']} @ {j.get('company_name','N/A')} (ID:{j['job_id']})": j['job_id'] for j in all_jobs_data_for_sel}
            job_disp_list_sel = ["--- Select Job ---"] + list(job_map_for_sel.keys())
            sel_job_disp_str = st.selectbox("Select Job:", job_disp_list_sel, 
                                            index=0, 
                                            key="sel_job_to_edit_delete_key") # Unique key

            if sel_job_disp_str and sel_job_disp_str != "--- Select Job ---":
                st.session_state.selected_job_id_for_edit = job_map_for_sel[sel_job_disp_str]
            else: st.session_state.selected_job_id_for_edit = None
            
            if st.session_state.selected_job_id_for_edit:
                job_dets = get_job_details(conn, st.session_state.selected_job_id_for_edit)
                if job_dets:
                    with st.form("edit_job_form_job_page_v2"): # Unique key
                        st.markdown(f"**Editing Job ID: {job_dets['job_id']}** - *{job_dets['job_title']}*")
                        edit_title = st.text_input("Job Title*", value=job_dets.get('job_title',''), key="edit_job_title_j")
                        edit_comp_id_val = job_dets.get('company_id') # Store original company_id
                        edit_comp_idx = 0
                        if actual_company_names and edit_comp_id_val:
                            for idx, name in enumerate(actual_company_names): # Iterate through actual names
                                if company_options_map.get(name) == edit_comp_id_val:
                                    edit_comp_idx = idx
                                    break
                        
                        sel_edit_comp_name = st.selectbox("Company*", options=actual_company_names, index=edit_comp_idx, key="edit_job_comp_j") if actual_company_names else st.text_input("Company ID (no companies listed)", value=str(edit_comp_id_val or ''), disabled=True)
                        
                        edit_loc = st.text_input("Location", value=job_dets.get('location',''), key="edit_job_loc_j")
                        edit_stat_idx = job_status_options.index(job_dets['status']) if job_dets.get('status') in job_status_options else 0
                        edit_stat = st.selectbox("Status*", options=job_status_options, index=edit_stat_idx, key="edit_job_stat_j")
                        edit_url = st.text_input("Job URL", value=job_dets.get('job_url',''), key="edit_job_url_j")
                        edit_notes = st.text_area("Notes", value=job_dets.get('notes',''), key="edit_job_notes_j")
                        edit_date_f = st.date_input("Date Found", value=job_dets.get('date_found'), key="edit_job_date_j")
                        
                        update_btn = st.form_submit_button("Update Job Details")
                        if update_btn:
                            is_valid_edit_j = True 
                            edit_sel_comp_id = company_options_map.get(sel_edit_comp_name) if sel_edit_comp_name and sel_edit_comp_name in company_options_map else None
                            if not edit_title: st.error("Title required"); is_valid_edit_j=False
                            if not edit_sel_comp_id and actual_company_names: st.error("Company required"); is_valid_edit_j=False 
                            if is_valid_edit_j:
                                if update_job_details(conn,job_dets['job_id'],edit_title,edit_sel_comp_id,edit_loc,edit_stat,edit_url,edit_notes,edit_date_f):
                                    st.success("Job updated!"); st.session_state.selected_job_id_for_edit=None; st.rerun()
                    # Delete action
                    st.markdown("---")
                    if st.button(f"Request to Delete Job ID {job_dets['job_id']}", key=f"del_req_btn_job_{job_dets['job_id']}"):
                        st.session_state.confirm_delete_job_id = job_dets['job_id']
                        st.rerun() # Rerun to show confirmation widgets
                    if st.session_state.confirm_delete_job_id == job_dets['job_id']:
                        st.error(f"FINAL WARNING: Permanently delete '{job_dets.get('job_title', 'this job')}'?")
                        col_confirm, col_cancel = st.columns(2)
                        with col_confirm:
                            if st.button("YES, Delete Now", type="primary", key=f"final_del_btn_job_{job_dets['job_id']}"):
                                if delete_job_record(conn, job_dets['job_id']):
                                    st.success("Job deleted!"); st.session_state.selected_job_id_for_edit=None; st.session_state.confirm_delete_job_id=None; st.rerun()
                        with col_cancel:
                            if st.button("Cancel Deletion", key=f"cancel_del_btn_job_{job_dets['job_id']}"):
                                st.session_state.confirm_delete_job_id = None; st.rerun()
                elif st.session_state.selected_job_id_for_edit: 
                    st.warning("Could not load selected job. It might have been deleted."); st.session_state.selected_job_id_for_edit=None

    with tab_view_jobs:
        st.subheader("📋 View All Jobs")
        all_jobs_data_disp = get_all_jobs(conn)
        if all_jobs_data_disp:
            disp_cols_jobs = ['job_title','company_name','location','status','date_found','job_url','notes']
            jobs_df_disp = [{col: jr.get(col, 'N/A') for col in disp_cols_jobs} for jr in all_jobs_data_disp]
            for job_dict in jobs_df_disp:
                if isinstance(job_dict.get('date_found'), datetime.date): job_dict['date_found'] = job_dict['date_found'].strftime('%Y-%m-%d')
            st.dataframe(jobs_df_disp, use_container_width=True, hide_index=True)
        else: st.info("No jobs found yet.")

elif page == "Recruiter Tracker":
    st.title("👥 Recruiter Tracker")
    st.markdown("Log recruiters and interactions.")
    tab_view_rec, tab_add_rec, tab_edit_delete_rec = st.tabs(["📋 View All Recruiters", "➕ Add New Recruiter", "✏️ Edit/Delete Recruiter"])

    with tab_add_rec:
        st.subheader("➕ Add New Recruiter")
        with st.form("add_recruiter_form_rec_page_v2", clear_on_submit=True):
            new_rec_name = st.text_input("Recruiter Name*")
            sel_agency_name_add_rec = st.selectbox("Agency/Company (Optional)", options=["--- No Specific Agency ---"] + actual_company_names, index=0)
            new_contact_add_rec = st.text_area("Contact Info")
            new_notes_add_rec = st.text_area("Notes")
            new_date_f_add_rec = st.date_input("Date of First Contact", value=None)
            submit_add_rec = st.form_submit_button("Add Recruiter")
            if submit_add_rec:
                is_valid_rec_add = True
                sel_agency_id_add_rec = None
                if sel_agency_name_add_rec and sel_agency_name_add_rec not in ["--- No Specific Agency ---", "--- Select Company ---"]:
                    sel_agency_id_add_rec = company_options_map.get(sel_agency_name_add_rec)
                if not new_rec_name: st.error("Name required"); is_valid_rec_add=False
                if is_valid_rec_add:
                    if add_new_recruiter(conn,new_rec_name,sel_agency_id_add_rec,new_contact_add_rec,new_notes_add_rec,new_date_f_add_rec):
                        st.success("Recruiter added!"); st.rerun()

    with tab_edit_delete_rec:
        st.subheader("✏️ Edit or 🗑️ Delete Recruiter")
        all_recruiters_data_for_sel = get_all_recruiters(conn)
        if not all_recruiters_data_for_sel:
            st.info("No recruiters to edit/delete.")
        else:
            rec_map_for_sel = {f"{r['name']} (ID:{r['recruiter_id']})": r['recruiter_id'] for r in all_recruiters_data_for_sel}
            rec_disp_list_sel = ["--- Select Recruiter ---"] + list(rec_map_for_sel.keys())
            sel_rec_disp_str = st.selectbox("Select Recruiter:", rec_disp_list_sel, index=0, key="sel_rec_to_edit_delete_key")
            if sel_rec_disp_str and sel_rec_disp_str != "--- Select Recruiter ---":
                st.session_state.selected_recruiter_id_for_edit = rec_map_for_sel[sel_rec_disp_str]
            else:
                st.session_state.selected_recruiter_id_for_edit = None

            if st.session_state.selected_recruiter_id_for_edit:
                rec_dets = next((r for r in all_recruiters_data_for_sel if r['recruiter_id'] == st.session_state.selected_recruiter_id_for_edit), None)
                if rec_dets:
                    with st.form("edit_recruiter_form_rec_page_v2"):
                        st.markdown(f"**Editing Recruiter ID: {rec_dets['recruiter_id']}** - *{rec_dets['name']}*")
                        edit_rec_name = st.text_input("Recruiter Name*", value=rec_dets.get('name',''))
                        edit_agency_idx = 0
                        if actual_company_names and rec_dets.get('agency_company_id'):
                            for idx, name in enumerate(actual_company_names):
                                if company_options_map.get(name) == rec_dets['agency_company_id']:
                                    edit_agency_idx = idx + 1
                                    break
                        edit_agency_name = st.selectbox("Agency/Company (Optional)", options=["--- No Specific Agency ---"] + actual_company_names, index=edit_agency_idx)
                        edit_contact = st.text_area("Contact Info", value=rec_dets.get('contact_info',''))
                        edit_notes = st.text_area("Notes", value=rec_dets.get('notes',''))
                        edit_date_f = st.date_input("Date of First Contact", value=rec_dets.get('first_contact_date'))
                        update_rec_btn = st.form_submit_button("Update Recruiter")
                        if update_rec_btn:
                            is_valid_edit_rec = True
                            edit_agency_id = None
                            if edit_agency_name and edit_agency_name not in ["--- No Specific Agency ---", "--- Select Company ---"]:
                                edit_agency_id = company_options_map.get(edit_agency_name)
                            if not edit_rec_name: st.error("Name required"); is_valid_edit_rec = False
                            if is_valid_edit_rec:
                                try:
                                    with conn.cursor() as cur:
                                        cur.execute(
                                            "UPDATE recruiters SET name=%s, agency_company_id=%s, contact_info=%s, notes=%s, first_contact_date=%s WHERE recruiter_id=%s",
                                            (edit_rec_name, edit_agency_id, edit_contact, edit_notes, edit_date_f, rec_dets['recruiter_id'])
                                        )
                                        conn.commit()
                                    st.success("Recruiter updated!"); st.session_state.selected_recruiter_id_for_edit=None; st.rerun()
                                except Exception as e:
                                    conn.rollback()
                                    st.error(f"Error updating recruiter: {e}")
                    st.markdown("---")
                    if st.button(f"Request to Delete Recruiter ID {rec_dets['recruiter_id']}", key=f"del_req_btn_rec_{rec_dets['recruiter_id']}"):
                        st.session_state.confirm_delete_recruiter_id = rec_dets['recruiter_id']
                        st.rerun()
                    if st.session_state.confirm_delete_recruiter_id == rec_dets['recruiter_id']:
                        st.error(f"FINAL WARNING: Delete recruiter '{rec_dets.get('name', 'this recruiter')}'?")
                        col_confirm_rec, col_cancel_rec = st.columns(2)
                        with col_confirm_rec:
                            if st.button("YES, Delete Now", type="primary", key=f"final_del_btn_rec_{rec_dets['recruiter_id']}"):
                                try:
                                    with conn.cursor() as cur:
                                        cur.execute("DELETE FROM recruiters WHERE recruiter_id = %s;", (rec_dets['recruiter_id'],))
                                        conn.commit()
                                    st.success("Recruiter deleted!"); st.session_state.selected_recruiter_id_for_edit=None; st.session_state.confirm_delete_recruiter_id=None; st.rerun()
                                except Exception as e:
                                    conn.rollback()
                                    st.error(f"Error deleting recruiter: {e}")
                        with col_cancel_rec:
                            if st.button("Cancel Deletion", key=f"cancel_del_btn_rec_{rec_dets['recruiter_id']}"):
                                st.session_state.confirm_delete_recruiter_id = None; st.rerun()
                elif st.session_state.selected_recruiter_id_for_edit:
                    st.warning("Could not load selected recruiter."); st.session_state.selected_recruiter_id_for_edit=None

    with tab_view_rec:
        st.subheader("📋 View All Recruiters")
        all_recruiters_data_disp = get_all_recruiters(conn)
        if all_recruiters_data_disp:
            disp_cols_rec = ['name','agency_name','contact_info','first_contact_date','notes']
            rec_df_disp = [{col: rr.get(col, 'N/A') for col in disp_cols_rec} for rr in all_recruiters_data_disp]
            for rec_dict in rec_df_disp:
                if isinstance(rec_dict.get('first_contact_date'), datetime.date): rec_dict['first_contact_date'] = rec_dict['first_contact_date'].strftime('%Y-%m-%d')
            st.dataframe(rec_df_disp, use_container_width=True, hide_index=True)
        else: st.info("No recruiters found yet.")

elif page == "Company Tracker":
    st.title("🏢 Company Tracker")
    st.markdown("Bookmark companies of interest.")
    tab_view_comp, tab_add_comp, tab_edit_delete_comp = st.tabs(["📋 View All Companies", "➕ Add New Company", "✏️ Edit/Delete Company"])

    with tab_add_comp:
        st.subheader("➕ Add New Company")
        with st.form("add_company_form_comp_page_v2", clear_on_submit=True):
            new_comp_name = st.text_input("Company Name*")
            new_sector_add_comp = st.text_input("Sector")
            new_web_add_comp = st.text_input("Website URL")
            new_notes_add_comp = st.text_area("Notes")
            new_src_add_comp = st.text_input("Source")
            submit_add_comp = st.form_submit_button("Add Company")
            if submit_add_comp:
                if not new_comp_name: st.error("Company name required");
                else:
                    if add_new_company(conn,new_comp_name,new_sector_add_comp,new_web_add_comp,new_notes_add_comp,new_src_add_comp):
                        st.success("Company added!"); st.rerun()

    with tab_edit_delete_comp:
        st.subheader("✏️ Edit or 🗑️ Delete Company")
        all_companies_data_for_sel = get_all_companies(conn)
        if not all_companies_data_for_sel:
            st.info("No companies to edit/delete.")
        else:
            comp_map_for_sel = {f"{c['company_name']} (ID:{c['company_id']})": c['company_id'] for c in all_companies_data_for_sel}
            comp_disp_list_sel = ["--- Select Company ---"] + list(comp_map_for_sel.keys())
            sel_comp_disp_str = st.selectbox("Select Company:", comp_disp_list_sel, index=0, key="sel_comp_to_edit_delete_key")
            if sel_comp_disp_str and sel_comp_disp_str != "--- Select Company ---":
                st.session_state.selected_company_id_for_edit = comp_map_for_sel[sel_comp_disp_str]
            else:
                st.session_state.selected_company_id_for_edit = None

            if st.session_state.selected_company_id_for_edit:
                comp_dets = next((c for c in all_companies_data_for_sel if c['company_id'] == st.session_state.selected_company_id_for_edit), None)
                if comp_dets:
                    with st.form("edit_company_form_comp_page_v2"):
                        st.markdown(f"**Editing Company ID: {comp_dets['company_id']}** - *{comp_dets['company_name']}*")
                        edit_comp_name = st.text_input("Company Name*", value=comp_dets.get('company_name',''))
                        edit_sector = st.text_input("Sector", value=comp_dets.get('sector',''))
                        edit_web = st.text_input("Website URL", value=comp_dets.get('website',''))
                        edit_notes = st.text_area("Notes", value=comp_dets.get('notes',''))
                        edit_src = st.text_input("Source", value=comp_dets.get('source',''))
                        update_comp_btn = st.form_submit_button("Update Company")
                        if update_comp_btn:
                            is_valid_edit_comp = True
                            if not edit_comp_name: st.error("Company name required"); is_valid_edit_comp = False
                            if is_valid_edit_comp:
                                try:
                                    with conn.cursor() as cur:
                                        cur.execute(
                                            "UPDATE companies SET company_name=%s, sector=%s, website=%s, notes=%s, source=%s WHERE company_id=%s",
                                            (edit_comp_name, edit_sector, edit_web, edit_notes, edit_src, comp_dets['company_id'])
                                        )
                                        conn.commit()
                                    st.success("Company updated!"); st.session_state.selected_company_id_for_edit=None; st.rerun()
                                except Exception as e:
                                    conn.rollback()
                                    st.error(f"Error updating company: {e}")
                    st.markdown("---")
                    if st.button(f"Request to Delete Company ID {comp_dets['company_id']}", key=f"del_req_btn_comp_{comp_dets['company_id']}"):
                        st.session_state.confirm_delete_company_id = comp_dets['company_id']
                        st.rerun()
                    if st.session_state.confirm_delete_company_id == comp_dets['company_id']:
                        st.error(f"FINAL WARNING: Delete company '{comp_dets.get('company_name', 'this company')}'?")
                        col_confirm_comp, col_cancel_comp = st.columns(2)
                        with col_confirm_comp:
                            if st.button("YES, Delete Now", type="primary", key=f"final_del_btn_comp_{comp_dets['company_id']}"):
                                try:
                                    with conn.cursor() as cur:
                                        cur.execute("DELETE FROM companies WHERE company_id = %s;", (comp_dets['company_id'],))
                                        conn.commit()
                                    st.success("Company deleted!"); st.session_state.selected_company_id_for_edit=None; st.session_state.confirm_delete_company_id=None; st.rerun()
                                except Exception as e:
                                    conn.rollback()
                                    st.error(f"Error deleting company: {e}")
                        with col_cancel_comp:
                            if st.button("Cancel Deletion", key=f"cancel_del_btn_comp_{comp_dets['company_id']}"):
                                st.session_state.confirm_delete_company_id = None; st.rerun()
                elif st.session_state.selected_company_id_for_edit:
                    st.warning("Could not load selected company."); st.session_state.selected_company_id_for_edit=None

    with tab_view_comp:
        st.subheader("📋 Saved Companies")
        all_companies_data_disp = get_all_companies(conn)
        if all_companies_data_disp:
            disp_cols_comp = ['company_name','sector','website','source','notes', 'created_at']
            comp_df_disp = []
            for cr_row in all_companies_data_disp:
                comp_dict_row = {col: cr_row.get(col, 'N/A') for col in disp_cols_comp}
                if isinstance(comp_dict_row.get('created_at'), datetime.datetime):
                    comp_dict_row['created_at'] = comp_dict_row['created_at'].strftime('%Y-%m-%d %H:%M')
                comp_df_disp.append(comp_dict_row)

            st.dataframe(comp_df_disp, use_container_width=True, hide_index=True,
                         column_config={"website": st.column_config.LinkColumn("Website URL", display_text="Visit Site ↗")})
        else: st.info("No companies saved yet.")


elif page == "Task Manager":
    st.title("⏰ Task Manager")
    st.markdown("Manage your to-do items, reminders, and follow-ups.")
    tab_view_tasks, tab_add_task, tab_edit_delete_task = st.tabs(["📋 View All Tasks", "➕ Add New Task", "✏️ Edit/Delete Task"])

    with tab_add_task:
        st.subheader("➕ Add New Task")
        with st.form("add_task_form_task_page", clear_on_submit=True): # Unique key
            new_task_desc = st.text_area("Task Description*")
            col_task_1, col_task_2 = st.columns(2)
            with col_task_1:
                new_task_due_date = st.date_input("Due Date", value=None, key="add_task_due_date_input")
                new_task_status = st.selectbox("Status*", options=task_status_options, index=task_status_options.index('Open'), key="add_task_status_select")
            with col_task_2:
                new_task_priority = st.selectbox("Priority", options=task_priority_options, index=0, key="add_task_priority_select")
            
            st.markdown("**Link Task to (Optional):**")
            link_col1, link_col2, link_col3 = st.columns(3)
            with link_col1: selected_job_title_task = st.selectbox("Job", options=["--- Select Job ---"] + actual_job_titles, index=0, key="add_task_job_link_sel")
            with link_col2: selected_rec_name_task = st.selectbox("Recruiter", options=["--- Select Recruiter ---"] + actual_recruiter_names, index=0, key="add_task_rec_link_sel")
            with link_col3: selected_comp_name_task = st.selectbox("Company", options=["--- Select Company ---"] + actual_company_names, index=0, key="add_task_comp_link_sel")

            new_task_notes = st.text_area("Additional Notes", key="add_task_notes_area")
            submit_add_task = st.form_submit_button("Add Task")

            if submit_add_task:
                is_valid_task_add = True
                if not new_task_desc or not new_task_status: st.error("Description and Status are required."); is_valid_task_add=False
                if is_valid_task_add:
                    task_job_id = job_options_map.get(selected_job_title_task) if selected_job_title_task != "--- Select Job ---" else None
                    task_rec_id = recruiter_options_map.get(selected_rec_name_task) if selected_rec_name_task != "--- Select Recruiter ---" else None
                    task_comp_id = company_options_map.get(selected_comp_name_task) if selected_comp_name_task != "--- Select Company ---" else None
                    final_task_priority = new_task_priority if new_task_priority != "---" else None
                    if add_new_task(conn, new_task_desc, new_task_due_date, new_task_status, final_task_priority, new_task_notes, task_job_id, task_rec_id, task_comp_id):
                        st.success("Task added!"); st.rerun()
    
    with tab_edit_delete_task:
        st.subheader("✏️ Edit or 🗑️ Delete Task")
        all_tasks_for_sel_task = get_all_tasks(conn)
        if not all_tasks_for_sel_task: st.info("No tasks to edit/delete.")
        else:
            task_map_for_sel = {
                f"{idx+1}. {task['task_description'][:40]}{'...' if len(task['task_description']) > 40 else ''} (Due: {task['due_date'].strftime('%y-%m-%d') if task.get('due_date') else 'N/A'}, ID:{task['task_id']})": task['task_id']
                for idx, task in enumerate(all_tasks_for_sel_task)
            }
            task_disp_list_sel = ["--- Select Task ---"] + list(task_map_for_sel.keys())
            sel_task_disp_str = st.selectbox("Select Task:", task_disp_list_sel, index=0, key="sel_task_to_edit_delete")

            if sel_task_disp_str and sel_task_disp_str != "--- Select Task ---":
                st.session_state.selected_task_id_for_edit = task_map_for_sel[sel_task_disp_str]
            else: st.session_state.selected_task_id_for_edit = None
            
            if st.session_state.selected_task_id_for_edit:
                task_dets = get_task_details(conn, st.session_state.selected_task_id_for_edit)
                if task_dets:
                    with st.form("edit_task_form_task_page"): # Unique form key
                        st.markdown(f"**Editing Task ID: {task_dets['task_id']}** - *{task_dets.get('task_description','')}*")
                        edit_task_desc = st.text_area("Description*", value=task_dets.get('task_description',''))
                        edit_col_task1, edit_col_task2 = st.columns(2)
                        with edit_col_task1:
                            edit_task_due = st.date_input("Due Date", value=task_dets.get('due_date'))
                            edit_stat_idx = task_status_options.index(task_dets['status']) if task_dets.get('status') in task_status_options else 0
                            edit_task_stat = st.selectbox("Status*", options=task_status_options, index=edit_stat_idx)
                        with edit_col_task2:
                            edit_prio_idx = task_priority_options.index(task_dets['priority']) if task_dets.get('priority') in task_priority_options else 0
                            edit_task_prio = st.selectbox("Priority", options=task_priority_options, index=edit_prio_idx)
                        
                        st.markdown("**Link Task to (Optional):**")
                        edit_link_col_task1, edit_link_col_task2, edit_link_col_task3 = st.columns(3)
                        # Pre-selection logic for linked items
                        def get_select_idx(current_id, options_map, actual_options_list, placeholder="--- Select ---"):
                            if actual_options_list and current_id:
                                for name, id_val in options_map.items():
                                    if id_val == current_id and name in actual_options_list:
                                        return ([placeholder] + actual_options_list).index(name)
                            return 0 # Default to placeholder
                        
                        edit_job_sel_idx = get_select_idx(task_dets.get('job_id'), job_options_map, actual_job_titles, "--- Select Job ---")
                        edit_rec_sel_idx = get_select_idx(task_dets.get('recruiter_id'), recruiter_options_map, actual_recruiter_names, "--- Select Recruiter ---")
                        edit_comp_sel_idx = get_select_idx(task_dets.get('company_id'), company_options_map, actual_company_names, "--- Select Company ---")

                        with edit_link_col_task1: sel_edit_job_task = st.selectbox("Job", options=["--- Select Job ---"]+actual_job_titles, index=edit_job_sel_idx)
                        with edit_link_col_task2: sel_edit_rec_task = st.selectbox("Recruiter", options=["--- Select Recruiter ---"]+actual_recruiter_names, index=edit_rec_sel_idx)
                        with edit_link_col_task3: sel_edit_comp_task = st.selectbox("Company", options=["--- Select Company ---"]+actual_company_names, index=edit_comp_sel_idx)
                        
                        edit_task_notes = st.text_area("Notes", value=task_dets.get('notes',''))
                        update_task_btn = st.form_submit_button("Update Task")
                        if update_task_btn:
                            is_valid_edit_t = True # validation
                            edit_task_j_id = job_options_map.get(sel_edit_job_task) if sel_edit_job_task != "--- Select Job ---" else None
                            edit_task_r_id = recruiter_options_map.get(sel_edit_rec_task) if sel_edit_rec_task != "--- Select Recruiter ---" else None
                            edit_task_c_id = company_options_map.get(sel_edit_comp_task) if sel_edit_comp_task != "--- Select Company ---" else None
                            edit_task_prio_val = edit_task_prio if edit_task_prio != "---" else None
                            if not edit_task_desc or not edit_task_stat: st.error("Desc and Status required"); is_valid_edit_t=False
                            if is_valid_edit_t:
                                if update_task_details(conn,task_dets['task_id'],edit_task_desc,edit_task_due,edit_task_stat,edit_task_prio_val,edit_task_notes,edit_task_j_id,edit_task_r_id,edit_task_c_id):
                                    st.success("Task updated!"); st.session_state.selected_task_id_for_edit=None; st.rerun()
                    # Delete action
                    st.markdown("---")
                    if st.button(f"Request to Delete Task ID {task_dets['task_id']}", key=f"del_req_btn_task_{task_dets['task_id']}"):
                        st.session_state.confirm_delete_task_id = task_dets['task_id']; st.rerun()
                    if st.session_state.confirm_delete_task_id == task_dets['task_id']:
                        st.error(f"FINAL WARNING: Delete task '{task_dets.get('task_description', 'this task')[:50]}...'?")
                        col_confirm_task, col_cancel_task = st.columns(2)
                        with col_confirm_task:
                            if st.button("YES, Delete Task Now", type="primary", key=f"final_del_btn_task_{task_dets['task_id']}"):
                                if delete_task_record(conn, task_dets['task_id']):
                                    st.success("Task deleted!"); st.session_state.selected_task_id_for_edit=None; st.session_state.confirm_delete_task_id=None; st.rerun()
                        with col_cancel_task:
                            if st.button("Cancel Task Deletion", key=f"cancel_del_btn_task_{task_dets['task_id']}"):
                                st.session_state.confirm_delete_task_id=None; st.rerun()
                elif st.session_state.selected_task_id_for_edit: 
                    st.warning("Could not load selected task."); st.session_state.selected_task_id_for_edit=None

    with tab_view_tasks:
        st.subheader("📋 View All Tasks")
        all_tasks_data_disp = get_all_tasks(conn)
        if all_tasks_data_disp:
            tasks_df_disp = []
            for tr_row in all_tasks_data_disp:
                task_d_dict = {
                    "Description": tr_row.get('task_description'),
                    "Due": tr_row.get('due_date').strftime('%Y-%m-%d') if tr_row.get('due_date') else 'N/A',
                    "Status": tr_row.get('status'), "Priority": tr_row.get('priority') or 'N/A', "Related": [],
                    "Notes": tr_row.get('notes', '')
                }
                if tr_row.get('job_title'): task_d_dict["Related"].append(f"J: {tr_row['job_title'][:15]}..")
                if tr_row.get('recruiter_name'): task_d_dict["Related"].append(f"R: {tr_row['recruiter_name'][:15]}..")
                if tr_row.get('related_company_name'): task_d_dict["Related"].append(f"C: {tr_row['related_company_name'][:15]}..")
                task_d_dict["Related"] = ", ".join(task_d_dict["Related"]) if task_d_dict["Related"] else "None"
                tasks_df_disp.append(task_d_dict)
            cols_order_task = ["Description", "Due", "Status", "Priority", "Related", "Notes"]
            st.dataframe(tasks_df_disp, column_order=cols_order_task, use_container_width=True, hide_index=True)
        else: st.info("No tasks found yet.")