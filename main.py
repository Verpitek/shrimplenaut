import pymysql
import pymysql.cursors
from flask import Flask, jsonify, request, render_template, url_for, redirect, session
import math
import os
import warnings
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth
load_dotenv()

try:
    host = os.environ.get("MYSQL_HOST")
    user = os.environ.get("MYSQL_USER")
    password = os.environ.get("MYSQL_PASSWORD")
    db_name = os.environ.get("MYSQL_DB")
    secret_key = os.environ.get("SECRET_KEY")
    client_id = os.environ.get("GITHUB_CLIENT_ID")
    client_secret = os.environ.get("GITHUB_CLIENT_SECRET")
except:
    warnings.warn("failed to load environment variables")
app = Flask(__name__)

app.secret_key = secret_key
profile_image = None
oauth = OAuth(app)
github = oauth.register("github",
               client_id=client_id,
               client_secret=client_secret,
               access_token_url="https://github.com/login/oauth/access_token",
               acess_token_params=None,
               authorize_url="https://github.com/login/oauth/authorize",
               authorize_params=None,
               api_base_url="https://api.github.com",
               client_kwargs={"scope": "openid profile email"})

@app.route("/")
def index():
    db = pymysql.connect(host=host,
                         user=user,
                         password=password,
                         database=db_name)
    cursor = db.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT COUNT(*) AS total_count FROM packages")
    total_items = cursor.fetchone()
    github_profile = session.get("github_profile", None)

    return render_template("index.html",
                           package_count=total_items["total_count"],
                           github_profile=github_profile,
                           )

@app.route("/login")
def login():
    redirect_uri = url_for("authorize", _external=True)
    return github.authorize_redirect(redirect_uri)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/authorize")
def authorize():
    token = github.authorize_access_token()
    # you can save the token into database
    profile = github.get("/user", token=token).json()
    session["github_profile"] = {
        "avatar_url": profile["avatar_url"],
        "username": profile["login"],
        "followers": profile["followers"],
        "id": profile["id"]
    }
    return redirect(url_for("index"))

@app.route("/usage")
def usage():
    return render_template("usage.html")

@app.route("/package_explorer")
def package_explorer():
    return render_template("package_explorer.html")
@app.route("/packages")
def packages():
    page = request.args.get("page", default=1, type=int)
    per_page = min(request.args.get("per_page", default=10, type=int), 100)
    tag = request.args.get("tag", default=None, type=str)
    id = request.args.get("id", default=None, type=str)
    name = request.args.get("name", default=None, type=str)
    license = request.args.get("license", default=None, type=str)
    server_platform = request.args.get("server_platform", default=None, type=str)
    project_type = request.args.get("project_type", default=None, type=str)
    search = request.args.get("search", default=None, type=str)

    db = pymysql.connect(host=host,
                         user=user,
                         password=password,
                         database=db_name)
    cursor = db.cursor(pymysql.cursors.DictCursor)

    offset = (page - 1) * per_page

    cursor.execute("""
                   SELECT *
                   FROM packages LIMIT %s
                   OFFSET %s
                   """, (per_page, offset))

    if search is not None:
        cursor.execute("""
        SELECT *
        FROM packages
        WHERE SOUNDEX(name) = SOUNDEX(%s)
        """, search)

    if project_type is not None:
        cursor.execute("""
        SELECT *
        FROM packages
        WHERE project_type = %s
        LIMIT %s OFFSET %s
        """, (project_type, per_page, offset))

    if license is not None:
        cursor.execute("""
        SELECT *
        FROM packages
        WHERE license = %s
        LIMIT %s OFFSET %s
        """, (license, per_page, offset))

    if server_platform is not None:
        cursor.execute("""
        SELECT *
        FROM packages
        WHERE server_platform = %s
        LIMIT %s OFFSET %s
        """, (server_platform, per_page, offset))

    if name is not None:
        cursor.execute("""
        SELECT *
        FROM packages
        WHERE name = %s
        LIMIT %s OFFSET %s
        """, (name, per_page, offset))

    if tag is not None:
        cursor.execute("""
        SELECT *
        FROM packages 
        WHERE tag = %s
        LIMIT %s
        OFFSET %s
        """, (tag, per_page, offset))

    if id is not None:
        cursor.execute("""
        SELECT *
        FROM packages
        WHERE id = %s
        """, id)

    rows = cursor.fetchall()

    # Get total count for pagination metadata
    cursor.execute("SELECT COUNT(*) AS total_count FROM packages")
    total_items = cursor.fetchone()
    total_pages = math.ceil(total_items["total_count"] / per_page)

    return jsonify({
        "items": rows,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total_items": total_items,
            "total_pages": total_pages
        }
    })

@app.route('/search', methods=['GET'])
def search():
    db = pymysql.connect(host=host,
                         user=user,
                         password=password,
                         database=db_name)
    cursor = db.cursor(pymysql.cursors.DictCursor)

    page = request.args.get("page", default=1, type=int)
    per_page = min(request.args.get("per_page", default=10, type=int), 100)
    offset = (page - 1) * per_page

    query = request.args.get('search_query')

    if search is not None:
        cursor.execute("""
        SELECT *
        FROM packages
        WHERE name LIKE %s
        ORDER BY name
        LIMIT %s
        OFFSET %s
        """, (f"%{query}%", per_page, offset))

    rows = cursor.fetchall()
    github_profile = session.get("github_profile", None)

    return render_template("results.html", github_profile=github_profile, results=rows)

if __name__ == "__main__":
    oauth.init_app(app)
    app.run(debug=True)
