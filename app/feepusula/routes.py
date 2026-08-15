
from html import escape
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, StreamingResponse, RedirectResponse
from app.auth.service import get_user_by_session
from app.documents.engine import form_state
from app.feepusula.service import build_harcama_pusulasi

router = APIRouter()

@router.post("/build")
async def build_pusula(request: Request):
    u = get_user_by_session(request.cookies.get("session"))
    if not u: return RedirectResponse("/auth/login", 303)
    form = await request.form()
    values, respondents, _, _ = form_state(form)
    taraf_sayisi = 1 + len(respondents)  # başvurucu dahil toplam
    try:
        xlsx_bytes, uyari = build_harcama_pusulasi(
            daire=values.get("daireBilgisi", ""),
            dosya_turu_text=values.get("dosyaTuru") or values.get("uyusmazlik") or "",
            dosya_no=values.get("dosyaNo", ""),
            taraf_sayisi=taraf_sayisi,
            arabulucu_adi=values.get("arabulucuAdi", ""),
            arabulucu_tc=values.get("arabulucuTc", ""),
            arabulucu_iban=u["iban"] or "",
        )
    except Exception as e:
        return HTMLResponse(f"Harcama Pusulası oluşturulurken hata: {e}", 500)
    import io
    headers = {"Content-Disposition": 'attachment; filename="harcama_pusulasi.xlsx"'}
    if uyari:
        headers["X-Tarife-Uyari"] = "1"
    resp = StreamingResponse(io.BytesIO(xlsx_bytes),
                              media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              headers=headers)
    return resp
