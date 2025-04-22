import os
import csv
import uuid
import pytz
import threading
import asyncio
from datetime import datetime, timedelta, time as dt_time
from flask import Flask, jsonify, send_file, request
from flask_sqlalchemy import SQLAlchemy
from io import StringIO
from wsgiref.simple_server import make_server
import ngrok
import nest_asyncio

nest_asyncio.apply()
os.environ["NGROK_AUTH_TOKEN"] = "2w2siUUtSLaKS2WlUOM5q43RTxp_6wGyexJwbs3aBrtQs8W2Q"

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///store_monitoring.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

class StoreStatus(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.String(50), nullable=False)
    timestamp_utc = db.Column(db.DateTime(timezone=True), nullable=False)
    status = db.Column(db.String(10), nullable=False)

class BusinessHours(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.String(50), nullable=False)
    day_of_week = db.Column(db.Integer, nullable=False)
    start_time_local = db.Column(db.Time, nullable=False)
    end_time_local = db.Column(db.Time, nullable=False)

class StoreTimezone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    store_id = db.Column(db.String(50), nullable=False)
    timezone_str = db.Column(db.String(50), nullable=False, default='America/Chicago')

class Report(db.Model):
    report_id = db.Column(db.String(50), primary_key=True)
    status = db.Column(db.String(20), default='Running')
    csv_data = db.Column(db.Text)

def load_csv_data():
    with app.app_context():
        db.create_all()
        if not StoreTimezone.query.first():
            with open('timezones.csv', 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    db.session.add(StoreTimezone(
                        store_id=row['store_id'],
                        timezone_str=row['timezone_str']
                    ))

            with open('menu_hours.csv', 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    db.session.add(BusinessHours(
                        store_id=row['store_id'],
                        day_of_week=int(row['dayOfWeek']),
                        start_time_local=datetime.strptime(row['start_time_local'], '%H:%M:%S').time(),
                        end_time_local=datetime.strptime(row['end_time_local'], '%H:%M:%S').time()
                    ))

            with open('store_status.csv', 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    db.session.add(StoreStatus(
                        store_id=row['store_id'],
                        timestamp_utc=pytz.utc.localize(datetime.strptime(row['timestamp_utc'], '%Y-%m-%d %H:%M:%S.%f UTC')),
                        status=row['status']
                    ))

            db.session.commit()

def get_max_timestamp():
    max_time = db.session.query(db.func.max(StoreStatus.timestamp_utc)).scalar()
    return max_time or pytz.utc.localize(datetime.utcnow())

def generate_report(report_id):
    with app.app_context():
        current_time = get_max_timestamp()
        cutoff_times = {
            'hour': current_time - timedelta(hours=1),
            'day': current_time - timedelta(days=1),
            'week': current_time - timedelta(weeks=1)
        }

        status_data = StoreStatus.query.all()
        store_ids = {s.store_id for s in db.session.query(StoreStatus.store_id).distinct()}
        business_map = {sid: ['']*7 for sid in store_ids}
        for bh in BusinessHours.query.all():
            business_map[bh.store_id][bh.day_of_week] = (bh.start_time_local, bh.end_time_local)

        timezone_map = {tz.store_id: tz.timezone_str for tz in StoreTimezone.query.all()}
        summary = []

        for store_id in store_ids:
            tz_str = timezone_map.get(store_id, 'America/Chicago')
            tz = pytz.timezone(tz_str)
            store_status = [s for s in status_data if s.store_id == store_id]
            store_status.sort(key=lambda x: x.timestamp_utc)
            metrics = {'hour': (0, 0), 'day': (0, 0), 'week': (0, 0)}

            for period, start_time in cutoff_times.items():
                uptime = downtime = 0
                end_time = current_time
                date_range = [start_time + timedelta(days=n) for n in range((end_time - start_time).days + 1)]
                for date in date_range:
                    dow = date.astimezone(tz).weekday()
                    entry = business_map.get(store_id, [('', '')]*7)[dow]
                    if entry == '' or not entry:
                        start_local, end_local = dt_time(0, 0), dt_time(23, 59, 59)
                    else:
                        start_local, end_local = entry
                    local_start = tz.localize(datetime.combine(date.date(), start_local))
                    local_end = tz.localize(datetime.combine(date.date(), end_local))
                    if end_local < start_local:
                        local_end += timedelta(days=1)
                    utc_start = max(local_start.astimezone(pytz.utc), start_time)
                    utc_end = min(local_end.astimezone(pytz.utc), end_time)
                    interval = [s for s in store_status if utc_start <= s.timestamp_utc <= utc_end]
                    if not interval:
                        downtime += (utc_end - utc_start).total_seconds()
                    else:
                        last = utc_start
                        for obs in interval:
                            delta = (obs.timestamp_utc - last).total_seconds()
                            if obs.status == 'active':
                                uptime += delta
                            else:
                                downtime += delta
                            last = obs.timestamp_utc
                        if last < utc_end:
                            delta = (utc_end - last).total_seconds()
                            if interval[-1].status == 'active':
                                uptime += delta
                            else:
                                downtime += delta
                if period == 'hour':
                    metrics[period] = (uptime/60, downtime/60)
                else:
                    metrics[period] = (uptime/3600, downtime/3600)

            summary.append({
                'store_id': store_id,
                'uptime_last_hour': round(metrics['hour'][0]),
                'downtime_last_hour': round(metrics['hour'][1]),
                'uptime_last_day': round(metrics['day'][0], 2),
                'downtime_last_day': round(metrics['day'][1], 2),
                'uptime_last_week': round(metrics['week'][0], 2),
                'downtime_last_week': round(metrics['week'][1], 2)
            })

        csv_output = StringIO()
        csv_output.write('store_id,uptime_last_hour,downtime_last_hour,uptime_last_day,downtime_last_day,uptime_last_week,downtime_last_week\n')
        for row in summary:
            csv_output.write(f"{row['store_id']},{row['uptime_last_hour']},{row['downtime_last_hour']},{row['uptime_last_day']},{row['downtime_last_day']},{row['uptime_last_week']},{row['downtime_last_week']}\n")

        report = db.session.get(Report, report_id)
        report.csv_data = csv_output.getvalue()
        report.status = 'Complete'
        db.session.commit()

@app.route("/")
def root():
    return " Use /trigger_report (POST) and /get_report?report_id= (GET) to generate uptime reports."

@app.route('/trigger_report', methods=['POST'])
def trigger_report():
    report_id = str(uuid.uuid4())
    db.session.add(Report(report_id=report_id))
    db.session.commit()
    thread = threading.Thread(target=generate_report, args=(report_id,))
    thread.start()
    return jsonify({'report_id': report_id})

@app.route('/get_report', methods=['GET'])
def get_report():
    report_id = request.args.get('report_id')
    report = db.session.get(Report, report_id)
    if not report:
        return jsonify({'error': 'Report not found'}), 404
    if report.status == 'Running':
        return jsonify({'status': 'Running'})
    return send_file(
        StringIO(report.csv_data),
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'report_{report_id}.csv'
    )

async def run_server():
    load_csv_data()
    ngrok.set_auth_token(os.environ["NGROK_AUTH_TOKEN"])
    server = make_server("localhost", 5001, app)
    tunnel = await ngrok.listen(server)
    print(f"🌐 Public URL: {tunnel.url()}")
    server.serve_forever()

if __name__ == "__main__":
    asyncio.run(run_server())
