
import json
from app.database import connect
from app.auth.service import now

DEFAULT_PLANS = {
    "free": {
        "name":"Ücretsiz","price_monthly":0,
        "features":{"files.create":True,"documents.ocr":True,"documents.udf":True,"files.copy":False,"files.versions":False},
        "limits":{"files.max":5,"storage.mb":100,"file.max_mb":10,"ocr.monthly":10,"udf.monthly":5}
    },
    "pro": {
        "name":"Pro","price_monthly":0,
        "features":{"files.create":True,"documents.ocr":True,"documents.udf":True,"files.copy":True,"files.versions":True},
        "limits":{"files.max":100,"storage.mb":10240,"file.max_mb":100,"ocr.monthly":500,"udf.monthly":100}
    }
}

def seed_plans():
    with connect() as c:
        for pid,p in DEFAULT_PLANS.items():
            c.execute("""INSERT OR IGNORE INTO plans
            (id,name,price_monthly,features_json,limits_json) VALUES(?,?,?,?,?)""",
            (pid,p["name"],p["price_monthly"],json.dumps(p["features"],ensure_ascii=False),
             json.dumps(p["limits"],ensure_ascii=False)))

def get_plan(plan_id):
    with connect() as c:
        r=c.execute("SELECT * FROM plans WHERE id=?",(plan_id,)).fetchone()
    if not r:return None
    return {"id":r["id"],"name":r["name"],"price_monthly":r["price_monthly"],
            "features":json.loads(r["features_json"]),"limits":json.loads(r["limits_json"])}

def feature_enabled(plan, feature):
    return bool(plan and plan["features"].get(feature,False))

def current_usage(user_id, metric, period):
    with connect() as c:
        r=c.execute("SELECT COALESCE(SUM(amount),0) n FROM usage WHERE user_id=? AND metric=? AND period=?",
                    (user_id,metric,period)).fetchone()
    return int(r["n"])

def consume(user_id, metric, limit, amount=1):
    period=now().strftime("%Y-%m")
    if limit is not None and current_usage(user_id,metric,period)+amount>limit:return False
    with connect() as c:
        c.execute("INSERT INTO usage(user_id,metric,amount,period,created_at) VALUES(?,?,?,?,?)",
                  (user_id,metric,amount,period,now().isoformat()))
    return True
