import torch
import sys
from classifier import MultiUserCompressionNet, MAX_USERS, load_model

model, scaler = load_model("./models")
has_nan = False
for name, param in model.named_parameters():
    if torch.isnan(param).any():
        print(f"NaN found in {name}")
        has_nan = True
        
if not has_nan:
    print("No NaNs in model weights!")
else:
    print("Model weights contain NaNs!")
    
