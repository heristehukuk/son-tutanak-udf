"""
Yetki sistemi.

`is_super_admin=1` olan kullanıcı HER ZAMAN her yetkiye sahiptir (kilitlenme
riskine karşı en az bir kişi her zaman tam yetkili kalmalı). Bunun altında,
süper admin olmayan kullanıcılara `PERMISSIONS` setinden TEK TEK yetki
verilebilir (örn. sadece üye onaylama + mesajlaşma, ama plan/tarife
değiştirme yok).

`admins.manage` (başka birine yetki verme/alma) KASITLI OLARAK sadece süper
admin'e aittir - aksi halde bir admin başka bir admine yetki verip zincirleme
yetki genişletmesi (privilege escalation) riski oluşur; bu yüzden
`PERMISSIONS` setinde yer almasına rağmen normal atama akışının dışında
tutulur (bkz. app/admin/routes.py).
"""
from app.database_layer import repos

PERMISSIONS = {
    "users.view","users.approve","users.reject","users.suspend","users.ban","users.message",
    "files.view","files.download","files.delete","documents.process","messages.view","messages.send",
    "surveys.create","surveys.view_results","surveys.view_individual_answers","plans.manage",
    "admins.manage","audit.view",
}

PERMISSION_LABELS = {
    "users.view":"Üyeleri Görüntüle","users.approve":"Üyelik Onayla","users.reject":"Üyelik Reddet",
    "users.suspend":"Şüpheli İşaretle","users.ban":"Yasakla / Hesap Sil","users.message":"Kullanıcıya Mesaj Gönder",
    "files.view":"Dosyaları Görüntüle","files.download":"Belge İndir","files.delete":"Belge Sil",
    "documents.process":"Belge İşleme (OCR/UDF)","messages.view":"Mesaj Panelini Görüntüle","messages.send":"Mesaj Gönder",
    "surveys.create":"Anket Oluştur","surveys.view_results":"Anket Sonuçlarını Gör","surveys.view_individual_answers":"Bireysel Cevapları Gör",
    "plans.manage":"Plan / Tarife Yönetimi","admins.manage":"Yönetici Yetkisi Ver/Al (sadece süper admin)","audit.view":"İşlem Geçmişini Gör",
}

# admins.manage normal atama arayüzünde gösterilmez (sadece süper admin'e ait).
ASSIGNABLE_PERMISSIONS = sorted(PERMISSIONS - {"admins.manage"})


def is_admin(user):
    return bool(user and user.get("is_super_admin"))


def has_permission(user_id, permission):
    user = repos.users.get(user_id)
    if not user:
        return False
    if user.get("is_super_admin"):
        return True
    return permission in repos.permissions.list_for_user(user_id)


def require_permission(user, permission):
    """Kullanıcı objesi zaten elde varsa (ekstra DB sorgusu istemiyorsan) bunu kullan."""
    if not user:
        return False
    if user.get("is_super_admin"):
        return True
    return permission in repos.permissions.list_for_user(user["id"])
