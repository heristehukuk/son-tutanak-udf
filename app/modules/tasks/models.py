STANDARD_TASKS = [
    {"key": "application_check", "title": "Başvuru dosyasını kontrol et", "offset_days": 0, "priority": "normal", "sort_order": 1},
    {"key": "respondent_check", "title": "Karşı taraf bilgilerini kontrol et", "offset_days": 1, "priority": "normal", "sort_order": 2},
    {"key": "invite", "title": "Davet gönder", "offset_days": 3, "priority": "normal", "sort_order": 3},
    {"key": "meeting", "title": "Toplantıyı gerçekleştir", "offset_days": 10, "priority": "normal", "sort_order": 4},
    {"key": "final_documents", "title": "Son tutanağı ve ücret pusulasını hazırla", "offset_days": 18, "priority": "high", "sort_order": 5},
    {"key": "close_case", "title": "Dosyayı kapat ve evrakları sisteme yükle", "offset_days": 20, "priority": "normal", "sort_order": 6},
]

STATUSES = {"pending", "in_progress", "completed", "cancelled"}
PRIORITIES = {"low", "normal", "high"}
