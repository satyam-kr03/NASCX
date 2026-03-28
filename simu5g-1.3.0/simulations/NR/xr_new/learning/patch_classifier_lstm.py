import re

with open('/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/learning/classifier.py', 'r') as f:
    content = f.read()

# Replace prepare_training_targets to remove strict groupby and return raw trajectory states
content = re.sub(
r'''    optimal_idx = df_n\.groupby\(group_cols\)\["total_cost"\]\.idxmin\(\)\n    opt         = df_n\.loc\[optimal_idx\]\.reset_index\(drop=True\)\n\n    X_active = opt\[state_cols\]\n    Y_active = \(opt\[comp_cols\] / COMP_STEP - COMP_OFFSET\)\.astype\(int\)''',
'''
    # REMOVED GROUPBY - Using best per-frame components directly
    # To prevent exploding dataset size, we'll subsample if too large but keep frame-level variance
    # df_n is already sorted by simulation frame sequence.
    # Group by frameNumber to get the true optimal component per frame instance:
    optimal_idx = df_n.groupby("frameNumber")["total_cost"].idxmin()
    opt         = df_n.loc[optimal_idx].reset_index(drop=True)
    
    Y_active = (opt[comp_cols] / COMP_STEP - COMP_OFFSET).astype(int)
    
    # Simple feature selection for LSTM (no rolling windows applied here yet, we do sequences later or just let the model process step by step)
    X_active = opt[state_cols]
''', content)

# Change Architecture to include GRU/LSTM
content = re.sub(
r'''class MultiUserCompressionNet\(nn\.Module\):.*\n    def __init__\(self, max_users: int = MAX_USERS\):\n        super\(\)\.__init__\(\)\n        self\.max_users = max_users\n        input_dim = max_users \* FEATURES_PER_USER \+ GLOBAL_FEATURES\n\n        self\.body = nn\.Sequential\(\n            nn\.Linear\(input_dim, 256\),\n            nn\.ReLU\(\),\n            nn\.Linear\(256, 128\),\n            nn\.ReLU\(\),\n        \)\n        self\.heads = nn\.ModuleList\(\[\n            nn\.Linear\(128, NUM_CLASSES\) for _ in range\(max_users\)\n        \]\)''',
'''class MultiUserCompressionNet(nn.Module):
    def __init__(self, max_users: int = MAX_USERS):
        super().__init__()
        self.max_users = max_users
        self.input_dim = max_users * FEATURES_PER_USER + GLOBAL_FEATURES

        # LSTM Layer for time sequence (batch_first=True)
        # Input shape expected: (Batch, Seq_len, input_dim) if sequences used.
        # Right now we'll support both (Batch, input_dim) and (Batch, seq, input_dim)
        self.rnn = nn.GRU(self.input_dim, 128, num_layers=1, batch_first=True)
        
        self.body = nn.Sequential(
            nn.Linear(128, 128),
            nn.ReLU(),
        )
        self.heads = nn.ModuleList([
            nn.Linear(128, NUM_CLASSES) for _ in range(max_users)
        ])''', content, flags=re.DOTALL)

content = re.sub(
r'''    def forward\(self, x\):\n        h = self\.body\(x\)\n        return \[head\(h\) for head in self\.heads\]''',
'''    def forward(self, x, hidden=None):
        # x shape can be (Batch, input_dim) -> add seq_len 1
        # or (Batch, Seq_len, input_dim)
        if x.dim() == 2:
            x = x.unsqueeze(1) # (B, 1, F)
            
        rnn_out, hidden = self.rnn(x, hidden)
        
        # Take the last time step output
        last_out = rnn_out[:, -1, :] 
        
        h = self.body(last_out)
        return [head(h) for head in self.heads], hidden''', content)

content = re.sub(
r'''        optimizer\.zero_grad\(\)\n        logits_list = model\(x\)\n''',
'''        optimizer.zero_grad()
        logits_list, _ = model(x)
''', content)

content = re.sub(
r'''                logits_list = model\(x\)\n''',
'''                logits_list, _ = model(x)
''', content)

content = re.sub(
r'''    with torch\.no_grad\(\):\n        logits_list = model\(x_t\)  # list of \(1, 16\)''',
'''    with torch.no_grad():
        logits_list, _ = model(x_t)  # list of (1, 16)''', content)

with open('/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/learning/classifier.py', 'w') as f:
    f.write(content)

