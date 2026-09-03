import pandas as pd

df = pd.read_csv("Road_Inventory_2024.csv", low_memory=False)
print(f"Total rows in full dataset: {len(df)}")

relevant_columns = [
    'Rd_Seg_ID', 'St_Name', 'City', 'F_F_Class', 'Num_Lanes',
    'Surface_Wd', 'Shldr_Lt_W', 'Shldr_Lt_T', 'Shldr_Rt_W', 'Shldr_Rt_T',
    'Speed_Lim'
]
df_filtered = df[relevant_columns].copy()

# Properly filter to USABLE data: not missing AND not zero
# (zero almost always means "not recorded" in this dataset, not "zero-width")
df_filtered = df_filtered[
    (df_filtered['Shldr_Rt_W'].notna()) & (df_filtered['Shldr_Rt_W'] > 0) &
    (df_filtered['Surface_Wd'].notna()) & (df_filtered['Surface_Wd'] > 0)
]

print(f"Rows with genuinely usable shoulder + surface data: {len(df_filtered)}")
print("\nFirst 5 rows:")
print(df_filtered.head())

df_filtered.to_csv("road_segments_filtered.csv", index=False)
print("\nSaved to road_segments_filtered.csv!")