
PERMISSIONS = {
    "users.view","users.approve","users.reject","users.suspend","users.ban","users.message",
    "files.view","files.download","files.delete","documents.process","messages.view","messages.send",
    "surveys.create","surveys.view_results","surveys.view_individual_answers","plans.manage",
    "admins.manage","audit.view"
}
def is_admin(user):
    return bool(user and user["is_super_admin"])
