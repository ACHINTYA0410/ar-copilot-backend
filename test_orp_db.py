from orp_db import fetch_orders

rows = fetch_orders(limit=5)

print(f"Fetched {len(rows)} row(s)")
for row in rows:
    print(row["Order Id"], row["Deal Id"], row["Customer Name"], row["Current Order Status"])