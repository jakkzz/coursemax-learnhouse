"""Server-side membership delta; not an authorization engine."""
from copy import deepcopy

_ERROR = "Learning access needs administrator review"


def _id(value):
    if type(value) is not int or value <= 0:
        raise ValueError(_ERROR)
    return value


def _member(value):
    if not isinstance(value, dict):
        raise ValueError(_ERROR)
    try:
        date = value["creation_date"]
        if type(date) is not str or not date:
            raise ValueError(_ERROR)
        return _id(value["id"]), _id(value["user_id"]), date
    except (KeyError, TypeError):
        raise ValueError(_ERROR) from None


def membership_delta(eligible_users, members, receipts):
    """Remove only exact row identities with live append-only ownership receipts."""
    if not all(isinstance(value, list) for value in (eligible_users, members, receipts)):
        raise ValueError(_ERROR)
    eligible = {_id(user) for user in eligible_users}
    rows, ids, users, owned = [], set(), set(), set()
    for member in members:
        key = _member(member)
        if key[0] in ids or key[1] in users:
            raise ValueError(_ERROR)
        ids.add(key[0]); users.add(key[1]); rows.append((key, member))
    for receipt in receipts:
        key = _member(receipt)
        action = receipt.get("action")
        if action not in ("added", "removed"):
            raise ValueError(_ERROR)
        if action == "added":
            owned.add(key)
        else:
            owned.discard(key)
    return {"add_user_ids": sorted(eligible - users),
            "remove_members": [deepcopy(row) for key, row in sorted(rows) if key in owned and key[1] not in eligible],
            "preserved_manual_count": sum(key not in owned for key, _ in rows)}
