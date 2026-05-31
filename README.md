# Fertility Dashboard

Overview
- Interactive Jupyter notebook and helper code for exploring global fertility data and mapped visualizations.
- Notebook: `main_interactive_v2.ipynb`
- Plotting helpers: `charts.py`
- Data directory: `data/` (includes `country_centroids.json`)

Requirements
- Python 3.8+
- Install dependencies:

```
pip install -r requirements.txt
```

Quick start
1. (Optional) Create and activate a virtual environment:

Windows:

```
python -m venv .venv
.venv\Scripts\activate
```

2. Install requirements:

```
pip install -r requirements.txt
```

3. Launch Jupyter and open the notebook:

```
jupyter lab
# or
jupyter notebook
```

4. Open `main_interactive_v2.ipynb` and run the cells.

Project layout
- `main_interactive_v2.ipynb` — primary interactive notebook.
- `charts.py` — reusable plotting functions used by the notebook.
- `requirements.txt` — Python dependencies.
- `data/` — input data files (e.g., `country_centroids.json`).

Notes
- If datasets grow large, consider sampling or incremental loading in the notebook.
- If you want, I can add a `requirements-dev.txt`, binder configuration, or a small demo script.

Contact
- Open an issue or ask in the repo for help or feature requests.
