
from pathlib import Path
from uuid import uuid4
from app.database import connect, UPLOAD_DIR, GENERATED_DIR
from app.auth.service import now

ALLOWED={".udf",".pdf",".jpg",".jpeg",".png"}

def save_document(owner_id,data,filename,kind="source",case_id=None):
    ext=Path(filename or "").suffix.lower()
    if ext not in ALLOWED:raise ValueError("Desteklenen dosyalar: UDF, PDF, JPG, JPEG, PNG.")
    doc_id=str(uuid4());path=UPLOAD_DIR/(doc_id+ext);path.write_bytes(data)
    with connect() as c:
        c.execute("""INSERT INTO documents
        (id,case_id,owner_id,original_name,stored_path,kind,size_bytes,created_at)
        VALUES(?,?,?,?,?,?,?,?)""",
        (doc_id,case_id,owner_id,filename,str(path),kind,len(data),now().isoformat()))
    return doc_id

def create_case(owner_id,file_no=None,application_no=None,title=None):
    cid=str(uuid4())
    with connect() as c:
        c.execute("""INSERT INTO cases
        (id,owner_id,file_no,application_no,title,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?)""",
        (cid,owner_id,file_no,application_no,title,now().isoformat(),now().isoformat()))
    return cid

def save_generated(owner_id,case_id,data,template_name):
    gid=str(uuid4());path=GENERATED_DIR/(gid+".udf");path.write_bytes(data)
    with connect() as c:
        c.execute("""INSERT INTO generated_documents
        (id,case_id,owner_id,original_template,stored_path,created_at)
        VALUES(?,?,?,?,?,?)""",
        (gid,case_id,owner_id,template_name,str(path),now().isoformat()))
    return gid
