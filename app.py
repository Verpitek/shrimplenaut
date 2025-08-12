import asyncio
import queue
from idlelib import query

import pymysql
import pymysql.cursors
from flask import Flask, jsonify, request, render_template, url_for, redirect, session
import math
import os
import warnings
from dotenv import load_dotenv
from authlib.integrations.flask_client import OAuth
import random
import requests
import json
load_dotenv()

# backgrounds
backgrounds_unfiltered = os.listdir("static/img/backgrounds")
backgrounds_filtered = []
for i in range(len(backgrounds_unfiltered)):
    if backgrounds_unfiltered[i] != ".DS_Store":
        backgrounds_filtered.append("static/img/backgrounds/" + backgrounds_unfiltered[i])

try:
    host = os.environ.get("MYSQL_HOST")
    user = os.environ.get("MYSQL_USER")
    password = os.environ.get("MYSQL_PASSWORD")
    db_name = os.environ.get("MYSQL_DB")
    secret_key = os.environ.get("SECRET_KEY")
    client_id = os.environ.get("GITHUB_CLIENT_ID")
    client_secret = os.environ.get("GITHUB_CLIENT_SECRET")
    discord_bot_token = os.environ.get("DISCORD_BOT_TOKEN")
    port = int(os.environ.get("PORT"))
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
                           random_background=random.choice(backgrounds_filtered),
                           custom_script=""
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

@app.route("/my_packages")
def my_packages():

    github_profile = session.get("github_profile", None)
    if github_profile == None:
        return "You are not logged in!"
    author = github_profile["id"]

    try:
        db = pymysql.connect(host=host, user=user, password=password, database=db_name)
        cursor = db.cursor(pymysql.cursors.DictCursor)

        page = request.args.get("page", default=1, type=int)
        per_page = min(request.args.get("per_page", default=10, type=int), 100)
        offset = (page - 1) * per_page

        github_profile = session.get("github_profile", None)

        base_query = "FROM packages"
        where_clauses = ["author = %s"]
        params = [f"{author}"]

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        count_query = f"SELECT COUNT(*) AS total_count {base_query} {where_sql}"
        cursor.execute(count_query, tuple(params))
        total_items = cursor.fetchone()["total_count"]
        total_pages = math.ceil(total_items / per_page) if total_items > 0 else 0

        offset = (page - 1) * per_page
        data_query = f"SELECT * {base_query} {where_sql} LIMIT %s OFFSET %s"
        final_params = tuple(params) + (per_page, offset)
        cursor.execute(data_query, final_params)
        rows = cursor.fetchall()

        results = {
            "items": rows,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_items": total_items,
                "total_pages": total_pages
            }
        }

        return render_template("my_packages.html", github_profile=github_profile, results=results, random_background=random.choice(backgrounds_filtered),)

    except pymysql.MySQLError as e:
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        if "db" in locals() and db.open:
            db.close()

@app.route("/submit_package")
def submit_package():
    github_profile = session.get("github_profile", None)
    return render_template("submit_package.html", github_profile=github_profile, random_background=random.choice(backgrounds_filtered))


@app.route("/packages")
def packages():
    page = request.args.get("page", default=1, type=int)
    per_page = min(request.args.get("per_page", default=10, type=int), 100)
    tag = request.args.get("tag", type=str)
    id = request.args.get("id", type=str)
    name = request.args.get("name", type=str)
    license = request.args.get("license", type=str)
    server_platform = request.args.get("server_platform", type=str)
    project_type = request.args.get("project_type", type=str)
    search = request.args.get("search", type=str)

    try:
        db = pymysql.connect(host=host, user=user, password=password, database=db_name)
        cursor = db.cursor(pymysql.cursors.DictCursor)

        if id:
            cursor.execute("SELECT * FROM packages WHERE id = %s", (id,))
            rows = cursor.fetchall()
            return jsonify({
                "items": rows,
                "pagination": {
                    "page": 1,
                    "per_page": len(rows),
                    "total_items": len(rows),
                    "total_pages": 1 if rows else 0
                }
            })

        base_query = "FROM packages"
        where_clauses = []
        params = []

        if search:
            where_clauses.append("name LIKE %s")
            params.append(f"%{search}%")

        filters = {
            "tag": tag,
            "name": name,
            "license": license,
            "server_platform": server_platform,
            "project_type": project_type
        }

        for column, value in filters.items():
            if value is not None:
                where_clauses.append(f"{column} = %s")
                params.append(value)


        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        count_query = f"SELECT COUNT(*) AS total_count {base_query} {where_sql}"
        cursor.execute(count_query, tuple(params))
        total_items = cursor.fetchone()["total_count"]
        total_pages = math.ceil(total_items / per_page) if total_items > 0 else 0


        offset = (page - 1) * per_page
        data_query = f"SELECT * {base_query} {where_sql} LIMIT %s OFFSET %s"
        final_params = tuple(params) + (per_page, offset)
        cursor.execute(data_query, final_params)
        rows = cursor.fetchall()

        return jsonify({
            "items": rows,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_items": total_items,
                "total_pages": total_pages
            }
        })

    except pymysql.MySQLError as e:
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        if "db" in locals() and db.open:
            db.close()

@app.route("/search", methods=["GET"])
def search():
    try:
        db = pymysql.connect(host=host,
                             user=user,
                             password=password,
                             database=db_name)
        cursor = db.cursor(pymysql.cursors.DictCursor)

        page = request.args.get("page", default=1, type=int)
        per_page = min(request.args.get("per_page", default=10, type=int), 100)
        offset = (page - 1) * per_page
        query = request.args.get("search_query")
        sorting_query = request.args.get("sort_by")

        github_profile = session.get("github_profile", None)

        base_query = "FROM packages"
        where_clauses = []
        params = []

        where_clauses.append("name LIKE %s")
        params.append(f"%{query}%")

        sorting_sql = "ORDER BY id ASC"
        if sorting_query == "upload_date_asc":
            sorting_sql = "ORDER BY created_at ASC"
        if sorting_query == "upload_date_desc":
            sorting_sql = "ORDER BY created_at DESC"
        if sorting_query == "updated_asc":
            sorting_sql = "ORDER BY last_updated ASC"
        if sorting_query == "updated_desc":
            sorting_sql = "ORDER BY last_updated DESC"
        if sorting_query == "random":
            sorting_sql = "ORDER BY RAND()"

        where_sql = ""
        if where_clauses:
            where_sql = "WHERE " + " AND ".join(where_clauses)

        count_query = f"SELECT COUNT(*) AS total_count {base_query} {where_sql}"
        cursor.execute(count_query, tuple(params))
        total_items = cursor.fetchone()["total_count"]
        total_pages = math.ceil(total_items / per_page) if total_items > 0 else 0

        offset = (page - 1) * per_page
        data_query = f"SELECT * {base_query} {where_sql} {sorting_sql} LIMIT %s OFFSET %s"
        final_params = tuple(params) + (per_page, offset)
        cursor.execute(data_query, final_params)
        rows = cursor.fetchall()

        results = {
            "items": rows,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total_items": total_items,
                "total_pages": total_pages
            }
        }


        return render_template("results.html", github_profile=github_profile, results=results, query=query, random_background=random.choice(backgrounds_filtered))

    except pymysql.MySQLError as e:
        return jsonify({"error": f"Database error: {e}"}), 500
    finally:
        if "db" in locals() and db.open:
            db.close()

@app.route("/submit_package_for_approval", methods=["GET"])
def submit_package_for_approval():
    package_name = request.args.get("package_name")
    project_type = request.args.get("project_type")
    current_version = request.args.get("current_version")
    repository_url = request.args.get("repository_url")
    license = request.args.get("license")
    versions_tested = request.args.get("versions_tested")
    tag = request.args.get("tag")
    package_icon = request.args.get("package_icon")

    github_profile = session.get("github_profile", None)
    db = pymysql.connect(host=host,
                         user=user,
                         password=password,
                         database=db_name)
    cursor = db.cursor(pymysql.cursors.DictCursor)
    values = (package_name, github_profile["id"], project_type, current_version, versions_tested, repository_url, license, tag, package_icon)
    if github_profile != None:
        try:
            command_prep = "INSERT INTO not_approved (name, author, project_type, current_version,versions_tested, repository_url, license, tag, package_icon) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)"
            cursor.execute(command_prep, values)
            db.commit()

        except pymysql.MySQLError as e:
            return jsonify({"error": f"Database error: {e}"}), 500
    cursor.execute("SELECT COUNT(*) AS total_count FROM packages")
    total_items = cursor.fetchone()
    if "db" in locals() and db.open:
        db.close()

    url = 'http://127.0.0.1:4747/discord_payload'
    try:
        discord_payload = requests.post(url, json=values)
    except:
        print("Discord payload error")

    return render_template("index.html",
                           package_count=total_items["total_count"],
                           github_profile=github_profile,
                           random_background=random.choice(backgrounds_filtered),
                           custom_script="The package has been submitted for approval"
                           )

if __name__ == "__main__":
    oauth.init_app(app)
    app.run(debug=False, port=port)