import io
from pathlib import Path
from fastapi.testclient import TestClient
from main import app
client=TestClient(app)
base=Path(__file__).parent/'examples'
def scan(changes=None):
 files={n:(f'{n}.csv',(base/f'{n}.csv').read_bytes(),'text/csv') for n in ['customers','orders','returns']}
 for name,raw in (changes or {}).items(): files[name]=(f'{name}.csv',raw,'text/csv')
 return client.post('/analyze',files=files)
r=scan();assert r.status_code==200,r.text
result=r.json();assert result['summary']['total_units_sold']==100
assert result['summary']['total_refunds']==1800
assert result['summary']['unit_return_rate']==20
assert len(result['alerts'])==1 and result['alerts'][0]['rule']=='High Return Rate'
assert scan({'orders':b'wrong\n1\n'}).status_code==422
raw=(base/'orders.csv').read_bytes().replace(b',100,100,',b',bad,100,')
assert scan({'orders':raw}).status_code==422
raw=(base/'returns.csv').read_bytes()+b'R002,O001,2026-01-11,90,100,Damaged in transit\n'
assert scan({'returns':raw}).status_code==422
headers=(base/'returns.csv').read_bytes().splitlines()[0]+b'\n'
r=scan({'returns':headers});assert r.status_code==200,r.text
assert r.json()['summary']['total_refunds']==0 and r.json()['alerts']==[]
assert client.post('/analyze').status_code==422
assert client.get('/health').json()=={'status':'ok'}
print('PASS: pipeline results, alerts, missing columns, invalid numbers, cumulative returns, empty returns, required uploads, health.')
