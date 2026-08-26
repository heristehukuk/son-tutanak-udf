"""
Anket modülünün servis katmanı.

Soru tipleri:
  - text          : serbest metin
  - single_choice  : çoktan seçmeli, tek seçim (options_json içinde şık listesi)
  - rating         : 1-5 arası puanlama (şık listesi yok, sabit ölçek)

Tasarım kararları (kullanıcıyla birlikte netleştirildi):
  - Bir kullanıcı bir soruyu bir kez cevaplar; tekrar gönderirse cevabı güncellenir
    (survey_answers üzerindeki (question_id,user_id) tekilliği ile garanti altına alınır).
  - Anonim toplu özet HERKESE açık: çoktan seçmeli/puanlama sorularında sayısal
    dağılım, serbest metin sorularında ise kimin yazdığı belirtilmeden salt cevap listesi.
  - Sonuçları görebilmek için kullanıcının o anketi ÖNCE cevaplamış olması şarttır.
  - Kim ne cevap vermiş (isimli) sadece 'surveys.view_individual_answers' yetkili
    staff'a gösterilir - anonim özetten tamamen ayrı bir görünüm.
"""
import json
from uuid import uuid4
from datetime import datetime
from app.database_layer import repos

QUESTION_KINDS = {"text", "single_choice", "rating"}
RATING_MIN, RATING_MAX = 1, 5


def _now_iso():
    return datetime.now().isoformat(timespec="seconds")


# --- Admin: anket yönetimi -------------------------------------------------

def create_survey(admin_id, title, description=""):
    title = (title or "").strip()
    if not title:
        raise ValueError("Anket başlığı boş olamaz.")
    return repos.surveys.create({
        "id": str(uuid4()), "title": title, "description": (description or "").strip(),
        "active": 1, "created_at": _now_iso(), "created_by": admin_id,
    })


def set_survey_active(survey_id, active: bool):
    survey = repos.surveys.get(survey_id)
    if not survey:
        raise ValueError("Anket bulunamadı.")
    return repos.surveys.update(survey_id, {"active": 1 if active else 0})


def update_survey_meta(survey_id, title, description):
    title = (title or "").strip()
    if not title:
        raise ValueError("Anket başlığı boş olamaz.")
    survey = repos.surveys.get(survey_id)
    if not survey:
        raise ValueError("Anket bulunamadı.")
    return repos.surveys.update(survey_id, {"title": title, "description": (description or "").strip()})


def delete_survey(survey_id):
    survey = repos.surveys.get(survey_id)
    if not survey:
        raise ValueError("Anket bulunamadı.")
    repos.surveys.delete(survey_id)  # ON DELETE CASCADE: sorular ve cevaplar da silinir.


def list_all_surveys():
    return repos.surveys.list_all()


def get_survey(survey_id):
    return repos.surveys.get(survey_id)


# --- Admin: soru yönetimi ---------------------------------------------------

def add_question(survey_id, question, kind, options=None):
    survey = repos.surveys.get(survey_id)
    if not survey:
        raise ValueError("Anket bulunamadı.")
    question = (question or "").strip()
    if not question:
        raise ValueError("Soru metni boş olamaz.")
    if kind not in QUESTION_KINDS:
        raise ValueError("Geçersiz soru tipi.")
    options_json = None
    if kind == "single_choice":
        opts = [o.strip() for o in (options or []) if o.strip()]
        if len(opts) < 2:
            raise ValueError("Çoktan seçmeli soru için en az 2 şık girin.")
        options_json = json.dumps(opts, ensure_ascii=False)
    existing = repos.survey_questions.list_for_survey(survey_id)
    next_order = (max((q.get("sort_order", 0) for q in existing), default=-1) + 1)
    return repos.survey_questions.create({
        "id": str(uuid4()), "survey_id": survey_id, "question": question,
        "kind": kind, "options_json": options_json, "sort_order": next_order,
    })


def update_question(question_id, question, kind, options=None):
    row = repos.survey_questions.get(question_id)
    if not row:
        raise ValueError("Soru bulunamadı.")
    question = (question or "").strip()
    if not question:
        raise ValueError("Soru metni boş olamaz.")
    if kind not in QUESTION_KINDS:
        raise ValueError("Geçersiz soru tipi.")
    options_json = None
    if kind == "single_choice":
        opts = [o.strip() for o in (options or []) if o.strip()]
        if len(opts) < 2:
            raise ValueError("Çoktan seçmeli soru için en az 2 şık girin.")
        options_json = json.dumps(opts, ensure_ascii=False)
    return repos.survey_questions.update(question_id, {
        "question": question, "kind": kind, "options_json": options_json,
    })


def delete_question(question_id):
    row = repos.survey_questions.get(question_id)
    if not row:
        raise ValueError("Soru bulunamadı.")
    repos.survey_questions.delete(question_id)  # cevapları da CASCADE ile silinir.


def question_options(question_row):
    if question_row.get("kind") != "single_choice":
        return []
    try:
        return json.loads(question_row.get("options_json") or "[]")
    except Exception:
        return []


# --- Kullanıcı: anket listeleme / cevaplama --------------------------------

def list_visible_surveys(user_id):
    """Kullanıcının görebileceği anketler: tüm aktif anketler + daha önce
    cevapladığı (artık kapalı olsa bile) anketler. Her satıra 'answered'
    bilgisini ekler."""
    out = []
    for s in repos.surveys.list_all():
        answered = repos.survey_answers.has_answered(s["id"], user_id)
        if not s.get("active") and not answered:
            continue
        row = dict(s)
        row["answered"] = answered
        out.append(row)
    return out


def get_survey_with_questions(survey_id):
    survey = repos.surveys.get(survey_id)
    if not survey:
        return None, []
    return survey, repos.survey_questions.list_for_survey(survey_id)


def get_user_answers_map(survey_id, user_id):
    rows = repos.survey_answers.list_for_user_survey(survey_id, user_id)
    return {r["question_id"]: r["answer"] for r in rows}


def has_answered(survey_id, user_id):
    return repos.survey_answers.has_answered(survey_id, user_id)


def submit_answers(survey_id, user_id, form_answers: dict):
    """form_answers: {question_id: cevap_metni}. Boş bırakılan sorular atlanır."""
    survey = repos.surveys.get(survey_id)
    if not survey:
        raise ValueError("Anket bulunamadı.")
    if not survey.get("active"):
        raise ValueError("Bu anket artık kapalı; cevap kabul edilmiyor.")
    questions = {q["id"]: q for q in repos.survey_questions.list_for_survey(survey_id)}
    if not questions:
        raise ValueError("Bu ankette henüz soru yok.")
    stamp = _now_iso()
    saved = 0
    for qid, raw in (form_answers or {}).items():
        q = questions.get(qid)
        if not q:
            continue  # başka ankete ait/uydurma soru id'si -> yok say
        val = (raw or "").strip()
        if not val:
            continue
        if q["kind"] == "single_choice":
            opts = question_options(q)
            if val not in opts:
                raise ValueError(f"'{q['question']}' için geçersiz seçim.")
        elif q["kind"] == "rating":
            try:
                n = int(val)
            except Exception:
                raise ValueError(f"'{q['question']}' için geçerli bir puan seçin.")
            if not (RATING_MIN <= n <= RATING_MAX):
                raise ValueError(f"'{q['question']}' için puan {RATING_MIN}-{RATING_MAX} arasında olmalı.")
            val = str(n)
        repos.survey_answers.upsert({
            "id": str(uuid4()), "survey_id": survey_id, "question_id": qid, "user_id": user_id,
            "answer": val, "created_at": stamp, "updated_at": stamp,
        })
        saved += 1
    if saved == 0:
        raise ValueError("En az bir soruyu cevaplamalısınız.")
    return saved


# --- Sonuçlar: anonim toplu özet + (staff için) isimli dökümü -------------

def compute_aggregate_results(survey_id):
    """Herkese açık, kimliksiz özet. text sorularda cevaplar isimsiz liste
    olarak döner (kim yazdığı gösterilmez)."""
    questions = repos.survey_questions.list_for_survey(survey_id)
    answers = repos.survey_answers.list_for_survey(survey_id)
    by_question = {}
    for a in answers:
        by_question.setdefault(a["question_id"], []).append(a["answer"])
    out = []
    for q in questions:
        vals = by_question.get(q["id"], [])
        entry = {"id": q["id"], "question": q["question"], "kind": q["kind"], "total": len(vals)}
        if q["kind"] == "single_choice":
            opts = question_options(q)
            counts = {o: 0 for o in opts}
            for v in vals:
                counts[v] = counts.get(v, 0) + 1
            entry["counts"] = counts
        elif q["kind"] == "rating":
            counts = {n: 0 for n in range(RATING_MIN, RATING_MAX + 1)}
            total_score = 0
            for v in vals:
                try:
                    n = int(v)
                except Exception:
                    continue
                if n in counts:
                    counts[n] += 1
                    total_score += n
            entry["counts"] = counts
            entry["average"] = round(total_score / len(vals), 2) if vals else None
        else:  # text
            entry["answers"] = vals
        out.append(entry)
    return out


def compute_individual_answers(survey_id):
    """Staff için: her cevabı yazan kullanıcının adıyla birlikte döner."""
    questions = {q["id"]: q for q in repos.survey_questions.list_for_survey(survey_id)}
    answers = repos.survey_answers.list_for_survey(survey_id)
    users_by_id = {u["id"]: u for u in repos.users.list_all()}
    out = []
    for a in answers:
        q = questions.get(a["question_id"])
        u = users_by_id.get(a["user_id"])
        out.append({
            "question": q["question"] if q else "(silinmiş soru)",
            "user_name": (u.get("display_name") or u.get("email")) if u else a["user_id"],
            "answer": a["answer"],
            "updated_at": a.get("updated_at") or a.get("created_at"),
        })
    return out
