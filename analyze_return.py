
import pandas as pd
from pathlib import Path

# =====================================
# 1. LOAD CLEANED DATA
# =====================================

BASE = Path(__file__).resolve().parent
DATA = BASE / "cleaned_data"

orders = pd.read_csv(DATA / "orders_clean.csv")
returns = pd.read_csv(DATA / "returns_merged.csv")

print("Orders loaded:", len(orders))
print("Returns loaded:", len(returns))


# =====================================
# 2. VERIFY THE DATA
# =====================================

# Make sure quantities and refund amounts are numbers, not text.

orders["quantity"] = pd.to_numeric(
    orders["quantity"], errors="coerce"
)

returns["quantity_returned"] = pd.to_numeric(
    returns["quantity_returned"], errors="coerce"
)

returns["refund_amount"] = pd.to_numeric(
    returns["refund_amount"], errors="coerce"
)

# Stop if important values are missing or invalid.
if orders["quantity"].isna().any():
    raise ValueError("Missing order quantities found.")

if (orders["quantity"] <= 0).any():
    raise ValueError("Invalid order quantities found.")

if returns[[
    "quantity_returned", "refund_amount"
]].isna().any().any():
    raise ValueError("Missing return values found.")

# Every return should have a unique return ID.
if returns["return_id"].duplicated().any():
    raise ValueError("Duplicate return IDs found.")


# =====================================
# 3. OVERALL BUSINESS METRICS
# =====================================

total_orders = orders["order_id"].nunique()

returned_orders = returns["order_id"].nunique()

total_refunds = returns["refund_amount"].sum()

total_units_sold = orders["quantity"].sum()

total_units_returned = returns[
    "quantity_returned"
].sum()

# Percentage of orders with a recorded return.
order_return_rate = (
    returned_orders / total_orders * 100
    if total_orders > 0 else 0
)

# Percentage of sold units returned.
unit_return_rate = (
    total_units_returned / total_units_sold * 100
    if total_units_sold > 0 else 0
)

print("\n===== OVERALL METRICS =====")

print("Total orders:", total_orders)
print("Returned orders:", returned_orders)
print(f"Total refunds: ${total_refunds:,.2f}")
print(f"Order return rate: {order_return_rate:.2f}%")
print(f"Unit return rate: {unit_return_rate:.2f}%")


# =====================================
# 4. RETURNS BY PRODUCT
# =====================================

# Count how many orders and units were sold for each product.

product_orders = orders.groupby(
    "product", as_index=False
).agg(
    total_orders=("order_id", "nunique"),
    units_sold=("quantity", "sum")
)

# Calculate returns for each product.
product_returns = returns.groupby(
    "product", as_index=False
).agg(
    returned_orders=("order_id", "nunique"),
    units_returned=("quantity_returned", "sum"),
    total_refunds=("refund_amount", "sum")
)

# Combine sales and returns.
product_analysis = product_orders.merge(
    product_returns,
    on="product",
    how="left",
    validate="one_to_one"
)

# Products with no returns get zero.
columns = [
    "returned_orders",
    "units_returned",
    "total_refunds"
]

product_analysis[columns] = (
    product_analysis[columns].fillna(0)
)

# Calculate order return rate.
product_analysis["order_return_rate"] = (
    product_analysis["returned_orders"]
    / product_analysis["total_orders"]
    * 100
)

# Calculate unit return rate.
product_analysis["unit_return_rate"] = (
    product_analysis["units_returned"]
    / product_analysis["units_sold"]
    * 100
)

product_analysis = product_analysis.sort_values(
    "total_refunds",
    ascending=False
)

print("\n===== RETURNS BY PRODUCT =====")

print(product_analysis.to_string(index=False))


# =====================================
# 5. REFUNDS BY RETURN REASON
# =====================================

reason_analysis = returns.groupby(
    "reason", as_index=False
).agg(
    return_records=("return_id", "nunique"),
    total_refunds=("refund_amount", "sum")
)

reason_analysis["refund_share"] = (
    reason_analysis["total_refunds"]
    / total_refunds * 100
    if total_refunds > 0 else 0
)

reason_analysis = reason_analysis.sort_values(
    "total_refunds",
    ascending=False
)

print("\n===== REFUNDS BY REASON =====")

print(reason_analysis.to_string(index=False))


# =====================================
# 6. SHIPPING DAMAGE ANALYSIS
# =====================================

damaged_returns = returns[
    returns["reason"].str.strip().str.casefold()
    == "damaged in transit"
].copy()

damage_analysis = damaged_returns.groupby(
    "product", as_index=False
).agg(
    damage_returns=("return_id", "nunique"),
    damaged_units=("quantity_returned", "sum"),
    damage_refunds=("refund_amount", "sum")
)

damage_analysis = damage_analysis.sort_values(
    "damage_refunds",
    ascending=False
)

print("\n===== SHIPPING DAMAGE =====")

print(damage_analysis.to_string(index=False))


# =====================================
# 7. REFUNDS BY CATEGORY
# =====================================

category_analysis = returns.groupby(
    "category", as_index=False
).agg(
    return_records=("return_id", "nunique"),
    total_refunds=("refund_amount", "sum")
)

category_analysis = category_analysis.sort_values(
    "total_refunds",
    ascending=False
)

print("\n===== REFUNDS BY CATEGORY =====")

print(category_analysis.to_string(index=False))


# =====================================
# 8. SAVE RESULTS FOR WEBSITE
# =====================================

OUTPUT = BASE / "analysis_results"
OUTPUT.mkdir(exist_ok=True)

product_analysis.to_csv(
    OUTPUT / "product_analysis.csv",
    index=False
)

reason_analysis.to_csv(
    OUTPUT / "reason_analysis.csv",
    index=False
)

damage_analysis.to_csv(
    OUTPUT / "damage_analysis.csv",
    index=False
)

category_analysis.to_csv(
    OUTPUT / "category_analysis.csv",
    index=False
)

# Save overall metrics as a one-row CSV.
summary = pd.DataFrame([{
    "total_orders": total_orders,
    "returned_orders": returned_orders,
    "total_refunds": total_refunds,
    "total_units_sold": total_units_sold,
    "total_units_returned": total_units_returned,
    "order_return_rate": order_return_rate,
    "unit_return_rate": unit_return_rate
}])

summary.to_csv(
    OUTPUT / "summary.csv",
    index=False
)

