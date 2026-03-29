with open("classifier.py", "w") as f:
    f.write("""import os
import pickle
import pandas as pd
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
import torch.optim as optim
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from lag_utils import add_lagged_delay

NUM_CLASSES  = 16
COMP_STEP    = 5
COMP_OFFSET  = 1
FEATURES_PER_USER = 7
GLOBAL_FEATURES   = 2
LABEL_SMOOTH_STD = 1.5

def class_to_components(cls: int) -> int:
    return (cls + COMP_OFFSET) * COMP_STEP

def components_to_class(comp: int) -> int:
    return int(comp / COMP_STEP) - COMP_OFFSET

def make_soft_labels(targets: torch.Tensor, num_classes: int, std: float) -> torch.Tensor:
    classes = torch.arange(num_classes, dtype=torch.float32, device=targets.device)
    t = targets.float().unsqueeze(1)
    gauss = torch.exp(-0.5 * ((classes - t) / std) ** 2)
    return gauss / gauss.sum(dim=1, keepdim=True)

def prepare_training_targets(df: pd.DataFrame, num_users: int):
    df_n = df[df["num_users"] == num_users].copy()
    df_n = add_lagged_delay(df_n, num_users)

    comp_cols = [f"user{i}_components" for i in range(num_users)]
    err_cols  = [f"user{i}_effectiveError" for i in range(num_users)]
    
    normalized_err_cols = []
    for i in range(num_users):
        norm_col = f"user{i}_normError"
        df_n[norm_col] = df_n[err_cols[i]] / df_n[f"user{i}_frame_rate"].clip(lower=1)
        normalized_err_cols.append(norm_col)
        
    df_n["total_error"] = df_n[normalized_err_cols].sum(axis=1)
    df_n["total_components"] = df_n[comp_cols].sum(axis=1)
    
    fairness_weight = 50.0
    df_n["variance_penalty"] = df_n[comp_cols].var(axis=1).fillna(0) * fairness_weight

    avg_comps_per_user = df_n["total_components"] / num_users
    
    error_min = df_n["total_error"].min()
    error_max = df_n["total_error"].max()
    df_n["total_error_scaled"] = (df_n["total_error"] - error_min) / (error_max - error_min + 1e-8)

    comp_min = avg_comps_per_user.min()
    comp_max = avg_comps_per_user.max()
    avg_comps_scaled = (avg_comps_per_user - comp_min) / (comp_max - comp_min + 1e-8)
    
    var_min = df_n["variance_penalty"].min()
    var_max = df_n["variance_penalty"].max()
    df_n["variance_penalty_scaled"] = (df_n["variance_penalty"] - var_min) / (var_max - var_min + 1e-8)
    
    avg_delay_ms = df_n[[f"prev_user{i}_delay_ms" for i in range(num_users)]].mean(axis=1)
    dynamic_strain_weight = 0.05 + (0.45 * df_n["dl_utilization"].clip(lower=0, upper=1)) + (0.5 * (avg_delay_ms / 50.0).clip(upper=1.0))
    
    df_n["total_cost"] = df_n["total_error_scaled"] + (0.15 * df_n["variance_penalty_scaled"]) + (dynamic_strain_weight * avg_comps_scaled)

    optimal_idx = df_n.groupby("frameNumber")["total_cost"].idxmin()
    opt         = df_n.loc[optimal_idx].reset_index(drop=True)
    
    Y_active = (opt[comp_cols] / COMP_STEP - COMP_OFFSET).astype(int)
    
    X_rows = []
    Y_rows = []
    
    for i in range(num_users):
        user_df = pd.DataFrame()
        user_df["error_at_80"] = opt[f"user{i}_error_at_80"]
        user_df["error_ratio"] = opt[f"user{i}_error_ratio"]
        user_df["cqi"] = opt[f"user{i}_cqi"]
        user_df["frame_rate"] = opt[f"user{i}_frame_rate"]
        user_df["prev_delay_ms"] = opt[f"prev_user{i}_delay_ms"]
        user_df["buffer_bytes"] = opt[f"user{i}_buffer_bytes"]
        user_df["mcs_index"] = opt[f"user{i}_mcs_index"]
        
        user_df["dl_utilization"] = opt["dl_utilization"]
        user_df["n_active_ues"] = opt["n_active_ues"]
        
        target = Y_active[f"user{i}_components"]
        
        X_rows.append(user_df)
        Y_rows.append(target)
        
    X_final = pd.concat(X_rows, ignore_index=True)
    Y_final = pd.concat(Y_rows, ignore_index=True)

    avg_target_components = opt[comp_cols].mean().mean()

    print(f"  [{num_users} users] {len(X_final)} single-user states  (from {len(opt)} total frames)")
    print(f"  [{num_users} users] Avg target component count: {avg_target_components:.1f}")
    return X_final, Y_final

class CompressionDataset(Dataset):
    def __init__(self, X: pd.DataFrame, Y: pd.Series, augment_std: float = 0.0):
        self.X = torch.tensor(X.values.astype(np.float32), dtype=torch.float32)
        self.Y = torch.tensor(Y.values.astype(np.int64), dtype=torch.long)
        self.augment_std = augment_std

    def __len__(self):
        return len(self.X)

    def __getitem__(self, idx):
        x = self.X[idx]
        if self.augment_std > 0.0:
            x = x + torch.randn_like(x) * self.augment_std
        return x, self.Y[idx]

class SingleUserCompressionNet(nn.Module):
    def __init__(self, user_feature_dim: int = FEATURES_PER_USER, num_classes: int = NUM_CLASSES, hidden_dim: int = 64):
        super().__init__()
        input_dim = user_feature_dim + GLOBAL_FEATURES
        self.network = nn.Sequential(
            nn.Linear(input_dim, hidden_dim * 2),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim * 2, hidden_dim),
            nn.ReLU(),
            nn.Dropout(0.2),
            nn.Linear(hidden_dim, num_classes)
        )

    def forward(self, x: torch.Tensor):
        return self.network(x)

def train_model(X_train, Y_train, epochs=300, batch_size=128, lr=1e-3, device='cpu'):
    ds = CompressionDataset(X_train, Y_train, augment_std=0.2)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=True)
    model = SingleUserCompressionNet().to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)
    
    print(f"  Training Single-Agent model ({len(ds):,} samples, {epochs} epochs)...")
    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0
        for bX, bY in loader:
            bX, bY = bX.to(device), bY.to(device)
            optimizer.zero_grad()
            outputs = model(bX)
            log_probs = F.log_softmax(outputs, dim=1)
            soft_target = make_soft_labels(bY, NUM_CLASSES, LABEL_SMOOTH_STD)
            loss = F.kl_div(log_probs, soft_target, reduction='batchmean')
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        scheduler.step()
        if epoch % 50 == 0 or epoch == 1:
            print(f"  Epoch {epoch:4d}/{epochs} | loss={total_loss/len(loader):.4f}")
    return model

def evaluate_model(model, X_test, Y_test, batch_size=128, device='cpu'):
    ds = CompressionDataset(X_test, Y_test)
    loader = DataLoader(ds, batch_size=batch_size, shuffle=False)
    model.eval()
    total = 0; exact = 0; within1 = 0; within3 = 0
    with torch.no_grad():
        for bX, bY in loader:
            bX, bY = bX.to(device), bY.to(device)
            outputs = model(bX)
            pred = torch.argmax(outputs, dim=1)
            diff = (pred - bY).abs()
            total += len(diff)
            exact += (diff == 0).sum().item()
            within1 += (diff <= 1).sum().item()
            within3 += (diff <= 3).sum().item()
    print(f"\\n  Overall exact accuracy: {exact / max(1, total) * 100:.1f}%")
    return exact / max(1, total) * 100

def save_model(model, scaler, save_dir: str):
    os.makedirs(save_dir, exist_ok=True)
    stem = os.path.join(save_dir, 'compression_single')
    torch.save(model.state_dict(), stem + '.pth')
    with open(stem + '_scaler.pkl', 'wb') as f:
        pickle.dump(scaler, f)
    print(f"  Saved to {stem}.pth")

def train_all(csv_path, epochs=300, batch_size=128, lr=1e-3, test_size=0.2, save_dir='./models', device='cpu'):
    df = pd.read_csv(csv_path)
    num_users_list = sorted(df['num_users'].unique().tolist())
    all_X = []; all_Y = []
    for n in num_users_list:
        X, Y = prepare_training_targets(df, n)
        all_X.append(X)
        all_Y.append(Y)
    X_full = pd.concat(all_X, ignore_index=True)
    Y_full = pd.concat(all_Y, ignore_index=True)
    
    X_tr, X_te, Y_tr, Y_te = train_test_split(X_full, Y_full, test_size=test_size, random_state=42)
    scaler = StandardScaler()
    X_tr_sc = pd.DataFrame(scaler.fit_transform(X_tr), columns=X_tr.columns, index=X_tr.index)
    X_te_sc = pd.DataFrame(scaler.transform(X_te), columns=X_te.columns, index=X_te.index)
    
    model = train_model(X_tr_sc, Y_tr, epochs=epochs, batch_size=batch_size, lr=lr, device=device)
    evaluate_model(model, X_te_sc, Y_te, device=device)
    save_model(model, scaler, save_dir)

if __name__ == '__main__':
    train_all('../datasets/pca/dataset.csv', epochs=300, batch_size=128, lr=1e-3, save_dir='./models', device='cuda' if torch.cuda.is_available() else 'cpu')
""")
