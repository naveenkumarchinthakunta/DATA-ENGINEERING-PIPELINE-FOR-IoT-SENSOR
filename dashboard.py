"""
Streamlit and Plotly Industrial IoT Monitoring Dashboard.
Provides a live-style 6-page interactive operational center connected directly
to the processed SQLite database and analytics engine.
"""

from datetime import datetime, timezone, timedelta
import json
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from storage.database import get_db_session, init_db
from storage.repositories import (
    SensorRepository,
    ProcessedDataRepository,
    RejectedDataRepository,
    AlertRepository,
    PipelineRunRepository,
)
from processing.aggregation import AnalyticsEngine
from pipeline.pipeline_runner import PipelineRunner
from config.settings import settings

# Streamlit Page Setup
st.set_page_config(
    page_title="IoT Industrial Telemetry & Quality Pipeline",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling for Industrial Dashboard
st.markdown("""
<style>
    .main-header {
        font-size: 26px;
        font-weight: 700;
        color: #1E293B;
        margin-bottom: 0px;
    }
    .sub-header {
        font-size: 14px;
        color: #64748B;
        margin-bottom: 20px;
    }
    .metric-card {
        background-color: #F8FAFC;
        border-radius: 8px;
        padding: 16px;
        border: 1px solid #E2E8F0;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .status-badge-active {
        color: #16A34A;
        font-weight: bold;
    }
    .status-badge-crit {
        color: #DC2626;
        font-weight: bold;
    }
    .status-badge-warn {
        color: #D97706;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)


# Sidebar Navigation & Execution Controls
st.sidebar.image("https://img.icons8.com/fluency/96/factory.png", width=64)
st.sidebar.title("Factory Telemetry")
st.sidebar.caption("IoT Data Engineering & Machine Health")

nav_choice = st.sidebar.radio(
    "Navigation",
    [
        "🏭 Factory Overview",
        "📡 Sensor Monitoring",
        "📈 Historical Trends",
        "🛡️ Data Quality & Quarantine",
        "🚨 Machine Health Alerts",
        "⚙️ Pipeline Operations",
    ],
)

st.sidebar.divider()
st.sidebar.subheader("Pipeline Controls")

if st.sidebar.button("▶️ Run Ingestion Cycle", use_container_width=True):
    with st.spinner("Executing pipeline cycle (Simulation -> Ingestion -> Validation -> Alerts)..."):
        runner = PipelineRunner()
        summary = runner.run_cycle()
        st.sidebar.success(f"Run completed: {summary.records_processed} valid, {summary.records_rejected} quarantined.")
        st.rerun()

st.sidebar.caption(f"DB Engine: SQLite (Local) | Sensors: {settings.simulation.total_sensors}")


# -------------------------------------------------------------------------------------------------
# PAGE 1: FACTORY OVERVIEW
# -------------------------------------------------------------------------------------------------
if nav_choice == "🏭 Factory Overview":
    st.markdown('<p class="main-header">🏭 Factory Overview & System Health</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Real-time status of 200 factory sensors, data quality yield, and operational anomalies.</p>', unsafe_allow_html=True)

    with get_db_session() as session:
        analytics = AnalyticsEngine(session)
        summary = analytics.get_overall_summary()

    # Top KPI Metrics Cards
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    with c1:
        st.metric("Total Sensors", summary["total_registered_sensors"])
    with c2:
        st.metric("Active Reporting", summary["active_sensors"], f"{summary['inactive_sensors']} Inactive")
    with c3:
        st.metric("Data Quality Yield", f"{summary['validation_success_rate']}%", f"{summary['data_rejection_rate']}% Rej")
    with c4:
        st.metric("Processed Telemetry", summary["total_processed_records"])
    with c5:
        st.metric("Active Alerts", summary["active_alerts"], f"{summary['total_alerts']} Total", delta_color="inverse")
    with c6:
        st.metric("Pipeline Health", f"{summary['pipeline_success_rate']}%", f"{summary['pipeline_runs_count']} Runs")

    st.divider()

    # Telemetry Global Averages & Distributions
    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("Global Process Telemetry Averages")
        m_t, m_p, m_v = st.columns(3)
        with m_t:
            st.metric("Avg Temperature", f"{summary['temperature_stats']['avg']} °C", f"Max: {summary['temperature_stats']['max']} °C")
        with m_p:
            st.metric("Avg Pressure", f"{summary['pressure_stats']['avg']} bar", f"Max: {summary['pressure_stats']['max']} bar")
        with m_v:
            st.metric("Avg Vibration", f"{summary['vibration_stats']['avg']} mm/s", f"Max: {summary['vibration_stats']['max']} mm/s")

        with get_db_session() as session:
            sensor_repo = SensorRepository(session)
            all_sensors = sensor_repo.get_all()
            if all_sensors:
                zone_counts = pd.DataFrame([s.to_dict() for s in all_sensors])["factory_zone"].value_counts().reset_index()
                zone_counts.columns = ["Zone", "Sensors"]
                fig_zone = px.pie(zone_counts, values="Sensors", names="Zone", title="Sensor Distribution by Factory Zone", hole=0.4)
                fig_zone.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=300)
                st.plotly_chart(fig_zone, use_container_width=True)

    with col_right:
        st.subheader("Operational Alert Breakdown")
        with get_db_session() as session:
            alert_repo = AlertRepository(session)
            sev_counts = alert_repo.get_counts_by_severity()

        if sev_counts:
            sev_df = pd.DataFrame(list(sev_counts.items()), columns=["Severity", "Count"])
            color_map = {"CRITICAL": "#DC2626", "WARNING": "#F59E0B", "INFO": "#3B82F6"}
            fig_sev = px.bar(
                sev_df,
                x="Severity",
                y="Count",
                color="Severity",
                color_discrete_map=color_map,
                title="Active & Historical Alerts by Severity",
            )
            fig_sev.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=300)
            st.plotly_chart(fig_sev, use_container_width=True)
        else:
            st.info("No operational alerts recorded in database yet. Run a pipeline cycle to ingest telemetry.")


# -------------------------------------------------------------------------------------------------
# PAGE 2: SENSOR MONITORING
# -------------------------------------------------------------------------------------------------
elif nav_choice == "📡 Sensor Monitoring":
    st.markdown('<p class="main-header">📡 Real-Time Sensor Telemetry Matrix</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Live monitoring grid across all 200 sensors, machine assignments, and measurement status.</p>', unsafe_allow_html=True)

    with get_db_session() as session:
        sensor_repo = SensorRepository(session)
        sensors = sensor_repo.get_all()

    if not sensors:
        st.warning("Database has no sensor records registered yet. Please click 'Run Ingestion Cycle' in the sidebar.")
    else:
        sensor_list = [s.to_dict() for s in sensors]
        sdf = pd.DataFrame(sensor_list)

        # Interactive Filtering
        col_f1, col_f2, col_f3 = st.columns(3)
        with col_f1:
            selected_zone = st.selectbox("Filter by Factory Zone", ["All"] + sorted(sdf["factory_zone"].unique().tolist()))
        with col_f2:
            selected_status = st.selectbox("Filter by Sensor Status", ["All"] + sorted(sdf["sensor_status"].unique().tolist()))
        with col_f3:
            search_sensor = st.text_input("Search Sensor ID / Machine ID", "").strip().upper()

        filtered_df = sdf.copy()
        if selected_zone != "All":
            filtered_df = filtered_df[filtered_df["factory_zone"] == selected_zone]
        if selected_status != "All":
            filtered_df = filtered_df[filtered_df["sensor_status"] == selected_status]
        if search_sensor:
            filtered_df = filtered_df[
                filtered_df["sensor_id"].str.contains(search_sensor)
                | filtered_df["machine_id"].str.contains(search_sensor)
            ]

        st.caption(f"Showing {len(filtered_df)} of {len(sdf)} registered sensors")

        # Join latest processed reading for each sensor
        with get_db_session() as session:
            proc_repo = ProcessedDataRepository(session)
            recent_readings = proc_repo.get_recent_readings(limit=400)

        latest_map = {}
        for r in recent_readings:
            if r.sensor_id not in latest_map:
                latest_map[r.sensor_id] = {
                    "temp_c": r.temperature_celsius,
                    "press_bar": r.pressure_bar,
                    "vib_mms": r.vibration_mm_s,
                    "last_seen": r.event_timestamp.strftime("%Y-%m-%d %H:%M:%S") if r.event_timestamp else "N/A",
                }

        filtered_df["Latest Temp (°C)"] = filtered_df["sensor_id"].apply(lambda s: latest_map.get(s, {}).get("temp_c", "No Data"))
        filtered_df["Latest Pressure (bar)"] = filtered_df["sensor_id"].apply(lambda s: latest_map.get(s, {}).get("press_bar", "No Data"))
        filtered_df["Latest Vibration (mm/s)"] = filtered_df["sensor_id"].apply(lambda s: latest_map.get(s, {}).get("vib_mms", "No Data"))
        filtered_df["Last Event UTC"] = filtered_df["sensor_id"].apply(lambda s: latest_map.get(s, {}).get("last_seen", "No Data"))

        st.dataframe(
            filtered_df[[
                "sensor_id",
                "machine_id",
                "factory_zone",
                "sensor_status",
                "Latest Temp (°C)",
                "Latest Pressure (bar)",
                "Latest Vibration (mm/s)",
                "Last Event UTC",
            ]],
            use_container_width=True,
            height=500,
        )


# -------------------------------------------------------------------------------------------------
# PAGE 3: HISTORICAL TRENDS
# -------------------------------------------------------------------------------------------------
elif nav_choice == "📈 Historical Trends":
    st.markdown('<p class="main-header">📈 Sensor Telemetry Historical Trends</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Time-series measurements plotted against machine operating thresholds.</p>', unsafe_allow_html=True)

    with get_db_session() as session:
        sensor_repo = SensorRepository(session)
        sensors = sensor_repo.get_all()

    if not sensors:
        st.warning("No sensors found. Please execute an ingestion cycle.")
    else:
        sensor_ids = [s.sensor_id for s in sensors]
        selected_sensor_id = st.selectbox("Select Sensor for Detailed Inspection", sensor_ids)

        sensor_meta = next((s for s in sensors if s.sensor_id == selected_sensor_id), None)

        with get_db_session() as session:
            proc_repo = ProcessedDataRepository(session)
            readings, total = proc_repo.get_readings_by_sensor(selected_sensor_id, page=1, per_page=200)

        if not readings:
            st.info(f"No telemetry readings recorded yet for sensor {selected_sensor_id}.")
        else:
            rdf = pd.DataFrame([r.to_dict() for r in readings])
            rdf["event_timestamp"] = pd.to_datetime(rdf["event_timestamp"])
            rdf = rdf.sort_values("event_timestamp")

            c_t, c_p, c_v = st.columns(3)
            with c_t:
                st.metric("Readings Count", len(rdf))
            with c_p:
                st.metric("Assigned Machine", sensor_meta.machine_id if sensor_meta else "N/A")
            with c_v:
                st.metric("Factory Zone", sensor_meta.factory_zone if sensor_meta else "N/A")

            # Temperature Chart with Threshold Overlay
            fig_temp = px.line(
                rdf,
                x="event_timestamp",
                y="temperature_celsius",
                title=f"Temperature (°C) Trend - {selected_sensor_id}",
                markers=True,
            )
            if sensor_meta:
                fig_temp.add_hline(
                    y=sensor_meta.temperature_limit_max,
                    line_dash="dash",
                    line_color="red",
                    annotation_text=f"Max Limit ({sensor_meta.temperature_limit_max}°C)",
                )
                fig_temp.add_hline(
                    y=sensor_meta.temperature_limit_min,
                    line_dash="dash",
                    line_color="blue",
                    annotation_text=f"Min Limit ({sensor_meta.temperature_limit_min}°C)",
                )
            fig_temp.update_layout(margin=dict(t=40, b=20, l=10, r=10), height=320)
            st.plotly_chart(fig_temp, use_container_width=True)

            # Pressure and Vibration side-by-side
            c1, c2 = st.columns(2)
            with c1:
                fig_press = px.line(
                    rdf,
                    x="event_timestamp",
                    y="pressure_bar",
                    title=f"Pressure (bar) Trend - {selected_sensor_id}",
                    markers=True,
                    color_discrete_sequence=["#10B981"],
                )
                if sensor_meta:
                    fig_press.add_hline(
                        y=sensor_meta.pressure_limit_max,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=f"Max Limit ({sensor_meta.pressure_limit_max} bar)",
                    )
                fig_press.update_layout(margin=dict(t=40, b=20, l=10, r=10), height=300)
                st.plotly_chart(fig_press, use_container_width=True)

            with c2:
                fig_vib = px.line(
                    rdf,
                    x="event_timestamp",
                    y="vibration_mm_s",
                    title=f"Vibration (mm/s) Trend - {selected_sensor_id}",
                    markers=True,
                    color_discrete_sequence=["#8B5CF6"],
                )
                if sensor_meta:
                    fig_vib.add_hline(
                        y=sensor_meta.vibration_limit_max,
                        line_dash="dash",
                        line_color="red",
                        annotation_text=f"Max Limit ({sensor_meta.vibration_limit_max} mm/s)",
                    )
                fig_vib.update_layout(margin=dict(t=40, b=20, l=10, r=10), height=300)
                st.plotly_chart(fig_vib, use_container_width=True)


# -------------------------------------------------------------------------------------------------
# PAGE 4: DATA QUALITY & QUARANTINE
# -------------------------------------------------------------------------------------------------
elif nav_choice == "🛡️ Data Quality & Quarantine":
    st.markdown('<p class="main-header">🛡️ Data Quality & Quarantine Isolation</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Inspection of quarantined records, validation rejection reasons, and schema conformance.</p>', unsafe_allow_html=True)

    with get_db_session() as session:
        rej_repo = RejectedDataRepository(session)
        proc_repo = ProcessedDataRepository(session)
        raw_repo = RawDataRepository(session)

        rejection_summary = rej_repo.get_rejection_summary()
        recent_rejections = rej_repo.get_recent_rejections(limit=50)
        total_rej = rej_repo.count()
        total_valid = proc_repo.count()
        total_raw = raw_repo.count()

    q1, q2, q3, q4 = st.columns(4)
    with q1:
        st.metric("Total Raw Ingested", total_raw)
    with q2:
        st.metric("Passed Validation", total_valid)
    with q3:
        st.metric("Quarantined Records", total_rej)
    with q4:
        total_eval = total_valid + total_rej
        pass_rate = round((total_valid / total_eval) * 100.0, 2) if total_eval > 0 else 100.0
        st.metric("Validation Pass Rate", f"{pass_rate}%")

    st.divider()

    col_chart, col_table = st.columns([1, 1])

    with col_chart:
        st.subheader("Rejection Reasons Breakdown")
        if rejection_summary:
            rdf = pd.DataFrame(rejection_summary)
            fig_reasons = px.bar(
                rdf,
                x="count",
                y="reason",
                orientation="h",
                color="count",
                color_continuous_scale="Reds",
                title="Quarantined Records by Failure Category",
            )
            fig_reasons.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=350, yaxis={'categoryorder':'total ascending'})
            st.plotly_chart(fig_reasons, use_container_width=True)
        else:
            st.info("No records quarantined yet.")

    with col_table:
        st.subheader("Data Quarantine Log")
        if recent_rejections:
            rej_data = [
                {
                    "Rejection ID": r.rejection_id,
                    "Event ID": r.event_id,
                    "Sensor ID": r.sensor_id,
                    "Reason": r.rejection_reason,
                    "Timestamp": r.rejection_timestamp.strftime("%Y-%m-%d %H:%M:%S") if r.rejection_timestamp else "N/A",
                }
                for r in recent_rejections
            ]
            st.dataframe(pd.DataFrame(rej_data), use_container_width=True, height=350)
        else:
            st.info("Quarantine table is currently empty.")


# -------------------------------------------------------------------------------------------------
# PAGE 5: MACHINE HEALTH ALERTS
# -------------------------------------------------------------------------------------------------
elif nav_choice == "🚨 Machine Health Alerts":
    st.markdown('<p class="main-header">🚨 Machine Health & Operational Alerts</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Threshold violation monitoring, severity classifications, and operator acknowledgements.</p>', unsafe_allow_html=True)

    with get_db_session() as session:
        alert_repo = AlertRepository(session)
        alerts, total = alert_repo.get_alerts(page=1, per_page=100)
        sev_counts = alert_repo.get_counts_by_severity()

    a1, a2, a3, a4 = st.columns(4)
    with a1:
        st.metric("Total Generated Alerts", total)
    with a2:
        st.metric("Critical Alerts", sev_counts.get("CRITICAL", 0))
    with a3:
        st.metric("Warning Alerts", sev_counts.get("WARNING", 0))
    with a4:
        active_count = len([a for a in alerts if a.alert_status == "ACTIVE"])
        st.metric("Active (Unacknowledged)", active_count)

    st.divider()

    if not alerts:
        st.info("No machine health alerts recorded in database.")
    else:
        adf = pd.DataFrame([a.to_dict() for a in alerts])

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            sel_sev = st.selectbox("Filter Severity", ["All"] + sorted(adf["severity"].unique().tolist()))
        with col_f2:
            sel_stat = st.selectbox("Filter Status", ["All"] + sorted(adf["alert_status"].unique().tolist()))

        filtered_adf = adf.copy()
        if sel_sev != "All":
            filtered_adf = filtered_adf[filtered_adf["severity"] == sel_sev]
        if sel_stat != "All":
            filtered_adf = filtered_adf[filtered_adf["alert_status"] == sel_stat]

        st.dataframe(
            filtered_adf[[
                "alert_id",
                "severity",
                "alert_type",
                "machine_id",
                "sensor_id",
                "measured_value",
                "configured_threshold",
                "alert_timestamp",
                "alert_status",
            ]],
            use_container_width=True,
            height=400,
        )

        # Acknowledgement action
        active_alert_ids = [a.alert_id for a in alerts if a.alert_status == "ACTIVE"]
        if active_alert_ids:
            st.subheader("Operator Acknowledgement")
            ack_col1, ack_col2 = st.columns([3, 1])
            with ack_col1:
                target_ack = st.selectbox("Select Alert to Acknowledge", active_alert_ids)
            with ack_col2:
                if st.button("Acknowledge Alert"):
                    with get_db_session() as session:
                        repo = AlertRepository(session)
                        repo.acknowledge_alert(target_ack)
                    st.success(f"Alert {target_ack} marked as ACKNOWLEDGED.")
                    st.rerun()


# -------------------------------------------------------------------------------------------------
# PAGE 6: PIPELINE OPERATIONS
# -------------------------------------------------------------------------------------------------
elif nav_choice == "⚙️ Pipeline Operations":
    st.markdown('<p class="main-header">⚙️ Data Pipeline Orchestration & Run History</p>', unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Execution logs, stage-by-stage latencies, throughput metrics, and audit records.</p>', unsafe_allow_html=True)

    with get_db_session() as session:
        run_repo = PipelineRunRepository(session)
        runs = run_repo.get_recent_runs(limit=25)

    if not runs:
        st.info("No pipeline execution runs found in the database. Use 'Run Ingestion Cycle' in the sidebar to execute.")
    else:
        run_list = [r.to_dict() for r in runs]
        rdf = pd.DataFrame(run_list)

        r1, r2, r3, r4 = st.columns(4)
        with r1:
            st.metric("Total Executed Cycles", len(rdf))
        with r2:
            completed = len(rdf[rdf["execution_status"] == "COMPLETED"])
            st.metric("Completed Cycles", completed)
        with r3:
            total_proc = rdf["records_processed"].sum()
            st.metric("Total Records Processed", int(total_proc))
        with r4:
            total_rej = rdf["records_rejected"].sum()
            st.metric("Total Records Quarantined", int(total_rej))

        st.divider()

        st.subheader("Recent Execution Runs")
        st.dataframe(
            rdf[[
                "run_id",
                "start_timestamp",
                "end_timestamp",
                "execution_status",
                "records_received",
                "records_processed",
                "records_rejected",
                "error_count",
            ]],
            use_container_width=True,
            height=300,
        )

        # Stage Timing breakdown for the latest run
        latest_run = runs[0]
        if latest_run.execution_summary:
            try:
                summary_data = json.loads(latest_run.execution_summary)
                timings = summary_data.get("stage_timings", {})
                if timings:
                    st.subheader(f"Stage Latency Breakdown for Run: {latest_run.run_id}")
                    timing_df = pd.DataFrame(list(timings.items()), columns=["Pipeline Stage", "Duration (ms)"])
                    fig_stage = px.bar(
                        timing_df,
                        x="Pipeline Stage",
                        y="Duration (ms)",
                        color="Pipeline Stage",
                        title="Execution Duration per Pipeline Stage (ms)",
                    )
                    fig_stage.update_layout(margin=dict(t=40, b=10, l=10, r=10), height=280)
                    st.plotly_chart(fig_stage, use_container_width=True)
            except Exception:
                pass
