# -*- coding: utf-8 -*-
"""
Hafif güvenlik middleware'leri: CSRF (Origin/Referer doğrulama) ve rate limiting.

CSRF NOTU
---------
Bu uygulama JSON API değil, sunucu tarafında render edilen HTML formlarından
oluşuyor. Klasik "her forma gizli csrf token alanı ekle + her POST route'ta
doğrula" yaklaşımı onlarca dosyadaki formu tek tek değiştirmeyi gerektirir ve
büyük, riskli bir değişiklik olurdu. Onun yerine, tarayıcıların devlet
değiştiren (state-changing) isteklerde her zaman gönderdiği ve JavaScript ile
sahteciliği mümkün olmayan Origin/Referer başlığını doğrulayan bir savunma
katmanı uyguluyoruz: istek POST/PUT/PATCH/DELETE ise ve Origin (yoksa Referer)
başlığı isteğin gittiği host ile eşleşmiyorsa istek 403 ile reddedilir.

Bu, "başka bir sitedeki gizli form bu siteye submit eder" tipindeki klasik
CSRF saldırısını engeller, çünkü saldırgan sitenin formu submit edildiğinde
tarayıcı Origin'i saldırganın kendi sitesi olarak gönderir. Token tabanlı
CSRF korumasının sağladığı TÜM garantileri vermez (ör. çok eski tarayıcılar
Origin/Referer göndermeyebilir), ama bu projenin risk profili (modern
tarayıcı, form tabanlı POST, API tüketicisi yok) için pratik ve düşük
müdahaleli bir ilk savunma hattıdır.

RATE LIMIT NOTU
----------------
Bellek-içi (in-memory), IP + yol bazlı basit bir sliding-window limiter.
Render'da tek worker ile çalıştığı sürece doğru çalışır; birden fazla worker/
instance'a ölçeklenirse (yatay ölçekleme) paylaşımlı bir depoya (Redis vb.)
taşınması gerekir - bu, ölçek büyüdüğünde değerlendirilmesi gereken bilinen
bir sınırlamadır.
"""
import time
from collections import defaultdict, deque

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import PlainTextResponse

STATE_CHANGING_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class CSRFOriginCheckMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        if request.method in STATE_CHANGING_METHODS:
            origin = request.headers.get("origin") or ""
            referer = request.headers.get("referer") or ""
            source = origin or referer
            if source:
                host = request.url.hostname or ""
                try:
                    from urllib.parse import urlparse
                    source_host = urlparse(source).hostname or ""
                except Exception:
                    source_host = ""
                if host and source_host and source_host != host:
                    return PlainTextResponse(
                        "İstek reddedildi: kaynak (Origin/Referer) doğrulanamadı.",
                        status_code=403,
                    )
            # Origin/Referer hiç yoksa (bazı eski istemciler, sunucudan sunucuya
            # entegrasyonlar) isteği reddetmiyoruz; bu katman ek bir savunma
            # hattıdır, tek koruma değildir.
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Basit sabit-pencere olmayan (sliding window) IP+yol bazlı rate limit.

    limits: {"path_prefix": (max_requests, window_seconds)} eşlemesi.
    Eşleşen ilk (en spesifik) prefix kullanılır; hiçbiri eşleşmezse istek
    sınırlanmaz.
    """

    def __init__(self, app, limits=None, default_limit=None):
        super().__init__(app)
        self.limits = limits or {}
        self.default_limit = default_limit
        self._hits = defaultdict(deque)

    def _limit_for(self, path):
        best = None
        for prefix, limit in self.limits.items():
            if path.startswith(prefix):
                if best is None or len(prefix) > len(best[0]):
                    best = (prefix, limit)
        return best[1] if best else self.default_limit

    async def dispatch(self, request, call_next):
        limit = self._limit_for(request.url.path)
        if limit:
            max_requests, window = limit
            ip = request.client.host if request.client else "unknown"
            key = (ip, request.url.path)
            now = time.monotonic()
            q = self._hits[key]
            while q and now - q[0] > window:
                q.popleft()
            if len(q) >= max_requests:
                return PlainTextResponse(
                    "Çok fazla istek gönderildi. Lütfen bir süre sonra tekrar deneyin.",
                    status_code=429,
                )
            q.append(now)
        return await call_next(request)
