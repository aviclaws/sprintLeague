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
    st.session_state.running = False  # green
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
    st.title(
        f"⏱️ Stopwatch — {st.session_state.get('name')} {TEAM_LOGOS[all_users[st.session_state.username].get('team')]}"
    )
    is_admin = all_users[st.session_state.username]["admin"]
    if is_admin:
        with st.expander("Update Teams", expanded=False):
            user_team_df = pd.DataFrame(
                {"username": list(all_users), "team": [all_users[u]["team"] for u in all_users]}
            )

            # Keep editable state
            if "user_team_df" not in st.session_state:
                st.session_state.df = user_team_df

            edited_user_team_df = st.data_editor(
                user_team_df,
                num_rows="fixed",
                width="content",
                column_config={
                    "username": st.column_config.TextColumn(
                        label="username", help="Unique user id", required=True, disabled=True
                    ),
                    "team": st.column_config.SelectboxColumn(
                        label="team", options=["White", "Blue", "Coach"], required=True
                    ),
                },
            )
            if st.button("Update Teams", key="update_teams"):
                usernames_to_update = edited_user_team_df["username"].tolist()
                teams_to_update = edited_user_team_df["team"].tolist()
                for u, t in zip(usernames_to_update, teams_to_update):
                    st.session_state.config["credentials"]["usernames"][u]["team"] = t
                with open("config.yaml", "w") as f:
                    yaml.dump(st.session_state.config, f)

    col1, col2 = st.columns([2, 1])
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
            st.session_state.btn_label = "▶️ Start"
            st.rerun()

    if st.session_state.running:
        st.session_state.time = time.time() - st.session_state.start_time

    curr_time_col, avg_time_col = st.columns(2)
    with curr_time_col:
        st.metric("Time (s)", f"{st.session_state.time:.2f}")
    with avg_time_col:
        df = load_times()
        today = datetime.now(timezone(timedelta(hours=-5))).date()
        user_df = df[df["username"] == st.session_state.username].copy()
        user_df = user_df[user_df["saved_at_date"] == str(today)]
        avg_time = user_df["time"].sum() / max(1, user_df.shape[0])
        st.metric("Avg Time (s)", value=f"{avg_time:.2f}")

    if st.button("💾 Save Time", key="save_time"):
        if st.session_state.time > 0 and not st.session_state.running:
            save_time(
                username=st.session_state.username,
                team=st.session_state.config["credentials"]["usernames"][st.session_state.username]["team"],
                time=float(st.session_state.time),
            )
            st.success("Saved time successfully!")
            st.session_state.time = 0
            st.rerun()
        elif st.session_state.time == 0:
            st.warning("You need to start the stopwatch first.")
        elif st.session_state.running:
            st.toast("You need to stop the stopwatch first.")

    st.divider()
    st.subheader(":trophy: Leader Board")

    if df.empty:
        st.info("No times saved yet.")
    else:
        df["time"] = df["time"].round(2)
        team_colors = ["Blue", "White"]
        edited_team_times_df = [None, None]
        color_cols = st.columns(2)
        for i, color_col in enumerate(color_cols):
            with color_col:
                color_df = df.copy()
                color_df = color_df[(color_df["team"] == team_colors[i]) & (color_df["saved_at_date"] == str(today))]
                color_df = color_df.drop(["team", "saved_at_date"], axis=1)
                # Make sure the index isn't shown/kept as a column
                color_df = color_df.reset_index(drop=True)  # removes the index
                color_df.index.name = None  # extra safety

                st.metric(
                    label=f"{team_colors[i]} Team Time {TEAM_LOGOS[team_colors[i]]}",
                    value=round(color_df["time"].sum(), 2),
                )

                if not is_admin:
                    st.dataframe(
                        color_df.drop(["id"], axis=1),
                        column_order=["username", "time", "sprint_number"],
                        width="content",
                        hide_index=True,
                    )
                else:
                    edited_team_times_df[i] = st.data_editor(
                        color_df,
                        num_rows="dynamic",
                        hide_index=True,
                        width="content",
                        column_order=["username", "time", "sprint_number", "id"],
                        column_config={
                            "id": st.column_config.NumberColumn(label="id", help="Row id (read-only)", disabled=True),
                            "username": st.column_config.SelectboxColumn(
                                label="username",
                                options=[u for u in all_users if all_users[u]["team"] == team_colors[i]],
                                required=True,
                            ),
                            "sprint_number": st.column_config.NumberColumn(
                                label="sprint_number", required=True, min_value=1, format="%d"
                            ),
                            "time": st.column_config.NumberColumn(
                                label="time", required=True, min_value=0.01, format="%.2f"
                            ),
                        },
                    )
        if is_admin:
            if st.button("Update Times", key="update_time"):
                for i, team in enumerate(team_colors):
                    edited = edited_team_times_df[i]
                    if edited is None:
                        continue  # non-admin view or no table rendered

                    # Ensure proper dtypes and presence of 'id'
                    edited = edited.copy()
                    if "id" not in edited.columns:
                        edited["id"] = pd.NA

                    # Coerce numeric fields safely
                    if "sprint_number" in edited:
                        edited["sprint_number"] = edited["sprint_number"].astype("Int64")
                    if "time" in edited:
                        edited["time"] = edited["time"].astype(float)

                    # Load fresh snapshot of what's in DB for this team/today
                    original = load_team_today(team)

                    # --- Deletes ---
                    edited_ids = set(edited["id"].dropna().astype(int).tolist())
                    original_ids = set(original["id"].tolist())
                    to_delete = list(original_ids - edited_ids)
                    if to_delete:
                        delete_time_by_ids(to_delete)

                    # --- Inserts & Updates ---
                    orig_by_id = {int(r.id): r for _, r in original.iterrows()}

                    for _, row in edited.iterrows():
                        row_id = row["id"]
                        if pd.isna(row_id):
                            insert_time(
                                str(row["username"]).strip(),
                                team,
                                int(row["sprint_number"]),
                                float(row["time"]),
                                str(datetime.now(timezone(timedelta(hours=-5))).date()),
                                datetime.now(timezone(timedelta(hours=-5))).isoformat(),
                            )
                        else:
                            # UPDATE if any values changed
                            rid = int(row_id)
                            o = orig_by_id.get(rid)
                            if o is None:
                                insert_time(
                                    str(row["username"]).strip(),
                                    team,
                                    int(row["sprint_number"]),
                                    float(row["time"]),
                                    str(datetime.now(timezone(timedelta(hours=-5))).date()),
                                    datetime.now(timezone(timedelta(hours=-5))).isoformat(),
                                )
                            else:
                                if (
                                    str(o["username"]) != str(row["username"]).strip()
                                    or int(o["sprint_number"]) != int(row["sprint_number"])
                                    or float(o["time"]) != float(row["time"])
                                ):
                                    update_time(
                                        rid, str(row["username"]).strip(), int(row["sprint_number"]), float(row["time"])
                                    )

                st.success("Times updated.")
                st.rerun()

        if is_admin:
            csv = df.to_csv(index=False).encode("utf-8")
            st.download_button("⬇️ Download CSV", data=csv, file_name="my_times.csv", mime="text/csv")

            with st.expander("🗑️ Delete a saved run"):
                sprint_number = st.number_input(label="Enter Sprint Number to Delete", min_value=1, step=1)
                del_username = st.selectbox(
                    label="Username to delete", options=st.session_state.config["credentials"]["usernames"]
                )
                if st.button("Delete"):
                    delete_time(del_username, int(sprint_number))
                    st.success(f"Deleted run #{int(sprint_number)}.")
                    st.rerun()

    if st.session_state.running:
        time.sleep(0.1)
        st.rerun()
