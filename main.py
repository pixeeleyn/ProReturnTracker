"""Risk404 upload API. Run: uvicorn main:app --reload"""
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import pandas as pd
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

ROOT = Path(__file__).resolve().parent
MAX_BYTES = 10 * 1024 * 1024
SCHEMAS = {
 'customers': ['customer_id','region','signup_date','segment','payment_terms','credit_limit'],
 'orders': ['order_id','customer_id','product','category','region','order_date','payment_date','quantity','unit_price','discount'],
 'returns': ['return_id','order_id','return_date','quantity_returned','refund_amount','reason'],
}
NUMBERS = {'customers':['credit_limit'], 'orders':['quantity','unit_price','discount'], 'returns':['quantity_returned','refund_amount']}
app = FastAPI(title='Risk404 CSV Analysis API', version='1.0.0')
origins = [x.strip() for x in os.getenv('ALLOWED_ORIGINS','http://localhost:8000,http://127.0.0.1:8000,https://zsp-gameboy-lab.burblingisle256.chatgpt.site').split(',') if x.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=['GET','POST'], allow_headers=['Content-Type'])

@app.get('/')
def home():
 return FileResponse(ROOT/'static'/'index.html')

@app.get('/health')
def health():
 return {'status':'ok'}

def read_input(upload, name):
 if not (upload.filename or '').lower().endswith('.csv'):
  raise HTTPException(422, f'{name}: choose a CSV file.')
 raw = upload.file.read(MAX_BYTES + 1)
 if len(raw)>MAX_BYTES:
  raise HTTPException(413, f'{name}: maximum file size is 10 MiB.')
 try:
  df = pd.read_csv(io.BytesIO(raw), encoding='utf-8-sig', dtype={c:'string' for c in ['order_id','customer_id','return_id']})
 except (ValueError, UnicodeError, pd.errors.ParserError) as exc:
  raise HTTPException(422, f'{name}: invalid UTF-8 CSV.') from exc
 if len(df)>100000:
  raise HTTPException(413, f'{name}: maximum 100,000 rows.')
 missing = sorted(set(SCHEMAS[name])-set(df.columns))
 if missing:
  raise HTTPException(422, f'{name}: missing columns: {", ".join(missing)}')
 for col in NUMBERS[name]:
  df[col] = pd.to_numeric(df[col], errors='coerce')
  if df[col].isna().any() or df[col].isin([float('inf'),float('-inf')]).any():
   raise HTTPException(422, f'{name}: {col} must contain finite numbers in every row.')
 for col in set(df.columns)&{'order_id','customer_id','return_id','product','category','region','reason'}:
  if df[col].isna().any() or df[col].astype(str).str.strip().eq('').any():
   raise HTTPException(422, f'{name}: {col} cannot be blank.')
 # The merge expects these fields to come from orders/customers, not returns.
 if name=='returns':
  extra=set(df.columns)&{'customer_id','product','category','region','quantity','segment','payment_terms','credit_limit'}
  if extra: raise HTTPException(422, 'returns: remove overlapping order/customer columns: '+', '.join(sorted(extra)))
 return df

def records(path):
 return json.loads(pd.read_csv(path).to_json(orient='records', date_format='iso'))

@app.post('/analyze')
def analyze(customers: UploadFile=File(...), orders: UploadFile=File(...), returns: UploadFile=File(...)):
 frames={name:read_input(file,name) for name,file in [('customers',customers),('orders',orders),('returns',returns)]}
 if frames['orders'].empty: raise HTTPException(422,'orders: at least one order is required.')
 # Multiple return records must not collectively claim more units than sold.
 clean_orders=frames['orders'].drop_duplicates()
 clean_returns=frames['returns'].drop_duplicates()
 if clean_orders['order_id'].duplicated().any(): raise HTTPException(422,'orders: conflicting duplicate order IDs.')
 if clean_returns['return_id'].duplicated().any(): raise HTTPException(422,'returns: conflicting duplicate return IDs.')
 totals=clean_returns.groupby('order_id')['quantity_returned'].sum()
 sold=clean_orders.set_index('order_id')['quantity']
 common=totals.index.intersection(sold.index)
 if (totals.loc[common]>sold.loc[common]).any():
  raise HTTPException(422,'returns: cumulative returned quantity exceeds quantity sold for an order.')
 # Each request has its own directory; no upload or generated CSV is shared.
 with tempfile.TemporaryDirectory(prefix='risk404-') as directory:
  work=Path(directory)
  for name,df in frames.items(): df.to_csv(work/f'{name}.csv',index=False)
  for script in ['clean_data.py','analyze_return.py','detect_risks.py']:
   shutil.copyfile(ROOT/'scripts'/script, work/script)
   try:
    result=subprocess.run([sys.executable,str(work/script)],cwd=work,capture_output=True,text=True,timeout=60)
   except subprocess.TimeoutExpired as exc:
    raise HTTPException(408,'Analysis timed out. Try smaller files.') from exc
   if result.returncode:
    detail='The uploaded data could not be analyzed.'
    for line in result.stderr.splitlines():
     if line.startswith('ValueError:'): detail=line.split(':',1)[1].strip()
    raise HTTPException(422, detail)
  output={name:records(work/'analysis_results'/f'{name}.csv') for name in ['summary','product_analysis','reason_analysis','damage_analysis','category_analysis']}
  output['summary']=output['summary'][0]
  output['alerts']=records(work/'automation_results'/'alerts.csv')
  output['tasks']=records(work/'automation_results'/'tasks.csv')
  output['audit']={name:len(pd.read_csv(work/'cleaned_data'/f'{name}.csv')) for name in ['invalid_orders','invalid_returns','unmatched_returns','invalid_return_quantities']}
  output['scope']='Returns and shipping damage; no margin or overdue-invoice analysis.'
  return output
