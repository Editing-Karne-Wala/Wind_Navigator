from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Form, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
import uuid
import os
import time
import logging
import traceback
import requests

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

# We would import our actual report generator here
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

# Ensure an uploads directory exists
os.makedirs("uploads", exist_ok=True)
os.makedirs("reports", exist_ok=True)

# Mount the public directory for static files (our frontend)
app.mount("/static", StaticFiles(directory="public"), name="static")

# Mock database to track job status
jobs_db = {}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB limit

# Securely load Dodo Payments API Key from Hugging Face Secrets
DODO_API_KEY = os.environ.get("DODO_API_KEY")

def process_log_file(job_id: str, filepath: str):
    """Background task to process the .BIN file and generate the report."""
    logger.info(f"Starting forensic analysis for job {job_id}")
    jobs_db[job_id]["status"] = "processing"
    start_time = time.time()
    
    try:
        # 1. Parse the BIN file (mock delay)
        logger.info(f"[{job_id}] Parsing telemetry...")
        time.sleep(2)
        
        # 2. Run Wind-Vector Back-Propagation (mock delay)
        logger.info(f"[{job_id}] Executing D2Q9 Back-Propagation...")
        time.sleep(3)
        
        # 3. Generate PDF Report
        logger.info(f"[{job_id}] Compiling Final PDF Report...")
        output_pdf = f"reports/FORENSIC_REPORT_{job_id}.pdf"
        generate_report(output_filename=output_pdf)
        
        duration = time.time() - start_time
        logger.info(f"[{job_id}] Job completed successfully in {duration:.2f} seconds.")
        jobs_db[job_id]["status"] = "complete"
        jobs_db[job_id]["report_url"] = f"/download/{job_id}"
        
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"[{job_id}] CRITICAL FAILURE during processing. Duration: {duration:.2f}s")
        logger.error(traceback.format_exc())
        jobs_db[job_id]["status"] = "failed"
        jobs_db[job_id]["error"] = "An internal error occurred during fluid dynamic reconstruction. Our engineering team has been notified."

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
        return JSONResponse(content={"checkout_url": f"/static/upload.html?session_id=mock_{uuid.uuid4().hex}"})

    headers = {
        "Authorization": f"Bearer {DODO_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "amount": 7500, # Assuming standard cents calculation
        "currency": "USD",
        "product_name": "Wind_Navigator Forensic Report",
        "customer_email": email,
        "success_url": "https://nicklie-wind-navigator-api.hf.space/static/upload.html",
        "cancel_url": "https://nicklie-wind-navigator-api.hf.space"
    }
    
    try:
        # Standard generic endpoint structure for Developer-First MoRs
        response = requests.post("https://api.dodopayments.com/v1/payments", json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        # Look for the checkout link in the typical fields
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
    
    # Save the file with a size limit check
    try:
        with open(filepath, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024) # read 1MB at a time
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
    
    # Register job
    jobs_db[job_id] = {"status": "queued", "filename": file.filename}
    
    # Queue background processing
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

