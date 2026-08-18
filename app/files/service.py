
from pathlib import Path
from uuid import uuid4
from app.database import UPLOAD_DIR, GENERATED_DIR
from app.database_layer import repos
from app.auth.service import now

ALLOWED={".udf",".pdf",".jpg",".jpeg",".png"}

def save_document(owner_id,data,filename,kind="source",case_id=None):
    ext=Path(filename or "").suffix.lower()
    if ext not in ALLOWED:raise ValueError("Desteklenen dosyalar: UDF, PDF, JPG, JPEG, PNG.")
    doc_id=str(uuid4());path=UPLOAD_DIR/(doc_id+ext);path.write_bytes(data)
    repos.documents.create({
        "id":doc_id,"case_id":case_id,"owner_id":owner_id,"original_name":filename,
        "stored_path":str(path),"kind":kind,"size_bytes":len(data),"created_at":now().isoformat(),
    })
    return doc_id

def create_case(owner_id,file_no=None,application_no=None,title=None,file_type=None):
    case=repos.cases.create({
        "owner_id":owner_id,"file_no":file_no,"application_no":application_no,
        "title":title,"file_type":file_type,"status":"open",
        "created_at":now().isoformat(),"updated_at":now().isoformat(),
    })
    from app.registry import ensure_registry_no
    ensure_registry_no(case["id"])
    return case["id"]

def save_generated(owner_id,case_id,data,template_name,doc_kind=None,ext=".udf"):
    gid=str(uuid4());path=GENERATED_DIR/(gid+ext);path.write_bytes(data)
    repos.generated_documents.create({
        "id":gid,"case_id":case_id,"owner_id":owner_id,"original_template":template_name,
        "stored_path":str(path),"doc_kind":doc_kind,"created_at":now().isoformat(),
    })
    return gid
