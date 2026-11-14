
import pandas as pd
from pathlib import Path

# =====================================
# 1. FILE PATHS
# =====================================

BASE = Path(__file__).resolve().parent

ORDERS_FILE = BASE / "cleaned_data" / "orders_clean.csv"
CUSTOMERS_FILE = BASE / "customers.csv"

OUTPUT = BASE / "customer_results"
OUTPUT.mkdir(exist_ok=True)


# =====================================
# 2. LOAD DATA
# =====================================

orders = pd.read_csv(ORDERS_FILE)
customers = pd.read_csv(CUSTOMERS_FILE)

print("Orders loaded:", len(orders))
print("Customers loaded:", len(customers))


# =====================================
# 3. CHECK REQUIRED COLUMNS
# =====================================

required_order_columns = [
    "customer_id",
    "order_id",
    "order_date",
    "net_sales"
]

required_customer_columns = [
    "customer_id"
]

for column in required_order_columns:
    if column not in orders.columns:
        raise ValueError(
            f"Missing column in orders: {column}"
        )

for column in required_customer_columns:
    if column not in customers.columns:
        raise ValueError(
            f"Missing column in customers: {column}"
        )


# =====================================
# 4. PREPARE THE DATA
# =====================================

# Convert order dates to real dates.
orders["order_date"] = pd.to_datetime(
    orders["order_date"],
    errors="coerce"
)

# Convert sales to numeric values.
orders["net_sales"] = pd.to_numeric(
    orders["net_sales"],
    errors="coerce"
)

# Remove records without important values.
orders = orders.dropna(
    subset=[
        "customer_id",
        "order_id",
        "order_date",
        "net_sales"
    ]
).copy()

# Standardize customer IDs for matching.
orders["customer_id"] = (
    orders["customer_id"].astype(str).str.strip()
)

customers["customer_id"] = (
    customers["customer_id"].astype(str).str.strip()
)

# Keep one row per customer in customer data.
customers = customers.drop_duplicates(
    subset=["customer_id"]
)

# Sort orders chronologically.
orders = orders.sort_values(
    ["customer_id", "order_date", "order_id"]
)


# =====================================
# 5. CHOOSE THE ANALYSIS DATE
# =====================================

# Use the latest order date in the dataset,
# not today's date.
#
# This is important because the hackathon
# dataset may contain historical orders.

if orders.empty:
    raise ValueError("No valid orders available.")

analysis_date = orders["order_date"].max()

print("\nAnalysis date:", analysis_date.date())


# =====================================
# 6. CALCULATE CUSTOMER METRICS
# =====================================

customer_analysis = orders.groupby(
    "customer_id", as_index=False
).agg(
    total_orders=("order_id", "nunique"),
    first_order=("order_date", "min"),
    last_order=("order_date", "max"),
    total_spent=("net_sales", "sum")
)

# How long has each customer been purchasing?
customer_analysis["customer_lifetime_days"] = (
    customer_analysis["last_order"]
    - customer_analysis["first_order"]
).dt.days

# How many days since their last order?
customer_analysis["days_inactive"] = (
    analysis_date
    - customer_analysis["last_order"]
).dt.days


# =====================================
# 7. CALCULATE USUAL ORDER FREQUENCY
# =====================================

# First, get one date per customer and order.
# This avoids counting multiple line items
# from the same order as separate purchases.

order_dates = orders[
    ["customer_id", "order_id", "order_date"]
].drop_duplicates(
    subset=["customer_id", "order_id"]
).copy()

order_dates = order_dates.sort_values(
    ["customer_id", "order_date"]
)

# Find the previous order date.
order_dates["previous_order"] = (
    order_dates.groupby("customer_id")[
        "order_date"
    ].shift(1)
)

# Calculate the number of days between orders.
order_dates["days_between_orders"] = (
    order_dates["order_date"]
    - order_dates["previous_order"]
).dt.days

# Calculate the average gap for each customer.
average_gaps = order_dates.groupby(
    "customer_id", as_index=False
).agg(
    avg_order_gap_days=(
        "days_between_orders", "mean"
    )
)

customer_analysis = customer_analysis.merge(
    average_gaps,
    on="customer_id",
    how="left"
)


# =====================================
# 8. COMPARE INACTIVITY TO USUAL GAP
# =====================================

# Example:
# Usual order gap = 30 days
# Current inactivity = 90 days
# Inactivity ratio = 90 / 30 = 3

customer_analysis["inactivity_ratio"] = (
    customer_analysis["days_inactive"]
    / customer_analysis["avg_order_gap_days"]
)

# Avoid division-by-zero problems.
customer_analysis.loc[
    customer_analysis["avg_order_gap_days"] <= 0,
    "inactivity_ratio"
] = float("nan")


# =====================================
# 9. ADD CUSTOMER INFORMATION
# =====================================

# Add customer details such as segment
# and region when those columns exist.

optional_columns = [
    "customer_name",
    "segment",
    "region",
    "payment_terms",
    "credit_limit"
]

available_columns = [
    column
    for column in optional_columns
    if column in customers.columns
]

customer_details = customers[
    ["customer_id"] + available_columns
]

customer_analysis = customer_analysis.merge(
    customer_details,
    on="customer_id",
    how="left"
)


# =====================================
# 10. SORT BY INACTIVITY
# =====================================

# Put customers with the highest inactivity
# relative to their usual order gap first.

customer_analysis = customer_analysis.sort_values(
    ["inactivity_ratio", "days_inactive"],
    ascending=False,
    na_position="last"
)


# =====================================
# 11. SAVE ANALYSIS
# =====================================

output_file = OUTPUT / "customer_analysis.csv"

customer_analysis.to_csv(
    output_file,
    index=False,
    float_format="%.2f"
)


# =====================================
# 12. DISPLAY RESULTS
# =====================================

print("\n===== CUSTOMER ACTIVITY SUMMARY =====")

print(
    "Total customers analyzed:",
    len(customer_analysis)
)

print(
    "Customers with 3+ orders:",
    (customer_analysis["total_orders"] >= 3).sum()
)

print("\n===== TOP INACTIVE CUSTOMERS =====")

display_columns = [
    "customer_id",
    "total_orders",
    "days_inactive",
    "avg_order_gap_days",
    "inactivity_ratio",
    "total_spent"
]

print(
    customer_analysis[display_columns]
    .head(15)
    .to_string(
        index=False,
        float_format="%.2f"
    )
)

