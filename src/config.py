"""Centralized configuration and paths for the PhonePe Pulse FinTech pipeline."""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
RAW_PULSE_DIR = ROOT_DIR / "data" / "raw" / "pulse" / "data"
PROCESSED_DIR = ROOT_DIR / "data" / "processed"
ASSETS_DIR = ROOT_DIR / "assets"
DB_PATH = PROCESSED_DIR / "pulse_fintech.db"

STATE_NAME_MAP = {
    "andaman-&-nicobar-islands": "Andaman & Nicobar Islands",
    "andhra-pradesh": "Andhra Pradesh",
    "arunachal-pradesh": "Arunachal Pradesh",
    "assam": "Assam",
    "bihar": "Bihar",
    "chandigarh": "Chandigarh",
    "chhattisgarh": "Chhattisgarh",
    "dadra-&-nagar-haveli-&-daman-&-diu": "Dadra & Nagar Haveli and Daman & Diu",
    "delhi": "Delhi",
    "goa": "Goa",
    "gujarat": "Gujarat",
    "haryana": "Haryana",
    "himachal-pradesh": "Himachal Pradesh",
    "jammu-&-kashmir": "Jammu & Kashmir",
    "jharkhand": "Jharkhand",
    "karnataka": "Karnataka",
    "kerala": "Kerala",
    "ladakh": "Ladakh",
    "lakshadweep": "Lakshadweep",
    "madhya-pradesh": "Madhya Pradesh",
    "maharashtra": "Maharashtra",
    "manipur": "Manipur",
    "meghalaya": "Meghalaya",
    "mizoram": "Mizoram",
    "nagaland": "Nagaland",
    "odisha": "Odisha",
    "puducherry": "Puducherry",
    "punjab": "Punjab",
    "rajasthan": "Rajasthan",
    "sikkim": "Sikkim",
    "tamil-nadu": "Tamil Nadu",
    "telangana": "Telangana",
    "tripura": "Tripura",
    "uttar-pradesh": "Uttar Pradesh",
    "uttarakhand": "Uttarakhand",
    "west-bengal": "West Bengal",
}


def format_state_name(slug: str) -> str:
    """Convert PhonePe Pulse state slug to clean title-cased state name."""
    if slug in STATE_NAME_MAP:
        return STATE_NAME_MAP[slug]
    return slug.replace("-", " ").replace("&", " & ").title()
