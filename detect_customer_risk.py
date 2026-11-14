
import pandas as pd
from pathlib import Path

# ==========================================
# 1. FILE PATHS
# ==========================================

BASE = Path(__file__).resolve().parent

INPUT_FILE = (
    BASE / "customer_results" / "customer_analysis.csv"
)

OUTPUT = BASE / "customer_results"
OUTPUT.mkdir(exist_ok=True)

ALERTS_FILE = OUTPUT / "customer_alerts.csv"
TASKS_FILE = OUTPUT / "customer_tasks.csv"


# ==========================================
# 2. RISK DETECTION THRESHOLDS
# ==========================================

BUSINESS_SEGMENTS = ["SMB", "Enterprise"]

MIN_ORDERS = 5
MIN_HISTORY_DAYS = 90
MIN_INACTIVE_DAYS = 60

HIGH_RISK_RATIO = 2.0
CRITICAL_RISK_RATIO = 3.0


# ==========================================
# 3. LOAD CUSTOMER ANALYSIS
# ==========================================

customers = pd.read_csv(INPUT_FILE)

print("Customers loaded:", len(customers))

required_columns = [
    "customer_id",
    "segment",
    "total_orders",
    "customer_lifetime_days",
    "days_inactive",
    "avg_order_gap_days",
    "inactivity_ratio",
    "total_spent",
]

for column in required_columns:
    if column not in customers.columns:
        raise ValueError(
            f"Missing required column: {column}"
        )

# Make sure numeric columns contain numbers.
numeric_columns = [
    "total_orders",
    "customer_lifetime_days",
    "days_inactive",
    "avg_order_gap_days",
    "inactivity_ratio",
    "total_spent",
]

for column in numeric_columns:
    customers[column] = pd.to_numeric(
        customers[column],
        errors="coerce"
    )


# ==========================================
# 4. SELECT LONG-TIME BUSINESS CUSTOMERS
# ==========================================

business_customers = customers[
    customers["segment"].isin(BUSINESS_SEGMENTS)
].copy()

loyal_customers = business_customers[
    (business_customers["total_orders"] >= MIN_ORDERS)
    & (
        business_customers["customer_lifetime_days"]
        >= MIN_HISTORY_DAYS
    )
].copy()

print("Business customers:", len(business_customers))
print("Established business customers:", len(loyal_customers))


# ==========================================
# 5. DETECT INACTIVE CUSTOMERS
# ==========================================

at_risk = loyal_customers[
    (loyal_customers["days_inactive"] >= MIN_INACTIVE_DAYS)
    & (
        loyal_customers["inactivity_ratio"]
        >= HIGH_RISK_RATIO
    )
    & (loyal_customers["avg_order_gap_days"] > 0)
].copy()


# ==========================================
# 6. ASSIGN RISK LEVELS
# ==========================================

def determine_risk(ratio):
    if ratio >= CRITICAL_RISK_RATIO:
        return "Critical"

    if ratio >= HIGH_RISK_RATIO:
        return "High"

    return "Low"


at_risk["risk_level"] = (
    at_risk["inactivity_ratio"].apply(determine_risk)
)

at_risk["risk_rule"] = "CUSTOMER_INACTIVITY"

at_risk["alert_id"] = (
    at_risk["customer_id"].astype(str)
    + "|"
    + at_risk["risk_rule"]
)


# ==========================================
# 7. EXPLAIN WHY CUSTOMER WAS FLAGGED
# ==========================================

def create_explanation(row):
    return (
        f"Customer has not ordered for "
        f"{int(row['days_inactive'])} days. "
        f"Their usual order interval is "
        f"{row['avg_order_gap_days']:.1f} days. "
        f"Current inactivity is "
        f"{row['inactivity_ratio']:.1f}x "
        f"their usual interval."
    )


at_risk["explanation"] = at_risk.apply(
    create_explanation,
    axis=1
)


# ==========================================
# 8. RECOMMEND FOLLOW-UP ACTIONS
# ==========================================

def recommend_action(row):
    if row["risk_level"] == "Critical":
        return (
            "Contact customer urgently. "
            "Ask about recent purchasing changes "
            "and any unresolved service issues."
        )

    return (
        "Schedule a customer check-in. "
        "Ask whether their business needs "
        "or purchasing plans have changed."
    )


at_risk["recommended_action"] = at_risk.apply(
    recommend_action,
    axis=1
)


# ==========================================
# 9. SORT ALERTS BY PRIORITY
# ==========================================

priority_order = {
    "Critical": 0,
    "High": 1
}

at_risk["priority_order"] = (
    at_risk["risk_level"].map(priority_order)
)

at_risk = at_risk.sort_values(
    [
        "priority_order",
        "total_spent",
        "inactivity_ratio"
    ],
    ascending=[True, False, False]
)

at_risk = at_risk.drop(
    columns=["priority_order"]
)
# Round values to 2 decimal places
at_risk["inactivity_ratio"] = at_risk["inactivity_ratio"].round(2)
at_risk["total_spent"] = at_risk["total_spent"].round(2)

# ==========================================
# 10. SAVE CUSTOMER ALERTS
# ==========================================

alert_columns = [
    "alert_id",
    "customer_id",
    "segment",
    "risk_level",
    "risk_rule",
    "total_orders",
    "total_spent",
    "days_inactive",
    "avg_order_gap_days",
    "inactivity_ratio",
    "explanation",
    "recommended_action"
]

alerts = at_risk[alert_columns].copy()

alerts.to_csv(
    ALERTS_FILE,
    index=False
)


# ==========================================
# 11. AUTOMATICALLY CREATE TASKS
# ==========================================

tasks = alerts[
    [
        "alert_id",
        "customer_id",
        "segment",
        "risk_level",
        "explanation",
        "recommended_action"
    ]
].copy()

tasks = tasks.rename(
    columns={
        "alert_id": "task_id",
        "risk_level": "priority",
        "recommended_action": "action"
    }
)

# Keep task statuses from previous runs.
# This prevents completed tasks from being
# reset to Pending every time we rerun.

if TASKS_FILE.exists():
    previous_tasks = pd.read_csv(TASKS_FILE)

    if {"task_id", "status"}.issubset(
        previous_tasks.columns
    ):
        previous_statuses = (
            previous_tasks.drop_duplicates(
                subset=["task_id"],
                keep="last"
            )
            .set_index("task_id")["status"]
        )

        tasks["status"] = (
            tasks["task_id"]
            .map(previous_statuses)
            .fillna("Pending")
        )
    else:
        tasks["status"] = "Pending"
else:
    tasks["status"] = "Pending"

tasks.to_csv(
    TASKS_FILE,
    index=False
)


# ==========================================
# 12. DISPLAY SUMMARY
# ==========================================

print("\n===== CUSTOMER RISK SUMMARY =====")

print("At-risk customers:", len(alerts))

print(
    "Critical:",
    (alerts["risk_level"] == "Critical").sum()
)

print(
    "High:",
    (alerts["risk_level"] == "High").sum()
)

print("\n===== TOP 10 ALERTS =====")

print(
    alerts[
        [
            "customer_id",
            "segment",
            "risk_level",
            "days_inactive",
            "inactivity_ratio",
            "total_spent"
        ]
    ].head(10).to_string(index=False)
)

print("\n===== TASK SUMMARY =====")

for status, count in tasks["status"].value_counts().items():
    print(f"{status}: {count}")

