"""Dependency-free classification metrics; rows actual, columns predicted."""

import math


def classification_metrics(actual, predicted, labels):
    if len(actual) != len(predicted) or not actual:
        raise ValueError("Nonempty matching label and prediction lists are required.")
    count = len(labels)
    matrix = [[0] * count for _ in labels]
    for a, p in zip(actual, predicted):
        if type(a) is not int or type(p) is not int or not (0 <= a < count and 0 <= p < count):
            raise ValueError("Class index outside the label list.")
        matrix[a][p] += 1
    classes = []
    for index, name in enumerate(labels):
        tp = matrix[index][index]
        support = sum(matrix[index])
        predicted_count = sum(row[index] for row in matrix)
        precision = tp / predicted_count if predicted_count else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        classes.append({"label": name, "precision": precision, "recall": recall,
                        "f1": f1, "support": support, "predicted_count": predicted_count})
    n = len(actual)
    accuracy = sum(matrix[i][i] for i in range(count)) / n
    z = 1.959963984540054
    denom = 1 + z * z / n
    center = (accuracy + z * z / (2 * n)) / denom
    half = z * math.sqrt(accuracy * (1 - accuracy) / n + z * z / (4 * n * n)) / denom
    return {"labels": list(labels), "samples": n, "confusion_matrix": matrix,
            "accuracy": accuracy, "accuracy_wilson_95ci": [max(0, center - half), min(1, center + half)],
            "macro_precision": sum(row['precision'] for row in classes) / count,
            "macro_recall": sum(row['recall'] for row in classes) / count,
            "macro_f1": sum(row['f1'] for row in classes) / count,
            "per_class": classes, "undefined_division": "zero", "matrix_axes": "rows=actual, columns=predicted"}
