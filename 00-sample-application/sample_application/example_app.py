import random

# simulates AI model, returns (prediction, confidence)
# prediction is a dictionary and contains the proposed diagnosis as output
# confidence represents how accurate is the prediction
def predict(image_bytes):
    
    label = random.choice(["healthy", "tumor"])

    confidence = round(random.uniform(0.6, 0.99), 2)
    
    return {"label": label}, confidence