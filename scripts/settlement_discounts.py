"""Approved, source-backed settlement discounts. Never writes accounting data."""
from collections import defaultdict
from decimal import Decimal
import hashlib,json

VERSION='settlement-discount-attribution-v1'

def collect(connection):
    from settlement_discount_queries import APPS,GL,SOP
    cursor=connection.cursor()
    def get(sql,params=(),cap=20000):
        cursor.execute(sql,params)
        cols=[x[0] for x in cursor.description]
        rows=[dict(zip(cols,r)) for r in cursor.fetchmany(cap+1)]
        if len(rows)>cap:raise ValueError('Settlement source row cap exceeded')
        return rows
    try:
        apps=get(APPS);gl=get(GL,cap=6000);sop=get(SOP,cap=40000)
        nums=sorted({r[k] for r in apps for k in ('invoice','payment')});rm=[]
        fields="RMDTYPAL AS type,RTRIM(DOCNUMBR) AS document,RTRIM(CUSTNMBR) AS customer,CONVERT(char(10),DOCDATE,120) AS date,VOIDSTTS AS voided,RTRIM(SLPRSNID) AS salesperson,CAST(SLSAMNT AS decimal(19,2)) AS sales,CAST(COSTAMNT AS decimal(19,2)) AS cost,CAST(ORTRXAMT AS decimal(19,2)) AS original_amount,RTRIM(TRXSORCE) AS source"
        for off in range(0,len(nums),600):
            part=nums[off:off+600];marks=','.join('CAST(? AS char(21))' for _ in part)
            sql="SELECT 'open' AS lifecycle,"+fields+' FROM dbo.RM20101 WHERE DOCNUMBR IN('+marks+") UNION ALL SELECT 'history',"+fields+' FROM dbo.RM30101 WHERE DOCNUMBR IN('+marks+')'
            rm.extend(get(sql,part+part,5000))
        return dict(apps=apps,gl=gl,sop=sop,rm=rm)
    finally:cursor.close()

def load_approved():
    from pathlib import Path
    path=Path.home()/'OneDrive/Hermes/Documents/SMI Approved Reporting Policies/settlement-discounts-v1-pinned.json'
    raw=path.read_bytes()
    if hashlib.sha256(raw).hexdigest()!='e71e081257257c1f7ad1b149e01ca270fa3cadb0c24432816d433bc2b30e903c':raise ValueError('Approved settlement policy hash changed')
    return json.loads(raw)

def money(value):
    result=Decimal(str(value))
    if not result.is_finite() or result!=result.quantize(Decimal('.01')):
        raise ValueError('Nonfinite or subcent settlement amount')
    return result

def identity(a):
    return json.dumps({k:str(v) if isinstance(v,Decimal) else v for k,v in a.items() if k not in ('row_id','lifecycle')},sort_keys=True)

SOP_FIELDS=('sop','type','customer_id','customer','salesperson','date','sales','raw_cost','voided')
RM_FIELDS=('type','document','customer','date','voided','salesperson','sales','cost','original_amount','source')
MONEY_FIELDS={'sales','raw_cost','cost','original_amount'}

def canonical_source(row, fields=None):
    return json.dumps({k:format(money(row[k]),'.2f') if k in MONEY_FIELDS else row[k]
                       for k in (fields if fields is not None else row)},sort_keys=True,separators=(',',':'))

def pinned_sources_match(event, legs, h, i, p):
    try:
        return (sorted(canonical_source(g) for g in legs)==sorted(canonical_source(g) for g in event['source_GL_rows'])
                and canonical_source(h,SOP_FIELDS)==canonical_source(event['source_sop'],SOP_FIELDS)
                and canonical_source(i,RM_FIELDS)==canonical_source(event['source_rm_invoice'],RM_FIELDS)
                and canonical_source(p,RM_FIELDS)==canonical_source(event['source_rm_payment'],RM_FIELDS))
    except (KeyError,ValueError,TypeError):
        return False

def rm_identity_rows(rows):
    # Only an exact immutable open/history mirror is interchangeable.
    if len(rows)==2 and {r.get('lifecycle') for r in rows}=={'open','history'}:
        if canonical_source(rows[0],RM_FIELDS)==canonical_source(rows[1],RM_FIELDS):
            return [next(r for r in rows if r['lifecycle']=='history')]
    return rows

def apply(rows, approved, evidence):
    buckets=defaultdict(list)
    for a in evidence['apps']:buckets[identity(a)].append(a)
    fresh={};payments=defaultdict(lambda:Decimal(0));glpay=defaultdict(lambda:Decimal(0));glrows=defaultdict(list)
    key=lambda a:(a['customer'],a['payment_type'],a['payment'])
    for text,rs in buckets.items():
        if len(rs)>1 and not (len(rs)==2 and {a['lifecycle'] for a in rs}=={'open','history'}):raise ValueError('Ambiguous same-lifecycle duplicate application')
        a=next((r for r in rs if r['lifecycle']=='history'),rs[0]);fresh[text]=a;payments[key(a)]+=money(a['actual_discount'])
    glids=set()
    for g in evidence['gl']:
        ident=(g['source_table'],g['fiscal_year'],g['row_id'])
        if ident in glids:raise ValueError('duplicate GL source leg')
        glids.add(ident);glpay[key(g)]+=money(g['cost']);glrows[key(g)].append(g)
    sop=defaultdict(list);rm=defaultdict(list);targets=defaultdict(list)
    for h in evidence['sop']:sop[h['sop']].append(h)
    for h in evidence['rm']:rm[(h['customer'],h['type'],h['document'])].append(h)
    approved_ids=set()
    for event in approved:
        text=identity(event['source_application'])
        if text in approved_ids:raise ValueError('duplicate approved application')
        approved_ids.add(text);targets[event['invoice']].append(event)
    result=[];documents=[];exceptions=[];seen=set()
    for source in rows:
        row=dict(source);doc=str(row.get('sop','')).strip();kind=str(row.get('kind','Invoice')).title()
        if kind!='Invoice' or doc not in targets:result.append(row);continue
        if doc in seen:raise ValueError('duplicate transaction target')
        seen.add(doc);events=targets[doc];reasons=[];valid=[]
        for event in events:
            a=fresh.get(identity(event['source_application']))
            if not a:reasons.append('approved_application_changed_or_removed');continue
            pkey=key(a);hs=sop[doc];ii=rm_identity_rows(rm[(a['customer'],1,doc)]);pp=rm_identity_rows(rm[pkey])
            if not (a['invoice_type']==1 and a['payment_type']==9 and a['posted']==1 and money(a['actual_discount'])>0 and '2026-01-01'<=a['invoice_date']<'2026-11-01'):
                reasons.append('unsupported_application_state_or_period');continue
            if payments[pkey]!=glpay[pkey] or glpay[pkey]<=0:reasons.append('payment_net_discount_GL_control_changed');continue
            if len(hs)!=1 or len(ii)!=1 or len(pp)!=1:reasons.append('source_identity_missing_or_ambiguous');continue
            h,i,p=hs[0],ii[0],pp[0]
            if not pinned_sources_match(event,glrows[pkey],h,i,p):
                reasons.append('approved_source_evidence_changed_or_missing');continue
            if any(x['voided'] for x in (h,i,p)):reasons.append('invoice_or_payment_voided');continue
            if not (h['customer_id']==a['customer']==event['customer_id'] and h['salesperson']==event['salesperson']==row['salesperson']):
                reasons.append('original_customer_or_salesperson_changed');continue
            if i['salesperson'] and i['salesperson']!=h['salesperson']:reasons.append('SOP_RM_owner_conflict');continue
            date=str(row.get('document_date',row.get('date')))[:10]
            if not (h['date']==i['date']==date==a['invoice_date']==event['invoice_date']) or p['date']!=a['payment_date']:
                reasons.append('source_date_changed');continue
            if not (money(h['sales'])==money(i['sales'])==money(row['sales'])) or row['customer']!=h['customer']:
                reasons.append('sales_or_customer_name_changed');continue
            original=money(row.get('gp_extended_cost',row['extended_cost']))
            if not (abs(money(h['raw_cost']))==abs(money(i['cost']))==abs(original)):
                reasons.append('source_cost_changed');continue
            current=money(row.get('_settlement_base_cost',row['extended_cost']))
            if not row.get('_misc_7518_bridge'):current=abs(current)
            if current!=money(event['baseline_invoice_cost']):reasons.append('management_base_cost_changed_or_already_incorporated');continue
            valid.append((event,a))
        if reasons or len(valid)!=len(events):
            exceptions.append(dict(sop=doc,kind='Invoice',salesperson=row.get('salesperson'),reasons=sorted(set(reasons))))
            if '_settlement_base_cost' in row:
                row['extended_cost']=row.pop('_settlement_base_cost');row.pop('_settlement_signature',None)
            result.append(row);continue
        old=money(events[0]['baseline_invoice_cost']);delta=sum((money(a['actual_discount']) for _,a in valid),Decimal(0))
        signature=hashlib.sha256(''.join(sorted(identity(a) for _,a in valid)).encode()).hexdigest()
        if '_settlement_signature' in row and (row['_settlement_signature']!=signature or money(row['extended_cost'])!=old+delta):raise ValueError('changed prior settlement application')
        row.setdefault('gp_extended_cost',row['extended_cost']);row['_settlement_base_cost']=float(old);row['_settlement_signature']=signature;row['extended_cost']=float(old+delta)
        documents.append(dict(sop=doc,kind='Invoice',salesperson=row['salesperson'],date=str(row.get('document_date',row.get('date')))[:10],cost_added=float(delta),before_cost=float(old),cost=float(old+delta),profit=float(money(row['sales'])-old-delta),application_ids=[hashlib.sha256(identity(a).encode()).hexdigest() for _,a in valid],payments=sorted({a['payment'] for _,a in valid}),posting_dates=sorted({g['date'] for _,a in valid for g in glrows[key(a)]})))
        result.append(row)
    for doc in set(targets)-seen:exceptions.append(dict(sop=doc,kind='Invoice',reasons=['approved_invoice_missing']))
    return result,dict(version=VERSION,documents=documents,exceptions=exceptions,cost_added=float(sum((money(d['cost_added']) for d in documents),Decimal(0))),company_GL_change=0,date_basis='invoice_document_date',scope='Approved January–October2026 invoice settlement discounts; no new unreviewed applications',source='Actual RM applications reconciled to all-source posted Discounts Given; original salesperson; no GP writes')
