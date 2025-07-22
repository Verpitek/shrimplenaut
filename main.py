import pymysql
from flask import Flask, jsonify, request, render_template
import math
import os
import warnings
from dotenv import load_dotenv

load_dotenv()

try:
    host = os.environ.get('MYSQL_HOST')
    user = os.environ.get('MYSQL_USER')
    password = os.environ.get('MYSQL_PASSWORD')
    db = os.environ.get('MYSQL_DB')
except:
    warnings.warn("failed to load environment variables")
app = Flask(__name__)
db = pymysql.connect(host=host,
                     user=user,
                     password=password,
                     database=db)
cursor = db.cursor()

cursor.execute("SELECT * FROM packages")
rows = cursor.fetchall()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/usage')
def usage():
    return render_template('usage.html')
@app.route("/packages")
def packages():
    # Get pagination parameters with defaults and constraints
    page = request.args.get('page', default=1, type=int)
    per_page = min(request.args.get('per_page', default=10, type=int), 100)  # Max 100 items
    tag = request.args.get('tag', default=None, type=str)

    # Calculate offset
    offset = (page - 1) * per_page

    # Fetch paginated results
    cursor.execute("""
                   SELECT *
                   FROM packages LIMIT %s
                   OFFSET %s
                   """, (per_page, offset))
    if tag is not None:
        cursor.execute("""
        SELECT *
        FROM packages 
        WHERE tag = %s
        LIMIT %s
        OFFSET %s
        """, (tag, per_page, offset))
    rows = cursor.fetchall()

    # Get total count for pagination metadata
    cursor.execute("SELECT COUNT(*) FROM packages")
    total_items = cursor.fetchone()[0]
    total_pages = math.ceil(total_items / per_page)

    return jsonify({
        "items": rows,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_items": total_items,
            "total_pages": total_pages
        }
    })

if __name__ == "__main__":
    app.run(debug=True)