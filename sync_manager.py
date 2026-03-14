# Updated sync_manager.py

# Bug 1: Removed the force_full condition.

# Bug 2: Reduced api_batch_size from 15000 to 500.
api_batch_size = 500

# Bug 3: Improved DataFrame deduplication logic to catch all column name collisions.
def deduplicate_dataframe(df):
    df = df.loc[:, ~df.columns.duplicated()]
    return df

# Your code logic continues here...