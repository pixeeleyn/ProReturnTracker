import pandas as pd
from pathlib import Path

# LOAD DATA
BASE = Path(__file__).resolve().parent
OUTPUT = BASE / "cleaned_data"
OUTPUT.mkdir(exist_ok=True)

customers = pd.read_csv(BASE / "customers.csv")
orders = pd.read_csv(BASE / "orders.csv")
returns = pd.read_csv(BASE / "returns.csv")

print("Original dataset sizes:")
print("Customers:", len(customers))
print("Orders:", len(orders))
print("Returns:", len(returns))

# REMOVE DUPLICATE
customers = customers.drop_duplicates().copy()
orders = orders.drop_duplicates().copy()
returns = returns.drop_duplicates().copy()

print("\nAfter removing exact duplicates:")
print("Customers:", len(customers))
print("Orders:", len(orders))
print("Returns:", len(returns))

# STANDARDIZE PRODUCTS NAMES
orders["product"] = orders["product"].str.strip()

product_mapping = {
    "mechanical keyboard": "Mechanical Keyboard",
    "Mech Keyboard": "Mechanical Keyboard",
    "USB C Dock": "USB-C Dock",
    "usb-c dock": "USB-C Dock",
    "24in Monitor": 'Monitor 24"',
    "Monitor 24": 'Monitor 24"',
    "27in Monitor": 'Monitor 27"',
    "Monitor 27": 'Monitor 27"',
    'monitor 27"': 'Monitor 27"',
    "ERGOLIFT STANDING DESK": "ErgoLift Standing Desk",
    "Ergolift Standing Desk": "ErgoLift Standing Desk",
    "ErgoLift Desk": "ErgoLift Standing Desk",
}

orders["product"] = orders["product"].replace(
    product_mapping
)

# STANDARDIZE REGIONS
region_mapping = {
    "ontario": "Ontario",
    "ON": "Ontario",
    "Québec": "Quebec",
    "quebec": "Quebec",
    "QC": "Quebec",
    "atlantic": "Atlantic",
    "ATL": "Atlantic",
    "prairies": "Prairies",
    "British Columbia": "BC",
    "B.C.": "BC",
}

for df in [orders, customers]:
    df["region"] = (
        df["region"].str.strip().replace(region_mapping)
    )

orders["category"] = orders["category"].str.strip()
returns["reason"] = returns["reason"].str.strip()

# CLEAN DATES
def parse_mixed_dates(series):
    values = series.astype("string").str.strip()

    # The data contains YYYY-MM-DD and MM/DD/YYYY
    iso = pd.to_datetime(
        values.where(~values.str.contains("/", na=False)),
        format="%Y-%m-%d",
        errors="coerce"
    )

    us = pd.to_datetime(
        values.where(values.str.contains("/", na=False)),
        format="%m/%d/%Y",
        errors="coerce"
    )

    return iso.fillna(us)


orders["order_date"] = parse_mixed_dates(
    orders["order_date"]
)
orders["payment_date"] = parse_mixed_dates(
    orders["payment_date"]
)

returns["return_date"] = parse_mixed_dates(
    returns["return_date"]
)

customers["signup_date"] = parse_mixed_dates(
    customers["signup_date"]
)

# VALIDATE ORDER DATA
# Discounts are fractions:
# 0.15 = 15% discount.
# Values outside 0 to 1 are invalid.

invalid_orders = (
    (orders["quantity"] <= 0)
    | (orders["discount"] < 0)
    | (orders["discount"] > 1)
    | (orders["discount"].isna())
    | (orders["unit_price"] < 0)
    | (orders["unit_price"].isna())
    | (orders["order_date"].isna())
)

bad_orders = orders[invalid_orders].copy()
orders_clean = orders[~invalid_orders].copy()

print("\nInvalid order rows:", len(bad_orders))

# Do not invent missing unit costs.
# Refund analysis can still use these orders.

# VALIDATE RETURN DATA
invalid_returns = (
    (returns["quantity_returned"] <= 0)
    | (returns["refund_amount"] < 0)
    | (returns["refund_amount"].isna())
    | (returns["return_date"].isna())
)

bad_returns = returns[invalid_returns].copy()
returns_clean = returns[~invalid_returns].copy()

# CONNECT RETURNS TO ORDERS
# Check order IDs are unique before joining.
if orders_clean["order_id"].duplicated().any():
    raise ValueError(
        "Duplicate order IDs remain after cleaning."
    )

merged = returns_clean.merge(
    orders_clean,
    on="order_id",
    how="left",
    validate="many_to_one",
    indicator=True
)

# Keep returns with no valid matching order
# in a separate file for investigation.

unmatched_returns = merged[
    merged["_merge"] != "both"
].copy()

merged = merged[
    merged["_merge"] == "both"
].drop(columns="_merge").copy()

# Flag returns that claim more units than ordered.
excess_quantity = (
    merged["quantity_returned"] > merged["quantity"]
)

bad_return_quantities = merged[
    excess_quantity
].copy()

merged = merged[~excess_quantity].copy()

# CONNECT CUSTOMER INFORMATION
if customers["customer_id"].duplicated().any():
    raise ValueError(
        "Duplicate customer IDs need investigation."
    )

customer_columns = [
    "customer_id",
    "segment",
    "payment_terms",
    "credit_limit"
]

merged = merged.merge(
    customers[customer_columns],
    on="customer_id",
    how="left",
    validate="many_to_one"
)

# CALCULATE BASIC METRICS
# Gross sales after discount, before returns.
orders_clean["net_sales"] = (
    orders_clean["quantity"]
    * orders_clean["unit_price"]
    * (1 - orders_clean["discount"])
)

merged["refund_amount"] = pd.to_numeric(
    merged["refund_amount"],
    errors="coerce"
)

print("\nCleaned data summary:")
print("Valid orders:", len(orders_clean))
print("Matched returns:", len(merged))
print("Unmatched returns:", len(unmatched_returns))
print("Excess-quantity returns:", len(bad_return_quantities))
print("Total matched refunds: $",
      round(merged["refund_amount"].sum(), 2))

# SAVE CLEAN DATA
orders_clean.to_csv(
    OUTPUT / "orders_clean.csv",
    index=False
)

merged.to_csv(
    OUTPUT / "returns_merged.csv",
    index=False
)

bad_orders.to_csv(
    OUTPUT / "invalid_orders.csv",
    index=False
)

bad_returns.to_csv(
    OUTPUT / "invalid_returns.csv",
    index=False
)

unmatched_returns.to_csv(
    OUTPUT / "unmatched_returns.csv",
    index=False
)

bad_return_quantities.to_csv(
    OUTPUT / "invalid_return_quantities.csv",
    index=False
)
