from datetime import date, datetime


DEFAULT_DB_PATH = "data/nepal_backtest.sqlite"
DEFAULT_SOURCES_CSV = "data/sources.csv"
DEFAULT_POSTS_CSV = "data/platform_posts.csv"
DEFAULT_GROUND_TRUTH_CSV = "data/ground_truth_events.csv"
DEFAULT_CALIBRATION_CSV = "data/calibration_examples.csv"
DEFAULT_REPORT_PATH = "reports/backtest_report.md"

REPLAY_START = date(2025, 8, 25)
REPLAY_END = date(2025, 9, 7)
INPUT_CUTOFF = datetime(2025, 9, 8, 0, 0, 0)
VERIFICATION_START = date(2025, 9, 8)
VERIFICATION_END = date(2025, 9, 10)
DEFAULT_HORIZON_DAYS = 3
DEFAULT_LOOKBACK_DAYS = 3

FORECAST_CITIES = [
    "Kathmandu",
    "Lalitpur",
    "Pokhara",
    "Biratnagar",
    "Dharan",
    "Itahari",
]

NATIONAL_CITY = "Nepal"

CITY_ALIASES = {
    "kathmandu": "Kathmandu",
    "ktm": "Kathmandu",
    "new baneshwor": "Kathmandu",
    "baneshwor": "Kathmandu",
    "maitighar": "Kathmandu",
    "maitighar mandala": "Kathmandu",
    "singha durbar": "Kathmandu",
    "parliament": "Kathmandu",
    "ratna park": "Kathmandu",
    "lalitpur": "Lalitpur",
    "patan": "Lalitpur",
    "pokhara": "Pokhara",
    "biratnagar": "Biratnagar",
    "dharan": "Dharan",
    "itahari": "Itahari",
    "nepal": NATIONAL_CITY,
}

PLACE_ALIASES = {
    "maitighar mandala": ("Kathmandu", "Maitighar Mandala"),
    "maitighar": ("Kathmandu", "Maitighar Mandala"),
    "new baneshwor": ("Kathmandu", "New Baneshwor"),
    "baneshwor": ("Kathmandu", "New Baneshwor"),
    "parliament": ("Kathmandu", "Parliament Kathmandu"),
    "singha durbar": ("Kathmandu", "Singha Durbar"),
    "ratna park": ("Kathmandu", "Ratna Park"),
    "itahari chowk": ("Itahari", "Itahari Chowk"),
    "dharan": ("Dharan", "Dharan"),
    "biratnagar": ("Biratnagar", "Biratnagar"),
    "pokhara": ("Pokhara", "Pokhara"),
    "lalitpur": ("Lalitpur", "Lalitpur"),
}

TOPIC_KEYWORDS = {
    "social_media_ban": [
        "social media ban",
        "blocked social media",
        "facebook ban",
        "instagram ban",
        "youtube ban",
        "x ban",
        "ban on social media",
        "26 platforms",
        "platform ban",
        "app ban",
        "registration rules",
    ],
    "corruption": [
        "corruption",
        "anti corruption",
        "anti-corruption",
        "nepotism",
        "nepo kid",
        "nepo kids",
        "public funds",
        "mismanagement",
    ],
    "gen_z": [
        "gen z",
        "gen-z",
        "generation z",
        "youth",
        "young people",
        "students",
        "student",
    ],
    "students": [
        "students",
        "student union",
        "campus",
        "college",
        "university",
        "school uniform",
    ],
    "government": [
        "government",
        "prime minister",
        "oli",
        "parliament",
        "minister",
        "state",
        "authorities",
    ],
    "strike": [
        "strike",
        "bandh",
        "shutdown",
    ],
}

ACTION_KEYWORDS = [
    "protest",
    "rally",
    "demonstration",
    "march",
    "mass gathering",
    "gather",
    "sit-in",
    "strike",
    "bandh",
    "andolan",
    "birodh",
    "aandolan",
    "आन्दोलन",
    "विरोध",
    "भेला",
]

CALL_TO_ACTION_KEYWORDS = [
    "join",
    "join us",
    "come to",
    "come at",
    "gather at",
    "march to",
    "rally at",
    "be there",
    "everyone come",
    "students will march",
    "we gather",
    "we will gather",
    "let's gather",
    "lets gather",
    "aau",
    "aaunus",
    "आउनुहोस्",
]

DATE_KEYWORDS = {
    "today": 0,
    "aaja": 0,
    "आज": 0,
    "tonight": 0,
    "tomorrow": 1,
    "bholi": 1,
    "भोली": 1,
    "भोलि": 1,
    "day after tomorrow": 2,
    "parsi": 2,
    "पर्सि": 2,
}

WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

MONTHS = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

SOURCE_PRIORITY_SCORE = {
    "high": 2,
    "medium": 1,
    "low": 0,
}
