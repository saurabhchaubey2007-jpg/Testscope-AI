import os
import re
import xml.etree.ElementTree as ET


def parse_junit_xml(path: str) -> list:
    if not os.path.isfile(path):
        return []
    try:
        root = ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return []
    cases = []
    for case in root.iter("testcase"):
        status = "PASSED"
        for tag in ("failure", "error", "skipped"):
            if case.find(tag) is not None:
                status = {"failure": "FAILED", "error": "ERROR", "skipped": "SKIPPED"}[tag]
                break
        cases.append({"name": case.attrib.get("name", "unknown"), "status": status})
    return cases


def parse_pytest_output(stdout: str, stderr: str) -> dict:
    output = stdout + "\n" + stderr
    return {status: int(match.group(1)) if (match := re.search(rf"(\d+) {status}", output)) else 0
            for status in ("passed", "failed", "error", "skipped")}
