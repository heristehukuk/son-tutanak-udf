
import json
from app.database_layer import repos
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
    plans=[{"id":pid,"name":p["name"],"price_monthly":p["price_monthly"],
            "features_json":json.dumps(p["features"],ensure_ascii=False),
            "limits_json":json.dumps(p["limits"],ensure_ascii=False)} for pid,p in DEFAULT_PLANS.items()]
    repos.plans.seed_defaults(plans)

def get_plan(plan_id):
    r=repos.plans.get(plan_id)
    if not r:return None
    return {"id":r["id"],"name":r["name"],"price_monthly":r["price_monthly"],
            "features":json.loads(r["features_json"]),"limits":json.loads(r["limits_json"])}

def feature_enabled(plan, feature):
    return bool(plan and plan["features"].get(feature,False))

def current_usage(user_id, metric, period):
    return repos.usage.sum_amount(user_id, metric, period)

def consume(user_id, metric, limit, amount=1):
    period=now().strftime("%Y-%m")
    if limit is not None and current_usage(user_id,metric,period)+amount>limit:return False
    repos.usage.record({"user_id":user_id,"metric":metric,"amount":amount,"period":period,"created_at":now().isoformat()})
    return True
