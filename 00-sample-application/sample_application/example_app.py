import random

from compliance_adapter.adapter import ComplianceAdapter


# simulates AI model, returns (prediction, confidence)
# prediction is a dictionary and contains the proposed diagnosis as output
# confidence represents how accurate is the prediction
# a fake model ignores its input, so image_bytes is unused on purpose
def predict(image_bytes: bytes) -> tuple[dict[str, str], float]:  # pylint: disable=unused-argument
    if random.random() < 0.3:
        raise ValueError("model crashed")

    label = random.choice(["healthy", "tumor"])

    confidence = round(random.uniform(0.6, 0.99), 2)

    print("Label: " + str(label) + "Confidence: " + str(confidence))

    return {"label": label}, confidence

def main() -> None:
    adapter = ComplianceAdapter("queue/queue.jsonl", "demo-model", "1.0")

    scans = {"patient-1": b"first scan", "patient-2": b"second scan", "patient-3": b"third scan"}

    # let an auditor asks the application for the id of a patient, then reads the associated events
    event_ids: dict[str, str] = {}

    for patient, data in scans.items():
        adapter.start(data)
        try:
            prediction, confidence = predict(data)
        except ValueError as e:
            adapter.error(e)
            continue
        event_ids[patient] = adapter.finish(prediction, confidence)

    print(event_ids)

if __name__ == "__main__":
    main()
