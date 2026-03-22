import pandas as pd
from classifier import prepare_training_targets
df = pd.read_csv("/home/teaching/Projects/NASCX/simu5g-1.3.0/simulations/NR/xr_new/datasets/pca/dataset.csv")
# suppress warnings
import warnings
warnings.filterwarnings("ignore")
X, Y = prepare_training_targets(df, 10)
print(Y.value_counts())
