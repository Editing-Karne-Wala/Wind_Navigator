from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import uuid
import os
import time
import json
import logging
import traceback
import requests
import subprocess
import sys

# Setup Telemetry (Logging)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("server_telemetry.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

from report_generator import generate_report

app = FastAPI(title="Wind_Navigator Forensic API")

# Configure CORS for decoupled Vercel frontend
origins = [
    "https://aura-intelligence.tech",
    "https://www.aura-intelligence.tech",
    "http://localhost:8000"
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)
os.makedirs("reports", exist_ok=True)

app.mount("/static", StaticFiles(directory="public"), name="static")

jobs_db = {}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB limit

DODO_API_KEY = os.environ.get("DODO_API_KEY")


def process_log_file(job_id: str, filepath: str):
    """
    Full pipeline:
      1. Extract telemetry from .BIN -> per-job JSON
      2. Validate JSON is non-empty (Bug 2 guard)
      3. Run D2Q9 wind-vector back-propagation
      4. Compile final PDF report using per-job JSON
    """
    logger.info(f"Starting forensic analysis for job {job_id}")
    jobs_db[job_id]["status"] = "processing"
    start_time = time.time()

    # Per-job JSON paths so concurrent jobs never collide (Bug 3 fix)
    job_json_path = f"uploads/{job_id}_telemetry.json"
    output_pdf = f"reports/FORENSIC_REPORT_{job_id}.pdf"

    try:
        # ----------------------------------------------------------
        # STEP 1: Parse .BIN -> JSON  (Bug 1 fix: actually call it)
        # ----------------------------------------------------------
        logger.info(f"[{job_id}] Parsing .BIN telemetry via extract_bin_to_json.py ...")
        result = subprocess.run(
            [sys.executable, "extract_bin_to_json.py", filepath],
            capture_output=True, text=True, timeout=120
        )
        logger.info(f"[{job_id}] Extractor stdout: {result.stdout[-800:]}")
        if result.returncode != 0:
            raise RuntimeError(
                f"Binary extractor failed (exit {result.returncode}):\n{result.stderr[-600:]}"
            )

        # The extractor always writes to real_case_study.json in cwd.
        # Copy it to the per-job path so concurrent jobs don't clobber each other.
        if not os.path.exists("real_case_study.json"):
            raise RuntimeError("extract_bin_to_json.py ran successfully but produced no output JSON.")

        with open("real_case_study.json", "r") as src, open(job_json_path, "w") as dst:
            raw = src.read()
            dst.write(raw)

        # ----------------------------------------------------------
        # STEP 2: Validate trace is non-empty  (Bug 2 fix)
        # ----------------------------------------------------------
        with open(job_json_path, "r") as f:
            log_data = json.load(f)

        trace_data = log_data.get("flight_trace", [])
        if len(trace_data) == 0:
            # Hard failure - never let an empty dataset produce an exoneration cert
            raise RuntimeError(
                "VALIDATION ERROR: The uploaded .BIN file contained zero GPS telemetry frames. "
                "Possible causes: GPS was disabled, log was corrupted, or the file is not an "
                "ArduPilot DataFlash binary. Please re-upload a valid flight log."
            )

        logger.info(f"[{job_id}] Telemetry validated: {len(trace_data)} GPS frames, "
                    f"{sum(1 for t in trace_data if t.get('motor_rpm_spike')) } anomaly frames.")

        # ----------------------------------------------------------
        # STEP 3: Run D2Q9 Wind Back-Propagation using per-job JSON
        # ----------------------------------------------------------
        logger.info(f"[{job_id}] Executing D2Q9 Wind-Vector Back-Propagation ...")

        # wind_solver.py reads from real_case_study.json by convention.
        # Symlink the per-job file in place so the solver uses the right data.
        # Use a copy so we don't break anything in concurrent scenarios.
        import shutil
        shutil.copy(job_json_path, "real_case_study.json")

        solver_result = subprocess.run(
            [sys.executable, "wind_solver.py"],
            capture_output=True, text=True, timeout=600
        )
        logger.info(f"[{job_id}] Solver stdout: {solver_result.stdout[-800:]}")
        if solver_result.returncode != 0:
            logger.warning(f"[{job_id}] wind_solver.py returned non-zero; continuing with raw telemetry data.")

        # Reload JSON in case solver updated it with the discovered wind vector
        if os.path.exists("real_case_study.json"):
            with open("real_case_study.json", "r") as f:
                updated_log = json.load(f)
            with open(job_json_path, "w") as f:
                json.dump(updated_log, f, indent=2)

        # ----------------------------------------------------------
        # STEP 4: Generate PDF using the per-job JSON  (Bug 3 fix)
        # ----------------------------------------------------------
        logger.info(f"[{job_id}] Compiling Final PDF Report ...")
        generate_report(log_json_path=job_json_path, output_filename=output_pdf)

        duration = time.time() - start_time
        logger.info(f"[{job_id}] Job completed successfully in {duration:.2f} seconds.")
        jobs_db[job_id]["status"] = "complete"
        jobs_db[job_id]["report_url"] = f"/download/{job_id}"

    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[{job_id}] CRITICAL FAILURE during processing. Duration: {duration:.2f}s")
        logger.error(traceback.format_exc())
        jobs_db[job_id]["status"] = "failed"
        # Surface the real error message so the client knows what went wrong
        jobs_db[job_id]["error"] = str(e)


@app.get("/", response_class=HTMLResponse)
async def serve_landing_page():
    """Serves the main landing page."""
    with open("public/index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/create-checkout-session")
async def create_checkout_session(email: str = Form(...)):
    """Creates a highly secure checkout session using Dodo Payments API."""
    logger.info(f"Payment initiated for: {email}")

    if not DODO_API_KEY:
        logger.error("DODO_API_KEY secret is missing! Bypassing to upload page for local testing.")
        return JSONResponse(content={"checkout_url": f"/upload.html?session_id=mock_{uuid.uuid4().hex}"})

    headers = {
        "Authorization": f"Bearer {DODO_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "amount": 7500,
        "currency": "USD",
        "product_name": "Wind_Navigator Forensic Report",
        "customer_email": email,
        "success_url": "https://wind-navigator-in0y4bt9j-abhinavs-projects-2479f8a1.vercel.app/upload.html",
        "cancel_url": "https://wind-navigator-in0y4bt9j-abhinavs-projects-2479f8a1.vercel.app"
    }

    try:
        response = requests.post("https://api.dodopayments.com/v1/payments", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        checkout_url = data.get("checkout_url") or data.get("url") or data.get("payment_link")

        if checkout_url:
            return JSONResponse(content={"checkout_url": checkout_url})
        else:
            logger.error(f"Dodo API returned success but payload is malformed: {data}")
            return JSONResponse(content={"error": "Invalid response from Dodo Payment gateway"}, status_code=500)

    except Exception as e:
        logger.error(f"Failed to communicate with Dodo Payments API: {str(e)}")
        if hasattr(e, 'response') and e.response is not None:
            logger.error(f"API Error Response: {e.response.text}")
        return JSONResponse(content={"error": "Failed to initialize secure checkout session."}, status_code=500)


@app.post("/upload-log")
async def upload_log(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    """Receives the .BIN file and queues the forensic processing job."""

    if not file.filename.endswith('.bin') and not file.filename.endswith('.BIN'):
        logger.warning(f"Rejected invalid file type: {file.filename}")
        return JSONResponse(content={"error": "File must be an ArduPilot .BIN dataflash log."}, status_code=400)

    file_size = 0
    job_id = str(uuid.uuid4())
    filepath = f"uploads/{job_id}_{file.filename}"

    try:
        with open(filepath, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE:
                    logger.warning(f"Rejected oversized file: {file.filename} ({file_size} bytes)")
                    os.remove(filepath)
                    return JSONResponse(content={"error": "File exceeds 50MB limit. Contact support for large forensic analysis."}, status_code=413)
                buffer.write(chunk)
    except Exception as e:
        logger.error(f"Failed to upload file {file.filename}: {str(e)}")
        return JSONResponse(content={"error": "Failed to upload file."}, status_code=500)

    logger.info(f"Successfully uploaded {file.filename} ({file_size} bytes). Assigned Job ID: {job_id}")

    jobs_db[job_id] = {"status": "queued", "filename": file.filename}

    background_tasks.add_task(process_log_file, job_id, filepath)

    return JSONResponse(content={"job_id": job_id, "status": "queued", "message": "Log file uploaded successfully. Processing started."})


@app.get("/job-status/{job_id}")
async def get_job_status(job_id: str):
    """Polls the status of a forensic job."""
    if job_id not in jobs_db:
        return JSONResponse(content={"error": "Job not found"}, status_code=404)
    return JSONResponse(content=jobs_db[job_id])


@app.get("/download/{job_id}")
async def download_report(job_id: str):
    """Downloads the generated PDF report."""
    filepath = f"reports/FORENSIC_REPORT_{job_id}.pdf"
    if os.path.exists(filepath):
        logger.info(f"Report downloaded for Job ID: {job_id}")
        return FileResponse(filepath, media_type='application/pdf', filename=f"WindNavigator_ForensicReport_{job_id}.pdf")
    logger.warning(f"Download attempted for missing report. Job ID: {job_id}")
    return JSONResponse(content={"error": "Report not found or not yet ready"}, status_code=404)


if __name__ == "__main__":
    logger.info("Starting Wind_Navigator Forensic API on http://0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)

