
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import requests


# Download, deduplicate, validate, and safely save TLE records.
def download_tles():
    """Download debris and primary satellite TLEs into the data directory."""
    data_dir = Path(__file__).resolve().parent
    base_url = "https://celestrak.org/NORAD/elements/gp.php"

    debris_groups = [
        "cosmos-2251-debris",
        "iridium-33-debris",
        "fengyun-1c-debris",
    ]

    primary_ids = ["25994", "27424", "39084", "43013"]
    force_download = "--force" in sys.argv

    debris_file = data_dir / "tle_debris.txt"
    primaries_file = data_dir / "tle_primaries.txt"
    primaries_json_file = data_dir / "primaries.json"

    output_files = [debris_file, primaries_file, primaries_json_file]

    if not force_download and all(path.is_file() for path in output_files):
        print("Files already exist. Run with --force to re-download.")
        return

    headers = {"User-Agent": "hackathon-student-project"}
    debris_objects = {}
    primary_objects = {}

    # Parse complete name, line 1, line 2 records and verify their IDs.
    def parse_tles(text):
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        records = []

        if len(lines) % 3 != 0:
            raise ValueError("TLE response does not contain complete 3-line records.")

        for i in range(0, len(lines), 3):
            name, line1, line2 = lines[i:i + 3]

            if not line1.startswith("1 ") or not line2.startswith("2 "):
                raise ValueError("Invalid TLE line prefixes in downloaded response.")

            norad_id = line1[2:7].strip()

            if not norad_id.isdigit() or line2[2:7].strip() != norad_id:
                raise ValueError("TLE lines have invalid or mismatched NORAD IDs.")

            records.append((norad_id, [name, line1, line2]))

        return records

    # Download every debris group; abort safely if a request fails.
    for index, group in enumerate(debris_groups):
        url = f"{base_url}?GROUP={group}&FORMAT=tle"

        try:
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            records = parse_tles(response.text)

            if not records:
                raise ValueError(f"No debris records returned for {group}.")

            for norad_id, tle in records:
                debris_objects[norad_id] = tle

        except (requests.RequestException, ValueError) as error:
            raise RuntimeError(
                f"Could not download valid data for {group}. "
                "Existing output files have been preserved."
            ) from error

        if index < len(debris_groups) - 1:
            time.sleep(2)

    if not debris_objects:
        raise RuntimeError("No debris records downloaded; output files were not changed.")

    # Download each primary satellite and skip unavailable or invalid records.
    for index, primary_id in enumerate(primary_ids):
        url = f"{base_url}?CATNR={primary_id}&FORMAT=tle"

        try:
            response = requests.get(url, headers=headers, timeout=60)
            response.raise_for_status()
            records = parse_tles(response.text)
            matching = [tle for norad_id, tle in records if norad_id == primary_id]

            if matching:
                primary_objects[primary_id] = matching[0]
            else:
                print(f"Warning: No valid TLE found for {primary_id}.")

        except (requests.RequestException, ValueError) as error:
            print(f"Warning: Could not download {primary_id}: {error}")

        if index < len(primary_ids) - 1:
            time.sleep(2)

    if len(primary_objects) < 3:
        raise RuntimeError(
            f"Only {len(primary_objects)} primary satellites downloaded. "
            "At least 3 are required; existing output files were preserved."
        )

    primaries_data = [
        {"id": satellite_id, "name": tle[0]}
        for satellite_id, tle in primary_objects.items()
    ]

    debris_text = "".join(
        "\n".join(tle) + "\n" for tle in debris_objects.values()
    )
    primaries_text = "".join(
        "\n".join(tle) + "\n" for tle in primary_objects.values()
    )
    json_text = json.dumps(primaries_data, indent=2) + "\n"

    # Validate the complete output before replacing any existing files.
    def validate_tle_text(text, expected_ids=None):
        records = parse_tles(text)

        if not records:
            raise ValueError("TLE output must not be empty.")

        if expected_ids is not None:
            actual_ids = {norad_id for norad_id, _ in records}
            if actual_ids != set(expected_ids):
                raise ValueError("Saved TLE IDs do not match the expected IDs.")

        return len(records)

    debris_count = validate_tle_text(debris_text)
    primary_count = validate_tle_text(primaries_text, primary_objects.keys())

    with tempfile.TemporaryDirectory(dir=data_dir) as temp_dir:
        temp_dir = Path(temp_dir)
        staged_files = [
            (temp_dir / debris_file.name, debris_text),
            (temp_dir / primaries_file.name, primaries_text),
            (temp_dir / primaries_json_file.name, json_text),
        ]

        # Write and check all temporary files before touching existing outputs.
        for path, content in staged_files:
            path.write_text(content, encoding="utf-8")

        parsed_json = json.loads(staged_files[2][1].read_text(encoding="utf-8"))
        if len(parsed_json) < 3:
            raise ValueError("Primary satellite JSON validation failed.")

        # Replace outputs only after all downloads and validations succeed.
        for temp_path, final_path in zip(
            [item[0] for item in staged_files], output_files
        ):
            os.replace(temp_path, final_path)

    print(f"Debris objects: {debris_count}")
    print(f"Primaries: {primary_count}")

    for primary in primaries_data:
        print(f"Primary {primary['id']}: {primary['name']}")

    print(f"{debris_file.name}: VALID ({debris_count} records)")
    print(f"{primaries_file.name}: VALID ({primary_count} records)")
    print(f"{primaries_json_file.name}: VALID")


if __name__ == "__main__":
    try:
        download_tles()
    except (RuntimeError, ValueError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        sys.exit(1)
