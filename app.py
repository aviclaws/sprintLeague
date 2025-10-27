import time
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as st_auth

from database import *
from constants import *


st.set_page_config(page_title="Stopwatch with Login & DB", page_icon="⏱️", layout="centered")

init_db()

# --- SESSION STATE ---
if "authentication_status" not in st.session_state:
    st.session_state.authentication_status = None
if "authenticator" not in st.session_state:
    st.session_state.authenticator = None
if "config" not in st.session_state:
    st.session_state.config = None
if "username" not in st.session_state:
    st.session_state.username = ""
if "start_time" not in st.session_state:
    st.session_state.start_time = None
if "time" not in st.session_state:
    st.session_state.time = 0.0
if "running" not in st.session_state:
    st.session_state.running = False # green
if "btn_label" not in st.session_state:
    st.session_state.btn_label = "▶️ Start"

# --- load config ---
if not st.session_state.config:
    with open("config.yaml") as f:
        st.session_state.config = yaml.load(f, Loader=SafeLoader)

# --- authenticator ---
if not st.session_state.authentication_status:
    st.session_state.authenticator = st_auth.Authenticate(
        st.session_state.config["credentials"],
        st.session_state.config["cookie"]["name"],
        st.session_state.config["cookie"]["key"],
        st.session_state.config["cookie"]["expiry_days"],
    )

    # --- login UI (main area) ---
    st.session_state.authenticator.login("main")

if st.session_state.get("authentication_status") is False:
    st.error("Invalid username or password")
    st.session_state.time = 0.0
    st.session_state.running = False
elif st.session_state.get("authentication_status") is None:
    st.warning("Please enter your username and password")
elif st.session_state.get("authentication_status"):
    # --- logged-in content ---
    st.sidebar.success(f"Signed in as {st.session_state.username}")
    st.session_state.authenticator.logout(button_name="Log out", location="sidebar")


    all_users = st.session_state.config["credentials"]["usernames"]
    st.title(f"⏱️ Stopwatch — {st.session_state.name} {TEAM_LOGOS[all_users[st.session_state.username]["team"]]}")
    is_admin = all_users[st.session_state.username]["admin"]
    if is_admin:
        with st.expander("Update Teams",expanded=False):
            df = pd.DataFrame({
                "username": list(all_users),
                "team": [all_users[u]["team"] for u in all_users]
            })

            # Keep editable state
            if "df" not in st.session_state:
                st.session_state.df = df

            edited_df = st.data_editor(
                df,
                num_rows="fixed",
                use_container_width=True,
                column_config={
                    "username": st.column_config.TextColumn(label="username", help="Unique user id", required=True, disabled=True),
                    "team": st.column_config.SelectboxColumn(label="team", options=["White", "Blue", "Coach"], required=True),
                }
            )
            if st.button("Update Teams"):
                usernames_to_update = edited_df["username"].tolist()
                teams_to_update = edited_df["team"].tolist()
                for u, t in zip(usernames_to_update, teams_to_update):
                    st.session_state.config["credentials"]["usernames"][u]["team"] = t
                with open("config.yaml", "w") as f:
                    yaml.dump(st.session_state.config, f)

    col1, col2 = st.columns([2,1])
    with col1:

        if st.button(st.session_state.btn_label, width="stretch", key="start_stop_btn"):
            if not st.session_state.running:
                st.session_state.start_time = time.time() - st.session_state.time
                st.session_state.running = True
                st.session_state.btn_label = "⏸️ Stop"
            else:
                st.session_state.time = time.time() - st.session_state.start_time
                st.session_state.running = False
                st.session_state.btn_label = "▶️ Start"
            st.rerun()

    with col2:
        if st.button("🔁 Reset", width="stretch", key="reset_btn"):
            st.session_state.start_time = None
            st.session_state.time = 0.0
            st.session_state.running = False

    if st.session_state.running:
        st.session_state.time = time.time() - st.session_state.start_time

    st.metric("Time (s)", f"{st.session_state.time:.2f}")

    if st.button("💾 Save Time"):
        if st.session_state.time > 0:
            save_time(
                username=st.session_state.username,
                team=st.session_state.config["credentials"]["usernames"][st.session_state.username]["team"],
                time=float(st.session_state.time),
            )
            st.success("Saved time successfully!")
            st.rerun()
        else:
            st.warning("You need to start the stopwatch first.")

    df = load_times()
    today = datetime.now().date()
    user_df = df[df["username"] == st.session_state.username]
    user_df["saved_at"] = user_df["saved_at"].apply(lambda x: datetime.fromisoformat(x).date())
    user_df = user_df[user_df['saved_at'] == today]
    avg_time = user_df["time"].sum() / user_df.shape[0]
    st.metric("Avg Time (s)", value=f"{avg_time:.2f}")
    st.divider()
    st.subheader(":trophy: Leader Board")


    if df.empty:
        st.info("No times saved yet.")
    else:
        df["time"] = df["time"].round(2)
        df["saved_at"] = df["saved_at"].apply(lambda x: datetime.fromisoformat(x).date())
        team_colors = ["Blue", "White"]
        color_cols = st.columns(2)
        for i, color_col in enumerate(color_cols):
            with color_col:
                color_df = df.copy()
                color_df = color_df[(color_df["team"] == team_colors[i]) & (color_df['saved_at'] == today)]
                color_df = color_df.drop(['team', 'saved_at'], axis=1)
                st.metric(label=f"{team_colors[i]}Team Time {TEAM_LOGOS[team_colors[i]]}", value=round(color_df["time"].sum(), 2))
                st.dataframe(color_df, width="content", hide_index=True)

        if is_admin:
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download CSV", data=csv, file_name="my_times.csv", mime="text/csv")

            with st.expander("🗑️ Delete a saved run"):
                sprint_number = st.number_input(label="Enter Sprint Number to Delete", min_value=1, step=1)
                del_username = st.selectbox(label="Username to delete", options=st.session_state.config["credentials"]["usernames"])
                if st.button("Delete"):
                    delete_time(del_username, int(sprint_number))
                    st.success(f"Deleted run #{int(sprint_number)}.")
                    st.rerun()

    if st.session_state.running:
        time.sleep(0.1)
        st.rerun()

