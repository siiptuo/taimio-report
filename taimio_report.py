from collections import defaultdict
import os.path
from getpass import getpass
import datetime
import sys
import json
import requests
import arrow

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


def fetch_activities(token, tag, year, month):
    req = requests.get(API_ROOT + '/activities',
                       params={
                           'start_date': datetime.date(year, month, 1),
                           'end_date': get_last_date_of_month(year, month),
                           'tag': tag,
                       },
                       headers={
                           'Authorization': 'Bearer ' + token,
                       })
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
    return dates


def generate_day_report(token, tag_projects, tag, year, month):
    activities = fetch_activities(token, tag, year, month)
    activities_by_date = group_activities_by_date(activities)

    for date in sorted(activities_by_date):
        activities = activities_by_date[date]
        projects = {get_activity_project(activity, tag_projects) or 'Other'
                    for activity in activities}
        hours = sum(calculate_activity_duration_hours(activity)
                    for activity in activities)
        yield date, hours, ', '.join(sorted(projects))


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
    total_hours = 0
    report = generate_day_report(token, tag_projects, sys.argv[1],
                                 int(sys.argv[2]), int(sys.argv[3]))
    for date, hours, projects in report:
        print(date, format_hours(hours), projects)
        total_hours += hours
    print('Total:', format_hours(total_hours))

if __name__ == "__main__":
    main()
