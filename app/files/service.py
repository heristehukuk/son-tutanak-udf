
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
    folder_id=None
    if case_id:
        from app.folders.service import ensure_case_folders, folder_for_type
        ensure_case_folders(owner_id, case_id)
        folder=folder_for_type(owner_id, case_id, "source")
        folder_id=folder.get("id") if folder else None
    repos.documents.create({
        "id":doc_id,"case_id":case_id,"owner_id":owner_id,"original_name":filename,
        "stored_path":str(path),"kind":kind,"size_bytes":len(data),"created_at":now().isoformat(),
        "folder_id":folder_id,
    })
    return doc_id

def create_case(owner_id,file_no=None,application_no=None,title=None,file_type=None):
    case=repos.cases.create({
        "owner_id":owner_id,"file_no":file_no,"application_no":application_no,
        "title":title,"file_type":file_type,"status":"open",
        "created_at":now().isoformat(),"updated_at":now().isoformat(),
    })
    try:
        from app.folders.service import ensure_case_folders
        ensure_case_folders(owner_id, case["id"])
    except Exception:
        # Dosya oluşturma, klasör servisindeki geçici bir sorundan dolayı başarısız olmamalı.
        pass
    return case["id"]

def save_generated(owner_id,case_id,data,template_name,doc_kind=None,extension=".udf"):
    ext = extension if str(extension).startswith(".") else "." + str(extension)
    gid=str(uuid4());path=GENERATED_DIR/(gid+ext);path.write_bytes(data)
    folder_id=None
    if case_id:
        from app.folders.service import ensure_case_folders, folder_for_type
        ensure_case_folders(owner_id, case_id)
        mapping={
            "son_tutanak":"final_report",
            "davet_mektubu":"invitation",
            "ucret_pusulasi":"fee",
            "ust_yazi":"cover_letter",
        }
        folder=folder_for_type(owner_id, case_id, mapping.get(doc_kind,"other"))
        folder_id=folder.get("id") if folder else None
    repos.generated_documents.create({
        "id":gid,"case_id":case_id,"owner_id":owner_id,"original_template":template_name,
        "stored_path":str(path),"doc_kind":doc_kind,"folder_id":folder_id,"created_at":now().isoformat(),
    })
    return gid

