from . import repo
def get_meters(user_id: str):
    return repo.list_meters_of_user(user_id)
