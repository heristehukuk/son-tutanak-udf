from datetime import timedelta
import json
from app.auth.service import now
from app.database_layer import repos
from app.storage import storage
PENDING_EXPIRY_HOURS = 24

def create_pending(owner_id, case_id, pending_key, filename, kind, incoming, respondents, base_values, base_respondents, locked, locked_resp, conflicts):
    created=now(); expires=created+timedelta(hours=PENDING_EXPIRY_HOURS)
    return repos.pending_merges.create({"owner_id":owner_id,"case_id":case_id,"pending_key":pending_key,"original_filename":filename,"kind":kind or "source","incoming_json":json.dumps(incoming,ensure_ascii=False),"respondents_json":json.dumps(respondents,ensure_ascii=False),"base_values_json":json.dumps(base_values,ensure_ascii=False),"base_respondents_json":json.dumps(base_respondents,ensure_ascii=False),"locked_json":json.dumps(list(locked),ensure_ascii=False),"locked_resp_json":json.dumps(list(locked_resp),ensure_ascii=False),"conflicts_json":json.dumps(conflicts,ensure_ascii=False),"status":"pending","created_at":created.isoformat(),"expires_at":expires.isoformat()})

def get_pending_for_user(pending_key,user):
    row=repos.pending_merges.get_by_key(pending_key) if pending_key else None
    if not row or row.get("status")!="pending": return None
    if row.get("owner_id")!=user.get("id") and not user.get("is_super_admin"): return None
    return row

def cleanup_expired_pending_merges():
    cutoff=now().isoformat(); removed=[]
    for row in repos.pending_merges.list_expired(cutoff):
        try: storage.delete(row["pending_key"])
        except Exception: pass
        repos.pending_merges.delete(row["id"]); removed.append(row["id"])
    return removed

def serialize_row(row):
    return {"incoming":json.loads(row.get("incoming_json") or "{}"),"respondents":json.loads(row.get("respondents_json") or "[]"),"base_values":json.loads(row.get("base_values_json") or "{}"),"base_respondents":json.loads(row.get("base_respondents_json") or "[]"),"locked":set(json.loads(row.get("locked_json") or "[]")),"locked_resp":set(int(x) for x in json.loads(row.get("locked_resp_json") or "[]")),"conflicts":json.loads(row.get("conflicts_json") or "[]")}
