# Spatial cross-validation and area of applicability (`research_helpers.spatial_cv`)

Spatial cross-validation and the area of applicability of a model.

    from research_helpers.spatial_cv import block_folds, AreaOfApplicability
    folds = block_folds(x, y, block_size=2000, k=5, seed=0)        # projected coordinates in metres
    for f in range(5):
        train, test = folds != f, folds == f
        ...
    aoa = AreaOfApplicability(weights=importances).fit(X_train)    # numeric predictors
    di, outside = aoa.predict(X_new)                                # dissimilarity index, True outside the AOA

Why: neighbouring observations are similar (spatial autocorrelation). With random folds, test points have close
neighbours in the training data and the error estimate is optimistic for areas without data (Roberts et al. 2017,
Ecography 40, 913-929; Ploton et al. 2020, Nature Communications 11, 4540). Block folds hold out whole squares of
`block_size` (same units as the coordinates). Run several seeds and block sizes to see how the estimate depends on
them; spatial cross-validation is not a design-based estimate of map accuracy (Wadoux et al. 2021, Ecological
Modelling 457, 109692).

Area of applicability (Meyer and Pebesma 2021, Methods in Ecology and Evolution 12, 1620-1633): the dissimilarity
index of a point is its distance to the nearest training point in the space of standardised predictors weighted by
importance, divided by the mean distance between training points. The threshold is the upper whisker
(Q3 + 1.5 IQR) of the training points' index computed against the other folds; points above it lie outside the area
where the model has seen similar conditions.

## Functions and classes


**`AreaOfApplicability(weights=None)`**




**`block_folds(x, y, block_size, k=5, seed=0)`**

fold number (0..k-1) of every point; whole blocks are assigned to folds at random (seed)


**`block_ids(x, y, block_size)`**




**`repeated_block_cv(fit_predict, X, y, x, yc, block_sizes=(1000, 2000, 5000), seeds=(0, 1, 2), k=5, score=None)`**

run fit_predict(X_train, y_train, X_test) over block sizes and seeds; returns a list of
{"block_size", "seed", "score"} with score(y_true, y_pred) (default: mean absolute error)
