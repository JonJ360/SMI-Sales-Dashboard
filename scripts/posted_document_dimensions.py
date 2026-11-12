"""Read-only immutable posted-header dimensions; no financial or owner changes."""
SQL = """SELECT LTRIM(RTRIM(SOPNUMBE)) AS sop, SOPTYPE AS soptype,
 CAST(DOCDATE AS date) AS date, LTRIM(RTRIM(SLPRSNID)) AS salesperson,
 LTRIM(RTRIM(CUSTNMBR)) AS customer_id, LTRIM(RTRIM(CITY)) AS city,
 LTRIM(RTRIM(STATE)) AS state FROM dbo.SOP30200
 WHERE SOPTYPE IN (3,4) AND VOIDSTTS=0 AND DOCDATE>='2024-01-01'
 AND DOCDATE<DATEADD(day,1,CAST(GETDATE() AS date))"""
def collect(connection):
 connection.timeout=45;cursor=connection.cursor();cursor.execute(SQL)
 fields=['sop','soptype','date','salesperson','customer_id','city','state']
 return build([dict(zip(fields,row)) for row in cursor.fetchall()])
def build(rows):
 documents={};conflicts=set()
 for r in rows:
  key=('Return' if int(r['soptype'])==4 else 'Invoice')+':'+str(r['sop']).strip()
  value={k:str(r.get(k) or '').strip() for k in ['date','salesperson','customer_id','city','state']};value['date']=value['date'][:10]
  if key in documents and documents[key]!=value:conflicts.add(key)
  documents[key]=value
 return dict(version='posted-header-dimensions-v1',source='SMI.dbo.SOP30200',basis='Original posted header; distinct nonblank customer IDs and ship-to city/state; never current customer master',documents={k:v for k,v in documents.items() if k not in conflicts},conflicts=sorted(conflicts))
