import base64
import io
import json
import logging
import multiprocessing
import time
import traceback
from typing import Any, Dict, List, Optional

import matplotlib
matplotlib.use("Agg")  # Non-interactive headless backend
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

logger = logging.getLogger(__name__)


def _worker_execute(
    code: str,
    data: List[Dict[str, Any]],
    output_format: str,
    result_queue: multiprocessing.Queue,
):
    try:
        # Prepare dataframe
        df = pd.DataFrame(data) if data else pd.DataFrame()

        # Restricted execution namespace
        exec_globals = {
            "pd": pd,
            "np": np,
            "plt": plt,
            "sns": sns,
            "df": df,
            "data": data,
            "__builtins__": {
                k: v for k, v in __builtins__.items()
                if k not in ("eval", "exec", "compile", "open", "input", "__import__")
            } if isinstance(__builtins__, dict) else {
                k: getattr(__builtins__, k)
                for k in dir(__builtins__)
                if k not in ("eval", "exec", "compile", "open", "input", "__import__")
            }
        }
        
        # Also allow plotly inside script if requested
        if output_format == "plotly":
            import plotly.express as px
            import plotly.graph_objects as go
            exec_globals["px"] = px
            exec_globals["go"] = go

        # Reset any previous matplotlib plots
        plt.clf()
        plt.close("all")

        # Execute code in clean namespace
        exec_locals = {}
        exec(code, exec_globals, exec_locals)

        if output_format == "matplotlib":
            # Extract Matplotlib figure
            fig = plt.gcf()
            buf = io.BytesIO()
            fig.savefig(buf, format="png", bbox_inches="tight", dpi=120)
            buf.seek(0)
            png_base64 = base64.b64encode(buf.read()).decode("utf-8")
            plt.close("all")
            result_queue.put({
                "status": "SUCCESS",
                "format": "matplotlib",
                "png_base64": png_base64,
                "plotly_spec": None,
                "error": None
            })
        elif output_format == "plotly":
            # Look for 'fig' in locals or globals
            fig = exec_locals.get("fig") or exec_globals.get("fig")
            if fig is None:
                raise ValueError("Script did not define a Plotly 'fig' object.")
            result_queue.put({
                "status": "SUCCESS",
                "format": "plotly",
                "png_base64": None,
                "plotly_spec": json.loads(fig.to_json()),
                "error": None
            })
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    except Exception as e:
        plt.close("all")
        result_queue.put({
            "status": "ERROR",
            "format": output_format,
            "png_base64": None,
            "plotly_spec": None,
            "error": f"{type(e).__name__}: {str(e)}\n{traceback.format_exc()}"
        })


class SandboxRunner:
    def __init__(self, default_timeout_sec: float = 5.0):
        self.default_timeout_sec = default_timeout_sec

    def execute(
        self,
        code: str,
        data: Optional[List[Dict[str, Any]]] = None,
        output_format: str = "matplotlib",
        timeout_sec: Optional[float] = None
    ) -> Dict[str, Any]:
        timeout = timeout_sec or self.default_timeout_sec
        data = data or []
        start_time = time.perf_counter()

        result_queue = multiprocessing.Queue()
        process = multiprocessing.Process(
            target=_worker_execute,
            args=(code, data, output_format, result_queue)
        )

        process.start()
        process.join(timeout=timeout)

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)

        if process.is_alive():
            process.terminate()
            process.join()
            return {
                "status": "TIMEOUT",
                "format": output_format,
                "png_base64": None,
                "plotly_spec": None,
                "error": f"Execution timed out after {timeout} seconds.",
                "execution_time_ms": elapsed_ms
            }

        if not result_queue.empty():
            res = result_queue.get()
            res["execution_time_ms"] = elapsed_ms
            return res

        return {
            "status": "ERROR",
            "format": output_format,
            "png_base64": None,
            "plotly_spec": None,
            "error": "Process terminated without returning results.",
            "execution_time_ms": elapsed_ms
        }
