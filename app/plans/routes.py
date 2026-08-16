
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from app.web import page
from app.database_layer import repos
router=APIRouter()

@router.get("/",response_class=HTMLResponse)
async def plans(request:Request):
    rows=repos.plans.list_all()
    cards=[]
    for r in rows:
        cards.append('<div class="card"><h2>%s</h2><p>₺%s/ay</p><pre>%s</pre></div>' %
                     (r["name"],r["price_monthly"],r["limits_json"]))
    return page("Planlar","<h1>Üyelik Planları</h1>"+"".join(cards))
