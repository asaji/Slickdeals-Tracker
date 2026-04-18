"""Category profiles for deal analysis — brands, review sources, specs, and sentiment vocab."""

import re
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class CategoryProfile:
    name: str
    detect_keywords: list[str]      # used to auto-detect category from deal title
    brands: list[str]               # known brands for model extraction
    review_site: str                # human-readable review source name
    review_query_template: str      # {model} placeholder
    positive_words: frozenset
    negative_words: frozenset
    extract_specs: Callable = field(default_factory=lambda: lambda t: {})


# ---------------------------------------------------------------------------
# Spec extractors
# ---------------------------------------------------------------------------

def _re(pattern: str) -> re.Pattern:
    return re.compile(pattern, re.IGNORECASE)


_TV_SIZE   = _re(r"\b(43|50|55|60|65|70|75|77|80|83|85|86|98)[\s\"-]?(?:inch|in\b|\"|\s*class)")
_MON_SIZE  = _re(r"\b(21|24|25|27|28|31|32|34|38|40|42|49)[\s\"-]?(?:inch|in\b|\"|\s*class)")
_LAP_SIZE  = _re(r"\b(11|12|13|14|15|16|17)[\s\.-]?(?:inch|in\b|\"|\s*class)")
_PHONE_SIZE= _re(r"\b([5-7]\.\d)[\s\"-]?(?:inch|in\b|\")")
_TAB_SIZE  = _re(r"\b(7|8|8\.7|9|10|10\.4|10\.5|10\.9|11|12\.4|12\.9|13|14)[\s\"-]?(?:inch|in\b|\"|\s*class)")
_RAM_RE    = _re(r"\b(\d+)\s*GB\s*(?:RAM|LPDDR\d*|DDR\d*)\b")
_STORAGE_RE= _re(r"\b(\d+(?:\.\d+)?)\s*(TB|GB)\b(?!\s*RAM|\s*LPDDR|\s*DDR)")
_HZ_RE     = _re(r"\b(60|75|100|120|144|165|240|360)\s*Hz\b")
_VRAM_RE   = _re(r"\b(\d+)\s*GB\s*(?:GDDR\d*|VRAM|HBM\d*)\b")
_CAM_MP_RE = _re(r"\b(\d+)\s*MP\b")
_WIFI_RE   = _re(r"\b(Wi-Fi\s*[567]E?|802\.11\s*a[cx]|AX\d+|BE\d+)\b")
_CPU_CORE  = _re(r"\b(\d+)[\s-]?cores?\b")


def _first(pat: re.Pattern, text: str) -> Optional[str]:
    m = pat.search(text)
    return m.group(0) if m else None


def _panel_tv(title: str) -> Optional[str]:
    t = title.upper()
    if "OLED" in t:
        return "OLED"
    if "MINI-LED" in t or "MINILED" in t or "MINI LED" in t:
        return "Mini-LED"
    if "QLED" in t:
        return "QLED"
    if "MICROLED" in t or "MICRO LED" in t:
        return "MicroLED"
    if "QNED" in t:
        return "QNED"
    if "LED" in t:
        return "LED"
    return None


def _panel_monitor(title: str) -> Optional[str]:
    t = title.upper()
    for p in ("OLED", "MINI-LED", "IPS", "VA", "TN", "NANO IPS", "FAST IPS"):
        if p in t:
            return p.title()
    return None


def _resolution(title: str) -> Optional[str]:
    t = title.upper()
    if "8K" in t:             return "8K"
    if "4K" in t or "UHD" in t: return "4K/UHD"
    if "1440" in t or "QHD" in t or "2K" in t: return "1440p/QHD"
    if "1080" in t or "FHD" in t: return "1080p/FHD"
    if "ULTRAWIDE" in t or "21:9" in t: return "Ultrawide"
    return None


def _wireless(title: str) -> str:
    t = title.lower()
    return "Yes" if any(w in t for w in ("wireless", "bluetooth", "wifi", "wi-fi", "true wireless", "tws", "anc")) else "No"


def _anc(title: str) -> Optional[str]:
    t = title.lower()
    if any(w in t for w in ("noise cancell", "anc", "active noise")):
        return "Yes"
    return None


# --- per-category extractors ---

def _specs_tv(title: str) -> dict[str, str]:
    specs = {}
    m = _TV_SIZE.search(title)
    if m:
        specs["Size"] = m.group(1) + '"'
    p = _panel_tv(title)
    if p:
        specs["Panel"] = p
    r = _resolution(title)
    if r:
        specs["Resolution"] = r
    hz = _first(_HZ_RE, title)
    if hz:
        specs["Refresh"] = hz
    return specs


def _specs_monitor(title: str) -> dict[str, str]:
    specs = {}
    m = _MON_SIZE.search(title)
    if m:
        specs["Size"] = m.group(1) + '"'
    p = _panel_monitor(title)
    if p:
        specs["Panel"] = p
    r = _resolution(title)
    if r:
        specs["Resolution"] = r
    hz = _first(_HZ_RE, title)
    if hz:
        specs["Refresh"] = hz
    return specs


def _specs_laptop(title: str) -> dict[str, str]:
    specs = {}
    m = _LAP_SIZE.search(title)
    if m:
        specs["Screen"] = m.group(1) + '"'
    ram = _RAM_RE.search(title)
    if ram:
        specs["RAM"] = ram.group(1) + " GB"
    storage = _STORAGE_RE.search(title)
    if storage:
        specs["Storage"] = storage.group(1) + " " + storage.group(2)
    t = title.upper()
    if "APPLE M" in t or "MACBOOK" in t:
        specs["CPU"] = "Apple Silicon"
    elif "INTEL" in t or "CORE I" in t or "CORE ULTRA" in t:
        specs["CPU"] = "Intel"
    elif "AMD" in t or "RYZEN" in t:
        specs["CPU"] = "AMD Ryzen"
    return specs


def _specs_headphones(title: str) -> dict[str, str]:
    specs = {}
    t = title.lower()
    if any(w in t for w in ("true wireless", "tws", "earbuds", "earphones", "in-ear")):
        specs["Type"] = "In-Ear / TWS"
    elif any(w in t for w in ("over-ear", "over ear", "headphones", "headset", "circumaural")):
        specs["Type"] = "Over-Ear"
    elif "on-ear" in t or "on ear" in t:
        specs["Type"] = "On-Ear"
    anc = _anc(title)
    if anc:
        specs["ANC"] = anc
    specs["Wireless"] = _wireless(title)
    return specs


def _specs_smartphone(title: str) -> dict[str, str]:
    specs = {}
    m = _PHONE_SIZE.search(title)
    if m:
        specs["Screen"] = m.group(1) + '"'
    storage = _STORAGE_RE.search(title)
    if storage:
        specs["Storage"] = storage.group(1) + " " + storage.group(2)
    t = title.upper()
    if "5G" in t:
        specs["Network"] = "5G"
    elif "4G" in t or "LTE" in t:
        specs["Network"] = "4G/LTE"
    return specs


def _specs_tablet(title: str) -> dict[str, str]:
    specs = {}
    m = _TAB_SIZE.search(title)
    if m:
        specs["Screen"] = m.group(1) + '"'
    storage = _STORAGE_RE.search(title)
    if storage:
        specs["Storage"] = storage.group(1) + " " + storage.group(2)
    t = title.lower()
    if "cellular" in t or "lte" in t or "5g" in t:
        specs["Connectivity"] = "WiFi + Cellular"
    else:
        specs["Connectivity"] = "WiFi"
    if any(w in t for w in ("s pen", "apple pencil", "stylus", "pencil")):
        specs["Stylus"] = "Included/Compatible"
    return specs


def _specs_gpu(title: str) -> dict[str, str]:
    specs = {}
    t = title.upper()
    vram = _VRAM_RE.search(title)
    if vram:
        specs["VRAM"] = vram.group(1) + " GB"
    for chip in ("RTX 4090", "RTX 4080", "RTX 4070 TI", "RTX 4070", "RTX 4060 TI",
                 "RTX 4060", "RTX 3090", "RTX 3080", "RTX 3070", "RTX 3060",
                 "RX 7900", "RX 7800", "RX 7700", "RX 7600", "RX 6800", "RX 6700"):
        if chip in t:
            specs["Chip"] = chip
            break
    return specs


def _specs_cpu(title: str) -> dict[str, str]:
    specs = {}
    cores = _CPU_CORE.search(title)
    if cores:
        specs["Cores"] = cores.group(1)
    t = title.upper()
    for series in ("CORE I9", "CORE I7", "CORE I5", "CORE I3",
                   "CORE ULTRA 9", "CORE ULTRA 7", "CORE ULTRA 5",
                   "RYZEN 9", "RYZEN 7", "RYZEN 5", "RYZEN 3",
                   "THREADRIPPER", "EPYC"):
        if series in t:
            specs["Series"] = series.title()
            break
    return specs


def _specs_ssd(title: str) -> dict[str, str]:
    specs = {}
    storage = _STORAGE_RE.search(title)
    if storage:
        specs["Capacity"] = storage.group(1) + " " + storage.group(2)
    t = title.upper()
    specs["Interface"] = "NVMe" if "NVME" in t or "M.2" in t else "SATA"
    specs["Form Factor"] = "M.2" if "M.2" in t else "2.5\"" if "2.5" in t else "Unknown"
    return specs


def _specs_camera(title: str) -> dict[str, str]:
    specs = {}
    mp = _CAM_MP_RE.search(title)
    if mp:
        specs["Resolution"] = mp.group(1) + " MP"
    t = title.upper()
    if "MIRRORLESS" in t:
        specs["Type"] = "Mirrorless"
    elif "DSLR" in t:
        specs["Type"] = "DSLR"
    elif "POINT" in t or "COMPACT" in t:
        specs["Type"] = "Compact"
    elif "ACTION" in t or "GOPRO" in t:
        specs["Type"] = "Action Cam"
    for sensor in ("FULL FRAME", "FULL-FRAME", "APS-C", "MICRO FOUR THIRDS", "MFT", "1 INCH", "1-INCH"):
        if sensor in t:
            specs["Sensor"] = sensor.title().replace("Mft", "MFT")
            break
    return specs


def _specs_gaming(title: str) -> dict[str, str]:
    specs = {}
    t = title.upper()
    for platform in ("PS5", "PLAYSTATION 5", "XBOX SERIES X", "XBOX SERIES S",
                     "NINTENDO SWITCH", "SWITCH OLED", "SWITCH LITE", "STEAM DECK", "PC"):
        if platform in t:
            specs["Platform"] = platform.title()
            break
    if "BUNDLE" in t:
        specs["Type"] = "Bundle"
    elif any(w in t for w in ("CONTROLLER", "GAMEPAD", "JOYSTICK")):
        specs["Type"] = "Controller"
    elif any(w in t for w in ("GAME", "DISC", "DIGITAL")):
        specs["Type"] = "Game"
    else:
        specs["Type"] = "Console/Hardware"
    return specs


def _specs_peripherals(title: str) -> dict[str, str]:
    specs = {}
    t = title.lower()
    if any(w in t for w in ("keyboard", "keeb", "mechanical", "tkl", "tenkeyless")):
        specs["Type"] = "Keyboard"
        if any(w in t for w in ("tkl", "tenkeyless")):
            specs["Form Factor"] = "TKL"
        elif "60%" in t:
            specs["Form Factor"] = "60%"
        elif "65%" in t:
            specs["Form Factor"] = "65%"
        elif "75%" in t:
            specs["Form Factor"] = "75%"
    elif any(w in t for w in ("mouse", "mice")):
        specs["Type"] = "Mouse"
    elif any(w in t for w in ("headset", "gaming headphone")):
        specs["Type"] = "Gaming Headset"
    elif "mousepad" in t or "mouse pad" in t:
        specs["Type"] = "Mousepad"
    elif "controller" in t or "gamepad" in t:
        specs["Type"] = "Controller"
    specs["Wireless"] = _wireless(title)
    return specs


def _specs_smarthome(title: str) -> dict[str, str]:
    specs = {}
    t = title.lower()
    type_map = [
        (["smart speaker", "echo", "google home", "homepod"], "Smart Speaker"),
        (["smart display", "echo show", "nest hub"], "Smart Display"),
        (["smart bulb", "smart light", "hue", "kasa bulb"], "Smart Lighting"),
        (["smart plug", "smart outlet", "smart switch"], "Smart Plug/Switch"),
        (["thermostat", "ecobee", "nest thermostat"], "Smart Thermostat"),
        (["doorbell", "ring", "nest doorbell"], "Video Doorbell"),
        (["security camera", "outdoor camera", "indoor camera", "ring camera"], "Security Camera"),
        (["smart lock", "deadbolt"], "Smart Lock"),
        (["smart tv", "fire tv", "chromecast", "fire stick", "streaming"], "Streaming Device"),
    ]
    for keywords, label in type_map:
        if any(k in t for k in keywords):
            specs["Type"] = label
            break
    platform_map = [
        ("alexa", "Amazon Alexa"), ("google assistant", "Google Home"),
        ("homekit", "Apple HomeKit"), ("matter", "Matter"),
        ("zigbee", "Zigbee"), ("z-wave", "Z-Wave"),
    ]
    for kw, label in platform_map:
        if kw in t:
            specs["Platform"] = label
            break
    return specs


def _specs_appliances(title: str) -> dict[str, str]:
    specs = {}
    t = title.lower()
    type_map = [
        (["robot vacuum", "roomba", "roborock", "eufy", "irobot"], "Robot Vacuum"),
        (["upright vacuum", "canister vacuum", "stick vacuum", "cordless vacuum", "dyson"], "Vacuum"),
        (["air fryer"], "Air Fryer"),
        (["instant pot", "pressure cooker", "multi cooker"], "Pressure Cooker"),
        (["air purifier"], "Air Purifier"),
        (["coffee maker", "espresso", "nespresso", "keurig"], "Coffee Maker"),
        (["blender", "vitamix", "nutribullet"], "Blender"),
        (["stand mixer", "kitchenaid"], "Stand Mixer"),
        (["dishwasher"], "Dishwasher"),
        (["refrigerator", "fridge"], "Refrigerator"),
        (["washer", "dryer", "laundry"], "Laundry"),
        (["microwave"], "Microwave"),
    ]
    for keywords, label in type_map:
        if any(k in t for k in keywords):
            specs["Type"] = label
            break
    storage = _STORAGE_RE.search(title)
    if storage and "qt" not in title.lower() and "l" not in storage.group(2).lower():
        pass
    qt = re.search(r"(\d+(?:\.\d+)?)\s*(?:qt|quart|liter|litre|l\b)", title, re.IGNORECASE)
    if qt:
        specs["Capacity"] = qt.group(0)
    return specs


def _specs_router(title: str) -> dict[str, str]:
    specs = {}
    t = title.upper()
    wifi = _WIFI_RE.search(title)
    if wifi:
        specs["WiFi"] = wifi.group(0)
    elif "WI-FI 7" in t or "WIFI 7" in t:
        specs["WiFi"] = "Wi-Fi 7"
    elif "WI-FI 6E" in t or "6E" in t:
        specs["WiFi"] = "Wi-Fi 6E"
    elif "WI-FI 6" in t or "AX" in t:
        specs["WiFi"] = "Wi-Fi 6"
    elif "WI-FI 5" in t or "AC" in t:
        specs["WiFi"] = "Wi-Fi 5"
    if "MESH" in t:
        specs["Type"] = "Mesh System"
    elif "EXTENDER" in t or "REPEATER" in t or "BOOSTER" in t:
        specs["Type"] = "Range Extender"
    else:
        specs["Type"] = "Router"
    return specs


def _specs_general(title: str) -> dict[str, str]:
    specs = {}
    storage = _STORAGE_RE.search(title)
    if storage:
        specs["Storage"] = storage.group(1) + " " + storage.group(2)
    hz = _first(_HZ_RE, title)
    if hz:
        specs["Refresh"] = hz
    return specs


# ---------------------------------------------------------------------------
# Category registry
# ---------------------------------------------------------------------------

CATEGORIES: dict[str, CategoryProfile] = {
    "TVs": CategoryProfile(
        name="TVs",
        detect_keywords=["tv", "television", "oled", "qled", "qned", "smart tv", "hdtv", "uhd"],
        brands=["lg", "samsung", "sony", "tcl", "hisense", "vizio", "philips", "panasonic",
                "sharp", "insignia", "toshiba", "westinghouse", "element", "sceptre"],
        review_site="RTINGS",
        review_query_template="{model} rtings.com review score",
        positive_words=frozenset(["excellent", "great", "outstanding", "impressive", "best",
                                  "recommended", "bright", "stunning", "vivid", "accurate",
                                  "fantastic", "value", "award", "winner", "punches above"]),
        negative_words=frozenset(["blooming", "banding", "dim", "washed out", "ghosting",
                                  "disappointing", "poor", "mediocre", "issues", "avoid"]),
        extract_specs=_specs_tv,
    ),

    "Monitors": CategoryProfile(
        name="Monitors",
        detect_keywords=["monitor", "display", "gaming monitor", "ultrawide", "curved monitor"],
        brands=["lg", "samsung", "dell", "asus", "acer", "benq", "viewsonic", "msi",
                "gigabyte", "aoc", "alienware", "hp", "lenovo", "eve", "nec", "eizo"],
        review_site="RTINGS",
        review_query_template="{model} rtings.com monitor review score",
        positive_words=frozenset(["accurate", "bright", "fast", "responsive", "crisp", "sharp",
                                  "excellent", "great", "value", "recommended", "impressive"]),
        negative_words=frozenset(["backlight bleed", "input lag", "ghosting", "dim", "washed",
                                  "flickering", "poor", "mediocre", "disappointing", "avoid"]),
        extract_specs=_specs_monitor,
    ),

    "Laptops": CategoryProfile(
        name="Laptops",
        detect_keywords=["laptop", "notebook", "chromebook", "macbook", "thinkpad", "ultrabook",
                         "gaming laptop", "2-in-1"],
        brands=["apple", "dell", "hp", "lenovo", "asus", "acer", "microsoft", "msi",
                "razer", "samsung", "lg", "gigabyte", "framework", "huawei", "toshiba",
                "surface"],
        review_site="NotebookCheck",
        review_query_template="{model} notebookcheck review rating",
        positive_words=frozenset(["fast", "battery life", "build quality", "keyboard", "display",
                                  "performance", "excellent", "great", "light", "thin",
                                  "recommended", "impressive", "value"]),
        negative_words=frozenset(["throttling", "overheating", "fan noise", "dim display",
                                  "flimsy", "slow", "poor", "mediocre", "disappointing",
                                  "short battery", "avoid"]),
        extract_specs=_specs_laptop,
    ),

    "Headphones": CategoryProfile(
        name="Headphones",
        detect_keywords=["headphones", "earbuds", "earphones", "headset", "true wireless",
                         "tws", "anc", "noise cancelling", "in-ear", "over-ear", "airpods"],
        brands=["sony", "bose", "apple", "samsung", "jabra", "sennheiser", "audio-technica",
                "beyerdynamic", "akg", "anker", "soundcore", "jbl", "skullcandy", "beats",
                "plantronics", "poly", "logitech", "hyperx", "steelseries", "corsair",
                "shure", "1more", "nothing"],
        review_site="RTINGS",
        review_query_template="{model} rtings.com headphones earbuds review score",
        positive_words=frozenset(["bass", "clarity", "noise cancelling", "comfortable",
                                  "detailed", "warm", "excellent", "great", "recommended",
                                  "impressive", "value", "balanced", "crisp"]),
        negative_words=frozenset(["muddy", "harsh", "uncomfortable", "leaks", "poor isolation",
                                  "tinny", "disappointing", "poor", "mediocre", "avoid",
                                  "distortion", "sibilant"]),
        extract_specs=_specs_headphones,
    ),

    "Smartphones": CategoryProfile(
        name="Smartphones",
        detect_keywords=["iphone", "smartphone", "android phone", "pixel", "galaxy s",
                         "galaxy a", "oneplus", "moto"],
        brands=["apple", "samsung", "google", "oneplus", "motorola", "sony", "nokia",
                "xiaomi", "nothing", "fairphone"],
        review_site="GSMArena",
        review_query_template="{model} gsmarena review score rating",
        positive_words=frozenset(["fast", "camera", "battery life", "display", "smooth",
                                  "excellent", "great", "flagship", "recommended", "impressive",
                                  "value", "stunning", "gorgeous"]),
        negative_words=frozenset(["slow", "overheating", "poor camera", "battery drain",
                                  "disappointing", "poor", "mediocre", "avoid", "lag",
                                  "plastic feel", "outdated"]),
        extract_specs=_specs_smartphone,
    ),

    "Tablets": CategoryProfile(
        name="Tablets",
        detect_keywords=["ipad", "tablet", "fire hd", "galaxy tab", "surface pro",
                         "surface go", "android tablet", "wacom"],
        brands=["apple", "samsung", "microsoft", "lenovo", "amazon", "google",
                "huawei", "xiaomi", "wacom"],
        review_site="NotebookCheck",
        review_query_template="{model} tablet review score rating",
        positive_words=frozenset(["fast", "battery", "display", "build quality", "smooth",
                                  "excellent", "great", "recommended", "impressive", "value",
                                  "responsive", "bright", "sharp"]),
        negative_words=frozenset(["slow", "dim", "poor", "mediocre", "disappointing",
                                  "avoid", "lag", "plasticky", "limited", "underpowered"]),
        extract_specs=_specs_tablet,
    ),

    "GPUs": CategoryProfile(
        name="GPUs",
        detect_keywords=["gpu", "graphics card", "rtx", "rx 7", "rx 6", "geforce",
                         "radeon", "video card", "nvidia", "amd gpu"],
        brands=["nvidia", "amd", "asus", "msi", "gigabyte", "sapphire", "xfx",
                "evga", "zotac", "powercolor", "palit"],
        review_site="Tom's Hardware",
        review_query_template="{model} toms hardware review benchmark fps",
        positive_words=frozenset(["fast", "efficient", "excellent", "great", "value",
                                  "recommended", "impressive", "rasterization", "ray tracing",
                                  "cool", "quiet", "powerful"]),
        negative_words=frozenset(["hot", "loud", "power hungry", "disappointing", "poor",
                                  "mediocre", "avoid", "slow", "overpriced", "stutter"]),
        extract_specs=_specs_gpu,
    ),

    "CPUs": CategoryProfile(
        name="CPUs",
        detect_keywords=["cpu", "processor", "ryzen", "core i", "core ultra",
                         "threadripper", "epyc", "xeon", "intel 13", "intel 14"],
        brands=["intel", "amd"],
        review_site="Tom's Hardware",
        review_query_template="{model} toms hardware CPU review benchmark score",
        positive_words=frozenset(["fast", "efficient", "excellent", "great", "value",
                                  "recommended", "impressive", "ipc", "performance",
                                  "power efficient", "multicore"]),
        negative_words=frozenset(["hot", "power hungry", "disappointing", "poor",
                                  "mediocre", "avoid", "throttle", "overpriced"]),
        extract_specs=_specs_cpu,
    ),

    "SSDs": CategoryProfile(
        name="SSDs",
        detect_keywords=["ssd", "nvme", "m.2", "solid state", "hard drive", "hdd",
                         "external drive", "flash drive", "usb drive", "portable ssd"],
        brands=["samsung", "western digital", "wd", "seagate", "crucial", "kingston",
                "sk hynix", "sabrent", "silicon power", "pny", "corsair", "teamgroup",
                "seagate", "toshiba", "lexar"],
        review_site="Tom's Hardware",
        review_query_template="{model} SSD review toms hardware read write speed",
        positive_words=frozenset(["fast", "excellent", "great", "value", "recommended",
                                  "impressive", "durable", "reliable", "consistent",
                                  "low latency", "sequential"]),
        negative_words=frozenset(["slow", "poor", "mediocre", "disappointing", "avoid",
                                  "unreliable", "failure", "dram-less", "cache drops"]),
        extract_specs=_specs_ssd,
    ),

    "Cameras": CategoryProfile(
        name="Cameras",
        detect_keywords=["camera", "mirrorless", "dslr", "lens", "gopro", "action cam",
                         "camcorder", "digital camera", "interchangeable"],
        brands=["canon", "nikon", "sony", "fujifilm", "panasonic", "olympus", "om system",
                "leica", "hasselblad", "ricoh", "sigma", "gopro", "dji", "insta360"],
        review_site="DPReview",
        review_query_template="{model} dpreview review score rating",
        positive_words=frozenset(["excellent", "great", "sharp", "dynamic range", "autofocus",
                                  "recommended", "impressive", "accurate", "vivid",
                                  "fast", "low noise", "value"]),
        negative_words=frozenset(["soft", "noisy", "poor autofocus", "slow", "disappointing",
                                  "poor", "mediocre", "avoid", "overexposed", "limited"]),
        extract_specs=_specs_camera,
    ),

    "Gaming": CategoryProfile(
        name="Gaming",
        detect_keywords=["ps5", "playstation", "xbox", "nintendo switch", "steam deck",
                         "game", "console bundle", "video game"],
        brands=["sony", "microsoft", "nintendo", "valve", "sega"],
        review_site="Metacritic / IGN",
        review_query_template="{model} review score metacritic rating",
        positive_words=frozenset(["excellent", "great", "recommended", "impressive", "fun",
                                  "engaging", "masterpiece", "must-play", "value",
                                  "deep", "replayable"]),
        negative_words=frozenset(["disappointing", "boring", "poor", "mediocre", "avoid",
                                  "buggy", "repetitive", "short", "overpriced", "shallow"]),
        extract_specs=_specs_gaming,
    ),

    "Gaming Peripherals": CategoryProfile(
        name="Gaming Peripherals",
        detect_keywords=["gaming keyboard", "gaming mouse", "mechanical keyboard", "gaming headset",
                         "mousepad", "keychron", "razer keyboard", "corsair keyboard",
                         "logitech mouse", "gaming controller"],
        brands=["logitech", "razer", "corsair", "steelseries", "hyperx", "asus rog",
                "msi", "zowie", "finalmouse", "glorious", "keychron", "ducky",
                "varmilo", "cherry", "endgame gear", "roccat", "cooler master"],
        review_site="Tom's Hardware / PCMag",
        review_query_template="{model} gaming peripheral review score rating",
        positive_words=frozenset(["accurate", "responsive", "comfortable", "clicky",
                                  "excellent", "great", "recommended", "impressive",
                                  "satisfying", "value", "precise", "fast"]),
        negative_words=frozenset(["mushy", "imprecise", "uncomfortable", "heavy", "noisy",
                                  "disappointing", "poor", "mediocre", "avoid",
                                  "faulty", "skip", "overpriced"]),
        extract_specs=_specs_peripherals,
    ),

    "Smart Home": CategoryProfile(
        name="Smart Home",
        detect_keywords=["smart home", "smart speaker", "echo", "alexa", "google home",
                         "homepod", "smart bulb", "smart plug", "smart lock", "thermostat",
                         "ring doorbell", "nest", "hue", "matter", "zigbee"],
        brands=["amazon", "google", "apple", "sonos", "bose", "ring", "nest",
                "ecobee", "lutron", "philips hue", "tp-link", "eero", "samsung",
                "wyze", "eufy", "arlo"],
        review_site="The Verge / PCMag",
        review_query_template="{model} smart home review score rating",
        positive_words=frozenset(["easy setup", "reliable", "responsive", "excellent",
                                  "great", "recommended", "impressive", "seamless",
                                  "value", "convenient", "smart", "compatible"]),
        negative_words=frozenset(["unreliable", "laggy", "privacy concerns", "disappointing",
                                  "poor", "mediocre", "avoid", "disconnects", "limited"]),
        extract_specs=_specs_smarthome,
    ),

    "Appliances": CategoryProfile(
        name="Appliances",
        detect_keywords=["vacuum", "robot vacuum", "roomba", "air fryer", "instant pot",
                         "air purifier", "coffee maker", "espresso", "blender", "stand mixer",
                         "washer", "dryer", "dishwasher", "refrigerator"],
        brands=["dyson", "irobot", "roborock", "shark", "bissell", "eufy", "ecovacs",
                "instant pot", "ninja", "cuisinart", "kitchenaid", "breville",
                "nespresso", "keurig", "vitamix", "oxo", "miele", "lg", "samsung",
                "whirlpool", "ge", "bosch"],
        review_site="Wirecutter / Consumer Reports",
        review_query_template="{model} wirecutter review rating best",
        positive_words=frozenset(["excellent", "great", "recommended", "impressive",
                                  "powerful suction", "quiet", "easy to clean", "reliable",
                                  "value", "effective", "smart mapping", "efficient"]),
        negative_words=frozenset(["weak suction", "noisy", "unreliable", "disappointing",
                                  "poor", "mediocre", "avoid", "flimsy", "short battery",
                                  "hard to empty"]),
        extract_specs=_specs_appliances,
    ),

    "Routers": CategoryProfile(
        name="Routers",
        detect_keywords=["router", "mesh wifi", "wifi system", "access point", "modem",
                         "range extender", "wifi 6", "wifi 7", "ax router", "be router"],
        brands=["tp-link", "netgear", "asus", "eero", "google", "linksys", "ubiquiti",
                "synology", "amazon", "orbi", "nighthawk", "deco", "archer"],
        review_site="Tom's Hardware / SmallNetBuilder",
        review_query_template="{model} router review throughput speed test",
        positive_words=frozenset(["fast", "excellent", "great", "recommended", "impressive",
                                  "coverage", "reliable", "easy setup", "value",
                                  "throughput", "low latency", "stable"]),
        negative_words=frozenset(["slow", "unreliable", "poor coverage", "disappointing",
                                  "poor", "mediocre", "avoid", "disconnects", "overpriced"]),
        extract_specs=_specs_router,
    ),

    "General": CategoryProfile(
        name="General",
        detect_keywords=[],
        brands=[],
        review_site="Google / PCMag",
        review_query_template="{model} review score rating",
        positive_words=frozenset(["excellent", "great", "recommended", "impressive",
                                  "value", "best", "outstanding", "fantastic"]),
        negative_words=frozenset(["disappointing", "poor", "mediocre", "avoid",
                                  "issues", "problems", "skip"]),
        extract_specs=_specs_general,
    ),
}


def detect_category(title: str, matched_keywords: list[str], hint: str = "") -> CategoryProfile:
    """Return the best-matching CategoryProfile for a deal."""
    if hint and hint in CATEGORIES:
        return CATEGORIES[hint]

    # Normalize hint to a known key (e.g. "TVs", "Laptops")
    hint_lower = hint.lower()
    for key, profile in CATEGORIES.items():
        if key.lower() == hint_lower:
            return profile

    text = (title + " " + " ".join(matched_keywords)).lower()
    scores: dict[str, int] = {}
    for key, profile in CATEGORIES.items():
        if key == "General":
            continue
        scores[key] = sum(1 for kw in profile.detect_keywords if kw in text)

    best = max(scores, key=lambda k: scores[k], default="General")
    if scores.get(best, 0) == 0:
        return CATEGORIES["General"]
    return CATEGORIES[best]
