"""Spatial cross-validation and the area of applicability of a model.

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
"""
import numpy as np

__all__ = ["block_folds", "AreaOfApplicability", "repeated_block_cv"]


def block_ids(x, y, block_size):
    x, y = np.asarray(x, float), np.asarray(y, float)
    return np.char.add(np.char.add(np.floor(x / block_size).astype(int).astype(str), "_"),
                       np.floor(y / block_size).astype(int).astype(str))


def block_folds(x, y, block_size, k=5, seed=0):
    """fold number (0..k-1) of every point; whole blocks are assigned to folds at random (seed)"""
    b = block_ids(x, y, block_size)
    u = np.unique(b)
    order = np.random.default_rng(seed).permutation(u)
    fold_of = {blk: i % k for i, blk in enumerate(order)}
    return np.array([fold_of[v] for v in b])


def repeated_block_cv(fit_predict, X, y, x, yc, block_sizes=(1000, 2000, 5000), seeds=(0, 1, 2), k=5, score=None):
    """run fit_predict(X_train, y_train, X_test) over block sizes and seeds; returns a list of
    {"block_size", "seed", "score"} with score(y_true, y_pred) (default: mean absolute error)"""
    score = score or (lambda a, b: float(np.mean(np.abs(np.asarray(a) - np.asarray(b)))))
    X, y = np.asarray(X), np.asarray(y)
    out = []
    for bs in block_sizes:
        for s in seeds:
            f = block_folds(x, yc, bs, k, s)
            pred = np.empty(len(y), dtype=float)
            for i in range(k):
                tr, te = f != i, f == i
                pred[te] = fit_predict(X[tr], y[tr], X[te])
            out.append({"block_size": bs, "seed": s, "score": score(y, pred)})
    return out


class AreaOfApplicability:
    def __init__(self, weights=None):
        self.weights = None if weights is None else np.asarray(weights, float)

    def _z(self, X):
        Z = (np.where(np.isnan(X), self.median, X) - self.median) / self.sd
        return Z * self.w

    def fit(self, X, folds=None, sample=3000, seed=0):
        from scipy.spatial import cKDTree
        from scipy.spatial.distance import pdist
        X = np.asarray(X, float)
        self.median = np.nanmedian(X, axis=0)
        sd = np.nanstd(X, axis=0); self.sd = np.where(sd > 0, sd, 1.0)
        w = self.weights if self.weights is not None else np.ones(X.shape[1])
        self.w = w / w.sum()
        self.Z = self._z(X)
        rng = np.random.default_rng(seed)
        sub = self.Z[rng.choice(len(self.Z), size=min(sample, len(self.Z)), replace=False)]
        self.mean_d = float(pdist(sub).mean())
        self.tree = cKDTree(self.Z)
        if folds is None:                                          # leave-one-out nearest neighbour
            d, _ = self.tree.query(self.Z, k=2); di = d[:, 1] / self.mean_d
        else:
            folds = np.asarray(folds); di = np.empty(len(X))
            for f in np.unique(folds):
                tr = folds != f
                di[folds == f] = cKDTree(self.Z[tr]).query(self.Z[folds == f], k=1)[0] / self.mean_d
        q1, q3 = np.percentile(di, [25, 75])
        self.threshold = float(q3 + 1.5 * (q3 - q1))
        return self

    def predict(self, X):
        di = self.tree.query(self._z(np.asarray(X, float)), k=1)[0] / self.mean_d
        return di, di > self.threshold
