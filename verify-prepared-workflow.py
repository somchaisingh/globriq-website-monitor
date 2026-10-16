"""Offline contract checks for the draft. No network or notifications."""
from pathlib import Path
from contextlib import redirect_stdout
from io import StringIO
import ast, datetime, json, urllib.request
from unittest.mock import patch
D = Path(__file__).resolve().parent
source=(D/'prepared-observation-workflow.yml').read_text().split("          python3 - <<'PY'\n",1)[1].split('\n          PY',1)[0]
source='\n'.join(x[10:] for x in source.splitlines())
ast.parse(source)
HOME='https://www.globriq.com/'
CSP="object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'"
SENSITIVE='DO_NOT_PERSIST_CUSTOMER_CONTENT'
class Response:
    def __init__(self,code,headers,body=b''):self.code=code;self.headers=headers;self.body=body
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def read(self,n):return self.body[:n]
class Boundary:
    def __init__(self,case):self.case=case;self.requests=[]
    def open(self,req,timeout):
        url=req.full_url;self.requests.append(req)
        assert req.method=='GET' and req.data is None
        headers={'X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Strict-Transport-Security':'max-age=63072000','Content-Security-Policy':CSP,'Content-Security-Policy-Report-Only':"default-src 'self'"}
        code=200;body=b'<form data-el="cform" action="/api/contact" method="post"></form>'+SENSITIVE.encode()
        if url.endswith('/api/contact'):code=405
        if url=='https://globriq.com/':code=308;headers['Location']=HOME
        if 'globriq-website-' in url:code=302;headers['Location']='https://vercel.com/sso-api?opaque=not-retained'
        if self.case=='pricing5xx' and url.endswith('/pricing'):code=503
        if self.case=='contact5xx' and url.endswith('/api/contact'):code=500
        if self.case=='missingForm' and url==HOME:body=SENSITIVE.encode()
        if self.case=='missingCSP' and url==HOME:headers.pop('Content-Security-Policy')
        if self.case=='noindex' and url==HOME:headers['X-Robots-Tag']='noindex'
        if self.case=='wrongCanonical' and url=='https://globriq.com/':headers['Location']='https://other.invalid/'
        if self.case=='unprotected' and 'globriq-website-' in url:code=200
        if self.case=='wrongSSO' and 'globriq-website-' in url:headers['Location']='https://other.invalid/'
        if self.case=='lookalikeSSO' and 'globriq-website-' in url:headers['Location']='https://vercel.com/sso-api.evil'
        if self.case=='timeout' and url==HOME:raise TimeoutError(SENSITIVE)
        return Response(code,headers,body)
results=[]
for case,want in [('healthy',0),('pricing5xx',1),('contact5xx',1),('missingForm',1),('missingCSP',1),('noindex',1),('wrongCanonical',1),('unprotected',1),('wrongSSO',1),('lookalikeSSO',1),('timeout',1)]:
    boundary=Boundary(case);output=StringIO()
    with patch('urllib.request.build_opener',return_value=boundary),redirect_stdout(output):
        try:exec(compile(source,'draft-observation','exec'),{});got=0
        except SystemExit as e:got=e.code
    assert got==want,(case,got,want)
    assert len(boundary.requests)==7
    assert SENSITIVE not in output.getvalue() and 'opaque=' not in output.getvalue()
    record=json.loads(output.getvalue())
    assert record['readOnly'] and record['checks']==7
    results.append({'case':case,'nativeExit':got,'expectedExit':want,'passed':True})
result={'at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'Offline mocked network boundary executes actual inline probe. No live HTTP, schedule activation or notification receipt.','results':results,'passed':True}
(D/'OBSERVATION-FIXTURE-RESULTS.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps({'passed':True,'cases':len(results),'network':False,'notificationSent':False}))
