
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone

# =====================================
# 1. FILE PATHS
# =====================================

BASE = Path(__file__).resolve().parent
DATA = BASE / "analysis_results"

product_analysis = pd.read_csv(
    DATA / "product_analysis.csv"
)

damage_analysis = pd.read_csv(
    DATA / "damage_analysis.csv"
)

# Folder for generated alerts and tasks
OUTPUT = BASE / "automation_results"
OUTPUT.mkdir(exist_ok=True)

ALERT_FILE = OUTPUT / "alerts.csv"
TASK_FILE = OUTPUT / "tasks.csv"



# =====================================
# 2. DEFINE DETECTION THRESHOLDS
# =====================================

# Company-wide return rate: 4.71%
# Highest product return rate: 12.90%

RETURN_RATE_THRESHOLD = 10
MIN_UNITS_SOLD = 100

# Shipping damage severity thresholds
DAMAGE_HIGH_THRESHOLD = 10000
DAMAGE_CRITICAL_THRESHOLD = 50000

alerts = []
new_tasks = []

now = datetime.now(timezone.utc).isoformat()



# =====================================
# 3. FUNCTION TO CREATE ALERTS
# =====================================

def create_alert(product, rule, severity,
                 message, action):

    alert_id = f"{product}|{rule}"

    alerts.append({
        "alert_id": alert_id,
        "product": product,
        "rule": rule,
        "severity": severity,
        "message": message,
        "recommended_action": action,
        "detected_at": now
    })

    new_tasks.append({
        "task_id": alert_id,
        "product": product,
        "rule": rule,
        "task": action,
        "priority": severity,
        "status": "Pending",
        "created_at": now
    })



# =====================================
# 4. RULE 1: HIGH RETURN RATE
# =====================================

for _, row in product_analysis.iterrows():

    product = row["product"]
    return_rate = row["unit_return_rate"]
    units_sold = row["units_sold"]

    if (
        units_sold >= MIN_UNITS_SOLD
        and return_rate > RETURN_RATE_THRESHOLD
    ):

        create_alert(
            product=product,
            rule="High Return Rate",
            severity="High",
            message=(
                f"{product} has a "
                f"{return_rate:.2f}% unit return rate. "
                f"The threshold is "
                f"{RETURN_RATE_THRESHOLD}%."
            ),
            action=(
                f"Investigate why customers return "
                f"{product}. Review product quality, "
                f"packaging, and customer feedback."
            )
        )




# =====================================
# 5. RULE 2: SHIPPING DAMAGE
# =====================================

for _, row in damage_analysis.iterrows():

    product = row["product"]
    damage_refunds = row["damage_refunds"]

    if damage_refunds > DAMAGE_CRITICAL_THRESHOLD:
        severity = "Critical"

    elif damage_refunds > DAMAGE_HIGH_THRESHOLD:
        severity = "High"

    else:
        continue

    create_alert(
        product=product,
        rule="Shipping Damage",
        severity=severity,
        message=(
            f"{product} generated "
            f"${damage_refunds:,.2f} in "
            f"shipping-damage refunds."
        ),
        action=(
            f"Review packaging materials, "
            f"shipping procedures, and delivery "
            f"damage reports for {product}."
        )
    )



# =====================================
# 6. SAVE ALERTS
# =====================================

alert_columns = [
    "alert_id", "product", "rule",
    "severity", "message",
    "recommended_action", "detected_at"
]

alerts_df = pd.DataFrame(
    alerts, columns=alert_columns
)

alerts_df.to_csv(ALERT_FILE, index=False)


# =====================================
# 7. SAVE TASKS WITHOUT DUPLICATES
# =====================================

task_columns = [
    "task_id", "product", "rule",
    "task", "priority", "status",
    "created_at"
]

new_tasks_df = pd.DataFrame(
    new_tasks, columns=task_columns
)

if TASK_FILE.exists():

    existing_tasks = pd.read_csv(TASK_FILE)

    # Preserve existing task status.
    # Only create tasks not already recorded.
    existing_ids = set(
        existing_tasks["task_id"].astype(str)
    )

    tasks_to_add = new_tasks_df[
        ~new_tasks_df["task_id"].isin(existing_ids)
    ]

    all_tasks = pd.concat(
        [existing_tasks, tasks_to_add],
        ignore_index=True
    )

else:
    tasks_to_add = new_tasks_df
    all_tasks = new_tasks_df

all_tasks.to_csv(TASK_FILE, index=False)


# =====================================
# 8. DISPLAY RESULTS
# =====================================

print("\n===== RETURNGUARD ALERTS =====")
print("Active alerts:", len(alerts_df))
print("New tasks created:", len(tasks_to_add))

if alerts_df.empty:
    print("No risks detected.")
else:
    for _, row in alerts_df.iterrows():

        print("\n-------------------------")
        print("Product:", row["product"])
        print("Severity:", row["severity"])
        print("Problem:", row["message"])
        print("Action:", row["recommended_action"])

print("\n===== TASK SUMMARY =====")

if not all_tasks.empty:
    for status, count in all_tasks["status"].value_counts().items():
        print(f"{status}: {count}")
    

