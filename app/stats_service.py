
from datetime import datetime, timezone
from app.database_layer import repos


def user_stats(owner_id):
    """Kullanıcının 'bu ay' ve 'tüm zamanlar' özet istatistiklerini hesaplar.
    Performans notu: mevcut repository arayüzünde toplu SAYIM/TOPLAM sorgusu
    olmadığından, kullanıcının kendi kayıtları (genelde birkaç yüzü geçmez)
    Python tarafında filtrelenir. Kullanıcı sayısı arttıkça repository'ye
    özel bir 'count'/'sum' metodu eklenmesi düşünülebilir.
    """
    now = datetime.now(timezone.utc)
    this_month_prefix = now.strftime("%Y-%m")

    cases = repos.cases.list_by_owner(owner_id)
    cases = [c for c in cases if c.get("status") != "deleted"]
    docs = repos.generated_documents.list_by_owner(owner_id)

    def _is_this_month(created_at):
        return bool(created_at) and str(created_at).startswith(this_month_prefix)

    docs_this_month = [d for d in docs if _is_this_month(d.get("created_at"))]
    cases_this_month = [c for c in cases if _is_this_month(c.get("created_at"))]

    def _sum_amount(rows):
        return sum(r["amount"] for r in rows if r.get("amount"))

    return {
        "cases_total": len(cases),
        "cases_this_month": len(cases_this_month),
        "docs_total": len(docs),
        "docs_this_month": len(docs_this_month),
        "amount_total": _sum_amount(docs),
        "amount_this_month": _sum_amount(docs_this_month),
    }
