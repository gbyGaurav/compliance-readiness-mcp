"""
Verification script: tests that python -m src.server starts over stdio,
outputs NO garbage on stdout, and properly responds to JSON-RPC MCP requests.
"""

import subprocess
import json
import sys
import time


def test_handshake():
    cmd = [r".venv\Scripts\python.exe", "-m", "src.server"]
    print(f"Launching MCP server: {' '.join(cmd)} ...")
    
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=0,
    )

    # 1. Send initialize request
    init_req = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }
    
    req_json = json.dumps(init_req) + "\n"
    proc.stdin.write(req_json)
    proc.stdin.flush()

    # 2. Read first response line from stdout
    line = proc.stdout.readline().strip()
    if not line:
        proc.kill()
        stderr_out = proc.stderr.read()
        print("ERROR: Server closed stdout without response. Stderr was:\n", stderr_out)
        sys.exit(1)

    print("Received raw line on stdout:")
    print(line)

    try:
        response = json.loads(line)
    except Exception as e:
        print(f"FAILED: stdout contained non-JSON output! Error: {e}")
        print("Raw output:", repr(line))
        proc.kill()
        sys.exit(1)

    print("\nSUCCESS: Output is valid JSON-RPC response:")
    print(json.dumps(response, indent=2))
    assert response.get("jsonrpc") == "2.0"
    assert response.get("id") == 1
    assert "result" in response
    assert response["result"]["serverInfo"]["name"] == "Consus Compliance Operations"

    # 3. Send initialized notification
    proc.stdin.write(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}) + "\n")
    proc.stdin.flush()

    # 4. Request tools/list
    tools_req = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }
    proc.stdin.write(json.dumps(tools_req) + "\n")
    proc.stdin.flush()

    tools_line = proc.stdout.readline().strip()
    tools_resp = json.loads(tools_line)
    tools = [t["name"] for t in tools_resp["result"]["tools"]]
    print("\nDiscovered MCP tools over stdio JSON-RPC:")
    for t in tools:
        print(f"  - {t}")

    expected_tools = [
        "register_company",
        "scan_company_documents",
        "store_company_documents",
        "ingest_company_documents",
        "analyze_compliance",
        "get_compliance_suggestions",
        "create_compliance_task",
        "create_compliance_tasks",
        "assign_compliance_task",
        "update_task_status",
        "recheck_requirement",
        "recheck_company_compliance",
        "generate_remediation_report",
        "generate_final_readiness_report",
        "generate_compliance_report",
    ]
    for et in expected_tools:
        assert et in tools, f"Missing tool {et}"

    print(f"\nALL {len(expected_tools)} TOOLS VERIFIED OVER STDIO!")

    # 5. Request prompts/list
    prompts_req = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "prompts/list",
        "params": {}
    }
    proc.stdin.write(json.dumps(prompts_req) + "\n")
    proc.stdin.flush()

    prompts_line = proc.stdout.readline().strip()
    prompts_resp = json.loads(prompts_line)
    prompts = [p["name"] for p in prompts_resp["result"]["prompts"]]
    print(f"\nDiscovered MCP prompts: {prompts}")
    assert "company_onboarding_and_readiness" in prompts
    assert "compliance_readiness_assessment" in prompts

    # 6. Test calling register_company over stdio
    reg_req = {
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "register_company",
            "arguments": {"company_name": "XYZ"}
        }
    }
    proc.stdin.write(json.dumps(reg_req) + "\n")
    proc.stdin.flush()
    reg_line = proc.stdout.readline().strip()
    reg_resp = json.loads(reg_line)
    print(f"\nregister_company response: {reg_resp}")
    assert "result" in reg_resp

    # 7. Test calling scan_company_documents over stdio
    scan_req = {
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "scan_company_documents",
            "arguments": {"company_id": "XYZ"}
        }
    }
    proc.stdin.write(json.dumps(scan_req) + "\n")
    proc.stdin.flush()
    scan_line = proc.stdout.readline().strip()
    scan_resp = json.loads(scan_line)
    print(f"\nscan_company_documents response: {scan_resp}")
    assert "result" in scan_resp

    print("\nALL STDIO ONBOARDING TOOL INVOCATIONS PASSED!")

    # Clean shutdown
    proc.terminate()
    proc.wait(timeout=2)
    print("Server cleanly terminated. All stdio communication validated.")


if __name__ == "__main__":
    test_handshake()
