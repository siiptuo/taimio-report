#!/usr/bin/env python3

from collections import defaultdict, OrderedDict
import os.path
import re
from getpass import getpass
import datetime
import sys
import json
from json import JSONDecodeError
import requests
from requests.exceptions import RequestException, HTTPError
import arrow


DATE_REGEX = r'^(\d+)(?:-(0\d|1[0-2])(?:-([0-2]\d|3[0-1]))?)?$'


def parse_date(date):
    """Parse ISO 8601 date with optional month and day"""
    match = re.match(DATE_REGEX, date)
    if match is None:
        raise ValueError
    return (int(s) if s else None for s in match.group(1, 2, 3))


API_ROOT = 'https://api.taim.io'


def fetch_token():
    if not os.path.isfile('token'):
        username = input('Username: ')
        password = getpass('Password: ')
        req = requests.post(API_ROOT + '/login', data={
            'username': username,
            'password': password,
        })
        token = req.json()['token']
        with open('token', mode='w') as file:
            file.write(token)
        return token
    with open('token') as file:
        return file.read()


class Activity:
    pass


def as_activity(data):
    activity = Activity()
    activity.title = data['title']
    activity.tags = data['tags']
    activity.started_at = arrow.get(data['started_at'])
    activity.finished_at = arrow.get(data['finished_at'])
    return activity


def get_last_date_of_month(year, month):
    from calendar import monthrange
    return datetime.date(year, month, monthrange(year, month)[1])


def get_last_date_of_year(year):
    return get_last_date_of_month(year, 12)


def fetch_activities(token, tag, start_date, end_date):
    req = requests.get(API_ROOT + '/activities',
                       params={
                           'start_date': start_date,
                           'end_date': end_date,
                           'tag': tag,
                       },
                       headers={
                           'Authorization': 'Bearer ' + token,
                       })
    if req.status_code != 200:
        try:
            raise HTTPError(json.loads(req.text)['error'])
        except (JSONDecodeError, KeyError):
            raise HTTPError(req.text)
    return json.loads(req.text, object_hook=as_activity)


def get_activity_project(activity, tag_projects):
    for tag in activity.tags:
        if tag in tag_projects:
            return tag_projects[tag]
    return None


def calculate_activity_duration_hours(activity):
    delta = activity.finished_at - activity.started_at
    return delta.total_seconds() / (60 * 60)


def group_activities_by_date(activities):
    dates = defaultdict(list)
    for activity in activities:
        dates[activity.started_at.date()].append(activity)
    return OrderedDict(sorted(dates.items()))


def generate_day_report(activities, tag_projects):
    for date, activities in group_activities_by_date(activities).items():
        projects = {get_activity_project(activity, tag_projects) or 'Other'
                    for activity in activities}
        yield date, activities, sorted(projects)


def generate_project_report(activities, tag_projects):
    for date, activities in group_activities_by_date(activities).items():
        projects = defaultdict(list)
        for activity in activities:
            activity_project = get_activity_project(activity, tag_projects)
            projects[activity_project].append(activity)
        for project in projects:
            yield date, project or 'Other', projects[project]


def load_projects(filename):
    tag_projects = {}
    with open(filename) as file:
        for line in file:
            tag, project = line.split('=', 1)
            tag_projects[tag.strip()] = project.strip()
    return tag_projects


def format_hours(number):
    return str(round(number * 2) / 2) + 'h'


def main():
    tag_projects = load_projects('projects')
    token = fetch_token()

    if len(sys.argv) < 4:
        print('Usage: ./taimio_report.py (day|project) tag <start-date> [<end-date>]')
        sys.exit()

    report_type = sys.argv[1]
    if report_type not in ('day', 'project'):
        sys.exit("invalid report type {}, use day or project".format(report_type))

    tag = sys.argv[2]

    try:
        year, month, day = parse_date(sys.argv[3])
        start_date = datetime.date(year, month or 1, day or 1)
        if len(sys.argv) > 4:
            year, month, day = parse_date(sys.argv[4])
        if not month:
            end_date = get_last_date_of_year(year)
        elif not day:
            end_date = get_last_date_of_month(year, month)
        else:
            end_date = datetime.date(year, month, day)
    except ValueError:
        sys.exit('Invalid date {}, use YYYY, YYYY-MM or YYYY-MM-DD'.format(sys.argv[3]))

    try:
        activities = fetch_activities(token, tag, start_date, end_date)
    except HTTPError as exception:
        sys.exit('API error: {}'.format(exception))
    except RequestException as exception:
        sys.exit('Failed to contact server {}: {}'.format(API_ROOT, exception))

    if report_type == 'day':
        total_hours = 0
        report = generate_day_report(activities, tag_projects)
        for date, activities, projects in report:
            hours = sum(calculate_activity_duration_hours(activity)
                        for activity in activities)
            print(date, format_hours(hours), ', '.join(projects))
            total_hours += hours
        print('Total:', format_hours(total_hours))
    elif report_type == 'project':
        report = generate_project_report(activities, tag_projects)
        for date, project, activities in report:
            hours = sum(calculate_activity_duration_hours(activity)
                        for activity in activities)
            titles = {activity.title for activity in activities}
            print(date, format_hours(hours), project,
                  '(' + ', '.join(titles) + ')')

if __name__ == "__main__":
    main()
