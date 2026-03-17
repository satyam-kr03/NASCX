#!/usr/bin/env python3
"""Diagnostic script to analyze model vs static CL performance."""
import pandas as pd
import numpy as np

for n in range(2, 11):
    df = pd.read_csv(f'comparison_results_pca/comparison_users{n}.csv')
    model = df[df['strategy'] == 'model']
    static = df[df['strategy'] == 'static']
    
    model_err = model['mean_effective_error'].mean()
    
    # Find best static CL
    cl_means = static.groupby('comp_level')['mean_effective_error'].mean()
    best_cl = cl_means.idxmin()
    best_err = cl_means.min()
    
    # What CL does the model seem to be picking?
    matches = []
    for cl in static['comp_level'].unique():
        cl_df = static[static['comp_level'] == cl]
        cl_errs = cl_df.sort_values('user')['mean_effective_error'].values
        mod_errs = model.sort_values('user')['mean_effective_error'].values
        if len(cl_errs) == len(mod_errs) and np.allclose(cl_errs, mod_errs, rtol=0.01):
            matches.append(cl)
    
    match_str = f'matches CL={matches}' if matches else 'no exact match'
    ratio = model_err / best_err if best_err > 0 else float('inf')
    print(f'n_u={n:2d}  model_err={model_err:8.1f}  best_static={best_err:8.1f} (CL={best_cl})  ratio={ratio:.2f}  {match_str}')
