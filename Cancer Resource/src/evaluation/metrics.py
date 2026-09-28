"""
Evaluation metrics for DRUGSYNC-NPxP.
Binary: ROC-AUC, balanced accuracy, precision, recall, F1.
Regression: Pearson R, R^2, RMSE.
"""
from __future__ import annotations
import math
import numpy as np


def roc_auc(y_true, y_score):
    """Area under the ROC curve using the trapezoid method."""
    yt = np.array(y_true, dtype=float)
    ys = np.array(y_score, dtype=float)
    # Sort descending by score (high score = positive prediction)
    order = np.argsort(-ys)
    yt, ys = yt[order], ys[order]
    pos = int(yt.sum())
    neg = len(yt) - pos
    if pos == 0 or neg == 0:
        return 0.5
    tp = 0
    fp = 0
    tpr_list = [0.0]
    fpr_list = [0.0]
    for i in range(len(yt)):
        if yt[i] == 1:
            tp += 1
        else:
            fp += 1
        if i == len(yt) - 1 or ys[i] != ys[i + 1]:
            tpr_list.append(tp / pos)
            fpr_list.append(fp / neg)
    # Ensure we end at (1,1)
    if tpr_list[-1] < 1 or fpr_list[-1] < 1:
        tpr_list.append(1.0)
        fpr_list.append(1.0)
    auc = 0.0
    for i in range(1, len(fpr_list)):
        auc += (fpr_list[i] - fpr_list[i - 1]) * (tpr_list[i] + tpr_list[i - 1]) / 2.0
    return float(auc)


def balanced_accuracy(y_true, y_pred):
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    tn = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 0)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    rp = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    rn = tn / (tn + fp) if (tn + fp) > 0 else 0.0
    return (rp + rn) / 2.0


def precision(y_true, y_pred):
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fp = sum(1 for t, p in zip(y_true, y_pred) if t == 0 and p == 1)
    return tp / (tp + fp) if (tp + fp) > 0 else 0.0


def recall(y_true, y_pred):
    tp = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 1)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t == 1 and p == 0)
    return tp / (tp + fn) if (tp + fn) > 0 else 0.0


def f1(y_true, y_pred):
    p = precision(y_true, y_pred)
    r = recall(y_true, y_pred)
    return 2 * p * r / (p + r) if (p + r) > 0 else 0.0


def pearson_correlation(y_true, y_pred):
    xs = np.array(y_true, dtype=float)
    ys = np.array(y_pred, dtype=float)
    if len(xs) < 2:
        return 0.0
    mx, my = xs.mean(), ys.mean()
    num = np.sum((xs - mx) * (ys - my))
    dx = math.sqrt(np.sum((xs - mx) ** 2))
    dy = math.sqrt(np.sum((ys - my) ** 2))
    if dx == 0 or dy == 0:
        return 0.0
    return float(num / (dx * dy))


def r_squared(y_true, y_pred):
    xs = np.array(y_true, dtype=float)
    ys = np.array(y_pred, dtype=float)
    ss_res = np.sum((xs - ys) ** 2)
    ss_tot = np.sum((xs - xs.mean()) ** 2)
    return float(1.0 - ss_res / ss_tot) if ss_tot != 0 else 0.0


def rmse(y_true, y_pred):
    return float(math.sqrt(np.mean((np.array(y_true) - np.array(y_pred)) ** 2)))


def evaluate_binary(y_true, y_prob, threshold=0.5):
    y_pred = [1 if p >= threshold else 0 for p in y_prob]
    return {"roc_auc": roc_auc(y_true, y_prob),
            "balanced_accuracy": balanced_accuracy(y_true, y_pred),
            "precision": precision(y_true, y_pred),
            "recall": recall(y_true, y_pred), "f1": f1(y_true, y_pred),
            "threshold": threshold, "n_samples": len(y_true)}


def evaluate_regression(y_true, y_pred):
    return {"pearson_r": pearson_correlation(y_true, y_pred),
            "r_squared": r_squared(y_true, y_pred),
            "rmse": rmse(y_true, y_pred), "n_samples": len(y_true)}