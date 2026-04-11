"""
Principal Component Analysis (PCA) skill for agent use.

CLI usage:
    python pca.py --fit --X_path=data.csv --n_components=5
    python pca.py --transform --X_path=data.csv
    python pca.py --fit_transform --X_path=data.csv --n_components=5
    python pca.py --config --n_components=10 --whiten=True
    python pca.py --performance
"""

import argparse
import os
import pickle
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

MODEL_PATH = "pca_model.pkl"
SCALER_PATH = "pca_scaler.pkl"
STATS_PATH = "pca_stats.pkl"
OUTPUT_DIR = "outputs"


class PCASkill:
    def __init__(self):
        self.model = None
        self.scaler = StandardScaler()
        self.model_params = {"n_components": None, "whiten": False, "random_state": 42}
        self.stats = {}

    def config(self, n_components=None, whiten: bool = False, random_state: int = 42):
        """Configure PCA parameters."""
        self.model_params = {
            "n_components": n_components,
            "whiten": whiten,
            "random_state": random_state,
        }
        self.model = PCA(**self.model_params)
        print(f"[Config] PCA configured with n_components={n_components}, "
              f"whiten={whiten}, random_state={random_state}")

    def fit(self, X_path: str, n_components=None, whiten: bool = False, random_state: int = 42):
        """Fit PCA on the dataset."""
        df = pd.read_csv(X_path)
        X = df.values.astype(float)

        X_scaled = self.scaler.fit_transform(X)

        self.config(n_components=n_components, whiten=whiten, random_state=random_state)
        self.model.fit(X_scaled)

        self.stats = {
            "n_samples": X.shape[0],
            "n_features": X.shape[1],
            "n_components": self.model.n_components_,
            "explained_variance_ratio": self.model.explained_variance_ratio_.tolist(),
            "cumulative_variance": np.cumsum(self.model.explained_variance_ratio_).tolist(),
            "singular_values": self.model.singular_values_.tolist(),
        }

        with open(MODEL_PATH, "wb") as f:
            pickle.dump(self.model, f)
        with open(SCALER_PATH, "wb") as f:
            pickle.dump(self.scaler, f)
        with open(STATS_PATH, "wb") as f:
            pickle.dump(self.stats, f)

        total_var = sum(self.model.explained_variance_ratio_)
        print(f"[Fit] Done. Samples={X.shape[0]}, Features={X.shape[1]}, "
              f"Components={self.model.n_components_}, TotalVarianceExplained={total_var:.4f}")

    def transform(self, X_path: str, output_path: str = "pca_transformed.csv"):
        """Transform data using the fitted PCA model."""
        if not os.path.exists(MODEL_PATH) or not os.path.exists(SCALER_PATH):
            print("[Transform] No fitted model found. Run --fit first.")
            return

        with open(MODEL_PATH, "rb") as f:
            self.model = pickle.load(f)
        with open(SCALER_PATH, "rb") as f:
            self.scaler = pickle.load(f)

        df = pd.read_csv(X_path)
        X = df.values.astype(float)
        X_scaled = self.scaler.transform(X)
        X_transformed = self.model.transform(X_scaled)

        cols = [f"PC{i+1}" for i in range(X_transformed.shape[1])]
        out_df = pd.DataFrame(X_transformed, columns=cols)
        out_df.to_csv(output_path, index=False)
        print(f"[Transform] Transformed shape={X_transformed.shape}, saved to {output_path}")
        return X_transformed

    def fit_transform(self, X_path: str, n_components=None, whiten: bool = False,
                      random_state: int = 42, output_path: str = "pca_transformed.csv"):
        """Fit and transform in one step."""
        self.fit(X_path, n_components=n_components, whiten=whiten, random_state=random_state)
        return self.transform(X_path, output_path=output_path)

    def performance(self):
        """Display explained variance stats and save scree plot."""
        if not os.path.exists(STATS_PATH):
            print("[Performance] No stats found. Run --fit first.")
            return

        with open(STATS_PATH, "rb") as f:
            self.stats = pickle.load(f)

        os.makedirs(OUTPUT_DIR, exist_ok=True)

        evr = self.stats["explained_variance_ratio"]
        cumvar = self.stats["cumulative_variance"]

        print("\n===== PCA Performance =====")
        print(f"  Samples              : {self.stats['n_samples']}")
        print(f"  Original features    : {self.stats['n_features']}")
        print(f"  Components kept      : {self.stats['n_components']}")
        print(f"  Total variance expl. : {cumvar[-1]:.4f}")
        print(f"\n  Per-component explained variance ratio:")
        for i, (ev, cv) in enumerate(zip(evr, cumvar)):
            print(f"    PC{i+1:>3}: {ev:.4f}  (cumulative: {cv:.4f})")
        print("===========================\n")

        # Scree plot
        components = list(range(1, len(evr) + 1))
        fig, ax1 = plt.subplots()
        ax1.bar(components, evr, alpha=0.6, label="Individual")
        ax1.set_xlabel("Principal Component")
        ax1.set_ylabel("Explained Variance Ratio")
        ax2 = ax1.twinx()
        ax2.plot(components, cumvar, color="red", marker="o", label="Cumulative")
        ax2.set_ylabel("Cumulative Explained Variance")
        ax1.set_title("PCA — Scree Plot")
        fig.legend(loc="center right", bbox_to_anchor=(0.85, 0.5))
        scree_path = os.path.join(OUTPUT_DIR, "pca_scree.png")
        plt.savefig(scree_path, bbox_inches="tight")
        plt.close()
        print(f"[Performance] Scree plot saved to {scree_path}")


def parse_args():
    parser = argparse.ArgumentParser(description="PCA Skill")
    parser.add_argument("--fit", action="store_true")
    parser.add_argument("--transform", action="store_true")
    parser.add_argument("--fit_transform", action="store_true")
    parser.add_argument("--config", action="store_true")
    parser.add_argument("--performance", action="store_true")

    parser.add_argument("--X_path", type=str)
    parser.add_argument("--n_components", type=int, default=None)
    parser.add_argument("--whiten", type=lambda x: x.lower() == "true", default=False)
    parser.add_argument("--random_state", type=int, default=42)
    parser.add_argument("--output_path", type=str, default="pca_transformed.csv")
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    skill = PCASkill()

    if args.config:
        skill.config(
            n_components=args.n_components,
            whiten=args.whiten,
            random_state=args.random_state,
        )
    elif args.fit:
        skill.fit(
            X_path=args.X_path,
            n_components=args.n_components,
            whiten=args.whiten,
            random_state=args.random_state,
        )
    elif args.transform:
        skill.transform(X_path=args.X_path, output_path=args.output_path)
    elif args.fit_transform:
        skill.fit_transform(
            X_path=args.X_path,
            n_components=args.n_components,
            whiten=args.whiten,
            random_state=args.random_state,
            output_path=args.output_path,
        )
    elif args.performance:
        skill.performance()
    else:
        print("Specify one of: --fit, --transform, --fit_transform, --config, --performance")
