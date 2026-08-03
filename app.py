"""
AI-Powered Business Intelligence Dashboard
Flask Backend - Production Ready
"""

import os
import re
import json
import uuid
from datetime import datetime
from flask import (
    Flask, render_template, request, jsonify, 
    send_file, session, redirect, url_for
)
import pandas as pd
import numpy as np
from werkzeug.utils import secure_filename
from io import BytesIO

# -------------------------------------------------
# App Configuration
# -------------------------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "bi-dashboard-secret-key-change-in-prod")

# Local pe "uploads/", Vercel pe "/tmp/bi_uploads"
_upload = (
    os.path.join("/tmp", "bi_uploads")
    if os.environ.get("VERCEL")
    else os.path.join(os.path.dirname(__file__), "uploads")
)
app.config["UPLOAD_FOLDER"] = _upload
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB
app.config["ALLOWED_EXTENSIONS"] = {"csv", "xlsx", "xls"}

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

# In-memory store for processed data (for demo; use Redis/DB in production)
DATA_STORE = {}

# Last file save paths (naya upload hone tak purana data dikhe)
LAST_DATA_FILE = os.path.join(app.config["UPLOAD_FOLDER"], "last_session.json")
LAST_DF_FILE = os.path.join(app.config["UPLOAD_FOLDER"], "last_df.pkl")

# -------------------------------------------------
# Utility Helpers
# -------------------------------------------------
def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in app.config["ALLOWED_EXTENSIONS"]


def clean_number(val):
    """Convert messy number strings to float."""
    if pd.isna(val) or val is None:
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    # Remove currency symbols, commas, spaces, special chars
    s = re.sub(r"[^\d.\-]", "", s)
    if s in ("", "-", ".", "-."):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def detect_columns(df):
    """
    Automatically detect semantic roles of columns based on name patterns.
    Returns a dict of role -> list of column names.
    """
    roles = {
        "date": [],
        "month": [],
        "year": [],
        "customer": [],
        "product": [],
        "category": [],
        "region": [],
        "state": [],
        "city": [],
        "sales": [],
        "revenue": [],
        "amount": [],
        "quantity": [],
        "profit": [],
        "loss": [],
        "growth": [],
        "code": [],
        "id": [],
        "other_numeric": [],
        "other_categorical": [],
    }

    # Patterns (case-insensitive)
    patterns = {
        "date": [r"date", r"invoice.?date", r"order.?date", r"transaction.?date"],
        "month": [r"month", r"period"],
        "year": [r"year", r"fy", r"fiscal"],
        "customer": [r"customer", r"client", r"party.?name", r"buyer", r"account.?name"],
        "product": [r"product", r"item", r"sku", r"material"],
        "category": [r"category", r"type", r"segment", r"class", r"party.?category"],
        "region": [r"region", r"zone", r"territory"],
        "state": [r"state", r"province", r"party.?group", r"group.?description"],
        "city": [r"city", r"town", r"location"],
        "sales": [r"sales", r"sale.?amount"],
        "revenue": [r"revenue", r"turnover"],
        "amount": [r"amount", r"value", r"total", r"row.?total"],
        "quantity": [r"qty", r"quantity", r"units", r"volume"],
        "profit": [r"profit", r"margin", r"gp"],
        "loss": [r"loss"],
        "growth": [r"growth", r"inc.?dec", r"%", r"percent", r"change"],
        "code": [r"code", r"id", r"customer.?code"],
        "id": [r"^id$", r"key"],
    }

    for col in df.columns:
        col_lower = str(col).lower().strip()
        matched = False
        for role, pats in patterns.items():
            for pat in pats:
                if re.search(pat, col_lower):
                    roles[role].append(col)
                    matched = True
                    break
            if matched:
                break
        if not matched:
            if pd.api.types.is_numeric_dtype(df[col]):
                roles["other_numeric"].append(col)
            else:
                roles["other_categorical"].append(col)

    return roles


def smart_clean_dataframe(df_raw):
    """
    Clean a raw uploaded dataframe.
    Handles multi-header CSVs like the sample sales file.
    """
    df = df_raw.copy()

    # Drop completely empty rows/cols
    df = df.dropna(how="all").dropna(axis=1, how="all")

    # Detect multi-row headers (month names on row 0, labels on row 1)
    if len(df) > 2:
        first_row_vals = [str(v).strip().lower() for v in df.iloc[0].tolist()]
        second_row_vals = [str(v).strip().lower() for v in df.iloc[1].tolist()]
        months = ["april", "may", "june", "july", "august", "september", "october",
                  "november", "december", "january", "february", "march"]
        has_months = any(any(m in v for m in months) for v in first_row_vals)
        has_labels = any("customer" in v or "amount" in v or "party" in v or "code" in v for v in second_row_vals)

        if has_months or has_labels:
            new_cols = []
            for i in range(len(df.columns)):
                v0 = str(df.iloc[0, i]).strip() if pd.notna(df.iloc[0, i]) else ""
                v1 = str(df.iloc[1, i]).strip() if len(df) > 1 and pd.notna(df.iloc[1, i]) else ""
                # Prefer meaningful label from row 1; fall back to month from row 0
                if v1 and v1.lower() not in ("nan", "", "amount"):
                    name = re.sub(r"\s+", " ", v1).strip()
                    new_cols.append(name)
                elif v0 and v0.lower() not in ("nan", ""):
                    name = re.sub(r"\s+", " ", v0).strip()
                    new_cols.append(name)
                else:
                    new_cols.append(f"col_{i}")
            df.columns = new_cols
            df = df.iloc[2:].reset_index(drop=True)

    # Clean column names
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
    # Make unique
    seen = {}
    new_cols = []
    for c in df.columns:
        if c in seen:
            seen[c] += 1
            new_cols.append(f"{c}_{seen[c]}")
        else:
            seen[c] = 0
            new_cols.append(c)
    df.columns = new_cols

    # Drop total / empty rows
    mask_total = pd.Series([False] * len(df))
    for col in df.columns[:4]:
        mask_total |= df[col].astype(str).str.lower().str.contains(
            r"total|grand|sum|overall", na=False
        )
    mask_empty = df.iloc[:, :3].isna().all(axis=1)
    df = df[~(mask_total | mask_empty)]

    # Convert numeric-looking columns
    for col in df.columns:
        sample = df[col].dropna().head(30).astype(str)
        if len(sample) == 0:
            continue
        numeric_count = sum(
            1 for v in sample
            if re.search(r"[\d,\.]", str(v)) and not re.search(r"[a-zA-Z]{3,}", str(v))
        )
        if numeric_count / max(len(sample), 1) > 0.5:
            df[col] = df[col].apply(clean_number)

    df = df.reset_index(drop=True)
    return df


def generate_kpis(df, roles):
    """Generate key performance indicators."""
    kpis = []

    # Total Revenue / Sales / Amount
    amount_cols = roles["amount"] + roles["sales"] + roles["revenue"] + roles["other_numeric"]
    # Prefer columns that look like totals or monthly amounts
    total_rev = 0
    for col in amount_cols:
        if df[col].dtype in [np.float64, np.int64, float, int]:
            s = df[col].sum()
            if s > total_rev:
                total_rev = s

    # Also try month columns specifically
    month_like = [c for c in df.columns if any(m in str(c).lower() 
                  for m in ["april", "may", "june", "july", "aug", "sep", "oct", "nov", "dec", "jan", "feb", "mar"])]
    if month_like:
        total_rev = sum(df[c].sum() for c in month_like if pd.api.types.is_numeric_dtype(df[c]))

    kpis.append({
        "title": "Total Revenue",
        "value": total_rev,
        "format": "currency",
        "icon": "fa-rupee-sign",
        "color": "primary"
    })

    # Number of customers
    cust_cols = roles["customer"] + roles["code"]
    n_customers = 0
    if cust_cols:
        n_customers = df[cust_cols[0]].nunique()
    else:
        n_customers = len(df)
    kpis.append({
        "title": "Customers",
        "value": n_customers,
        "format": "number",
        "icon": "fa-users",
        "color": "success"
    })

    # Number of products / categories
    cat_cols = roles["category"] + roles["product"]
    n_cats = 0
    if cat_cols:
        n_cats = df[cat_cols[0]].nunique()
    kpis.append({
        "title": "Categories / Products",
        "value": n_cats,
        "format": "number",
        "icon": "fa-tags",
        "color": "info"
    })

    # Regions / States
    reg_cols = roles["state"] + roles["region"] + roles["city"]
    n_regions = 0
    if reg_cols:
        n_regions = df[reg_cols[0]].nunique()
    kpis.append({
        "title": "Regions / States",
        "value": n_regions,
        "format": "number",
        "icon": "fa-map-marker-alt",
        "color": "warning"
    })

    # Average order / record value
    avg_val = total_rev / max(len(df), 1)
    kpis.append({
        "title": "Avg. Value per Record",
        "value": avg_val,
        "format": "currency",
        "icon": "fa-chart-line",
        "color": "secondary"
    })

    # Growth if available
    growth_cols = roles["growth"]
    if growth_cols:
        # Try to find a numeric growth column
        for gc in growth_cols:
            if pd.api.types.is_numeric_dtype(df[gc]):
                avg_growth = df[gc].mean()
                kpis.append({
                    "title": "Avg. Growth %",
                    "value": avg_growth,
                    "format": "percent",
                    "icon": "fa-percentage",
                    "color": "danger" if avg_growth < 0 else "success"
                })
                break

    return kpis


def prepare_chart_data(df, roles):
    """Prepare data structures for various charts based on detected columns."""
    charts = {}

    # Identify month columns
    month_order = ["April", "May", "June", "July", "August", "September",
                   "October", "November", "December", "January", "February", "March"]
    month_cols = []
    for m in month_order:
        for c in df.columns:
            if m.lower() in str(c).lower() and pd.api.types.is_numeric_dtype(df[c]):
                month_cols.append(c)
                break

    # If no named months, use numeric amount columns
    amount_cols = [c for c in (roles["amount"] + roles["sales"] + roles["revenue"] + roles["other_numeric"])
                   if pd.api.types.is_numeric_dtype(df[c])]

    # 1. Monthly Trend (Line)
    if month_cols:
        monthly_totals = [float(df[c].sum()) for c in month_cols]
        charts["monthly_trend"] = {
            "type": "line",
            "title": "Monthly Sales Trend",
            "labels": [c.split("_")[0] if "_" in c else c for c in month_cols],
            "datasets": [{"name": "Sales", "data": monthly_totals}]
        }

    # 2. Category / Product Breakdown (Pie / Donut)
    cat_col = None
    for role in ["category", "product"]:
        if roles[role]:
            cat_col = roles[role][0]
            break
    if cat_col and month_cols:
        cat_sales = df.groupby(cat_col)[month_cols].sum().sum(axis=1).sort_values(ascending=False)
        charts["category_pie"] = {
            "type": "pie",
            "title": f"Sales by {cat_col}",
            "labels": cat_sales.index.astype(str).tolist()[:12],
            "data": cat_sales.values.tolist()[:12]
        }
        charts["category_donut"] = {
            "type": "donut",
            "title": f"Share by {cat_col}",
            "labels": cat_sales.index.astype(str).tolist()[:10],
            "data": cat_sales.values.tolist()[:10]
        }

    # 3. Region / State Bar
    reg_col = None
    for role in ["state", "region", "city"]:
        if roles[role]:
            reg_col = roles[role][0]
            break
    if reg_col and month_cols:
        reg_sales = df.groupby(reg_col)[month_cols].sum().sum(axis=1).sort_values(ascending=False)
        charts["region_bar"] = {
            "type": "bar",
            "title": f"Sales by {reg_col}",
            "labels": reg_sales.index.astype(str).tolist()[:15],
            "datasets": [{"name": "Sales", "data": reg_sales.values.tolist()[:15]}]
        }

    # 4. Top 10 Customers
    cust_col = None
    for role in ["customer", "code"]:
        if roles[role]:
            cust_col = roles[role][0]
            break
    if not cust_col and "Customer Code" in df.columns:
        cust_col = "Customer Code"
    if cust_col and month_cols:
        # Prefer name if available
        name_col = None
        for c in df.columns:
            if "name" in str(c).lower() and "customer" in str(c).lower():
                name_col = c
                break
        group_col = name_col if name_col and df[name_col].notna().any() else cust_col
        top_cust = df.groupby(group_col)[month_cols].sum().sum(axis=1).sort_values(ascending=False).head(10)
        charts["top_customers"] = {
            "type": "bar",
            "title": "Top 10 Customers",
            "labels": top_cust.index.astype(str).tolist(),
            "datasets": [{"name": "Sales", "data": top_cust.values.tolist()}]
        }
        bottom_cust = df.groupby(group_col)[month_cols].sum().sum(axis=1).sort_values(ascending=True).head(10)
        charts["bottom_customers"] = {
            "type": "bar",
            "title": "Bottom 10 Customers",
            "labels": bottom_cust.index.astype(str).tolist(),
            "datasets": [{"name": "Sales", "data": bottom_cust.values.tolist()}]
        }

    # 5. Heatmap-like: Region x Month
    if reg_col and month_cols:
        pivot = df.groupby(reg_col)[month_cols].sum()
        # Limit to top regions
        top_regs = pivot.sum(axis=1).sort_values(ascending=False).head(10).index
        pivot = pivot.loc[top_regs]
        charts["heatmap"] = {
            "type": "heatmap",
            "title": f"{reg_col} × Month Heatmap",
            "x_labels": [c.split("_")[0] if "_" in c else c for c in month_cols],
            "y_labels": pivot.index.astype(str).tolist(),
            "data": pivot.values.tolist()
        }

    # 6. Treemap (Category)
    if cat_col and month_cols:
        cat_sales = df.groupby(cat_col)[month_cols].sum().sum(axis=1).sort_values(ascending=False)
        charts["treemap"] = {
            "type": "treemap",
            "title": f"Sales Treemap – {cat_col}",
            "data": [{"name": str(k), "value": float(v)} for k, v in cat_sales.items()]
        }

    # 7. Growth analysis if available
    growth_col = None
    for c in df.columns:
        if "inc" in str(c).lower() or "growth" in str(c).lower() or "% " in str(c).lower():
            if pd.api.types.is_numeric_dtype(df[c]):
                growth_col = c
                break
    if growth_col and reg_col:
        growth_by_reg = df.groupby(reg_col)[growth_col].mean().sort_values(ascending=False)
        charts["growth_bar"] = {
            "type": "bar",
            "title": "Avg Growth % by Region",
            "labels": growth_by_reg.index.astype(str).tolist()[:12],
            "datasets": [{"name": "Growth %", "data": growth_by_reg.values.tolist()[:12]}]
        }

    return charts


def generate_ai_insights(df, roles, kpis, charts):
    """
    Rule-based AI Insights & Recommendations.
    In production you can plug in an LLM; here we use deterministic analytics.
    """
    insights = []
    recommendations = []

    # Total revenue
    total = next((k["value"] for k in kpis if k["title"] == "Total Revenue"), 0)

    insights.append({
        "type": "summary",
        "title": "Overall Performance",
        "text": f"Total recorded revenue across the dataset is ₹{total:,.0f}. "
                f"There are {len(df)} transaction / customer records."
    })

    # Monthly trend insight
    if "monthly_trend" in charts:
        data = charts["monthly_trend"]["datasets"][0]["data"]
        labels = charts["monthly_trend"]["labels"]
        if len(data) >= 2:
            change = data[-1] - data[-2]
            pct = (change / data[-2] * 100) if data[-2] else 0
            direction = "increased" if change > 0 else "decreased"
            insights.append({
                "type": "trend",
                "title": "Recent Month Trend",
                "text": f"Sales {direction} by ₹{abs(change):,.0f} ({pct:+.1f}%) from "
                        f"{labels[-2]} to {labels[-1]}."
            })
            if pct < -10:
                recommendations.append({
                    "priority": "high",
                    "text": f"Investigate the {pct:.1f}% drop in the latest month. "
                            "Review customer churn, pricing, or supply issues."
                })
            elif pct > 20:
                recommendations.append({
                    "priority": "medium",
                    "text": f"Strong growth of {pct:.1f}% last month. Consider scaling "
                            "inventory and marketing for high-performing regions."
                })

    # Top region
    if "region_bar" in charts:
        labels = charts["region_bar"]["labels"]
        data = charts["region_bar"]["datasets"][0]["data"]
        if labels:
            top = labels[0]
            share = data[0] / sum(data) * 100 if sum(data) else 0
            insights.append({
                "type": "region",
                "title": "Top Performing Region",
                "text": f"{top} contributes the highest sales (≈{share:.1f}% of total "
                        f"among top regions)."
            })
            if share > 40:
                recommendations.append({
                    "priority": "medium",
                    "text": f"Heavy concentration in {top}. Diversify sales efforts "
                            "into other states to reduce geographic risk."
                })

    # Category insight
    if "category_pie" in charts:
        labels = charts["category_pie"]["labels"]
        data = charts["category_pie"]["data"]
        if labels:
            top_cat = labels[0]
            share = data[0] / sum(data) * 100 if sum(data) else 0
            insights.append({
                "type": "category",
                "title": "Dominant Category",
                "text": f"'{top_cat}' accounts for approximately {share:.1f}% of sales."
            })

    # Customer concentration
    if "top_customers" in charts:
        data = charts["top_customers"]["datasets"][0]["data"]
        if data:
            top10_share = sum(data) / total * 100 if total else 0
            insights.append({
                "type": "customer",
                "title": "Customer Concentration",
                "text": f"Top 10 customers represent ≈{top10_share:.1f}% of total revenue."
            })
            if top10_share > 50:
                recommendations.append({
                    "priority": "high",
                    "text": "High customer concentration risk. Develop retention programs "
                            "for key accounts and expand the mid-tier customer base."
                })

    # Growth recommendation
    if "growth_bar" in charts:
        data = charts["growth_bar"]["datasets"][0]["data"]
        labels = charts["growth_bar"]["labels"]
        if data:
            best = labels[0]
            worst = labels[-1]
            recommendations.append({
                "priority": "medium",
                "text": f"Focus growth initiatives on under-performing regions such as "
                        f"{worst}. Replicate success factors from {best}."
            })

    # Generic best practices
    recommendations.append({
        "priority": "low",
        "text": "Set up automated monthly dashboards and anomaly alerts for early detection "
                "of sales drops or inventory issues."
    })
    recommendations.append({
        "priority": "low",
        "text": "Segment customers by value (ABC analysis) and tailor pricing / service levels."
    })

    return insights, recommendations


def prepare_table_data(df, max_rows=500):
    """Prepare data for DataTables."""
    # Limit rows for performance
    display_df = df.head(max_rows).copy()
    # Convert everything to JSON-serializable
    for col in display_df.columns:
        if pd.api.types.is_numeric_dtype(display_df[col]):
            display_df[col] = display_df[col].round(2)
        else:
            display_df[col] = (
                display_df[col]
                .astype(str)
                .replace({"nan": "", "None": "", "NaT": ""})
                .fillna("")
            )
    return {
        "columns": list(display_df.columns),
        "data": display_df.values.tolist()
    }

def load_last_session():
    """Purana saved data load karo agar naya upload nahi hua."""
    try:
        if not os.path.exists(LAST_DATA_FILE) or not os.path.exists(LAST_DF_FILE):
            return None
        with open(LAST_DATA_FILE, "r", encoding="utf-8") as f:
            meta = json.load(f)
        df = pd.read_pickle(LAST_DF_FILE)
        sid = meta.get("session_id") or uuid.uuid4().hex
        DATA_STORE[sid] = {
            "df": df,
            "roles": meta.get("roles", {}),
            "filename": meta.get("filename", "last_file"),
            "uploaded_at": meta.get("uploaded_at", ""),
        }
        return sid
    except Exception:
        return None

# -------------------------------------------------
# Routes
# -------------------------------------------------
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    if not allowed_file(file.filename):
        return jsonify({"error": "Only CSV / Excel files are allowed"}), 400

    try:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], f"{uuid.uuid4().hex}_{filename}")
        file.save(filepath)

        # Read file
        if filename.lower().endswith(".csv"):
            # Try different encodings and separators
            try:
                df_raw = pd.read_csv(filepath, header=None, encoding="utf-8", low_memory=False)
            except UnicodeDecodeError:
                df_raw = pd.read_csv(filepath, header=None, encoding="latin-1", low_memory=False)
        else:
            df_raw = pd.read_excel(filepath, header=None)

        # Clean
        df = smart_clean_dataframe(df_raw)

        if df.empty:
            return jsonify({"error": "Could not extract usable data from the file"}), 400

        # Detect roles
        roles = detect_columns(df)

        # KPIs
        kpis = generate_kpis(df, roles)

        # Charts
        charts = prepare_chart_data(df, roles)

        # AI Insights
        insights, recommendations = generate_ai_insights(df, roles, kpis, charts)

        # Table
        table = prepare_table_data(df)

        # Store in memory
        session_id = uuid.uuid4().hex
        DATA_STORE[session_id] = {
            "df": df,
            "roles": roles,
            "filename": filename,
            "uploaded_at": datetime.now().isoformat()
        }
        session["data_id"] = session_id

        # Save last session (naya file aane tak yeh data rahega)
        try:
            df.to_pickle(LAST_DF_FILE)
            meta = {
                "session_id": session_id,
                "filename": filename,
                "uploaded_at": datetime.now().isoformat(),
                "roles": roles,
            }
            with open(LAST_DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(meta, f)
        except Exception:
            pass

        return jsonify({
            "success": True,
            "session_id": session_id,
            "filename": filename,
            "rows": len(df),
            "columns": list(df.columns),
            "kpis": kpis,
            "charts": charts,
            "insights": insights,
            "recommendations": recommendations,
            "table": table,
            "roles": {k: v for k, v in roles.items() if v}
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500


@app.route("/dashboard")
def dashboard():
    data_id = session.get("data_id")
    if not data_id or data_id not in DATA_STORE:
        data_id = load_last_session()
        if data_id:
            session["data_id"] = data_id
        else:
            return redirect(url_for("index"))
    return render_template("dashboard.html")


@app.route("/api/data")
def api_data():
    data_id = session.get("data_id") or request.args.get("session_id")
    if not data_id or data_id not in DATA_STORE:
        data_id = load_last_session()
        if data_id:
            session["data_id"] = data_id
        else:
            return jsonify({"error": "No data loaded"}), 404

    store = DATA_STORE[data_id]
    df = store["df"]
    roles = store["roles"]

    kpis = generate_kpis(df, roles)
    charts = prepare_chart_data(df, roles)
    insights, recommendations = generate_ai_insights(df, roles, kpis, charts)
    table = prepare_table_data(df)

    return jsonify({
        "filename": store["filename"],
        "rows": len(df),
        "columns": list(df.columns),
        "kpis": kpis,
        "charts": charts,
        "insights": insights,
        "recommendations": recommendations,
        "table": table,
        "roles": {k: v for k, v in roles.items() if v}
    })


@app.route("/api/filter", methods=["POST"])
def api_filter():
    """Apply simple filters and return refreshed KPIs/charts."""
    data_id = session.get("data_id")
    if not data_id or data_id not in DATA_STORE:
        return jsonify({"error": "No data"}), 404

    payload = request.get_json() or {}
    filters = payload.get("filters", {})

    df = DATA_STORE[data_id]["df"].copy()
    roles = DATA_STORE[data_id]["roles"]

    for col, values in filters.items():
        if col in df.columns and values:
            df = df[df[col].astype(str).isin([str(v) for v in values])]

    kpis = generate_kpis(df, roles)
    charts = prepare_chart_data(df, roles)
    table = prepare_table_data(df)

    return jsonify({
        "kpis": kpis,
        "charts": charts,
        "table": table,
        "rows": len(df)
    })


@app.route("/export/<fmt>")
def export(fmt):
    data_id = session.get("data_id")
    if not data_id or data_id not in DATA_STORE:
        return jsonify({"error": "No data"}), 404

    df = DATA_STORE[data_id]["df"]

    if fmt == "csv":
        buf = BytesIO()
        df.to_csv(buf, index=False)
        buf.seek(0)
        return send_file(buf, mimetype="text/csv",
                         as_attachment=True, download_name="export.csv")
    elif fmt == "excel":
        buf = BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Data")
        buf.seek(0)
        return send_file(buf, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                         as_attachment=True, download_name="export.xlsx")
    else:
        return jsonify({"error": "Unsupported format"}), 400


@app.route("/api/filter_options")
def filter_options():
    data_id = session.get("data_id")
    if not data_id or data_id not in DATA_STORE:
        return jsonify({})
    df = DATA_STORE[data_id]["df"]
    roles = DATA_STORE[data_id]["roles"]

    options = {}
    for role in ["category", "state", "region", "product", "customer"]:
        for col in roles.get(role, []):
            if col in df.columns:
                vals = df[col].dropna().astype(str).unique().tolist()
                options[col] = sorted(vals)[:100]  # limit
    return jsonify(options)


# -------------------------------------------------
# Run
# -------------------------------------------------
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)