# Run Pro Return Tracker Locally

## 1. Install Python

Install **Python 3.11 or newer** from https://www.python.org/downloads/.

## 2. Download the project

Open https://github.com/pixeeleyn/ProReturnTracker, select **Code → Download ZIP**, and extract it.

Open a terminal inside the extracted folder containing `main.py` and `requirements.txt`.

## 3. Install dependencies and start the website

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn main:app --reload
```

### Windows — PowerShell

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn main:app --reload
```

If `py` is unavailable, use `python` for the first command.

## 4. Open the website

Keep the terminal running and open **http://127.0.0.1:8000/** in your browser.

Do not open `index.html` directly.

Click the cartridge, select your **customers**, **orders**, and **returns** CSV files, then click **Upload & Scan**.

Press **Ctrl+C** in the terminal to stop the server.
