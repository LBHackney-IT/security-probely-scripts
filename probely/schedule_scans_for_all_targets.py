#!/usr/bin/env python

"""
Find all targets with zero or one scheduled scans
and update them all to run at the same time (roughly)
"""

from datetime import datetime
from datetime import time
from datetime import timedelta
from urllib.parse import urljoin
import requests

API_BASE_URL = "https://api.probely.com"


def api_headers(api_token):
    """Get the appropriate API headers for Probely"""
    return {
        "Authorization": f"JWT {api_token}",
        "Content-Type": "application/json"
        }


def target_schedules(api_token):
    """Get a list of all the scheduled scans, grouped by target"""
    scheduled_scans_endpoint = urljoin(
        API_BASE_URL, "scheduledscans/?length=10000"
    )

    response = requests.get(scheduled_scans_endpoint,
                            headers=api_headers(api_token),
                            timeout=30)

    # print(response.content)
    # results = list(map(flatten_scan_response, response.json()["results"]))

    targets = {}
    for scheduled_scan in response.json()["results"]:
        target_id = scheduled_scan["target"]["id"]
        if target_id not in targets:
            targets[target_id] = {
                "id": target_id,
                "name": scheduled_scan["target"]["site"]["name"],
                "scheduled_scans": []
            }

        targets[target_id]["scheduled_scans"].append({
            "id": scheduled_scan["id"],
            "next_scan": scheduled_scan["date_time"],
            "recurrence": scheduled_scan["recurrence"],
        })
    return targets


def main():  # pylint: disable=too-many-locals
    """
    Find and update all targets with one or fewer scheduled scans to use
    a new schedule, stepping targets to prevent heavy load across our estate
    """

    api_token = input("API Token:")
    targets = target_schedules(api_token=api_token)

    # Get targets with no schedule
    targets_endpoint = urljoin(
        API_BASE_URL, "targets/?include=compliance&length=10000"
    )

    response = requests.get(targets_endpoint,
                            headers=api_headers(api_token=api_token),
                            timeout=30)

    results = response.json()["results"]

    for target in results:
        target_id = target["id"]
        if target_id not in targets:
            targets[target_id] = {
                "id": target_id,
                "name": target["site"]["name"],
                "scheduled_scans": []
            }

    tomorrow = datetime.today() + timedelta(days=1)
    midnight = time(0, 0, 0)

    start_time = datetime.combine(tomorrow, midnight)

    for target_id, target in targets.items():
        target_name = target["name"]

        start_time = start_time + timedelta(minutes=2)

        # Create a payload to create a scheduled scan.
        # See https://developers.probely.com
        schedule_payload = {
            "date_time": start_time.strftime('%Y-%m-%dT%H:%M:%SZ'),
            "recurrence": "d",  # daily
            "timezone": "UTC"
        }

        schedule_count = len(target["scheduled_scans"])

        if schedule_count > 1:
            print(f"ERROR: multiple scheduled scans found for target '{target_name}', skipping")  # pylint: disable=line-too-long # noqa
        elif schedule_count == 1:
            old_schedule = target["scheduled_scans"][0]["next_scan"]
            old_recurrence = target["scheduled_scans"][0]["recurrence"]
            print(f"Updating schedule for {target_name} from {old_schedule} ({old_recurrence}) to {schedule_payload}")  # pylint: disable=line-too-long # noqa

            scheduled_scan_put_url = urljoin(
                API_BASE_URL,
                f'targets/{target_id}/scheduledscans/{target["scheduled_scans"][0]["id"]}/')  # noqa

            response = requests.put(
                scheduled_scan_put_url,
                headers=api_headers(api_token=api_token),
                json=schedule_payload,
                timeout=10
            )

            if response.status_code != 200:
                print(scheduled_scan_put_url)
                print(schedule_payload)
                print(response.status_code)
                print(response.reason)
                print(response.content)
        else:
            print(f"Creating schedule for {target_name}: {schedule_payload}")

            response = requests.post(
                urljoin(API_BASE_URL, f"targets/{target_id}/scheduledscans/"),
                headers=api_headers(api_token=api_token),
                json=schedule_payload,
                timeout=10
            )

            if response.status_code != 201:
                print(response.status_code)
                print(response.reason)
                print(response.content)


if __name__ == '__main__':
    main()
