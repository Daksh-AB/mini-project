# Reports page design

## Intent

Add a separate Reports page to the Streamlit dashboard so managers can review
weekly, monthly, or quarterly operational performance and download the filtered
report as CSV.

## Scope

- Add a Reports item to the existing dashboard navigation.
- Provide Weekly, Monthly, and Quarterly period choices.
- Show the selected period and its start/end dates.
- Summarize tasks, completion, delays, assignments, reallocations,
  disturbances, workload utilization, and prediction accuracy where data is
  available.
- Provide CSV downloads for the report's summary and detailed records.

## Data rules

- Use existing timestamped records (`assigned_at`, `changed_at`, `created_at`)
  for period filtering.
- Treat the current period as ending at the current time.
- Clearly label metrics that are snapshots (current employee workload and task
  status) rather than historical events.
- Do not invent historical creation dates for records that do not store them.

## Approaches considered

1. Add report controls inside Analytics: smallest change, but mixes live
   analytics with period reporting.
2. Add a separate Reports page with native Streamlit controls and CSV export:
   keeps navigation clear, uses existing data, and avoids new dependencies.
3. Add scheduled email/PDF reports: useful later, but requires an email
   provider, scheduler, and more deployment configuration.

Chosen approach: option 2, because it delivers the requested reporting value
without adding infrastructure and remains compatible with a future PostgreSQL
migration.

## Non-goals

- Automated email delivery.
- PDF generation.
- Rewriting the existing Analytics page.
- Claiming causal productivity or fairness improvements from descriptive data.
