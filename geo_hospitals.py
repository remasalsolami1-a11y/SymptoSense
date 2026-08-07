"""
geo_hospitals.py — find nearby hospitals using OpenStreetMap's Overpass API.
Free, no API key required. Used only for urgent (high-severity) cases.
"""

import math
import logging
import requests

logger = logging.getLogger(__name__)

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def find_nearby_hospitals(lat, lon, radius_m=8000, limit=5):
    """Returns up to `limit` nearby hospitals as
    [{"name", "lat", "lon", "distance_km", "maps_url"}], sorted by distance."""
    query = f"""
    [out:json][timeout:12];
    (
      node["amenity"="hospital"](around:{radius_m},{lat},{lon});
      way["amenity"="hospital"](around:{radius_m},{lat},{lon});
    );
    out center {limit * 3};
    """
    headers = {
        "User-Agent": "SymptoSenseBot/2.0 (health-awareness web app; contact: none)",
        "Accept": "application/json",
    }
    try:
        resp = requests.post(OVERPASS_URL, data={"data": query}, headers=headers, timeout=20)
        resp.raise_for_status()
        elements = resp.json().get("elements", [])
    except Exception as e:
        logger.warning(f"Overpass API request failed: {e}")
        return []

    results = []
    for el in elements:
        name = el.get("tags", {}).get("name")
        if not name:
            continue
        if el["type"] == "node":
            elat, elon = el["lat"], el["lon"]
        else:
            center = el.get("center")
            if not center:
                continue
            elat, elon = center["lat"], center["lon"]
        dist = _haversine_km(lat, lon, elat, elon)
        results.append({
            "name": name,
            "lat": elat,
            "lon": elon,
            "distance_km": round(dist, 1),
            "maps_url": f"https://www.google.com/maps/search/?api=1&query={elat},{elon}",
        })

    results.sort(key=lambda r: r["distance_km"])
    return results[:limit]
