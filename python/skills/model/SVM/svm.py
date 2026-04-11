"""
Support Vector Machine (SVR) skill for agent use.

CLI usage:
    python svm.py --train --X_path=data.csv --y_col=target --C=1.0 --kernel=rbf
    python svm.py --predict --X_path=data.csv
    python svm.py --config --C=0.5 --epsilon=0.1 --kernel=linear
    python svm.py --performance
"""

import argparse
import os
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.svm import SVR
from sklearn.metrics import (
    mean_squared_error, r2_score,
    precision_recall_curve, roc_auc_score, roc_curve
)
from sklearn.model_selection import train_test_split

MODEL_PATH = "svm_model.pkl"
STATS_PATH = "svm_stats.pkl"
OUTPUT_DIR = "outputs"


class SVMRegressionSkill:
    def __init__(self):
        self.model = None
        self.model_params = {"C": 1.0, "epsilon": 0.1, "kernel": "rbf"}
        self.stats = {}

    def config(self, C: float = 1.0, epsilon: float = 0.1, kernel: str = "rbf"):
        """Configure the SVR model parameters."""
        self.model_params = {"C": C, "epsilon": epsilon, "kernel": kernel}
        self.model = SVR(**self.model_params)
        print(f"[Config] SVR configured with C={C}, epsilon={epsilon}, kernel={kernel}")

    def train(self, X_path: str, y_col: str, test_size: float = 0.2, random_state: int = 42):
        """Train the SVR model."""
        df = pd.read_csv(X_path)
        X = df.drop(columns=[y_col]).values
        y = df[y_col].values

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )

        if self.model is None:
            self.config(**self.model_params)

        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_test)

        self.stats = {
            "train_size": len(X_train),
            "test_size": len(X_test),
            "total_size": len(X),
            "n_features": X.shape[1],
            "mse": mean_squared_error(y_test, y_pred),
            "rmse": np.sqrt(mean_squared_error(y_test, y_pred)),
            "r2": r2_score(y_test, y_pred),
            "y_test": y_test,
            "y_pred": y_pred,
        }

        with open(MODEL_PATH, "wb") as f:
            pickle.dump(self.model, f)
        with open(STATS_PATH, "wb") as f:
            pickle.dump(self.stats, f)

        print(f"[Train] Done. Train={len(X_train)}, Test={len(X_test)}, "
              f"MSE={self.stats['mse']:.4f}, R2={self.stats['r2']:.4f}")

    def predict(self, X_path: str):
        """Predict using the trained model."""
        if not os.path.exists(MODEL_PATH):
            print("[Predict] No trained model found. Run --train first.")
            return

        with open(MODEL_PATH, "rb") as f:
            self.model = pickle.load(f)

        df = pd.read_csv(X_path)
        X = df.values
        preds = self.model.predict(X)
        print(f"[Predict] Predictions:\n{preds}")
        return preds

    def performance(self):
        """Display and save training statistics, precision-recall, and ROC-AUC curves."""
        if not os.path.exists(STATS_PATH):
            print("[Performance] No stats found. Run --train first.")
            return

        with open(STATS_PATH, "rb") as f:
            self.stats = pickle.load(f)

        os.makedirs(OUTPUT_DIR, exist_ok=True)

        print("\n===== SVR Performance =====")
        print(f"  Total dataset size : {self.stats['total_size']}")
        print(f"  Training set size  : {self.stats['train_size']}")
        print(f"  Test set size      : {self.stats['test_size']}")
        print(f"  Number of features : {self.stats['n_features']}")
        print(f"  MSE                : {self.stats['mse']:.4f}")
        print(f"  RMSE               : {self.stats['rmse']:.4f}")
        print(f"  R2 Score           : {self.stats['r2']:.4f}")
        print("===========================\n")

        y_test = self.stats["y_test"]
        y_pred = self.stats["y_pred"]

        # Binarize for PR and ROC curves (threshold at median)
        threshold = np.median(y_test)
        y_test_bin = (y_test >= threshold).astype(int)
        y_score = (y_pred - y_pred.min()) / (y_pred.max() - y_pred.min() + 1e-9)

        # Precision-Recall Curve
        precision, recall, _ = precision_recall_curve(y_test_bin, y_score)
        plt.figure()
        plt.plot(recall, precision, marker=".")
        plt.xlabel("Recall")
        plt.ylabel("Precision")
        plt.title("SVR — Precision-Recall Curve")
        pr_path = os.path.join(OUTPUT_DIR, "svm_precision_recall.png")
        plt.savefig(pr_path)
        plt.close()
        print(f"[Performance] Precision-Recall curve saved to {pr_path}")

        # ROC-AUC Curve
        fpr, tpr, _ = roc_curve(y_test_bin, y_score)
        auc = roc_auc_score(y_test_bin, y_score)
        plt.figure()
        plt.plot(fpr, tpr, label=f"AUC = {auc:.4f}")
        plt.plot([0, 1], [0, 1], "k--")
        plt.xlabel("False Positive Rate")
        plt.ylabel("True Positive Rate")
        plt.title("SVR — ROC-AUC Curve")
        plt.legend()
        roc_path = os.path.join(OUTPUT_DIR, "svm_roc_auc.png")
        plt.savefig(roc_path)
        plt.close()
        print(f"[Performance] ROC-AUC curve saved to {roc_path} (AUC={auc:.4f})")


def parse_args():
    parser = argparse.ArgumentParser(description="SVM Regression Skill")
    parser.add_argument("--train", action="store_true")
    parser.add_argument("--predict", action="store_true")
    parser.add_argument("--config", action="store_true")
    parser.add_argument("--performance", action="store_true")

    parser.add_argument("--X_path", type=str)
    parser.add_argument("--y_col", type=str)
    parser.add_argument("--C", type=float, default=1.0)
    parser.add_argument("--epsilon", type=float, default=0.1)
    parser.add_argument("--kernel", type=str, default="rbf")
    parser.add_argument("--test_size", type=float, default=0.2)
    parser.add_argument("--random_state", type=int, default=42)
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    skill = SVMRegressionSkill()

    if args.config:
        skill.config(C=args.C, epsilon=args.epsilon, kernel=args.kernel)
    elif args.train:
        skill.config(C=args.C, epsilon=args.epsilon, kernel=args.kernel)
        skill.train(
            X_path=args.X_path,
            y_col=args.y_col,
            test_size=args.test_size,
            random_state=args.random_state,
        )
    elif args.predict:
        skill.predict(X_path=args.X_path)
    elif args.performance:
        skill.performance()
    else:
        print("Specify one of: --train, --predict, --config, --performance")
