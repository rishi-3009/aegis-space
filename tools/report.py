"""
Report generator for aegis-space.
Produces human-readable collision risk reports.
"""


def _burn_line(recommendation):
    """Describe the recommended burn, or say that no tested burn is enough."""
    if recommendation and recommendation.get("recommended_delta_v_ms") is not None:
        return (
            f"Perform a {recommendation['direction']} burn of "
            f"{recommendation['recommended_delta_v_ms']} m/s at least 6 hours before TCA."
        )
    return "No tested burn brings the risk below the safe threshold. Re-screen before acting."


def generate_report(conjunction, recommendation=None):
    """Generate a text report from a conjunction dict and its burn recommendation (optional)."""
    c = conjunction
    risk = c["risk_level"]

    text = f"COLLISION RISK ALERT ({risk})\n"
    text += f"Event: {c['id']}\n"
    if c.get("synthetic"):
        text += "*** SYNTHETIC DEMO EVENT, NOT REAL DATA ***\n"
    text += "-" * 50 + "\n"
    text += f"Primary satellite : {c['primary']['name']}\n"
    text += f"Other object      : {c['secondary']['name']}\n"
    text += f"Closest approach  : {c['tca']}\n"
    text += f"Miss distance     : {c['miss_distance_km']} km\n"
    text += f"Relative speed    : {c['relative_speed_kms']} km/s\n"
    text += f"Collision chance  : {c['pc']:.2e}"

    if risk == "HIGH":
        text += f" (1 in {1 / c['pc']:.0f})\n\nASSESSMENT\nImmediate attention recommended.\n"
        text += f"RECOMMENDED ACTION\n{_burn_line(recommendation)}\n"
    elif risk == "MEDIUM":
        text += f" (1 in {1 / c['pc']:.0f})\n\nASSESSMENT\nMonitor closely.\n"
        text += f"RECOMMENDED ACTION\nConsider a small corrective burn. {_burn_line(recommendation)}\n"
    else:
        text += "\n\nASSESSMENT\nLow risk, no action required.\n"

    text += "\nASSUMPTIONS: Position uncertainty 0.5 km, combined object size 20 m."
    return text
