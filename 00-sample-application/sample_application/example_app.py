import random

from compliance_adapter.adapter import ComplianceAdapter

# simulates AI model, returns (prediction, confidence)
# prediction is a dictionary and contains the proposed diagnosis as output
# confidence represents how accurate is the prediction
def predict(image_bytes: bytes) -> tuple[dict[str, str], float]:
    if random.random() < 0.3:
        raise ValueError("model crashed")
    
    label = random.choice(["healthy", "tumor"])

    confidence = round(random.uniform(0.6, 0.99), 2)

    print("Label: " + str(label) + "Confidence: " + str(confidence))
    
    return {"label": label}, confidence

def main():
    adapter = ComplianceAdapter("queue/queue.jsonl", "demo-model", "1.0")

    inputs = [b"first scan", b"second scan", b"third scan"]

    for data in inputs:
        try:
            adapter.start(data)
            prediction, confidence = predict(data)
            adapter.finish(prediction, confidence)
        except Exception as e:
            adapter.error(e)

if __name__ == "__main__":
    main()