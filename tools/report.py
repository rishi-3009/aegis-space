"""
Report generator for aegis-space.
Produces human-readable collision risk reports.
"""


def generate_report(conjunction: dict) -> str:
    """Generate a text report from a conjunction dict."""
    c = conjunction
    risk = c["risk_level"]
    
    text = f"COLLISION RISK ALERT ({risk})\n"
    text += f"Event: {c['id']}\n"
    text += "-" * 50 + "\n"
    text += f"Primary satellite : {c['primary']['name']}\n"
    text += f"Other object      : {c['secondary']['name']}\n"
    text += f"Closest approach  : {c['tca']}\n"
    text += f"Miss distance     : {c['miss_distance_km']} km\n"
    text += f"Relative speed    : {c['relative_speed_kms']} km/s\n"
    text += f"Collision chance  : {c['pc']:.2e}"

    if risk == "HIGH":
        text += " (1 in {:.0f})\n\nASSESSMENT\nImmediate attention recommended.\n"
        text += "RECOMMENDED ACTION\nPerform a prograde burn of ~0.05 m/s before TCA.\n"
    elif risk == "MEDIUM":
        text += f" (1 in {:.0f})\n\nASSESSMENT\nMonitor closely.\n"
        text += "RECOMMENDED ACTION\nConsider a small corrective burn.\n"
    else:
        text += "\n\nASSESSMENT\nLow risk, no action required.\n"

    text += "\nASSUMPTIONS: Position uncertainty 0.5 km, combined object size 20 m."
    return text
