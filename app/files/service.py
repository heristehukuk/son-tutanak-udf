
from pathlib import Path
from uuid import uuid4
from app.database_layer import repos
from app.auth.service import now
from app.storage import storage

ALLOWED={".udf",".pdf",".jpg",".jpeg",".png"}

def save_document(owner_id,data,filename,kind="source",case_id=None):
    ext=Path(filename or "").suffix.lower()
    if ext not in ALLOWED:raise ValueError("Desteklenen dosyalar: UDF, PDF, JPG, JPEG, PNG.")
    doc_id=str(uuid4());key=f"uploads/{doc_id}{ext}"
    storage.save(key,data)
    folder_id=None
    if case_id:
        from app.folders.service import folder_for_document
        # NOT: 'kind' burada belgenin çıkarma yöntemini ("ocr"/"udf") tutar,
        # klasör türünü DEĞİL. save_document() her zaman kullanıcının
        # yüklediği KAYNAK belgeler için çağrılır, bu yüzden klasör
        # yönlendirmesi için her zaman sabit "source" rolünü kullanıyoruz -
        # aksi halde "ocr"/"udf" değeri DOC_FOLDER_TYPES'ta eşleşmediği için
        # belge yanlışlıkla "07 - Diğer Belgeler"e düşer.
        folder=folder_for_document(owner_id, case_id, kind="source")
        folder_id=folder.get("id") if folder else None
    repos.documents.create({
        "id":doc_id,"case_id":case_id,"folder_id":folder_id,"owner_id":owner_id,"original_name":filename,
        "stored_path":key,"kind":kind,"size_bytes":len(data),"created_at":now().isoformat(),
    })
    return doc_id

def create_case(owner_id,file_no=None,application_no=None,title=None,file_type=None,start_date=None,case_data_json=None):
    case=repos.cases.create({
        "owner_id":owner_id,"file_no":file_no,"application_no":application_no,
        "title":title,"file_type":file_type,"start_date":start_date,"case_data_json":case_data_json,
        "status":"open","created_at":now().isoformat(),"updated_at":now().isoformat(),
    })
    from app.registry import ensure_registry_no
    ensure_registry_no(case["id"])
    from app.folders.service import ensure_case_folders
    ensure_case_folders(owner_id, case["id"])
    return case["id"]

def save_generated(owner_id,case_id,data,template_name,doc_kind=None,ext=".udf"):
    gid=str(uuid4());key=f"generated/{gid}{ext}"
    storage.save(key,data)
    folder_id=None
    if case_id:
        from app.folders.service import folder_for_document
        # doc_kind bilinmiyorsa (ör. kütüphaneye kaydedilmemiş, tek seferlik özel
        # şablon çıktısı) "01 - Kaynak Belgeler"e DEĞİL "07 - Diğer Belgeler"e
        # düşmeli - bu yüzden kind için "source" yerine boş bırakıyoruz.
        folder=folder_for_document(owner_id, case_id, doc_kind=doc_kind, kind=None)
        folder_id=folder.get("id") if folder else None
    repos.generated_documents.create({
        "id":gid,"case_id":case_id,"folder_id":folder_id,"owner_id":owner_id,"original_template":template_name,
        "stored_path":key,"doc_kind":doc_kind,"created_at":now().isoformat(),
    })
    return gid
