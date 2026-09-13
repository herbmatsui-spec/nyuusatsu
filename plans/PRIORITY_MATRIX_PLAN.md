# Priority Matrix Implementation Plan (Steps 1-8 of 72-Step Plan)

## Objective
Implement the priority matrix functionality to prioritize prefectures for crawling based on agency count and industry match.

## Steps

### Step 1: Crawl Priority Model
- **File**: `database/models/crawl_priority.py`
- **Details**:
  - Create SQLAlchemy model `CrawlPriority` with the following columns:
    - `id`: Integer, primary key, autoincrement
    - `prefecture_code`: String(2), index=True
    - `prefecture_name`: String(32)
    - `agency_count`: Integer, default=0
    - `target_industry_match`: Float, default=0.0
    - `score`: Float, default=0.0
    - `status`: String(16), default="pending" (pending/active/done)
    - `created_at`, `updated_at`: DateTime
  - Ensure the model imports `Base` from `database.models.base` (or use declarative base if not already unified).
  - Add `__tablename__ = "crawl_priority"`.

### Step 2: Prefectures Master Constants File
- **File**: `config/prefectures.py`
- **Details**:
  - Define a dictionary `PREFECTURES` mapping prefecture codes (2-digit strings) to prefecture names.
  - Include all 47 prefectures plus an optional "国外" (foreign) entry if needed.
  - Example:
    ```python
    PREFECTURES = {
        "01": "北海道",
        "02": "青森県",
        # ...
        "47": "沖縄県",
    }
    ```

### Step 3: Priority Score Calculation Function
- **File**: `services/priority_scorer.py`
- **Details**:
  - Create a service module with two functions:
    - `calc_score(agency_count: int, industry_match: float) -> float`:
      - Compute raw score: `agency_count * 0.6 + industry_match * 0.4`
      - Normalize to 0-100 scale (assuming max agency_count and industry_match are known; if not, return raw score and normalize later).
    - `rank_prefectures(rows: List[Dict]) -> List[Dict]`:
      - Accept a list of dictionaries each containing at least `prefecture_code`, `agency_count`, `target_industry_match`.
      - Calculate score for each using `calc_score`.
      - Sort descending by score and return the list.

### Step 4: Count Agencies by Prefecture Script
- **File**: `scripts/count_agencies_by_pref.py`
- **Details**:
  - Script to count existing agencies (from `bids` table or `agency_inventory`?) per prefecture.
  - According to the 72-step plan: "既存 `bids_system.db` の `bids` テーブルから `prefecture` ごとに発注機関数を COUNT"
  - However, we may not have a `prefecture` column in `bids`. We might need to join with `agency` or `agency_inventory`.
  - For now, we can count from `agency_inventory` (which already has `prefecture_code`).
  - Steps:
    1. Session to `bids_system.db`.
    2. Query `agency_inventory` table, group by `prefecture_code`, count.
    3. For each prefecture, update or insert a `CrawlPriority` record with the `agency_count`.
  - Save results to `crawl_priority.agency_count`.

### Step 5: Target Industries Mapping Config
- **File**: `config/target_industries.py`
- **Details**:
  - Define a list `TARGET_INDUSTRIES` of industry keywords the company is interested in.
  - Example:
    ```python
    TARGET_INDUSTRIES = ["清掃", "警備", "派遣", "情報通信", "調査", "建設"]
    ```

### Step 6: Industry Match Score Calculation Script
- **File**: `scripts/score_industry_match.py`
- **Details**:
  - For each prefecture, calculate the proportion of bids (or agency titles?) that match the target industries.
  - According to the plan: "各都道府県の既存案件タイトルと `TARGET_INDUSTRIES` を突合"
  - We need to decide what data to use: perhaps the `bids` table's `title` or `agency_inventory`?
  - Since we don't have a direct link from bids to prefecture, we might need to use `agency_inventory` and maybe the agency name? Or we can use the `bids` table and join via `agency_id` to get the agency's prefecture.
  - For simplicity, we can compute industry match based on the agency inventory? But the plan says "既存案件タイトル".
  - Let's assume we have a `bids` table with a `title` column and a foreign key to `agency` (which has `prefecture_code` via `agency_inventory` or `agency` table).
  - We'll need to examine the schema. If not available, we may need to approximate.
  - For now, we'll implement a placeholder that reads from `bids` and joins to get prefecture, then calculates match ratio.
  - Steps:
    1. Session to `bids_system.db`.
    2. Query: select `bids.title`, `agencies.preferred_prefecture_code` (or similar) joining `bids` to `agency` to `agency_inventory`.
    3. For each prefecture, count total titles and count of titles containing any target industry keyword.
    4. Compute match ratio = (matching titles) / (total titles) (or 0 if no titles).
    5. Update `crawl_priority.target_industry_match` for each prefecture.

### Step 7: Priority Matrix Aggregation Script
- **File**: `scripts/build_priority_matrix.py`
- **Details**:
  - Read `agency_count` from step 4 and `target_industry_match` from step 6 for each prefecture.
  - Calculate score using `priority_scorer.calc_score`.
  - Assign `status="active"` to top prefectures (initial run: prioritize Hokkaido, Tohoku, Shikoku, Kyushu as per plan).
  - Update `crawl_priority` table with `score` and `status`.

### Step 8: Priority Matrix UI Tab
- **File**: `app_admin.py`
- **Details**:
  - Add a new tab labeled "優先度マトリクス".
  - Display a DataFrame with columns: prefecture code, prefecture name, agency count, industry match, score, status.
  - Use `st.dataframe()` to show the table.
  - Fetch data from `crawl_priority` table.

## Implementation Notes
- Each step should be implemented as a separate file or modification.
- After each step, run `python -m py_compile` on the new/modified files to check syntax.
- After completing all steps, run migrations if any models changed (though we are adding a new model, so we need an Alembic migration).
- However, the 72-step plan does not mention migrations for these steps; we will create a migration script for the new model.

## Migration for CrawlPriority Model
- We will create an Alembic migration script after implementing step 1.
- The migration will create the `crawl_priority` table.

## Order of Implementation
1. Step 1: Model
2. Create migration for model
3. Step 2: Prefectures constants
4. Step 3: Priority scorer service
5. Step 4: Count agencies script
6. Step 5: Target industries config
6. Step 6: Industry match script
7. Step 7: Build priority matrix script
8. Step 8: UI tab

## Testing
- Each script should be runnable and produce expected results.
- After step 4, check that `crawl_priority` table has agency counts.
- After step 6, check that industry match scores are filled.
- After step 7, check that scores and statuses are set.
- After step 8, verify the UI tab shows the data.

## Dependencies
- Ensure `config/prefectures.py` is importable from scripts and services.
- Ensure `services/priority_scorer.py` is importable from scripts.