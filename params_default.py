import logging

#
# Enter project and wp details:
#
project = "<your-project-name>"
project_months = 0  # e.g., 36
project_start = 'yyyy-mm'

pms_start_month = 0  # e.g., 1
pms_end_month = 0  # e.g., 36

wps = [
    # <your-wp-list>, e.g.,:
    # { 'id' : 1, 'start' : 1, 'end' : 36, 'pms' :  1 },
    # ...
]

# END

# Exponential decay to penalize wps ending later when dropping pms:
# - the higher, the more aggressively we drop pms for WPs ending later as needed.
# - when 0, we drop pms uniformly across WPs as needed.
wp_pms_drop_decay_rate = 0.1

# Output settings
output_file_fmt = '{project} - PM assignment ({total_assigned_pms} out of {total_pms} PMs)'
gantt_chart_show = False
gantt_chart_save = True
csv_save = True
csv_delimiter = ','
csv_active = '-'
csv_assigned = 'x'

# Debug (enables verbose output and saving of intermediate results)
debug_enabled = False

log_level = logging.INFO
