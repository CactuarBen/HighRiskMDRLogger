import json

from compliance_adapter.adapter import ComplianceAdapter

# integration test examining adapter and SDK
def test_finish_writes_one_event(tmp_path):
    # GIVEN
    # make a queue file path inside tmp_path
    queue_file = tmp_path / "queue.jsonl"
    # create the adapter, call start() then finish()
    adapter = ComplianceAdapter(str(queue_file), "demo-model", "1.0")

    # WHEN
    adapter.start(b"fake image bytes")
    adapter.finish({"label": "healthy"}, 0.95)

    # THEN
    # read the file and assert it has 1 line
    lines = queue_file.read_text().splitlines()
    assert len(lines) == 1
    # assert the line contains the model_name you passed
    event = json.loads(lines[0])
    assert event["system"]["model_name"] == "demo-model"
