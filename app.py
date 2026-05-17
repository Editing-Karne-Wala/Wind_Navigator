from fastapi import FastAPI, UploadFile, File, BackgroundTasks, Form
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn
import uuid
import os
import time

# We would import our actual report generator here
from report_generator import generate_report

app = FastAPI(title="Wind_Navigator Forensic API")

# Ensure an uploads directory exists
os.makedirs("uploads", exist_ok=True)
os.makedirs("reports", exist_ok=True)

# Mount the public directory for static files (our frontend)
app.mount("/static", StaticFiles(directory="public"), name="static")

# Mock database to track job status
jobs_db = {}

def process_log_file(job_id: str, filepath: str):
    """Background task to process the .BIN file and generate the report."""
    jobs_db[job_id]["status"] = "processing"
    
    # 1. Parse the BIN file (mock delay)
    time.sleep(2)
    
    # 2. Run Wind-Vector Back-Propagation (mock delay)
    time.sleep(3)
    
    # 3. Generate PDF Report
    output_pdf = f"reports/FORENSIC_REPORT_{job_id}.pdf"
    generate_report(output_filename=output_pdf)
    
    jobs_db[job_id]["status"] = "complete"
    jobs_db[job_id]["report_url"] = f"/download/{job_id}"
    print(f"[*] Job {job_id} complete. Report ready.")

@app.get("/", response_class=HTMLResponse)
async def serve_landing_page():
    """Serves the main landing page."""
    with open("public/index.html", "r") as f:
        return f.read()

@app.post("/create-checkout-session")
async def create_checkout_session(email: str = Form(...)):
    """Mocks the Stripe checkout session creation."""
    # In production, this uses stripe.checkout.Session.create()
    # For MVP, we'll bypass the actual payment gateway and return a mock success
    print(f"[*] Payment initiated for: {email}")
    return JSONResponse(content={"checkout_url": "/static/upload.html?session_id=mock_stripe_session_123"})

@app.post("/upload-log")
async def upload_log(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks()):
    """Receives the .BIN file and queues the forensic processing job."""
    
    if not file.filename.endswith('.bin') and not file.filename.endswith('.BIN'):
        return JSONResponse(content={"error": "File must be an ArduPilot .BIN dataflash log."}, status_code=400)
    
    job_id = str(uuid.uuid4())
    filepath = f"uploads/{job_id}_{file.filename}"
    
    # Save the file
    with open(filepath, "wb") as buffer:
        content = await file.read()
        buffer.write(content)
        
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
        return FileResponse(filepath, media_type='application/pdf', filename=f"WindNavigator_ForensicReport_{job_id}.pdf")
    return JSONResponse(content={"error": "Report not found or not yet ready"}, status_code=404)

if __name__ == "__main__":
    print("[*] Starting Wind_Navigator Forensic API on http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
