"""Sample deals for offline demo/testing."""
from datetime import datetime, timedelta, timezone

from .models import Deal


def sample_deals() -> list[Deal]:
    now = datetime.now(tz=timezone.utc).replace(tzinfo=None)
    return [
        Deal(
            id="demo-1",
            title='LG C3 65" OLED 4K Smart TV',
            url="https://slickdeals.net/f/demo-lg-c3",
            price="$1,199.99",
            original_price="$1,799.99",
            score=312,
            category="TVs",
            store="Best Buy",
            published=now - timedelta(hours=2),
            summary="Incredible OLED deal — lowest price ever on the LG C3. Members save extra 10%.",
            matched_keywords=["oled", "4k", "tv"],
        ),
        Deal(
            id="demo-2",
            title='Samsung 75" QN90C QLED 4K TV',
            url="https://slickdeals.net/f/demo-samsung-qn90c",
            price="$997.99",
            original_price="$1,697.99",
            score=187,
            category="TVs",
            store="Amazon",
            published=now - timedelta(hours=5),
            summary="Samsung Neo QLED with Mini LED backlight at a record low price.",
            matched_keywords=["qled", "4k", "tv"],
        ),
        Deal(
            id="demo-3",
            title='TCL 55" S Class 4K UHD HDR Smart TV with Google TV',
            url="https://slickdeals.net/f/demo-tcl-55",
            price="$199.99",
            original_price="$329.99",
            score=94,
            category="TVs",
            store="Walmart",
            published=now - timedelta(hours=9),
            summary="Budget pick at an all-time low. Ships free.",
            matched_keywords=["4k", "uhd", "tv"],
        ),
        Deal(
            id="demo-4",
            title='Sony A80L 55" OLED 4K Google TV',
            url="https://slickdeals.net/f/demo-sony-a80l",
            price="$899.99",
            original_price="$1,399.99",
            score=256,
            category="TVs",
            store="Costco",
            published=now - timedelta(minutes=45),
            summary="Sony XR Cognitive Processor + Acoustic Surface Audio+. Includes 2-year warranty.",
            matched_keywords=["oled", "4k", "tv"],
        ),
        Deal(
            id="demo-5",
            title='Hisense U8K 65" Mini-LED QLED 4K TV',
            url="https://slickdeals.net/f/demo-hisense-u8k",
            price="$649.99",
            original_price="$999.99",
            score=143,
            category="TVs",
            store="Best Buy",
            published=now - timedelta(hours=14),
            summary="144Hz gaming TV with Dolby Vision IQ. Top value pick this year.",
            matched_keywords=["qled", "4k", "tv"],
        ),
    ]
