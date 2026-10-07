import subprocess
import xml.etree.ElementTree as ET
import os

with open("test_dummy.py", "w") as f:
    f.write("""
def test_a(): pass
def test_b(): assert False
""")

subprocess.run(["./venv/bin/python3", "-m", "pytest", "test_dummy.py", "--junitxml=report.xml"])

tree = ET.parse("report.xml")
root = tree.getroot()
for testcase in root.iter('testcase'):
    name = testcase.get('name')
    failure = testcase.find('failure')
    status = "FAILED" if failure is not None else "PASSED"
    print(f"{name}: {status}")

os.remove("test_dummy.py")
os.remove("report.xml")
