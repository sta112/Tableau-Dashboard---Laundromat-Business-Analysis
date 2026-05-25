import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# Set random seed for reproducibility
np.random.seed(42)

# =====================================================================
# CONSTANTS & CONFIGURATION
# =====================================================================
START_DATE = datetime(2024, 1, 1)
END_DATE = datetime(2025, 12, 31)
TOTAL_DAYS = (END_DATE - START_DATE).days + 1

TOTAL_WASHERS = 10
TOTAL_DRYERS = 10
NUM_CUSTOMERS = 500  # Total customer pool over 2 years

# =====================================================================
# STEP 1: DEVELOP THE DIMENSION TABLES
# =====================================================================

# 1. Machine Type Table
machines = []
for i in range(1, TOTAL_WASHERS + 1):
    machines.append({
        'machine_id': f'W{i:02d}',
        'machine_type': 'Washer',
        'capacity_lbs': 30 if i <= 7 else 50,  # 7 small, 3 large washers
        'vend_price': 4.50 if i <= 7 else 6.75,
        'base_cogs_utility': 0.45 if i <= 7 else 0.65  # Water/Electricity cost
    })
for i in range(1, TOTAL_DRYERS + 1):
    machines.append({
        'machine_id': f'D{i:02d}',
        'machine_type': 'Dryer',
        'capacity_lbs': 45,
        'vend_price': 2.25,
        'base_cogs_utility': 0.30  # Gas/Electricity cost
    })
df_machines = pd.DataFrame(machines)

# 2. Vending Machine Type Table
vending_items = [
    {'item_id': 'V01', 'vending_machine': 'M1_Soap', 'item_name': 'Tide Pod Single', 'vend_price': 1.50, 'base_item_cost': 0.40},
    {'item_id': 'V02', 'vending_machine': 'M1_Soap', 'item_name': 'Fabric Softener Sheet', 'vend_price': 1.00, 'base_item_cost': 0.20},
    {'item_id': 'V03', 'vending_machine': 'M2_Snacks', 'item_name': 'Potato Chips', 'vend_price': 1.75, 'base_item_cost': 0.60},
    {'item_id': 'V04', 'vending_machine': 'M2_Snacks', 'item_name': 'Soda Can', 'vend_price': 2.00, 'base_item_cost': 0.55}
]
df_vending = pd.DataFrame(vending_items)

# 3. Customer Table (With Logistic Ramp-Up Growth)
customers = []
for c_id in range(1, NUM_CUSTOMERS + 1):
    # Simulating a gradual local market adoption over the first 180 days (S-Curve)
    # Customers register earlier or later based on a logistic probability distribution
    ramp_up_day = int(np.random.logistic(loc=90, scale=30))
    ramp_up_day = max(0, min(ramp_up_day, 180))  # Cap within realistic initialization window
    join_date = START_DATE + timedelta(days=ramp_up_day)
    
    customers.append({
        'customer_id': f'CUST{c_id:04d}',
        'join_date': join_date.strftime('%Y-%m-%d'),
        'customer_segment': np.random.choice(['Loyal Weekly', 'Bi-Weekly', 'Occasional'], p=[0.4, 0.4, 0.2])
    })
df_customers = pd.DataFrame(customers)

# =====================================================================
# STEP 2: GENERATE THE TRANSACTION FACT TABLE (THE ENGINE)
# =====================================================================
transactions = []
tx_id_counter = 1

# Dictionary to look up properties efficiently inside the loop
machine_lookup = df_machines.set_index('machine_id').to_dict('index')
vending_lookup = df_vending.set_index('item_id').to_dict('index')

for day_offset in range(TOTAL_DAYS):
    current_date = START_DATE + timedelta(days=day_offset)
    day_of_week = current_date.weekday()  # 5 = Saturday, 6 = Sunday
    month = current_date.month
    
    # 1. Evaluate Seasonality / Day of Week Modifiers
    is_weekend = day_of_week >= 5
    weekend_multiplier = 1.6 if is_weekend else 0.8
    
    # Winter months (Nov-Feb) see a minor 15% bump in dryer utility costs/usage due to heavy clothing
    is_winter = month in [11, 12, 1, 2]
    winter_multiplier = 1.15 if is_winter else 1.0
    
    # 2. Evaluate Business Ramp-Up Cap (First 6 months scales up baseline transactions)
    if day_offset < 180:
        ramp_up_factor = (day_offset / 180) * 0.7 + 0.3  # Starts at 30% capacity, climbs to 100%
    else:
        ramp_up_factor = 1.0
        
    # Baseline transactions expected per day at full maturity
    base_tx_count = int(np.random.poisson(lam=45) * weekend_multiplier * ramp_up_factor)
    
    # Filter out customers available to use the laundromat on this specific date
    available_cust_pool = df_customers[df_customers['join_date'] <= current_date.strftime('%Y-%m-%d')]['customer_id'].values
    
    if len(available_cust_pool) == 0:
        continue
        
    # Generate transactions for the day
    for _ in range(base_tx_count):
        cust_id = np.random.choice(available_cust_pool)
        
        # Decide if they are using a Machine or buying Vending
        tx_type = np.random.choice(['Machine', 'Vending'], p=[0.75, 0.25])
        
        # Randomize an operation hour based on realistic peak times (Peak afternoon/evening)
        hour = int(np.random.beta(a=5, b=2) * 14) + 8  # Distributes hours mostly between 8 AM and 10 PM
        tx_time = current_date + timedelta(hours=hour, minutes=np.random.randint(0, 59))
        
        if tx_type == 'Machine':
            mach_id = np.random.choice(df_machines['machine_id'].values)
            mach_props = machine_lookup[mach_id]
            
            revenue = mach_props['vend_price']
            
            # Inject tight variance into utility COGS using a normal distribution (std dev = 0.02)
            base_utility = mach_props['base_cogs_utility']
            if mach_props['machine_type'] == 'Dryer' and is_winter:
                base_utility *= winter_multiplier
                
            actual_cogs = round(np.random.normal(loc=base_utility, scale=0.02), 2)
            actual_cogs = max(0.05, actual_cogs)  # Prevent negative costs
            
            transactions.append({
                'transaction_id': f'TX{tx_id_counter:06d}',
                'timestamp': tx_time.strftime('%Y-%m-%d %H:%M:%S'),
                'customer_id': cust_id,
                'asset_id': mach_id,
                'item_id': np.nan,
                'revenue': revenue,
                'cogs': actual_cogs
            })
            tx_id_counter += 1
            
        elif tx_type == 'Vending':
            item_id = np.random.choice(df_vending['item_id'].values)
            vend_props = vending_lookup[item_id]
            
            revenue = vend_props['vend_price']
            
            # Wholesale goods have tighter margins/variances than utility spikes, simulate stock variance
            actual_cogs = round(np.random.normal(loc=vend_props['base_item_cost'], scale=0.01), 2)
            
            transactions.append({
                'transaction_id': f'TX{tx_id_counter:06d}',
                'timestamp': tx_time.strftime('%Y-%m-%d %H:%M:%S'),
                'customer_id': cust_id,
                'asset_id': 'VENDING',
                'item_id': item_id,
                'revenue': revenue,
                'cogs': actual_cogs
            })
            tx_id_counter += 1

df_transactions = pd.DataFrame(transactions)

# =====================================================================
# STEP 3: EXPORT TO CSV FOR TABLEAU INPUT
# =====================================================================
df_machines.to_csv('machine_type_table.csv', index=False)
df_vending.to_csv('vending_machine_type_table.csv', index=False)
df_customers.to_csv('customer_table.csv', index=False)
df_transactions.to_csv('transaction_table.csv', index=False)

print(f"Successfully generated database pipeline assets:")
print(f" -> machine_type_table.csv ({len(df_machines)} rows)")
print(f" -> vending_machine_type_table.csv ({len(df_vending)} rows)")
print(f" -> customer_table.csv ({len(df_customers)} rows)")
print(f" -> transaction_table.csv ({len(df_transactions)} rows)")