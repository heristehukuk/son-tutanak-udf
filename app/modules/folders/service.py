from app.database_layer import repos

STANDARD_CODES={"source":"01","davet_mektubu":"02","gorusme":"03","son_tutanak":"04","ucret_pusulasi":"05","ust_yazi":"06","other":"07"}

def ensure_case_folders(case_id, owner_id):
    return repos.folders.create_standard(case_id, owner_id)

def folder_for_kind(kind):
    return STANDARD_CODES.get(kind,"07")

def choose_folder(case_id, owner_id, kind):
    ensure_case_folders(case_id,owner_id)
    code=folder_for_kind(kind)
    rows=repos.folders.list_for_case(case_id,owner_id)
    return next((r for r in rows if r.get("code")==code),None)
