import logging
from typing import Any, Dict, List, Literal, Optional
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from runner import SandboxRunner

logging.basicConfig(level=logging.INFO, format="%(asctime)s - [SANDBOX] - %(message)s")
logger = logging.getLogger("sandbox")

app = FastAPI(
    title="YouTube Analytics Code Sandbox",
    description="Secure, isolated code execution runner for Matplotlib PNG and Plotly JSON generation",
    version="1.0.0"
)

runner = SandboxRunner(default_timeout_sec=5.0)


class ExecuteRequest(BaseModel):
    code: str = Field(..., description="Python plotting script using df, plt, sns, px or go")
    data: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Dataset rows loaded into df")
    format: Literal["matplotlib", "plotly"] = Field("matplotlib", description="Target visualization output")
    timeout_sec: Optional[float] = Field(5.0, ge=1.0, le=15.0)


class ExecuteResponse(BaseModel):
    status: str
    format: str
    png_base64: Optional[str] = None
    plotly_spec: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    execution_time_ms: float


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "code-sandbox"}


@app.get("/warmup")
def warmup():
    """Warmup compiler, matplotlib Agg engine, and pandas."""
    test_code = "plt.figure(figsize=(3,2))\nplt.plot([1, 2], [3, 4])\nplt.title('warmup')"
    res = runner.execute(code=test_code, data=[], output_format="matplotlib", timeout_sec=3.0)
    return {"warmup": "complete", "execution_time_ms": res.get("execution_time_ms")}


@app.post("/execute", response_model=ExecuteResponse)
def execute_code(request: ExecuteRequest):
    result = runner.execute(
        code=request.code,
        data=request.data,
        output_format=request.format,
        timeout_sec=request.timeout_sec
    )
    if result["status"] == "ERROR" and not result.get("error"):
        raise HTTPException(status_code=500, detail="Unknown execution failure in sandbox.")
    return result


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8080)
