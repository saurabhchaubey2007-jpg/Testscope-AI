import re

with open('apps/api/app/services/report_service.py', 'r') as f:
    content = f.read()

# Replace the tests list construction
old_tests = """        "tests": [
            {
                "name": tc.name,
                "status": next((tr.status for tr in test_results if tr.test_case_id == tc.id), "UNKNOWN")
            } for tc in test_cases
        ],"""

new_tests = """        "tests": [],"""

content = content.replace(old_tests, new_tests)

# Insert the logic to parse -v output and populate 'tests' array
logic = """
    all_tests = []
    for tc in test_cases:
        tr = next((tr for tr in test_results if tr.test_case_id == tc.id), None)
        if tr and tr.stdout:
            # Parse pytest -v output lines like "test_token.py::test_create_token_returns_string PASSED"
            for line in tr.stdout.split("\\n"):
                match = re.search(r'::([^ ]+) (PASSED|FAILED|ERROR|SKIPPED)', line)
                if match:
                    all_tests.append({
                        "name": match.group(1),
                        "status": match.group(2)
                    })
        elif tr and tr.status == "ERROR":
            # If it failed to run completely (e.g. syntax error)
            all_tests.append({
                "name": tc.name,
                "status": "ERROR"
            })
            
    # Remove duplicates if any (though shouldn't be)
    seen = set()
    unique_tests = []
    for t in all_tests:
        if t["name"] not in seen:
            seen.add(t["name"])
            unique_tests.append(t)
"""

# We need to insert this before return {
parts = content.split("    return {")
content = parts[0] + logic + "    return {" + parts[1]

# Now we need to replace "tests": [], with "tests": unique_tests,
content = content.replace('"tests": [],', '"tests": unique_tests,')

with open('apps/api/app/services/report_service.py', 'w') as f:
    f.write(content)
