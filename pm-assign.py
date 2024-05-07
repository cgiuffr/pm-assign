#!/usr/bin/python3

import sys
import logging

import matplotlib.pyplot as plt

import pulp
import math

import csv
from datetime import datetime


def save_gantt_chart(project, file, project_months, wps, wp_assignments=None, show=False):
    num_wps = len(wps)
    wp_assigned_pms = [0] * num_wps
    if wp_assignments:
        wp_assigned_pms = [len(a) for a in wp_assignments]

    x_labels = [f'M{i+1}' for i in range(project_months)]
    y_labels = [
        f'WP{i+1} ({wp_assigned_pms[i]}/{wps[i]["pms"]})' for i in range(num_wps)]
    # Create figure and axis
    fig, ax = plt.subplots(figsize=(15, 6))

    # Plot each work package
    for idx in range(num_wps):
        # Calculate duration
        duration = wps[idx]['end'] - wps[idx]['start'] + 1
        # Plot light grey bar for entire active period
        ax.barh(y_labels[idx], duration, left=wps[idx]
                ['start'] - 1, color='lightgrey', edgecolor='black')

        # Highlight assigned months in blue
        assigned_months = set(wp_assignments[idx]) if wp_assignments else set()
        for month in range(wps[idx]['start'], wps[idx]['end'] + 1):
            if month in assigned_months:
                ax.barh(y_labels[idx], 1, left=month - 1,
                        color='blue', edgecolor='black')
            else:
                ax.barh(y_labels[idx], 1, left=month - 1,
                        color='lightgrey', edgecolor='black')

    # Setting labels for x-axis
    # Start from 0, then every 6 months from    month 6
    x_tick_locations = [0] + list(range(5, project_months, 6))
    ax.set_xlabel('Months')
    ax.set_ylabel('Work Packages')
    ax.set_yticks(range(num_wps))
    ax.set_yticklabels(y_labels)
    ax.set_xticks(x_tick_locations)
    ax.set_xticklabels([x_labels[i] for i in x_tick_locations], rotation=45)
    ax.set_title(f'{project} Gantt Chart')

    # Set limits for better view
    ax.set_xlim(0, project_months)
    ax.set_ylim(-0.5, num_wps - 0.5)

    plt.gca().invert_yaxis()  # Invert y axis so that the first task is on top
    if file:
        plt.savefig(file)
        logger.info(f'Saved Gantt chart: {file}.')
    if show:
        plt.show()

# Function to increment months correctly


def add_months(start_date, months):
    month = start_date.month - 1 + months
    year = start_date.year + month // 12
    month = month % 12 + 1
    day = min(start_date.day, [31, 29 if year % 4 == 0 and not year % 100 == 0 or year %
              400 == 0 else 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1])
    return datetime(year, month, day)


def save_csv(project, file, project_months, wps, wp_assignments=None):
    wp_assigned_pms = [0] * len(wps)
    if wp_assignments:
        wp_assigned_pms = [len(a) for a in wp_assignments]

    # Convert project start to datetime object
    start_date = datetime.strptime(params.project_start, '%Y-%m')

    # Create header for the months
    headers = [f'{project}']
    headers2 = ['']
    for i in range(project_months):
        month_label = add_months(start_date, i).strftime('%Y-%m')
        headers.append(month_label)
        headers2.append(f'M{i+1}')
    csv_data = [headers, headers2]

    # Add WP data
    for idx, wp in enumerate(wps):
        row = [f'WP{wp["id"]} ({wp_assigned_pms[idx]}/{wps[idx]["pms"]})']
        active_months = set(range(wp['start'], wp['end'] + 1))
        assignments = set(wp_assignments[idx]) if wp_assignments else set()
        for month in range(1, project_months + 1):
            if month in active_months:
                if month in assignments:
                    row.append(params.csv_assigned)  # Mark as assigned
                else:
                    # Mark as active but not assigned
                    row.append(params.csv_active)
            else:
                row.append('')
        csv_data.append(row)

    # Add schedule
    csv_data.append([''])
    assigned_pms = sum(pms for pms in wp_assigned_pms)
    total_pms = sum(wp['pms'] for wp in wps)
    row = [f'Schedule ({assigned_pms}/{total_pms})']
    for month in range(1, project_months + 1):
        cell = ''
        for idx, assignment in enumerate(wp_assignments):
            if month in assignment:
                cell = f'WP{wps[idx]["id"]}'
                break
        row.append(cell)
    csv_data.append(row)

    # Write to CSV file
    with open(file, 'w', newline='') as f:
        writer = csv.writer(f, delimiter=params.csv_delimiter)
        writer.writerows(csv_data)

    logger.info(f'Saved CSV file: {file}.')


def may_save_assignments(project_months, wps, wp_assignments, undistributed=False):
    file = params.output_file_fmt.format(
        project=params.project,
        total_pms=sum(wp['pms'] for wp in params.wps),
        total_assigned_pms=sum(len(a) for a in wp_assignments)
    )
    if undistributed:
        file += "-undistributed"
    if not undistributed or params.debug_enabled:
        if params.gantt_chart_show or params.gantt_chart_save:
            save_gantt_chart(params.project, file + ".pdf",
                             project_months, wps, wp_assignments,
                             params.gantt_chart_show)
        if params.csv_save:
            save_csv(params.project, file + ".csv",
                     project_months, wps, wp_assignments)


def redistribute_person_months(wps, initial_assignments, start_month, end_month):
    model = pulp.LpProblem("redistribute_person_months", pulp.LpMinimize)

    # Indices for wps and months
    WPs = range(len(wps))
    Months = range(start_month-1, end_month)

    # Initialize variables for actual assignments and deviations
    x = pulp.LpVariable.dicts("assignment", ((i, j)
                              for i in WPs for j in Months), cat=pulp.LpBinary)
    deviations = pulp.LpVariable.dicts(
        "deviation", ((i, j) for i in WPs for j in Months), lowBound=0)

    # Objective: Minimize total deviation from the ideal distribution with PMs evenly spread out
    model += pulp.lpSum(deviations[i, j] for i in WPs for j in Months)

    for i in WPs:
        wp = wps[i]
        total_pm = len(initial_assignments[i])
        wp_start_month = max(wp['start'], start_month)
        wp_end_month = min(wp['end'], end_month)
        wp_Months = range(wp_start_month-1, wp_end_month)
        duration = wp_end_month - wp_start_month + 1
        ideal_cumulative = [
            (total_pm * (j - wp_start_month) / duration) for j in wp_Months]

        for idx, j in enumerate(wp_Months):
            actual_cumulative = pulp.lpSum(
                x[i, k] for k in range(wp_start_month-1, j + 1))
            model += deviations[i, j] >= actual_cumulative - \
                ideal_cumulative[idx]
            model += deviations[i,
                                j] >= ideal_cumulative[idx] - actual_cumulative

    # Constraints
    # Assignment Constraint: Exactly one wp per month
    for j in Months:
        model += pulp.lpSum(x[(i, j)] for i in WPs if wps[i]['start']-1 <= j < wps[i]['end']) \
            == 1

    # Total Assignment Constraint: Match the PMs required for any wp
    for i in WPs:
        model += pulp.lpSum(x[(i, j)] for j in Months if wps[i]['start']-1 <= j < wps[i]['end']) \
            == len(initial_assignments[i])

    # Solve the model
    solver = pulp.PULP_CBC_CMD(msg=params.debug_enabled)
    model.solve(solver)

    # Output the redistributed assignments
    assignments = [
        [j+1 for j in Months if pulp.value(x[(i, j)]) == 1] for i in WPs]

    return assignments


def assign_person_months(wps, start_month, end_month, decay_rate):
    model = pulp.LpProblem("assign_person_months", pulp.LpMinimize)

    # Indices for wps and months
    WPs = range(len(wps))
    Months = range(start_month-1, end_month)

    # Decision variables for assignments
    x = pulp.LpVariable.dicts("assignment", ((i, j)
                              for i in WPs for j in Months), cat=pulp.LpBinary)

    # Objective: Minimize unspent person months with exponential decay weights
    # - The higher the decay, the higher the probability wps ending later have more PMs dropped
    model += sum(math.exp(-decay_rate * (wps[i]['end'])) * (wps[i]['pms'] - sum(
        x[(i, j)] for j in Months if wps[i]['start']-1 <= j < wps[i]['end'])) for i in WPs)

    # Constraints
    # Assignment Constraint: Exactly one work package per month
    for j in Months:
        model += pulp.lpSum(x[(i, j)] for i in WPs if wps[i]['start']-1 <= j < wps[i]['end']) \
            == 1

    # Total Assignment Constraint: Do not exceed the person-months required for any work package
    for i in WPs:
        model += pulp.lpSum(x[(i, j)] for j in Months if wps[i]['start']-1 <= j < wps[i]['end']) \
            <= wps[i]['pms']

    # Solve the model
    solver = pulp.PULP_CBC_CMD(msg=params.debug_enabled)
    model.solve(solver)

    # Output the assignments
    assignments = [
        [j+1 for j in Months if pulp.value(x[(i, j)]) == 1] for i in WPs]
    return assignments


#
# main()
#
try:
    import params
except ImportError:
    print("Please create params.py based on params_default.py first.")
    sys.exit(1)

# Initialize logging
if params.debug_enabled:
    params.log_level = logging.DEBUG
logger = logging.getLogger()
logging.basicConfig(format='%(asctime)s [%(levelname)s] %(message)s')
logger.setLevel(params.log_level)

#
# Assign person months (PMs) by minimizing the number of unspent PMs
# per work package, leaving more unspent PMs for work packages ending later
#
logging.info('Assigning person months per work package...')
assignments = assign_person_months(
    params.wps, params.pms_start_month, params.pms_end_month, decay_rate=params.wp_pms_drop_decay_rate)
may_save_assignments(params.project_months, params.wps,
                     assignments, undistributed=True)

#
# Redistribute PMs for each work package so they are as evenly spread out
# as possible.
#
logging.info('Redistributing person months uniformly per work package...')
assignments = redistribute_person_months(
    params.wps, assignments, params.pms_start_month, params.pms_end_month)
may_save_assignments(params.project_months, params.wps, assignments)
