with open('apps/api/app/services/report_service.py', 'r') as f:
    content = f.read()

content = content.replace(
    "total_generated += tc_generated",
    "total_generated += max(tc_generated, tc_passed + tc_failed)"
)

with open('apps/api/app/services/report_service.py', 'w') as f:
    f.write(content)
