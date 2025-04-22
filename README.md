
# Store Uptime Monitoring Solution

## Overview

This project provides a backend solution for restaurant owners to monitor their store's uptime and downtime during business hours. It uses Flask, SQLAlchemy, and ngrok to provide a REST API for generating reports based on store status and business hours data.

## Features
- **API Endpoints:**
    - `POST /trigger_report` to trigger the generation of a report
    - `GET /get_report?report_id=<id>` to retrieve the generated report
    - `GET /` for a welcome message
- **Timezone-Aware Business Hours**: Converts business hours to UTC and computes uptime and downtime accurately.
- **Asynchronous Processing**: Uses background threading to generate reports without blocking the main thread.

## Performance & Optimization Improvements

### 1. **Query-level Filtering**
- Instead of loading all data into memory, filter records at the database level to improve performance.
```python
status_data = db.session.query(StoreStatus).filter(
    StoreStatus.timestamp_utc >= min(cutoff_times.values())
).all()
```

### 2. **Batch Processing with SQL JOINs**
- Avoid loading all database data into Python memory. Use JOINs for more efficient processing in the database:
    - Pull relevant business hours, timezones, and statuses in a single query.
    - Reduces memory usage and increases execution speed.

## Accuracy & Logic Enhancements

### 3. **Improved Interpolation Between Sparse Polls**
- Interpolate between polling data more accurately by assuming that the last known state persists until the next poll.
- Add logic to handle missing end states if polling stops midway.

### 4. **Store Creation and Closure Times**
- Prevent uptime/downtime calculation from considering stores that were created or closed after the reporting period started.

## Usability Improvements

### 5. **Add Support for Date Range Inputs**
- Users can now specify a date range for reports:
```bash
POST /trigger_report?start=2025-04-01&end=2025-04-07
```
- Makes the API more flexible and valuable for analytics dashboards.

### 6. **Serve Report via HTML Viewer**
- Serve reports in an easily viewable HTML format for quicker inspection, great for stakeholders.
```python
@app.route('/view_report')
def view_report():
    ...
```

## Reliability & Monitoring Enhancements

### 7. **Logging & Monitoring**
- Add structured logging to the application to track report generation, errors, and status updates.
- Log important actions like generating reports or fetching status.

### 8. **Database Indexing**
- Add indexes on `store_id` and `timestamp_utc` to speed up querying times:
```sql
CREATE INDEX idx_store_time ON store_status (store_id, timestamp_utc);
```
- This drastically improves filtering speed when querying statuses.

## Scalability Features

### 9. **Scheduled Reports (Cron Jobs)**
- Generate reports on a scheduled basis (hourly/daily) and store them for later retrieval.
- Utilize tools like Celery, APScheduler, or Cron jobs to automate the report generation process.

### 10. **CSV Export to Cloud (S3, GCS)**
- Automatically upload generated reports to cloud storage (S3, GCS, etc.) to provide permanent access to historical reports.
```python
upload_to_s3(report_id, csv_data)
```

## Example of CSV Output

| store_id                               | uptime_last_hour | downtime_last_hour | uptime_last_day | downtime_last_day | uptime_last_week | downtime_last_week |
|----------------------------------------|------------------|---------------------|------------------|---------------------|-------------------|----------------------|
| b5d0a65d-6d54-47aa-95e9-9312f0353326   | 60               | 0                   | 0                | 0                   | 0                 | 0                    |
| a792089b-e23d-435f-bc18-113b7cc95e11   | 60               | 0                   | 0                | 0                   | 0                 | 0                    |
| 7a242d0e-309c-4915-9755-e9019d69108d   | 60               | 0                   | 0                | 0                   | 0                 | 0                    |
| ca793240-b974-4551-ba0b-649d1a52956c   | 60               | 0                   | 0                | 0                   | 0                 | 0                    |
| 3a2313be-27d9-429f-9906-ccd142d9906c   | 60               | 0                   | 0                | 0                   | 0                 | 0                    |

## Summary of Enhancements

| Area              | Improvement                                 | Impact                     |
|-------------------|---------------------------------------------|----------------------------|
| Performance       | Query-level filtering, SQL JOINs            | 🔥 Faster execution        |
| Accuracy          | Better interpolation, store creation check  | ✅ More correct metrics     |
| Usability         | HTML viewer, date range support             | 🧑‍💻 Easier for clients      |
| Reliability       | Logging, monitoring, indexing               | 🔒 Robust & debuggable     |
| Scalability       | Scheduled jobs, cloud storage               | ☁️ Grows with demand        |

## Getting Started

### 1. Install Dependencies
```bash
pip install flask flask_sqlalchemy pytz pyngrok python-dotenv flask_ngrok nest_asyncio
```

### 2. Run the Application
```bash
python final_uptime_backend_fixed.py
```

The app will start and an **ngrok URL** will be displayed, providing you with public access to the endpoints.

---

### 📌 API Endpoints:

- **POST /trigger_report**: Triggers a report generation.
- **GET /get_report?report_id=<id>**: Fetches a generated report.
- **GET /view_report**: (Optional) View reports directly in HTML format.
