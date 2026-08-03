# AI-Powered Business Intelligence Dashboard

Professional Power-BI / Tableau style executive dashboard built with **only**:

- **Backend**: Python, Flask, Pandas, NumPy  
- **Frontend**: HTML5, CSS3, Vanilla JavaScript, Bootstrap 5  
- **Charts**: Apache ECharts  
- **Tables**: DataTables.js  
- **Icons**: Font Awesome  

No React, Vue, Angular or any frontend framework.

## Features

- CSV / Excel upload with drag-and-drop  
- Automatic data cleaning (messy headers, currency symbols, total rows…)  
- Automatic semantic column detection (Customer, State, Category, Month, Amount, Growth…)  
- Dynamic KPI cards  
- Dynamic charts (only relevant ones are generated):
  - Line (Monthly Trend)
  - Bar (Region, Top/Bottom Customers, Growth)
  - Pie & Donut (Category)
  - Treemap
  - Heatmap (Region × Month)
- Dynamic filters  
- Searchable data table  
- Export CSV / Excel / PDF (print)  
- Rule-based **AI Business Insights** & **Recommendations**  
- Dark mode  
- Fully responsive  

## Folder Structure


bi_dashboard/
├── app.py                 # Flask backend + analytics engine
├── requirements.txt
├── README.md
├── uploads/               # Uploaded files (git-ignored in prod)
├── static/
│   ├── css/style.css
│   └── js/dashboard.js
└── templates/
├── index.html         # Upload landing page
└── dashboard.html     # Executive dashboard



## Quick Start

```bash
cd bi_dashboard
pip install -r requirements.txt
python app.py