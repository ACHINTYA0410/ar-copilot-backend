import random
import string


def generate_deal_id() -> str:
    digits = "".join(random.choices(string.digits, k=5))
    return f"DL-{digits}"
