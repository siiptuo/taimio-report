from collections import defaultdict
import os.path
import sys
import requests
import arrow

API_ROOT = 'http://api.tiima.dev'


def fetch_token():
    if not os.path.isfile('token'):
        username = input('Username: ')
        password = input('Password: ')
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


def fetch_activities(token):
    req = requests.get(API_ROOT + '/activities', headers={
        'Authorization': 'Bearer ' + token,
    })
    for activity in req.json():
        activity['started_at'] = arrow.get(activity['started_at'])
        activity['finished_at'] = arrow.get(activity['finished_at'])
        yield activity


def get_activity_project(activity, tag_projects):
    for tag in activity['tags']:
        if tag in tag_projects:
            return tag_projects[tag]
    return None


def calculate_activity_duration_hours(activity):
    delta = activity['finished_at'] - activity['started_at']
    return delta.total_seconds() / (60 * 60)


def filter_activities_by_month(activities, year, month):
    for activity in activities:
        activity_year = activity['started_at'].year
        activity_month = activity['started_at'].month
        if activity_year == year and activity_month == month:
            yield activity


def filter_activities_by_tag(activities, tag):
    for activity in activities:
        if tag in activity['tags']:
            yield activity


def group_activities_by_date(activities):
    dates = defaultdict(list)
    for activity in activities:
        dates[activity['started_at'].date()].append(activity)
    return dates


def generate_day_report(activities, tag_projects, tag, year, month):
    activities = filter_activities_by_month(activities, year, month)
    activities = filter_activities_by_tag(activities, tag)
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
    activities = fetch_activities(token)
    total_hours = 0
    report = generate_day_report(activities, tag_projects, sys.argv[1],
                                 int(sys.argv[2]), int(sys.argv[3]))
    for date, hours, projects in report:
        print(date, format_hours(hours), projects)
        total_hours += hours
    print('Total:', format_hours(total_hours))

if __name__ == "__main__":
    main()
