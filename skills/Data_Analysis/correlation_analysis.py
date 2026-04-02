import argparse
import json
import numpy as np
from datetime import datetime
from scipy import stats
from sklearn.metrics import mutual_info_score
from sklearn.preprocessing import KBinsDiscretizer

from skills.Data_Analysis.struct import DescriptiveStat
from struct import EffectSizeTTest, EffectSizeChiTest, StabilityTest

#Default
DEFAULT_THRESHOLDS = {
    "pearson": {"bad": 0.1, "moderate": 0.3, "good": 0.5},
    "cohen_d": {"bad": 0.2, "moderate": 0.5, "good": 0.8},
    "cramer_v": {"bad": 0.1, "moderate": 0.3, "good": 0.5},
}

DEFAULT_WEIGHTS = {"w1": 0.4, "w2": 0.3, "w3": 0.3}


#Utilities
def parse_timestamp(ts: str) -> datetime:
    #Snowflake time format parsing
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt)
        except ValueError:
            continue
    raise ValueError(f"Cannot parse timestamp: {ts}")


def align_series(data1: dict, data2: dict):
    common_keys = sorted(
        set(data1.keys()) & set(data2.keys()),
        key=parse_timestamp
    )
    x = np.array([float(data1[k]) for k in common_keys])
    y = np.array([float(data2[k]) for k in common_keys])
    return x, y, common_keys


def label_effect(value: float, thresholds: dict) -> str:
    # Labeling Based on Threshold
    if value >= thresholds["good"]:
        return "good"
    elif value >= thresholds["moderate"]:
        return "moderate"
    return "bad"


def discretize(arr: np.ndarray, n_bins: int = 10) -> np.ndarray:
    #Discritize Continuous Value using number of bin, range will be divided equally into number of bin
    kbd = KBinsDiscretizer(n_bins=n_bins, encode="ordinal", strategy="quantile")
    return kbd.fit_transform(arr.reshape(-1, 1)).ravel().astype(int)



def descriptive_stats(arr: np.ndarray) -> dict:
    # hypothesis testingL t-test, chi-test
    test_result = DescriptiveStat()
    test_result.mean = float(np.mean(arr))
    test_result.std = float(np.std(arr))
    test_result.variance = float(np.var(arr))
    return test_result.to_dict()


def hypothesis_test(x: np.ndarray, y: np.ndarray, type1: str, type2: str) -> dict:
    #continuous >< continuous: t-test
    #continuous >< categorical: chi-test
    if type1 == "continuous" and type2 == "continuous":
        #t-test
        stat, p = stats.ttest_ind(x, y)
        return {"test": "t-test", "statistic": float(stat), "p_value": float(p)}
    else:
        #chi - test
        x_disc = discretize(x) if type1 == "continuous" else x.astype(int)
        y_disc = discretize(y) if type2 == "continuous" else y.astype(int)
        contingency = np.zeros((int(x_disc.max()) + 1, int(y_disc.max()) + 1), dtype=int)
        for xi, yi in zip(x_disc, y_disc):
            contingency[xi, yi] += 1
        stat, p, _, _ = stats.chi2_contingency(contingency)
        return {"test": "chi-squared", "statistic": float(stat), "p_value": float(p)}


def effect_size(x: np.ndarray, y: np.ndarray, hyp_test: dict, thresholds: dict) -> dict:
    # t_test -> pearson corr and cohen_d,
    # chi_test -> cramer's V
    if hyp_test["test"] == "t-test":
        test_result = EffectSizeTTest()
        # Pearson correlation
        corr, _ = stats.pearsonr(x, y)
        test_result.pearson_correlation = float(corr)
        test_result.pearson_label = label_effect(abs(corr), thresholds["pearson"])
        # Cohen's d
        pooled_std = np.sqrt((np.std(x) ** 2 + np.std(y) ** 2) / 2)
        test_result.cohen_d = float(abs(np.mean(x) - np.mean(y)) / pooled_std) if pooled_std > 0 else 0.0
        test_result.cohen_d_label = label_effect(test_result.cohen_d, thresholds["cohen_d"])
        return test_result.to_dict()

    # Cramer's V
    test_result = EffectSizeChiTest()
    x_disc = discretize(x)
    y_disc = discretize(y)
    contingency = np.zeros(
        (int(x_disc.max()) + 1, int(y_disc.max()) + 1), dtype=int
    )
    for xi, yi in zip(x_disc, y_disc):
        contingency[xi, yi] += 1
    chi2 = stats.chi2_contingency(contingency)[0]
    n = len(x)
    min_dim = min(contingency.shape) - 1
    test_result.cramer_v = float(np.sqrt(chi2 / (n * min_dim))) if (n * min_dim) > 0 else 0.0
    test_result.cramer_v_label = label_effect(test_result.cramer_v, thresholds["cramer_v"])
    return test_result.to_dict()


def mutual_info(x: np.ndarray, y: np.ndarray) -> float:
    x_disc = discretize(x)
    y_disc = discretize(y)
    return float(mutual_info_score(x_disc, y_disc))

class StabilityAnalysis:
    __slots__ = ("_test_result", "_weight")
    def __init__(self):
        self._test_result = StabilityTest()
        self._weight = {"time_splitting_w": 0.4, "time_rolling_w": 0.3, "sampling_w": 0.3}

    def set_weight_config(self, time_splitting_w: float = 0.4, time_rolling_w: float = 0.3, sampling_w: float = 0.3):
        self._weight["time_splitting_w"] = time_splitting_w
        self._weight["time_rolling_w"] = time_rolling_w
        self._weight["sampling_w"] = sampling_w

    def _pearson_safe(self, a, b):
        if np.std(a) == 0 or np.std(b) == 0:
            return 0.0
        return float(stats.pearsonr(a, b)[0])

    def _time_based_stability(self, x: np.ndarray, y: np.ndarray, n_splits: int = 5) -> float:
        # Split time window stability test
        size = len(x) // n_splits
        if size < 2:
            return 0.0
        scores = []
        for i in range(n_splits):
            xi = x[i * size: (i + 1) * size]
            yi = y[i * size: (i + 1) * size]
            scores.append(abs(self._pearson_safe(xi, yi)))
        return float(np.mean(scores))


    def _rolling_stability(self, x: np.ndarray, y: np.ndarray, window: int = 50) -> float:
        #Time sliding window stability test
        correlations = []
        for i in range(len(x) - window + 1):
            correlations.append(self._pearson_safe(x[i:i + window], y[i:i + window]))
        if not correlations:
            return 0.0
        signs = np.sign(correlations)
        # Sign fraction
        dominant = 1 if np.sum(signs > 0) >= np.sum(signs < 0) else -1
        return float(np.mean(signs == dominant))


    def _sampling_stability(self, x: np.ndarray, y: np.ndarray, n_samples: int = 20) -> float:
        #Sampling with replacement stability test, min_sample = 20
        if n_samples < 20:
            print("Your sample size is smaller than recommended: 20")

        rng = np.random.default_rng(42)
        correlations = []
        for _ in range(n_samples):
            idx = rng.integers(0, len(x), size=len(x))
            correlations.append(self._pearson_safe(x[idx], y[idx]))
        cv = float(np.std(correlations) / (abs(np.mean(correlations)) + 1e-9))
        return float(max(0.0, 1.0 - cv))


    def stability_tests(self, x: np.ndarray, y: np.ndarray, n_samples: int = 20) -> dict:
        self._test_result.splitting_window_score = self._time_based_stability(x, y)
        self._test_result.rolling_window_score = self._rolling_stability(x, y)
        self._test_result.sampling_score = self._sampling_stability(x, y, n_samples=n_samples)
        self._test_result.final_score = (self._weight["time_splitting_w"] * self._test_result.splitting_window_score
                                         + self._weight["time_rolling_w"] * self._test_result.rolling_window_score
                                         + self._weight["sampling_w"] * self._test_result.sampling_score)
        self._test_result.number_of_iterations = n_samples
        return self._test_result.to_dict()



def analyze(data1: dict, data2: dict, weights: dict, thresholds: dict) -> dict:
    name1, type1 = data1["data_name"], data1["type"]
    name2, type2 = data2["data_name"], data2["type"]

    x, y, _ = align_series(data1["data"], data2["data"])
    n = len(x)

    desc1 = descriptive_stats(x)
    desc2 = descriptive_stats(y)
    hyp = hypothesis_test(x, y, type1, type2)
    fx = effect_size(x, y, hyp, thresholds)
    mi = mutual_info(x, y)

    result = {
        "test_name": f"Correlation between {name1} and {name2}",
        name1: {"type": type1, **desc1},
        name2: {"type": type2, **desc2},
        "tests": {
            "p_value": hyp["p_value"],
            "hypothesis_test": hyp["test"],
            "correlation": fx,
            "mutual_info": mi,
            "side_effect": {k: v for k, v in fx.items() if "label" in k},
        },
    }

    if n > 1000:
        result["tests"]["stability"] = StabilityAnalysis().stability_tests(x, y)
    else:
        result["tests"]["stability"] = None

    return result


# ─── CLI ──────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(description="Correlation Analysis Skill")

    parser.add_argument("--data1", type=str, help="JSON string for dataset 1")
    parser.add_argument("--data2", type=str, help="JSON string for dataset 2")

    # Weights config
    parser.add_argument("--configure_weights", action="store_true")
    parser.add_argument("--w1", type=float, default=DEFAULT_WEIGHTS["w1"])
    parser.add_argument("--w2", type=float, default=DEFAULT_WEIGHTS["w2"])
    parser.add_argument("--w3", type=float, default=DEFAULT_WEIGHTS["w3"])

    # Threshold config
    parser.add_argument("--configure_thresholds", action="store_true")
    parser.add_argument("--test", type=str, choices=["pearson", "cohen_d", "cramer_v"])
    parser.add_argument("--bad", type=float)
    parser.add_argument("--moderate", type=float)
    parser.add_argument("--good", type=float)

    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()

    weights = {"w1": args.w1, "w2": args.w2, "w3": args.w3}
    thresholds = DEFAULT_THRESHOLDS.copy()

    if args.configure_weights:
        total = args.w1 + args.w2 + args.w3
        if abs(total - 1.0) > 1e-6:
            print(f"[Warning] Weights sum to {total:.4f}, not 1.0. Normalizing.")
            weights = {k: v / total for k, v in weights.items()}
        print(f"[Config] Stability weights set: {weights}")

    elif args.configure_thresholds:
        if not args.test:
            print("[Error] --test is required with --configure_thresholds")
        else:
            thresholds[args.test] = {
                "bad": args.bad,
                "moderate": args.moderate,
                "good": args.good,
            }
            print(f"[Config] Thresholds for '{args.test}' updated: {thresholds[args.test]}")

    elif args.data1 and args.data2:
        d1 = json.loads(args.data1)
        d2 = json.loads(args.data2)
        result = analyze(d1, d2, weights, thresholds)
        print(json.dumps(result, indent=2))

    else:
        print("Provide --data1 and --data2, or use --configure_weights / --configure_thresholds")
