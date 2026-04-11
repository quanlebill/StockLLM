import sys
import os
import subprocess
import contextlib
from io import StringIO
from typing import Any
import requests as _requests


@contextlib.contextmanager
def _in_root():
    prev = os.getcwd()
    os.chdir(ROOT)
    try:
        yield
    finally:
        os.chdir(prev)

ROOT = os.environ["STOCKLLM_ROOT"]


def _capture_stdout(func, **kwargs) -> tuple[Any, str]:
    """Call func(**kwargs), capturing stdout. Returns (return_value, captured_stdout)."""
    buf = StringIO()
    result = None
    with contextlib.redirect_stdout(buf):
        result = func(**kwargs)
    return result, buf.getvalue()

def skill_get_mart_tables(**kwargs) -> Any:
    from skills.snowflake.mcp_snowflake import get_mart_tables
    return get_mart_tables()


def _validate_table_columns(table_name: list, column_name: dict) -> None:
    from skills.snowflake.mcp_snowflake import _connect
    conn = _connect()
    cur  = conn.cursor()
    try:
        for tbl in table_name:
            if not tbl.upper().startswith("MART"):
                raise ValueError(f"Table '{tbl}' must start with MART_.")
            cur.execute(f"""
                SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = 'DBT_STOCK'
                  AND TABLE_NAME   = '{tbl.upper()}'
                ORDER BY ORDINAL_POSITION
            """)
            actual = [r[0].upper() for r in cur.fetchall()]
            if not actual:
                raise ValueError(f"Table '{tbl}' not found in DBT_STOCK schema.")
            requested = [c.upper() for c in column_name.get(tbl, [])]
            bad = [c for c in requested if c not in actual]
            if bad:
                raise ValueError(
                    f"Unknown columns for '{tbl}': {bad}. Available: {actual}"
                )
    finally:
        cur.close()
        conn.close()


def skill_check_valid_column(**kwargs) -> Any:
    table_name  = kwargs["table_name"]
    column_name = kwargs["column_name"]
    _validate_table_columns(table_name, column_name)
    from skills.snowflake.mcp_snowflake import save_conversation
    return save_conversation(table_name=table_name, column_name=column_name)


def skill_worldometer_gdp_by_country(**kwargs) -> Any:
    from skills.Extraction.worldometer_gdp_by_country import main
    _, stdout = _capture_stdout(main)
    return stdout.strip() or "Completed"


def skill_worldometer_gdp_all_countries(**kwargs) -> Any:
    from skills.Extraction.worldometer_gdp_all_countries import main
    _, stdout = _capture_stdout(main)
    return stdout.strip() or "Completed"


def skill_country_iso_codes(**kwargs) -> Any:
    from skills.Extraction.country_iso_codes import main
    _, stdout = _capture_stdout(main)
    return stdout.strip() or "Completed"



def skill_snowflake_json_to_query(**kwargs) -> Any:
    from skills.snowflake.snowflake_json_to_query import json_parser
    json_input = kwargs.get("json_input", kwargs)
    return json_parser(json_input)


def skill_finance_data_for_week(**kwargs) -> Any:
    ticker = kwargs.get("ticker")
    if not ticker:
        raise ValueError("'ticker' argument is required")
    script = os.path.join(ROOT, "skills", "Extraction", "finance_data_for_week.py")
    proc = subprocess.run(
        [sys.executable, script, f"--ticker={ticker}"],
        capture_output=True, text=True, timeout=120,
    )
    output = proc.stdout.strip()
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or output or "finance_data_for_week failed")
    return output or "Completed"


def skill_train_gradient_boosting(**kwargs) -> str:
    key = kwargs.get("conversation_key")
    if not key:
        raise ValueError("'conversation_key' is required")
    # Ensure snowflake_io is importable from the training directory
    training_dir = os.path.join(ROOT, "skills", "model", "training")
    if training_dir not in sys.path:
        sys.path.insert(0, training_dir)
    from skills.model.training.train_gradient_boosting import run_training
    with _in_root():
        _, out = _capture_stdout(run_training, key=key)
    return out.strip()


def skill_gradient_boosting_train(**kwargs) -> str:
    from skills.model.GradientBoosting.gradient_boosting import GradientBoostingSkill
    skill = GradientBoostingSkill()
    with _in_root():
        _, out = _capture_stdout(
            skill.train,
            X_path=kwargs["X_path"],
            y_col=kwargs["y_col"],
            test_size=float(kwargs.get("test_size", 0.2)),
            random_state=int(kwargs.get("random_state", 42)),
        )
    return out.strip()


def skill_gradient_boosting_predict(**kwargs) -> list:
    from skills.model.GradientBoosting.gradient_boosting import GradientBoostingSkill
    skill = GradientBoostingSkill()
    with _in_root():
        preds = skill.predict(X_path=kwargs["X_path"])
    if preds is None:
        raise RuntimeError("No trained GradientBoosting model found. Run gradient_boosting_train first.")
    return preds.tolist()


def skill_gradient_boosting_performance(**kwargs) -> str:
    from skills.model.GradientBoosting.gradient_boosting import GradientBoostingSkill
    skill = GradientBoostingSkill()
    with _in_root():
        _, out = _capture_stdout(skill.performance)
    return out.strip()


def skill_lasso_train(**kwargs) -> str:
    from skills.model.Regression.regression import LassoRegressionSkill
    skill = LassoRegressionSkill()
    with _in_root():
        _, out = _capture_stdout(
            skill.train,
            X_path=kwargs["X_path"],
            y_col=kwargs["y_col"],
            test_size=float(kwargs.get("test_size", 0.2)),
            random_state=int(kwargs.get("random_state", 42)),
        )
    return out.strip()


def skill_lasso_predict(**kwargs) -> list:
    from skills.model.Regression.regression import LassoRegressionSkill
    skill = LassoRegressionSkill()
    with _in_root():
        preds = skill.predict(X_path=kwargs["X_path"])
    if preds is None:
        raise RuntimeError("No trained Lasso model found. Run lasso_train first.")
    return preds.tolist()


def skill_lasso_performance(**kwargs) -> str:
    from skills.model.Regression.regression import LassoRegressionSkill
    skill = LassoRegressionSkill()
    with _in_root():
        _, out = _capture_stdout(skill.performance)
    return out.strip()


def skill_svm_train(**kwargs) -> str:
    from skills.model.SVM.svm import SVMRegressionSkill
    skill = SVMRegressionSkill()
    with _in_root():
        _, out = _capture_stdout(
            skill.train,
            X_path=kwargs["X_path"],
            y_col=kwargs["y_col"],
            test_size=float(kwargs.get("test_size", 0.2)),
            random_state=int(kwargs.get("random_state", 42)),
        )
    return out.strip()


def skill_svm_predict(**kwargs) -> list:
    from skills.model.SVM.svm import SVMRegressionSkill
    skill = SVMRegressionSkill()
    with _in_root():
        preds = skill.predict(X_path=kwargs["X_path"])
    if preds is None:
        raise RuntimeError("No trained SVM model found. Run svm_train first.")
    return preds.tolist()


def skill_svm_performance(**kwargs) -> str:
    from skills.model.SVM.svm import SVMRegressionSkill
    skill = SVMRegressionSkill()
    with _in_root():
        _, out = _capture_stdout(skill.performance)
    return out.strip()


def skill_random_forest_train(**kwargs) -> str:
    from skills.model.RandomForest.random_forest import RandomForestSkill
    skill = RandomForestSkill()
    with _in_root():
        _, out = _capture_stdout(
            skill.train,
            X_path=kwargs["X_path"],
            y_col=kwargs["y_col"],
            test_size=float(kwargs.get("test_size", 0.2)),
            random_state=int(kwargs.get("random_state", 42)),
        )
    return out.strip()


def skill_random_forest_predict(**kwargs) -> list:
    from skills.model.RandomForest.random_forest import RandomForestSkill
    skill = RandomForestSkill()
    with _in_root():
        preds = skill.predict(X_path=kwargs["X_path"])
    if preds is None:
        raise RuntimeError("No trained RandomForest model found. Run random_forest_train first.")
    return preds.tolist()


def skill_random_forest_performance(**kwargs) -> str:
    from skills.model.RandomForest.random_forest import RandomForestSkill
    skill = RandomForestSkill()
    with _in_root():
        _, out = _capture_stdout(skill.performance)
    return out.strip()


def skill_pca_fit(**kwargs) -> str:
    from skills.model.PCA.pca import PCASkill
    skill = PCASkill()
    with _in_root():
        _, out = _capture_stdout(
            skill.fit,
            X_path=kwargs["X_path"],
            n_components=kwargs.get("n_components", None),
            whiten=bool(kwargs.get("whiten", False)),
            random_state=int(kwargs.get("random_state", 42)),
        )
    return out.strip()


def skill_pca_transform(**kwargs) -> str:
    from skills.model.PCA.pca import PCASkill
    skill = PCASkill()
    with _in_root():
        _, out = _capture_stdout(
            skill.transform,
            X_path=kwargs["X_path"],
            output_path=kwargs.get("output_path", "pca_transformed.csv"),
        )
    return out.strip()


def skill_pca_fit_transform(**kwargs) -> str:
    from skills.model.PCA.pca import PCASkill
    skill = PCASkill()
    with _in_root():
        _, out = _capture_stdout(
            skill.fit_transform,
            X_path=kwargs["X_path"],
            n_components=kwargs.get("n_components", None),
            whiten=bool(kwargs.get("whiten", False)),
            random_state=int(kwargs.get("random_state", 42)),
            output_path=kwargs.get("output_path", "pca_transformed.csv"),
        )
    return out.strip()


def skill_pca_performance(**kwargs) -> str:
    from skills.model.PCA.pca import PCASkill
    skill = PCASkill()
    with _in_root():
        _, out = _capture_stdout(skill.performance)
    return out.strip()


def _bk_get(base: str, path: str, params: dict = None) -> Any:
    r = _requests.get(f"{base}{path}", params=params, timeout=60)
    r.raise_for_status()
    return r.json()


def _bk_post(base: str, path: str, body: dict, timeout: int = 60) -> Any:
    r = _requests.post(f"{base}{path}", json=body, timeout=timeout)
    r.raise_for_status()
    return r.json()

_BK_CHUNKING  = "http://localhost:8004"
_BK_ANALYSIS  = "http://localhost:8001"
_BK_STORING   = "http://localhost:8002"
_BK_RETRIEVAL = "http://localhost:8000"

def skill_bk_get_topics(**kwargs) -> Any:
    return _bk_get(_BK_CHUNKING, "/topics")

def skill_bk_select_file(**kwargs) -> Any:
    return _bk_get(_BK_CHUNKING, "/select-file")

def skill_bk_split_pdf(**kwargs) -> Any:
    return _bk_post(_BK_CHUNKING, "/split", {"filepath": kwargs["filepath"], "topic": kwargs["topic"]})

def skill_bk_get_page(**kwargs) -> Any:
    return _bk_get(_BK_ANALYSIS, "/page")

def skill_bk_save_summary(**kwargs) -> Any:
    return _bk_post(_BK_ANALYSIS, "/summary", {"index": kwargs["index"], "summary": kwargs["summary"]})

def skill_bk_analysis_status(**kwargs) -> Any:
    return _bk_get(_BK_ANALYSIS, "/status")

def skill_bk_add_entities(**kwargs) -> Any:
    return _bk_post(_BK_STORING, "/entities", {"entities": kwargs["entities"]})

def skill_bk_build_graph(**kwargs) -> Any:
    return _bk_post(_BK_STORING, "/build-graph", {
        "summary_file": kwargs["summary_file"],
        "book_name":    kwargs["book_name"],
    })

def skill_bk_add_relationship(**kwargs) -> Any:
    return _bk_post(_BK_STORING, "/relationship", {
        "relationship": kwargs["relationship"],
        "from_entity":  kwargs["from_entity"],
        "to_entity":    kwargs["to_entity"],
    })

def skill_retrieve(**kwargs) -> Any:
    if "queries" not in kwargs or not kwargs["queries"]:
        raise ValueError("retrieve requires argument: 'queries' (dict of structured query entries)")
    r = _requests.post(f"{_BK_RETRIEVAL}/retrieve", json={"queries": kwargs["queries"]}, timeout=180)
    r.raise_for_status()
    return r.json()


def skill_bk_build_lookup_index(**kwargs) -> Any:
    from baseknowledge_utils.lookup_index import build_index
    return build_index()


def invoke_skill(skill_name: str, arguments: dict) -> Any:
    """Look up and call a skill by name with the given arguments."""
    if skill_name not in REGISTRY:
        raise ValueError(
            f"Unknown skill '{skill_name}'. Available skills: {sorted(REGISTRY.keys())}"
        )
    return REGISTRY[skill_name](**arguments)

# Registry
REGISTRY: dict[str, Any] = {
    "get_mart_tables": skill_get_mart_tables,
    "check_valid_column": skill_check_valid_column,
    "worldometer_gdp_by_country": skill_worldometer_gdp_by_country,
    "worldometer_gdp_all_countries": skill_worldometer_gdp_all_countries,
    "country_iso_codes": skill_country_iso_codes,
    "snowflake_json_to_query": skill_snowflake_json_to_query,
    "finance_data_for_week": skill_finance_data_for_week,
    "train_gradient_boosting": skill_train_gradient_boosting,
    "gradient_boosting_train": skill_gradient_boosting_train,
    "gradient_boosting_predict": skill_gradient_boosting_predict,
    "gradient_boosting_performance": skill_gradient_boosting_performance,
    "lasso_train":  skill_lasso_train,
    "lasso_predict": skill_lasso_predict,
    "lasso_performance": skill_lasso_performance,
    "svm_train": skill_svm_train,
    "svm_predict": skill_svm_predict,
    "svm_performance": skill_svm_performance,
    "random_forest_train": skill_random_forest_train,
    "random_forest_predict":  skill_random_forest_predict,
    "random_forest_performance": skill_random_forest_performance,
    "pca_fit": skill_pca_fit,
    "pca_transform": skill_pca_transform,
    "pca_fit_transform": skill_pca_fit_transform,
    "pca_performance": skill_pca_performance,
    "retrieve": skill_retrieve,
    "baseknowledge.get_topics": skill_bk_get_topics,
    "baseknowledge.select_file": skill_bk_select_file,
    "baseknowledge.split_pdf": skill_bk_split_pdf,
    "baseknowledge.get_page": skill_bk_get_page,
    "baseknowledge.save_summary": skill_bk_save_summary,
    "baseknowledge.analysis_status": skill_bk_analysis_status,
    "baseknowledge.add_entities": skill_bk_add_entities,
    "baseknowledge.add_relationship": skill_bk_add_relationship,
    "baseknowledge.build_graph": skill_bk_build_graph,
    "baseknowledge.build_lookup_index": skill_bk_build_lookup_index,
}


SKILLS_DATA: list[str] = [
    "get_mart_tables",
    "check_valid_column",
    "snowflake_json_to_query",
]

SKILLS_EXTRACTION: list[str] = [
    "worldometer_gdp_by_country",
    "worldometer_gdp_all_countries",
    "country_iso_codes",
    "finance_data_for_week",
]

SKILLS_MODEL: list[str] = [
    "train_gradient_boosting",
    "gradient_boosting_train",
    "gradient_boosting_predict",
    "gradient_boosting_performance",
    "lasso_train",
    "lasso_predict",
    "lasso_performance",
    "svm_train",
    "svm_predict",
    "svm_performance",
    "random_forest_train",
    "random_forest_predict",
    "random_forest_performance",
    "pca_fit",
    "pca_transform",
    "pca_fit_transform",
    "pca_performance",
]

# Skills available only under the "storing" flag:
# covers the full pipeline for chunking, analysis, and writing to the knowledge graph.
SKILLS_STORING: list[str] = [
    "baseknowledge.get_topics",
    "baseknowledge.select_file",
    "baseknowledge.split_pdf",
    "baseknowledge.get_page",
    "baseknowledge.save_summary",
    "baseknowledge.analysis_status",
    "baseknowledge.add_entities",
    "baseknowledge.add_relationship",
    "baseknowledge.build_graph",
    "baseknowledge.build_lookup_index",
]

SKILLS_RETRIEVE: list[str] = [
    "retrieve",
]

SKILLS_BY_CATEGORY: dict[str, list[str]] = {
    "data":       SKILLS_DATA,
    "extraction": SKILLS_EXTRACTION,
    "model":      SKILLS_MODEL,
    "storing":    SKILLS_STORING,
    "retrieve":   SKILLS_RETRIEVE,
}
