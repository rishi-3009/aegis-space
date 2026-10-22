
from datetime import datetime, timezone
from textwrap import dedent


# Generates a readable plain-text alert for a conjunction event.
def generate_report(conj: dict, recommendation: dict | None = None) -> str:
    """Generate a plain-text collision risk report."""

    risk_levels = {
        "HIGH": (
            "Immediate attention recommended. Collision probability "
            "is above the action threshold of 1 in 10,000."
        ),
        "MEDIUM": (
            "Monitor closely. Probability is elevated but below "
            "the action threshold."
        ),
        "LOW": "No action needed. Probability is very low."
    }

    # Format collision probability and its inverse.
    pc = conj["pc"]

    if pc > 0:
        collision_chance = (
            f"{pc:.2e} (1 in {round(1 / pc):,})"
        )
    else:
        collision_chance = "effectively zero"

    # Parse the timestamp safely on Python 3.10 and normalize it to UTC.
    tca_text = conj["tca"]
    if tca_text.endswith("Z"):
        tca_text = tca_text[:-1] + "+00:00"

    tca_datetime = datetime.fromisoformat(tca_text)

    if tca_datetime.tzinfo is None:
        tca_datetime = tca_datetime.replace(tzinfo=timezone.utc)

    tca = tca_datetime.astimezone(timezone.utc).strftime(
        "%Y-%m-%d %H:%M:%S UTC"
    )

    # Decide what action to display based on the recommendation.
    if recommendation is None:
        recommended_action = "No maneuver analysis available."

    elif recommendation["recommended_delta_v_ms"] is None:
        recommended_action = (
            "No tested burn brings the risk below the safe level."
        )

    else:
        direction = recommendation["direction"]
        delta_v = recommendation["recommended_delta_v_ms"]
        new_miss = recommendation["new_miss_distance_km"]
        new_pc = recommendation["new_pc"]
        new_risk = recommendation["new_risk_level"]

        recommended_action = (
            f"Perform a {direction} burn of {delta_v:g} m/s "
            "about 6 hours before closest approach. "
            f"Expected result: miss distance {new_miss:g} km, "
            f"probability {new_pc:.2e}, risk {new_risk}."
        )

    assessment = risk_levels.get(
        conj["risk_level"],
        "Risk level is not recognized."
    )

    # Build the report without unwanted indentation.
    template = """
COLLISION RISK ALERT ({risk_level})
Event: {id}
------------------------------------------------
Primary satellite : {primary_name}
Other object      : {secondary_name}
Closest approach  : {tca}
Miss distance     : {miss_distance_km:.2f} km
Relative speed    : {relative_speed_kms:g} km/s
Collision chance  : {collision_chance}

ASSESSMENT
{assessment}

RECOMMENDED ACTION
{recommended_action}

ASSUMPTIONS
Position uncertainty 0.5 km, combined object size 20 m. Orbit data from public TLEs.
"""

    report = dedent(template).strip().format(
        risk_level=conj["risk_level"],
        id=conj["id"],
        primary_name=conj["primary"]["name"],
        secondary_name=conj["secondary"]["name"],
        tca=tca,
        miss_distance_km=conj["miss_distance_km"],
        relative_speed_kms=conj["relative_speed_kms"],
        collision_chance=collision_chance,
        assessment=assessment,
        recommended_action=recommended_action
    )

    # Mark synthetic scenarios clearly on the first line.
    if conj.get("synthetic", False):
        report = "*** DEMO SCENARIO (SYNTHETIC DATA) ***\n" + report

    return report


# Test the report using one example for each risk level.
if __name__ == "__main__":
    base_conj = {
        "primary": {"id": "25994", "name": "TERRA"},
        "secondary": {"id": "25995", "name": "COSMOS 2251 DEB"},
        "tca": "2026-10-23T04:12:30Z"
    }

    examples = [
        ("c001", "HIGH", 0.00019, 0.84, 10.2),
        ("c002", "MEDIUM", 0.00001, 1.23, 5.1),
        ("c003", "LOW", 0.0000001, 2.34, 2.5)
    ]

    for event_id, risk_level, pc, miss, speed in examples:
        conj = {
            **base_conj,
            "id": event_id,
            "risk_level": risk_level,
            "pc": pc,
            "miss_distance_km": miss,
            "relative_speed_kms": speed
        }

        print(generate_report(conj))
        print()

    # Verify the fallback when no tested burn reaches the safe level.
    no_burn = {
        "recommended_delta_v_ms": None,
        "direction": None,
        "new_miss_distance_km": None,
        "new_pc": None,
        "new_risk_level": None
    }

    test_conj = {
        **base_conj,
        "id": "test",
        "risk_level": "HIGH",
        "pc": 0.00019,
        "miss_distance_km": 0.84,
        "relative_speed_kms": 10.2
    }

    assert (
        "No tested burn brings the risk below the safe level."
        in generate_report(test_conj, no_burn)
    )
    print("Recommendation fallback test passed.")
